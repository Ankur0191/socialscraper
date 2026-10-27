"""Dismiss ordinary, non-access-control public-page UI conservatively."""
from __future__ import annotations
from dataclasses import dataclass, field
from urllib.parse import urlparse
from playwright.sync_api import Page

DISMISS_LABELS = [
    "Close", "Close dialog", "Close modal", "Dismiss", "Got it",
    "Accept all cookies", "Accept cookies", "Allow all cookies",
    "Reject optional cookies", "Decline cookies", "Continue without accepting",
    "No thanks", "Not now", "Skip",
]
DISMISS_SELECTORS = [
    'button[aria-label="Close"]', 'button[aria-label="close"]', 'button[title="Close"]',
    '[role="dialog"] button[aria-label="Close"]', '[data-testid="close-button"]',
    '[data-testid="modal-close"]', '#onetrust-accept-btn-handler', '#onetrust-reject-all-handler',
]
GATE_PATTERNS = [
    "sign in to x", "log in to x", "create your account", "something went wrong",
    "sign in to continue", "log in to continue", "you must be logged in",
    "create an account to continue", "subscribe to continue", "subscription required",
    "verify you are human", "checking your browser", "unusual traffic", "access denied",
    "captcha", "rate limit exceeded", "too many requests", "automated requests", "not authorized",
]

@dataclass
class DismissReport:
    dismissed: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    @property
    def safe_to_continue(self) -> bool:
        return not self.blockers

def _page_text(page: Page) -> str:
    try:
        return page.locator("body").inner_text(timeout=1500).lower()[:50000]
    except Exception:
        return ""

def detect_access_gate(page: Page) -> list[str]:
    found = [p for p in GATE_PATTERNS if p in _page_text(page)]
    parsed = urlparse(page.url or "")
    path = parsed.path.lower()
    if any(part in path for part in ("/login", "/signin", "/sign-in", "/auth/")):
        found.append("login route")
    if any(part in path for part in ("/challenge", "/captcha", "/checkpoint")):
        found.append("challenge route")
    return found

def dismiss_ordinary_overlays(page: Page, *, max_dismissals: int = 8) -> DismissReport:
    """Click explicit ordinary close/consent buttons; never delete DOM elements."""
    report = DismissReport()
    gates = detect_access_gate(page)
    if gates:
        report.blockers.extend(gates)
        return report
    for label in DISMISS_LABELS:
        if len(report.dismissed) >= max_dismissals:
            break
        try:
            locator = page.get_by_role("button", name=label, exact=False)
            for idx in range(min(locator.count(), 3)):
                if len(report.dismissed) >= max_dismissals:
                    break
                candidate = locator.nth(idx)
                try:
                    if candidate.is_visible(timeout=250) and candidate.is_enabled(timeout=250):
                        candidate.click(timeout=1000)
                        report.dismissed.append("button:" + label)
                        page.wait_for_timeout(150)
                        gates = detect_access_gate(page)
                        if gates:
                            report.blockers.extend(gates)
                            return report
                except Exception:
                    continue
        except Exception:
            continue
    for selector in DISMISS_SELECTORS:
        if len(report.dismissed) >= max_dismissals:
            break
        try:
            locator = page.locator(selector)
            for idx in range(min(locator.count(), 2)):
                if len(report.dismissed) >= max_dismissals:
                    break
                candidate = locator.nth(idx)
                try:
                    if candidate.is_visible(timeout=250) and candidate.is_enabled(timeout=250):
                        candidate.click(timeout=1000)
                        report.dismissed.append("selector:" + selector)
                        page.wait_for_timeout(150)
                        gates = detect_access_gate(page)
                        if gates:
                            report.blockers.extend(gates)
                            return report
                except Exception:
                    continue
        except Exception:
            continue
    gates = detect_access_gate(page)
    if gates:
        report.blockers.extend(gates)
    if not report.dismissed:
        report.warnings.append("No allowlisted dismiss button found; page left unchanged.")
    return report
