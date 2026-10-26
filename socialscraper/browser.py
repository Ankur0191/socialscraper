"""Visible browser inspector for public pages.

Stops when it sees a sign-in wall, CAPTCHA/challenge, denial, rate limit or paywall.
"""
from __future__ import annotations

from typing import Any

from playwright.sync_api import sync_playwright

from socialscraper.ui_dismiss import detect_access_gate, dismiss_ordinary_overlays


def inspect_public_page(
    url: str,
    *,
    headed: bool = True,
    timeout_ms: int = 30000,
    keep_open_seconds: float = 0,
) -> dict[str, Any]:
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS URLs are accepted.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            locale="en-US",
        )
        page = context.new_page()
        page.set_default_navigation_timeout(timeout_ms)
        result: dict[str, Any] = {
            "url_requested": url,
            "url_final": None,
            "title": None,
            "status": "unknown",
            "dismissed": [],
            "blockers": [],
            "warnings": [],
        }
        try:
            response = page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5000))
            except Exception:
                pass
            result["url_final"] = page.url
            result["title"] = page.title()
            gates = detect_access_gate(page)
            if response is not None and response.status in (401, 403, 429):
                result["status"] = "access_limited"
                result["blockers"] = ["HTTP " + str(response.status)]
            elif gates:
                result["status"] = "blocked_or_gated"
                result["blockers"] = gates
            else:
                report = dismiss_ordinary_overlays(page)
                result["dismissed"] = report.dismissed
                result["blockers"] = report.blockers
                result["warnings"] = report.warnings
                result["status"] = "ok" if report.safe_to_continue else "blocked_or_gated"
            if headed and keep_open_seconds > 0 and result["status"] == "ok":
                page.wait_for_timeout(int(max(0, min(keep_open_seconds, 60)) * 1000))
        finally:
            context.close()
            browser.close()
        return result
