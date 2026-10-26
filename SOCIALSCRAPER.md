# SocialScraper operating plan

Standalone repo: socialscraper. Do not add any of this code to testscraper---Copy until a later integration PR.

1. Start with the Supabase-derived competitor manifest and review statuses/evidence.
2. Check URLs for malformed hosts and basic reachability; a 200/redirect never proves ownership.
3. Use Playwright only to inspect public pages and click ordinary cookie/modal close buttons.
4. Stop on login, CAPTCHA, anti-bot, access denied, rate limit, or paywall states.
5. Add official X API reads only after the required developer access is configured. Use bounded reads, retries with backoff, cost estimate, deduplication and collection run logs.
6. Later connect this service to the existing RivalMap backend through an authenticated server-to-server endpoint; no browser-visible secrets.
