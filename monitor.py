"""
monitor.py — Read public profile data for a list of Reddit accounts via
Reddit's OAuth 2.0 API. Logs key metrics (karma, last activity, suspension
status) for each account in the configured portfolio.

Run periodically (e.g. daily via cron or a Windows Task Scheduler entry)
to track health metrics over time for accounts you own.

Configuration: see .env.example for the required environment variables.
"""
import json
import logging
import os
import random
import sys
import time
from typing import Optional, Dict

import requests
from dotenv import load_dotenv

import reddit_oauth

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("monitor")

ACCOUNTS_TO_MONITOR = os.environ.get(
    "MONITORED_ACCOUNTS", "spez,reddit"
).split(",")

PACING_MIN_SECS = 5.0
PACING_MAX_SECS = 15.0
HTTP_TIMEOUT_SECS = 15


def fetch_profile(username: str, endpoint: str) -> Optional[Dict]:
    """Fetch one profile endpoint for the given username.

    endpoint should be 'about', 'submitted', or 'comments'.
    Returns the parsed JSON dict, or None on any error.
    """
    token = reddit_oauth.get_oauth_token()
    if not token:
        log.error("No OAuth token available, check .env configuration")
        return None

    paths = {
        "about":     f"/user/{username}/about.json",
        "submitted": f"/user/{username}/submitted.json?limit=100",
        "comments":  f"/user/{username}/comments.json?limit=100",
    }
    if endpoint not in paths:
        log.error(f"Unknown endpoint: {endpoint}")
        return None

    url = f"{reddit_oauth.oauth_api_base()}{paths[endpoint]}"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent":    reddit_oauth.oauth_user_agent() or "monitor/1.0",
    }
    proxy = reddit_oauth.oauth_proxy()
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        resp = requests.get(
            url, headers=headers, timeout=HTTP_TIMEOUT_SECS, proxies=proxies,
        )
        if resp.status_code == 200:
            return resp.json()
        log.warning(f"[{username}/{endpoint}] HTTP {resp.status_code}")
        return None
    except Exception as e:
        log.warning(f"[{username}/{endpoint}] {type(e).__name__}: {e}")
        return None


def check_account(username: str) -> Dict:
    """Fetch all three endpoints for one account and return a summary."""
    log.info(f"Checking @{username}")
    about     = fetch_profile(username, "about")
    submitted = fetch_profile(username, "submitted")
    comments  = fetch_profile(username, "comments")

    summary = {"username": username}

    if about and "data" in about:
        d = about["data"]
        summary["link_karma"]    = d.get("link_karma", 0)
        summary["comment_karma"] = d.get("comment_karma", 0)
        summary["is_suspended"]  = d.get("is_suspended", False)
        summary["created_utc"]   = d.get("created_utc")
    else:
        summary["fetch_failed"] = True

    if submitted and "data" in submitted:
        summary["recent_submissions"] = len(submitted["data"].get("children", []))
    if comments and "data" in comments:
        summary["recent_comments"] = len(comments["data"].get("children", []))

    return summary


def main():
    if not reddit_oauth.is_oauth_configured():
        log.error("OAuth not configured. See .env.example.")
        sys.exit(1)

    log.info(f"Monitoring {len(ACCOUNTS_TO_MONITOR)} accounts")
    summaries = []
    for username in ACCOUNTS_TO_MONITOR:
        username = username.strip()
        if not username:
            continue
        summary = check_account(username)
        summaries.append(summary)
        log.info(json.dumps(summary, default=str))
        time.sleep(random.uniform(PACING_MIN_SECS, PACING_MAX_SECS))

    log.info(f"Done. Checked {len(summaries)} accounts.")


if __name__ == "__main__":
    main()
