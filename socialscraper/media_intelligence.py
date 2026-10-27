"""Opt-in vision analysis for public media metadata already captured by the inspector."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4.1-mini"
MAX_POSTS_HARD_LIMIT = 5
MAX_IMAGES_HARD_LIMIT = 4

ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "media_summary": {"type": "string"},
        "visible_text": {"type": "array", "items": {"type": "string"}},
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "evidence": {"type": "string"},
                    "evidence_type": {
                        "type": "string",
                        "enum": ["caption", "image", "video_poster", "uncertain"],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
                "required": ["claim", "evidence", "evidence_type", "confidence"],
                "additionalProperties": False,
            },
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "entity_type": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "entity_type", "evidence"],
                "additionalProperties": False,
            },
        },
        "strategic_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "signal": {"type": "string"},
                    "interpretation": {"type": "string"},
                    "evidence": {"type": "string"},
                    "classification": {
                        "type": "string",
                        "enum": ["observation", "inference"],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
                "required": [
                    "signal",
                    "interpretation",
                    "evidence",
                    "classification",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "unknowns": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "media_summary",
        "visible_text",
        "facts",
        "entities",
        "strategic_signals",
        "unknowns",
    ],
    "additionalProperties": False,
}

SYSTEM_INSTRUCTIONS = (
    "You are an evidence-first competitive-intelligence analyst. Analyze only the "
    "provided public post text and attached public images. Some supplied images may "
    "be video poster frames; a poster is not the full video. Extract readable text, "
    "entities, numbers, dates, products/services, locations, financial or operational "
    "claims, and relevant strategic signals. Separate directly observed facts from "
    "inferences. Every fact and signal must quote or clearly point to visible evidence. "
    "Never invent unreadable text, dates, numbers, products, customers, or causal claims. "
    "If content is unclear or unavailable, say so under unknowns. Do not treat social "
    "engagement counts as business performance. Return only the requested structured data."
)


def _public_image_url(value: Any) -> str | None:
    """Allow only public X image CDN URLs recorded by the inspector."""
    if not isinstance(value, str) or not value.startswith("https://"):
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    if parsed.hostname != "pbs.twimg.com" or parsed.username or parsed.password:
        return None
    if not (
        parsed.path.startswith("/media/")
        or parsed.path.startswith("/ext_tw_video_thumb/")
    ):
        return None
    return value


def _post_images(post: dict[str, Any], limit: int) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in post.get("media") or []:
        if not isinstance(item, dict):
            continue
        # Prefer image media. Use a video poster only when a direct image URL is
        # not already represented; this deliberately does not claim video analysis.
        candidates = []
        if item.get("type") == "image":
            candidates.append((item.get("url"), "image"))
        elif item.get("type") == "video":
            candidates.append((item.get("poster_url"), "video_poster"))
        for candidate, media_kind in candidates:
            url = _public_image_url(candidate)
            if not url or url in seen:
                continue
            seen.add(url)
            found.append({"url": url, "kind": media_kind})
            if len(found) >= limit:
                return found
    return found


def _extract_response_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "refusal":
                raise RuntimeError("The vision model refused to analyze this input.")
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    if not chunks:
        raise RuntimeError("The vision API returned no structured text output.")
    return "\n".join(chunks)


def _analyze_one_post(
    session: requests.Session,
    *,
    post: dict[str, Any],
    image_items: list[dict[str, str]],
    model: str,
    api_key: str,
) -> dict[str, Any]:
    caption = str(post.get("caption") or "").strip()
    card_text = str(post.get("text") or "").strip()
    outbound_links = post.get("external_links") or []
    post_url = str(post.get("url") or "")

    user_parts: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": (
                f"Post URL: {post_url or 'unavailable'}\n"
                f"Caption field: {caption or 'not separately exposed by the page'}\n"
                f"Full visible post-card text: {card_text[:5000] or 'unavailable'}\n"
                f"Outbound links displayed in the post (not opened by this command): "
                f"{json.dumps(outbound_links, ensure_ascii=False)[:2000]}\n"
                f"Image evidence order: {json.dumps(image_items, ensure_ascii=False)}\n\n"
                "Analyze each supplied image in order. If a media item is a video poster, "
                "describe only what is visible in that still image; do not infer the "
                "full video's speech or events. Extract numerical claims verbatim when "
                "readable. Label strategic implications as inference, not fact."
            ),
        }
    ]
    for item in image_items:
        user_parts.append({
            "type": "input_image",
            "image_url": item["url"],
            "detail": "high",
        })

    request_body = {
        "model": model,
        "store": False,
        "max_output_tokens": 1400,
        "input": [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_parts},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "competitor_media_intelligence",
                "strict": True,
                "schema": ANALYSIS_SCHEMA,
            }
        },
    }
    response = session.post(
        RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=request_body,
        timeout=(10, 90),
    )
    if not response.ok:
        try:
            error_payload = response.json()
            message = error_payload.get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            message = ""
        # Avoid dumping headers, credentials, or an unbounded upstream response.
        raise RuntimeError(
            f"Vision API HTTP {response.status_code}: {str(message or 'request failed')[:300]}"
        )

    payload = response.json()
    analysis = json.loads(_extract_response_text(payload))
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    return {
        "post_url": post_url or None,
        "analysis_status": "analyzed",
        "model": model,
        "images_analyzed": image_items,
        "analysis": analysis,
        "usage": {
            key: usage.get(key)
            for key in ("input_tokens", "output_tokens", "total_tokens")
            if usage.get(key) is not None
        },
    }


def analyze_media_report(
    *,
    input_path: str | Path,
    output_path: str | Path,
    model: str | None = None,
    max_posts: int = 5,
    max_images_per_post: int = 2,
) -> dict[str, Any]:
    """Analyze up to five captured posts using an explicitly configured vision API."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is not configured. Set it in your local environment or .env file; "
            "vision analysis is opt-in and may incur API charges."
        )

    model_name = (model or os.getenv("OPENAI_VISION_MODEL") or DEFAULT_MODEL).strip()
    if not model_name:
        raise ValueError("A vision-capable model name is required.")
    post_limit = max(1, min(int(max_posts), MAX_POSTS_HARD_LIMIT))
    image_limit = max(1, min(int(max_images_per_post), MAX_IMAGES_HARD_LIMIT))

    source_path = Path(input_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Inspection JSON not found: {source_path}")
    try:
        source = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid inspection JSON: {exc}") from exc
    if not isinstance(source, dict):
        raise ValueError("Inspection JSON must be an object.")
    if source.get("status") != "ok":
        raise ValueError(
            "The source inspection did not finish with status 'ok'; media analysis stopped."
        )

    posts = source.get("visible_posts")
    if not isinstance(posts, list):
        raise ValueError("Inspection JSON does not contain a visible_posts array.")

    results: list[dict[str, Any]] = []
    skipped = 0
    with requests.Session() as session:
        for post in posts[:post_limit]:
            if not isinstance(post, dict):
                skipped += 1
                continue
            images = _post_images(post, image_limit)
            if not images:
                results.append({
                    "post_url": post.get("url"),
                    "analysis_status": "skipped_no_allowed_public_images",
                    "analysis": None,
                })
                skipped += 1
                continue
            try:
                results.append(
                    _analyze_one_post(
                        session,
                        post=post,
                        image_items=images,
                        model=model_name,
                        api_key=api_key,
                    )
                )
            except (requests.RequestException, ValueError, RuntimeError, json.JSONDecodeError) as exc:
                results.append({
                    "post_url": post.get("url"),
                    "analysis_status": "error",
                    "error": f"{type(exc).__name__}: {str(exc)[:400]}",
                    "images_analyzed": images,
                    "analysis": None,
                })

    completed = sum(1 for item in results if item.get("analysis_status") == "analyzed")
    overall_status = "ok" if completed == len(results) and results else "partial"
    output = {
        "source_file": str(source_path),
        "source_page": source.get("url_final") or source.get("url_requested"),
        "status": overall_status,
        "model": model_name,
        "max_posts": post_limit,
        "max_images_per_post": image_limit,
        "posts_considered": len(results),
        "posts_analyzed": completed,
        "posts_skipped_or_failed": len(results) - completed,
        "results": results,
        "notes": [
            "This command sends only recorded public image/poster URLs and post text to the configured model.",
            "Video poster analysis is not full video or audio transcription.",
            "Model interpretations are hypotheses; verify material claims against original sources.",
        ],
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    return output
