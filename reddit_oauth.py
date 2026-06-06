"""
reddit_oauth.py — Reddit OAuth 2.0 password-grant client.

Acquires and caches access tokens for use with Reddit's Data API. Handles
TTL-aware caching (tokens are valid for ~1 hour; this module refreshes
when less than 5 minutes of validity remain).

Environment variables (all REDDIT_OAUTH_* prefix):

  REDDIT_OAUTH_ENABLED=1       Master toggle. Anything truthy enables OAuth.
  REDDIT_OAUTH_CLIENT_ID       14-char client_id from reddit.com/prefs/apps
  REDDIT_OAUTH_CLIENT_SECRET   The "secret" string from the same page
  REDDIT_OAUTH_USERNAME        Reddit username (no /u/ prefix)
  REDDIT_OAUTH_PASSWORD        Reddit password
  REDDIT_OAUTH_PROXY           Optional. HTTP/HTTPS proxy URL for outbound
                               requests.

User-Agent format
-----------------
Reddit's OAuth endpoint requires a specific User-Agent format:

  <platform>:<app id>:<version> (by /u/<reddit username>)

This module constructs the UA automatically from CLIENT_ID and USERNAME.

Public surface
--------------
  is_oauth_configured() -> bool
  get_oauth_token() -> Optional[str]
  oauth_api_base() -> str
  oauth_proxy() -> Optional[str]
  oauth_user_agent() -> Optional[str]
  reset_token_cache() -> None
"""
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import requests

log = logging.getLogger("reddit_oauth")

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_OAUTH_API_BASE = "https://oauth.reddit.com"

_TOKEN_TTL_SECS = 3600
_TOKEN_SAFETY_MARGIN_SECS = 300
_TOKEN_REQUEST_TIMEOUT_SECS = 10


@dataclass
class _Config:
    client_id: str
    client_secret: str
    username: str
    password: str
    proxy: str

    @property
    def user_agent(self) -> str:
        return f"python:{self.client_id}:v1.0 (by /u/{self.username})"


@dataclass
class _CachedToken:
    token: str
    acquired_at: float

    def is_valid(self) -> bool:
        age = time.time() - self.acquired_at
        return age < (_TOKEN_TTL_SECS - _TOKEN_SAFETY_MARGIN_SECS)


_TOKEN_CACHE: Optional[_CachedToken] = None


def _load_config_from_env() -> Optional[_Config]:
    fields = {
        "client_id":     os.environ.get("REDDIT_OAUTH_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("REDDIT_OAUTH_CLIENT_SECRET", "").strip(),
        "username":      os.environ.get("REDDIT_OAUTH_USERNAME", "").strip(),
        "password":      os.environ.get("REDDIT_OAUTH_PASSWORD", "").strip(),
        "proxy":         os.environ.get("REDDIT_OAUTH_PROXY", "").strip(),
    }
    required = ["client_id", "client_secret", "username", "password"]
    if not all(fields[k] for k in required):
        return None
    return _Config(**fields)


def is_oauth_configured() -> bool:
    toggle = os.environ.get("REDDIT_OAUTH_ENABLED", "").strip().lower()
    if toggle not in {"1", "true", "yes"}:
        return False
    if not _load_config_from_env():
        log.warning(
            "REDDIT_OAUTH_ENABLED is set but REDDIT_OAUTH_* credentials "
            "are not configured; OAuth will not be active"
        )
        return False
    return True


def _acquire_token(config: _Config) -> Optional[str]:
    headers = {"User-Agent": config.user_agent}
    data = {
        "grant_type": "password",
        "username":   config.username,
        "password":   config.password,
    }
    proxies = (
        {"http": config.proxy, "https": config.proxy}
        if config.proxy else None
    )
    try:
        resp = requests.post(
            _TOKEN_URL,
            auth=(config.client_id, config.client_secret),
            data=data,
            headers=headers,
            timeout=_TOKEN_REQUEST_TIMEOUT_SECS,
            proxies=proxies,
        )
        if resp.status_code != 200:
            log.warning(
                f"Token endpoint returned HTTP {resp.status_code}: "
                f"{resp.text[:200]}"
            )
            return None
        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            log.warning(f"Token response missing access_token: {payload}")
            return None
        log.info("Acquired fresh access token")
        return token
    except Exception as e:
        log.warning(f"Token request failed: {type(e).__name__}: {e}")
        return None


def get_oauth_token() -> Optional[str]:
    """Return a valid access token, refreshing if needed.

    Returns None if OAuth is not configured or token acquisition fails.
    """
    global _TOKEN_CACHE
    if not is_oauth_configured():
        return None
    config = _load_config_from_env()
    if not config:
        return None

    if _TOKEN_CACHE and _TOKEN_CACHE.is_valid():
        return _TOKEN_CACHE.token

    token = _acquire_token(config)
    if token:
        _TOKEN_CACHE = _CachedToken(token=token, acquired_at=time.time())
    return token


def oauth_api_base() -> str:
    return _OAUTH_API_BASE


def oauth_proxy() -> Optional[str]:
    config = _load_config_from_env()
    return config.proxy if (config and config.proxy) else None


def oauth_user_agent() -> Optional[str]:
    config = _load_config_from_env()
    return config.user_agent if config else None


def reset_token_cache() -> None:
    """Drop the cached token. Useful at the start of a fresh scrape run."""
    global _TOKEN_CACHE
    _TOKEN_CACHE = None
    log.info("Token cache reset")
