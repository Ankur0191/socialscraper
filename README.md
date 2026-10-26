# SocialScraper

Standalone social intelligence collector for RivalMap. This repository is intentionally separate from testscraper---Copy.

## Strategy
1. Read tracked competitor definitions from Supabase, not hard-coded competitors.
2. Keep URLs, platform, account scope, verification status, source/evidence URL and last-checked timestamp.
3. Confirm X profiles using the official API when credentials are available; a plausible handle or HTTP 200 is not proof of corporate ownership.
4. Use visible browser inspection only for public pages and ordinary dismissible UI, like cookie banners, newsletter modals and close buttons.
5. Stop at login walls, CAPTCHA/challenges, anti-bot screens, rate limits, access denied, paywalls or other access controls; do not remove these to collect gated data.
6. Default to dry-run, record every run and keep the collector bounded by per-run page/post and cost limits.
7. Later, connect this independent service to the existing RivalMap backend through authenticated server-to-server calls. Do not put credentials in the frontend.

## Setup
Run from the repo root:
    python -m venv .venv
    # Windows: .venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium

## Commands
    python -m socialscraper.cli --help
    python -m socialscraper.cli seed-preview
    python -m socialscraper.cli verify-links --manifest data/competitor_socials.json
    python -m socialscraper.cli inspect-public-page --url https://example.org --headed

The verifier tests URL shape and basic reachability only. Platform responses such as 403/429, login redirects and challenge pages are treated as restricted or inconclusive rather than bypassed.

## X API collection phase
When official API access is configured, add user lookup, profile timelines, public mention search where entitled, bounded pagination, rate-limit handling, cost estimates before execution, post normalization, deduplication, and collection run logs. Do not use browser scraping as an interim replacement for official API access to X.

## Next phase
Test and deploy this service separately. Then connect it to RivalMap through authenticated backend-to-backend calls. No frontend credentials and no shared code changes to testscraper---Copy until a separate integration change is reviewed.
