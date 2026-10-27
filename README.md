# SocialScraper

Standalone social intelligence collector for RivalMap. This repository is intentionally separate from testscraper---Copy.

## Strategy
1. Read tracked competitor definitions from Supabase, not hard-coded competitors.
2. Keep URLs, platform, account scope, verification status, source/evidence URL and last-checked timestamp.
3. Confirm X profiles using the official API when credentials are available; a plausible handle or HTTP 200 is not proof of corporate ownership.
4. Use visible browser inspection only for public pages and ordinary dismissible UI, like cookie banners, newsletter modals and close buttons.
5. Stop at login walls, CAPTCHA/challenges, anti-bot screens, rate limits, access denied, paywalls or other access controls; do not remove these to collect gated data.
6. Default to preview mode for account lists. API collection requires the explicit x-collect command and an X API bearer token.
7. Later, connect this independent service to the existing RivalMap backend through authenticated server-to-server calls. Do not put credentials in the frontend.

## Setup
Run from the repo root:

    python -m venv .venv
    # Windows: .venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium

Set X_BEARER_TOKEN in your environment when approved X API access is available. Do not commit a real token.

## Commands
Preview profiles without network access:

    python -m socialscraper.cli seed-preview
    python -m socialscraper.cli x-preview

Check URL syntax/reachability (not proof of ownership):

    python -m socialscraper.cli verify-links --manifest data/competitor_socials.json

Inspect a public HTTPS page and dismiss ordinary UI only:

    python -m socialscraper.cli inspect-public-page --url https://example.org --headed

### Local headed browser debugging

On Windows, activate your virtual environment, then run this from the repository root:

    python -m socialscraper.cli inspect-public-page --url https://x.com/SGS_SA --headed --debug --timeout-ms 45000 --keep-open-seconds 15

The browser window is visible, verbose diagnostic logs are printed in the terminal, and the command saves a Playwright trace and final screenshot under output/debug/. The JSON result includes the HTTP status, final URL/title, detected access-control signals, and the number of article elements visible in the page DOM. It does not extract post text.

Open a trace locally with:

    playwright show-trace output/debug/playwright-trace.zip

A trace can contain page content and screenshots; keep it local and review it before sharing. If X shows a login, challenge, rate-limit, or other access-control screen, the inspector reports it and stops without trying to bypass it.

Collect recent public posts from manifest accounts whose status is explicitly official_link_verified or regional_only:

    python -m socialscraper.cli x-collect --max-posts 10 --output output/x_posts.json

Collection requires X_BEARER_TOKEN and X API endpoint entitlement. It is not run automatically, and it does not scrape the X website.

## X API collection phase
The adapter supports username lookup and bounded profile-timeline reads, with retry/backoff, post URL normalization and structured JSON output. Next, add stricter cost estimates, paging/cursor handling, persistence/run logs and a dry-run budget gate before scheduling.

## Next phase
Test and deploy this service separately. Then connect it to RivalMap through authenticated backend-to-backend calls. No frontend credentials and no code changes to testscraper---Copy until a separate integration change is reviewed.
