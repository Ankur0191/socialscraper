"""Conservative URL checks for a social-link manifest.

The verifier checks syntax and basic HTTP reachability only. A successful response
is not sufficient evidence that a profile is owned by the named company.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlparse

import requests


SOCIAL_HOSTS = {
    "x": {"x.com", "www.x.com", "twitter.com", "www.twitter.com"},
    "linkedin": {"linkedin.com", "www.linkedin.com"},
    "facebook": {"facebook.com", "www.facebook.com", "fb.me", "m.facebook.com"},
    "instagram": {"instagram.com", "www.instagram.com"},
    "youtube": {"youtube.com", "www.youtube.com", "youtu.be"},
    "threads": {"threads.net", "www.threads.net"},
    "tiktok": {"tiktok.com", "www.tiktok.com"},
}


@dataclass
class LinkCheck:
    company: str
    platform: str
    url: str
    status: str
    http_status: int | None = None
    final_url: str | None = None
    note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def validate_social_url(platform: str, url: str) -> tuple[bool, str]:
    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https":
        return False, "Only HTTPS social profile URLs are accepted."
    host = (parsed.hostname or "").lower()
    allowed = SOCIAL_HOSTS.get(platform.lower())
    if not allowed:
        return False, "Unknown platform: " + platform
    if host not in allowed:
        return False, "Unexpected host for " + platform + ": " + (host or "(missing)")
    if not parsed.path or parsed.path == "/":
        return False, "URL does not identify a specific profile/page."
    return True, "URL format accepted."


def check_link(
    company: str,
    platform: str,
    url: str,
    *,
    timeout: float = 8.0,
    session: requests.Session | None = None,
) -> LinkCheck:
    valid, note = validate_social_url(platform, url)
    if not valid:
        return LinkCheck(company, platform, url, "invalid_url", note=note)

    own_session = session is None
    client = session or requests.Session()
    try:
        response = client.get(
            url,
            allow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "SocialScraper/0.1 (+public-link-verification)"},
        )
        final_host = (urlparse(response.url).hostname or "").lower()
        expected_hosts = SOCIAL_HOSTS[platform.lower()]
        if response.status_code == 404:
            status, detail = "not_found", "HTTP 404; confirm manually before classifying as deleted."
        elif response.status_code in (401, 403, 429):
            status, detail = "access_limited", "Platform restricted this request; do not retry with bypass techniques."
        elif 200 <= response.status_code < 300 and final_host in expected_hosts:
            status, detail = "reachable", "Reachable; this does not verify company ownership."
        else:
            status, detail = "redirected_or_unclear", "Response/redirect is inconclusive; review the final URL manually."
        return LinkCheck(company, platform, url, status, response.status_code, response.url, detail)
    except requests.RequestException as exc:
        return LinkCheck(company, platform, url, "network_error", note=type(exc).__name__)
    finally:
        if own_session:
            client.close()
