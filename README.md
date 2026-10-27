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

    python -m socialscraper.cli inspect-public-page --url https://x.com/SGS_SA --headed --debug --timeout-ms 45000 --keep-open-seconds 15 --output-json output/sgs_x_public_page.json

The browser window is visible, verbose diagnostic logs are printed in the terminal, and the command saves a Playwright trace and final screenshot under output/debug/. The JSON result includes HTTP status, final URL/title, detected access-control signals, article counts, and up to five already-rendered public X posts with short text snippets, timestamps and post URLs. It does not scroll to load more posts or extract content if a login, challenge, rate-limit, or other access-control signal is detected.

The inspector also separates the post caption from the full visible card text and captures bounded media evidence for each rendered post:
- Images: public image URL, available alt text, and dimensions.
- Videos: video/poster URLs when exposed in the DOM, duration/dimensions when available, and links to caption/subtitle tracks if the page exposes them.
- Outbound URLs shown inside the post, without opening them.
- The time label displayed by X (for example, "4h") alongside the machine-readable timestamp when available.

The complete structured report is saved to output/sgs_x_public_page.json (or the path passed to --output-json). This is metadata extraction, not full media understanding. It does not download video files, defeat protected media URLs, or generate an image/video transcript. To turn media into intelligence, a later analysis stage can run OCR/vision on accessible images/keyframes and speech transcription on legitimately accessible audio, then produce a structured event summary with source links and confidence. Missing alt text or captions should be recorded as unavailable, not guessed.

### Optional AI media analysis (API usage may be billed separately)

After an inspection JSON exists, you can ask a vision-capable model to extract text visible inside images, important numbers, named entities and business signals. The model is instructed to separate observations from inferences and list unknowns rather than guessing.

1. Copy .env.example to .env if you do not already have a local .env file.
2. Add your own API key to the local .env file by setting OPENAI_API_KEY. Do not commit or share this key.
3. Run the explicit analysis command:

    python -m socialscraper.cli analyze-media --input output/sgs_x_public_page.json --output output/sgs_x_media_intelligence.json --max-posts 5 --max-images-per-post 2

The command is opt-in; the browser inspection alone does not call the model. It analyzes at most five posts and two unique publicly exposed image/poster URLs per post. It accepts only the public X image CDN host recorded by the inspector. It does not download video files or transcribe their audio. A video poster is analyzed only as a still image. Vision input/output usage is billed according to the API account and selected model; check current model pricing before running larger batches. The output preserves source post URLs, image references, evidence quotes, confidence and model usage token counts. Verify extracted numbers against the underlying report before treating them as confirmed intelligence.

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
