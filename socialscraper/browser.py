"""Visible public-page inspector; stops when access-control signals appear."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from socialscraper.ui_dismiss import detect_access_gate, dismiss_ordinary_overlays

LOGGER = logging.getLogger(__name__)


def _extract_media_evidence(article: Any) -> list[dict[str, Any]]:
    """Collect media metadata already present in a rendered post card."""
    media: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    try:
        images = article.locator("img")
        image_count = min(images.count(), 30)
    except Exception:
        image_count = 0
        images = None

    for index in range(image_count):
        image = images.nth(index)
        try:
            details = image.evaluate(
                """el => {
                    const rect = el.getBoundingClientRect();
                    const wrapper = el.closest(
                        '[data-testid="tweetPhoto"], [data-testid^="card.layout"]'
                    );
                    return {
                        src: el.currentSrc || el.src || "",
                        alt: el.getAttribute("alt") || el.getAttribute("aria-label") || "",
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                        natural_width: el.naturalWidth || 0,
                        natural_height: el.naturalHeight || 0,
                        in_media_container: Boolean(wrapper)
                    };
                }"""
            )
        except Exception:
            continue

        src = str(details.get("src") or "")
        if not src.startswith(("https://", "http://")):
            continue
        # Profile pictures and tiny emoji are not useful post-media evidence.
        if "/profile_images/" in src or "default_profile" in src:
            continue
        alt_text = str(details.get("alt") or "").strip()
        is_x_media = "pbs.twimg.com/media/" in src
        is_large = max(
            int(details.get("width") or 0),
            int(details.get("height") or 0),
            int(details.get("natural_width") or 0),
            int(details.get("natural_height") or 0),
        ) >= 100
        if not (
            details.get("in_media_container")
            or is_x_media
            or (alt_text and is_large)
            or is_large
        ):
            continue

        key = ("image", src)
        if key in seen:
            continue
        seen.add(key)
        media.append({
            "type": "image",
            "url": src,
            "alt_text": alt_text or None,
            "alt_text_available": bool(alt_text),
            "width": details.get("natural_width") or details.get("width"),
            "height": details.get("natural_height") or details.get("height"),
        })

    try:
        videos = article.locator("video")
        video_count = min(videos.count(), 5)
    except Exception:
        video_count = 0
        videos = None

    for index in range(video_count):
        video = videos.nth(index)
        try:
            if not video.is_visible(timeout=250):
                continue
        except Exception:
            continue
        try:
            details = video.evaluate(
                """el => ({
                    src: el.currentSrc || el.getAttribute("src") || "",
                    poster: el.poster || "",
                    width: el.videoWidth || el.clientWidth || 0,
                    height: el.videoHeight || el.clientHeight || 0,
                    duration: Number.isFinite(el.duration) ? el.duration : null,
                    label: el.getAttribute("aria-label") || "",
                    tracks: Array.from(el.querySelectorAll("track")).map(t => ({
                        kind: t.kind || "",
                        src: t.src || "",
                        language: t.srclang || "",
                        label: t.label || ""
                    }))
                })"""
            )
        except Exception:
            details = {}

        raw_src = str(details.get("src") or "")
        poster = str(details.get("poster") or "")
        video_url = raw_src if raw_src.startswith(("https://", "http://")) else None
        poster_url = poster if poster.startswith(("https://", "http://")) else None
        tracks = []
        for track in details.get("tracks") or []:
            if not isinstance(track, dict):
                continue
            raw_track_src = str(track.get("src") or "")
            tracks.append({
                "kind": track.get("kind") or None,
                "url": raw_track_src if raw_track_src.startswith(("https://", "http://")) else None,
                "language": track.get("language") or None,
                "label": track.get("label") or None,
            })

        key = ("video", video_url or poster_url or f"video-{index}")
        if key in seen:
            continue
        seen.add(key)
        media.append({
            "type": "video",
            "url": video_url,
            "poster_url": poster_url,
            "duration_seconds": details.get("duration"),
            "width": details.get("width") or None,
            "height": details.get("height") or None,
            "label": str(details.get("label") or "").strip() or None,
            "caption_tracks": tracks,
            "video_url_available": bool(video_url),
        })

    # X can expose a video-player container before attaching a <video> element.
    if video_count == 0:
        try:
            players = article.locator('[data-testid="videoPlayer"], [data-testid="videoComponent"]')
            if players.count():
                player = players.first
                label = (
                    player.get_attribute("aria-label", timeout=300)
                    or player.inner_text(timeout=500)
                    or ""
                ).strip()
                media.append({
                    "type": "video",
                    "url": None,
                    "poster_url": None,
                    "duration_seconds": None,
                    "label": label[:300] or None,
                    "caption_tracks": [],
                    "video_url_available": False,
                    "note": "Video player container is visible; no direct video URL exposed in the DOM.",
                })
        except Exception:
            pass

    return media


def _extract_outbound_links(article: Any) -> list[dict[str, str]]:
    """List HTTP(S) links shown inside a post, without opening them."""
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    try:
        anchors = article.locator("a[href]")
        count = min(anchors.count(), 40)
    except Exception:
        return links

    for index in range(count):
        anchor = anchors.nth(index)
        try:
            href = anchor.get_attribute("href", timeout=300)
            if not href or not href.startswith(("https://", "http://")):
                continue
            parsed = urlparse(href)
            host = (parsed.hostname or "").lower()
            if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
                continue
            if href in seen:
                continue
            seen.add(href)
            try:
                label = anchor.inner_text(timeout=300).strip()
            except Exception:
                label = ""
            try:
                title = anchor.get_attribute("title", timeout=300) or ""
            except Exception:
                title = ""
            links.append({
                "url": href,
                "label": (label or title)[:300],
            })
        except Exception:
            continue
    return links


def _extract_caption(article: Any) -> str | None:
    """Read the post's caption field separately from engagement controls."""
    try:
        caption = article.locator('[data-testid="tweetText"]').first
        if caption.count():
            value = caption.inner_text(timeout=800).strip()
            return value[:3000] or None
    except Exception:
        pass
    return None


def inspect_public_page(
    url: str,
    *,
    headed: bool = True,
    timeout_ms: int = 30000,
    keep_open_seconds: float = 0,
    debug: bool = False,
    debug_dir: str | Path = "output/debug",
) -> dict[str, Any]:
    """Inspect a public HTTPS page without attempting to get past access controls.

    In debug mode, write a Playwright trace and final screenshot under debug_dir.
    The trace may contain page content, so keep the debug artifacts local.
    """
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS URLs are accepted.")

    debug_path = Path(debug_dir)
    trace_path = debug_path / "playwright-trace.zip"
    screenshot_path = debug_path / "page.png"

    out: dict[str, Any] = {
        "url_requested": url,
        "url_final": None,
        "title": None,
        "http_status": None,
        "status": "unknown",
        "dismissed": [],
        "blockers": [],
        "warnings": [],
        "article_element_count": None,
        "visible_article_count_checked": None,
        "posts_returned": 0,
        "visible_posts": [],
    }
    if debug:
        out["debug_artifacts"] = {
            "trace": str(trace_path),
            "screenshot": str(screenshot_path),
        }
        debug_path.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = None
        context = None
        page = None
        trace_started = False
        try:
            LOGGER.debug("Launching Chromium (headed=%s)", headed)
            browser = p.chromium.launch(headless=not headed)
            context = browser.new_context(
                viewport={"width": 1440, "height": 1000},
                locale="en-US",
            )
            page = context.new_page()
            page.set_default_navigation_timeout(timeout_ms)

            if debug:
                context.tracing.start(screenshots=True, snapshots=True, sources=True)
                trace_started = True
                page.on(
                    "console",
                    lambda message: LOGGER.debug(
                        "Browser console %s: %s", message.type, message.text[:500]
                    )
                    if message.type in {"warning", "error"}
                    else None,
                )
                page.on(
                    "pageerror",
                    lambda error: LOGGER.debug("Page error: %s", str(error)[:500]),
                )
                page.on(
                    "requestfailed",
                    lambda request: LOGGER.debug(
                        "Request failed: %s | %s", request.url, request.failure
                    ),
                )
                page.on(
                    "response",
                    lambda response: LOGGER.debug(
                        "HTTP %s %s", response.status, response.url
                    )
                    if response.status >= 400
                    else None,
                )

            LOGGER.info("Navigating to public page: %s", url)
            response = page.goto(url, wait_until="domcontentloaded")
            if response is not None:
                out["http_status"] = response.status
                LOGGER.info("Navigation response: HTTP %s", response.status)
            else:
                LOGGER.info("Navigation did not return a main-document response")

            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5000))
            except Exception as exc:
                LOGGER.debug("Network-idle wait ended without settling: %s", exc)

            out["url_final"] = page.url
            out["title"] = page.title()
            LOGGER.info("Final URL: %s", page.url)
            LOGGER.info("Page title: %s", out["title"])

            gates = detect_access_gate(page)
            if response is not None and response.status in (401, 403, 429):
                out["status"] = "access_limited"
                out["blockers"] = ["HTTP " + str(response.status)]
            elif gates:
                out["status"] = "blocked_or_gated"
                out["blockers"] = gates
            else:
                report = dismiss_ordinary_overlays(page)
                out["dismissed"] = report.dismissed
                out["blockers"] = report.blockers
                out["warnings"] = report.warnings
                out["status"] = "ok" if report.safe_to_continue else "blocked_or_gated"

            articles = page.locator("article")
            article_count = articles.count()
            visible_count = 0
            for index in range(min(article_count, 100)):
                try:
                    if articles.nth(index).is_visible(timeout=200):
                        visible_count += 1
                except Exception:
                    continue
            out["article_element_count"] = article_count
            out["visible_article_count_checked"] = visible_count

            # Read only post cards already rendered on an accessible public X page.
            # Never scroll or collect post text after a login/challenge/rate-limit signal.
            host = (urlparse(page.url).hostname or "").lower()
            if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"} and out["status"] == "ok":
                visible_posts = []
                for index in range(min(article_count, 5)):
                    article = articles.nth(index)
                    try:
                        if not article.is_visible(timeout=300):
                            continue
                        text = article.inner_text(timeout=1500).strip()
                    except Exception:
                        continue
                    if not text:
                        continue

                    created_at = None
                    displayed_time = None
                    try:
                        times = article.locator("time")
                        if times.count():
                            created_at = times.first.get_attribute("datetime", timeout=500)
                            displayed_time = times.first.inner_text(timeout=300).strip() or None
                    except Exception:
                        pass

                    post_url = None
                    try:
                        links = article.locator('a[href*="/status/"]')
                        for link_index in range(min(links.count(), 8)):
                            href = links.nth(link_index).get_attribute("href", timeout=500)
                            if href and "/status/" in href:
                                if href.startswith("/"):
                                    post_url = "https://x.com" + href
                                elif href.startswith("https://x.com/"):
                                    post_url = href
                                if post_url:
                                    break
                    except Exception:
                        pass

                    media = _extract_media_evidence(article)
                    outbound_links = _extract_outbound_links(article)
                    caption = _extract_caption(article)

                    visible_posts.append({
                        "created_at": created_at,
                        "displayed_time": displayed_time,
                        "url": post_url,
                        "caption": caption,
                        "text": text[:1200],
                        "media": media,
                        "external_links": outbound_links,
                        "media_count": len(media),
                    })
                out["visible_posts"] = visible_posts
                out["posts_returned"] = len(visible_posts)

            LOGGER.info(
                "Inspection status: %s; article elements: %s; visible articles checked: %s; public posts captured: %s",
                out["status"],
                article_count,
                visible_count,
                out["posts_returned"],
            )
            if out["blockers"]:
                LOGGER.warning(
                    "Access-control or page blocker detected: %s. No bypass attempted.",
                    ", ".join(out["blockers"]),
                )

            # Keep the page visible for local debugging, even when a gate is detected.
            if headed and keep_open_seconds > 0 and page.url != "about:blank":
                wait_seconds = max(0, min(keep_open_seconds, 60))
                LOGGER.info("Keeping browser window open for %.1f seconds.", wait_seconds)
                page.wait_for_timeout(int(wait_seconds * 1000))

        except Exception as exc:
            out["status"] = "error"
            out["error"] = f"{type(exc).__name__}: {exc}"
            LOGGER.exception("Public-page inspection failed")
        finally:
            if debug and page is not None and page.url != "about:blank":
                try:
                    page.screenshot(
                        path=str(screenshot_path),
                        full_page=True,
                        animations="disabled",
                        timeout=10000,
                    )
                    LOGGER.info("Saved debug screenshot: %s", screenshot_path)
                except Exception as exc:
                    LOGGER.warning("Could not save debug screenshot: %s", exc)

            if trace_started and context is not None:
                try:
                    context.tracing.stop(path=str(trace_path))
                    LOGGER.info("Saved Playwright trace: %s", trace_path)
                except Exception as exc:
                    LOGGER.warning("Could not save Playwright trace: %s", exc)

            if context is not None:
                try:
                    context.close()
                except Exception as exc:
                    LOGGER.debug("Context cleanup issue: %s", exc)
            if browser is not None:
                try:
                    browser.close()
                except Exception as exc:
                    LOGGER.debug("Browser cleanup issue: %s", exc)

    return out
