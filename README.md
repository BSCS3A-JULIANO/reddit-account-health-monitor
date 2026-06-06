# Reddit Account Health Monitor

A personal Python script that periodically checks public profile data for a small portfolio of Reddit accounts I own. Tracks karma growth, last-activity timestamps, and suspension status so I can identify dormant or removed accounts.

## What it does

Reads public profile JSON endpoints for a configurable list of Reddit accounts:
- `/user/{username}/about.json` — karma, account age, suspension status
- `/user/{username}/submitted.json?limit=100` — recent submissions
- `/user/{username}/comments.json?limit=100` — recent comments

Aggregates the results into a local snapshot for trend analysis over time. Read-only operations only, no posting, voting, commenting, or any state-changing API calls.

## Authentication

Uses Reddit's OAuth 2.0 password grant flow. Requires a registered "script" type app at https://www.reddit.com/prefs/apps. The script app's `client_id` and `client_secret`, plus the Reddit account credentials, are loaded from environment variables.

See `.env.example` for the required configuration.

## Rate limits

The script paces requests well below Reddit's authenticated rate limit of 100 requests/minute. Default cadence is once per day with randomized delays between accounts.

## Compliance

Respects Reddit's [Data API Terms](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki) and the [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy):

- Read-only operations only
- Minimum-necessary OAuth scopes (read)
- Reddit-compliant User-Agent header identifying the app and developer
- No data redistribution or resale
- No caching of personal data beyond operational necessity

## Setup

```bash
git clone https://github.com/BSCS3A-JULIANO/reddit-account-health-monitor.git
cd reddit-account-health-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Reddit script app credentials
python monitor.py
