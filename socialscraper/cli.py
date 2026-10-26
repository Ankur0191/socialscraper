"""Command-line interface for SocialScraper."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from socialscraper.browser import inspect_public_page
from socialscraper.link_verifier import check_link


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "competitor_socials.json"


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError("Manifest not found: " + str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("companies"), list):
        raise ValueError("Manifest must be a JSON object containing a companies array.")
    return value


def cmd_seed_preview(args: argparse.Namespace) -> int:
    manifest = read_manifest(Path(args.manifest))
    for company in manifest["companies"]:
        print(str(company.get("name", "(unnamed)")) + ":")
        for platform, profile in (company.get("socials") or {}).items():
            accounts = profile.get("accounts") if isinstance(profile, dict) and isinstance(profile.get("accounts"), list) else [profile]
            for account in accounts:
                if not isinstance(account, dict):
                    continue
                url = account.get("url")
                print("  " + platform + ": " + str(url or "(no confirmed URL)") + " [" + str(account.get("status", "not_confirmed")) + "]")
                if not url and account.get("search_url"):
                    print("    search: " + str(account["search_url"]))
    return 0


def cmd_verify_links(args: argparse.Namespace) -> int:
    manifest = read_manifest(Path(args.manifest))
    results = []
    for company in manifest["companies"]:
        name = str(company.get("name", "(unnamed)"))
        for platform, profile in (company.get("socials") or {}).items():
            if not isinstance(profile, dict):
                continue
            accounts = profile.get("accounts") if isinstance(profile.get("accounts"), list) else [profile]
            for account in accounts:
                if not isinstance(account, dict) or not account.get("url"):
                    continue
                item = check_link(name, platform, account["url"], timeout=args.timeout).to_dict()
                results.append(item)
                print(f"{name} | {platform} | {item['status']} | HTTP {item.get('http_status') or '-'} | {item['url']}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(results)} checks to {output}")
    return 0


def cmd_inspect_public_page(args: argparse.Namespace) -> int:
    result = inspect_public_page(args.url, headed=args.headed, timeout_ms=args.timeout_ms, keep_open_seconds=args.keep_open_seconds)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 2


def main() -> None:
    parser = argparse.ArgumentParser(prog="socialscraper")
    commands = parser.add_subparsers(dest="command", required=True)
    preview = commands.add_parser("seed-preview", help="Preview social profiles from the JSON manifest.")
    preview.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    preview.set_defaults(handler=cmd_seed_preview)
    verify = commands.add_parser("verify-links", help="Check profile URL syntax/reachability, not ownership.")
    verify.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    verify.add_argument("--output", default="output/link_checks.json")
    verify.add_argument("--timeout", type=float, default=8)
    verify.set_defaults(handler=cmd_verify_links)
    inspect = commands.add_parser("inspect-public-page", help="Inspect an HTTPS public page and dismiss ordinary UI.")
    inspect.add_argument("--url", required=True)
    inspect.add_argument("--headed", action="store_true")
    inspect.add_argument("--timeout-ms", type=int, default=30000)
    inspect.add_argument("--keep-open-seconds", type=float, default=0)
    inspect.set_defaults(handler=cmd_inspect_public_page)
    args = parser.parse_args()
    try:
        raise SystemExit(args.handler(args))
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
