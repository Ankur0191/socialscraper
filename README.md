# SocialScraper

Standalone X-first social intelligence collector for RivalMap. This repository is intentionally separate from `testscraper---Copy`.

## Strategy

- Read tracked competitor definitions from Supabase, not hard-coded lists.
- Store social URLs with evidence and explicit verification statuses (`official_link_verified`, `profile_exists`, `candidate`, `regional_only`, `not_found`, `access_limited`, `not_confirmed`).
- Use official X API v2 for collection after credentials are available; do not automate X website scraping as an interim replacement.
- Allow regular close buttons/cookie banners on public pages to be dismissed. Stop on sign-in walls, CAPTCHA, challenge, paywall, 403/429 or anti-bot gates.
- Keep a dry-run default, a per-run result log, deduplication and budget controls.

## Scaffold

See `SOCIALSCRAPER.md` for setup, CLI commands and the later integration plan.