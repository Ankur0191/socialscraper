# SocialScraper

Standalone social intelligence collector for RivalMap. This repository is intentionally separate from testscraper---Copy.

## Strategy
1. Read canonical tracked companies from Supabase, not hard-coded competitors.
2. Keep URLs, platform, account scope, verification status, source/evidence URL and last-checked timestamp.
3. Confirm X profiles using the official API when credentials are available; a plausible handle or HTTP 200 is not proof of corporate ownership.
4. Use visible browser inspection only for public pages and ordinary dismissible UI, like cookie banners, newsletter modals and close buttons.
5. Stop at login walls, CAPTCHA/challenges, anti-bot screens, rate limits, access denied, paywalls or other access controls; do not remove these to collect gated data.
6. Default to dry-run, record every run and keep the collector bounded by per-run page/post and cost limits.
7. Later, connect this independent service to testscraper---Copy / demo.rivalmap.ai with authenticated backend-to-backend calls. Do not put credentials in the frontend.

## Setup
From the repo root:

    python -m venv .venv
    # Windows: .venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium
    copy .env.example .env

Fill server-only values in .env. Never commit secrets.

## Commands

    python -m socialscraper.cli --help
    python -m socialscraper.cli seed-preview
    python -m socialscraper.cli verify-links --manifest data/competitor_socials.json
    python -m socialscraper.cli inspect-public-page --url https://example.org --headed

The verifier tests URL shape and basic reachability only. Platforms may return 403/429 or login redirects. These are recorded as access-limited/inconclusive; the tool does not try to bypass them.

## X collection phase (after API access)
Add a token-backed X API adapter for:
- user/profile lookup and handle confirmation
- public profile timeline reads
- recent public mention searches if enabled by account entitlement
- bounded pagination, rate-limit handling, cost estimate before execution
- post normalization and de-duplication
- collection run records with errors, counts and timestamps

Do not use browser scraping as a temporary replacement for official API access to X.

## Next phase
After this service is independently tested, wire it into the RivalMap backend through a server-side authenticated job trigger. Keep the new scraper deployable and testable without importing the existing backend.
