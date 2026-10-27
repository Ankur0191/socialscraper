"""SocialScraper CLI."""
from __future__ import annotations
import argparse, json, logging
from pathlib import Path
from typing import Any
from socialscraper.browser import inspect_public_page
from socialscraper.link_verifier import check_link
from socialscraper.media_intelligence import analyze_media_report
from socialscraper.x_api import XAPIClient, XAPIError, collect_official_profile

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST=ROOT/"data"/"competitor_socials.json"

def read_manifest(path:Path)->dict[str,Any]:
    if not path.exists(): raise FileNotFoundError("Manifest not found: "+str(path))
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or not isinstance(data.get("companies"),list):
        raise ValueError("Manifest must contain a companies array.")
    return data

def _accounts(company:dict[str,Any],platform:str):
    profile=(company.get("socials") or {}).get(platform) or {}
    return profile.get("accounts") if isinstance(profile.get("accounts"),list) else [profile]

def cmd_seed_preview(args):
    data=read_manifest(Path(args.manifest))
    for company in data["companies"]:
        print(str(company.get("name","(unnamed)"))+":")
        for platform,profile in (company.get("socials") or {}).items():
            accounts=profile.get("accounts") if isinstance(profile,dict) and isinstance(profile.get("accounts"),list) else [profile]
            for account in accounts:
                if not isinstance(account,dict): continue
                print("  "+platform+": "+str(account.get("url") or "(no confirmed URL)")+" ["+str(account.get("status","not_confirmed"))+"]")
                if not account.get("url") and account.get("search_url"): print("    search: "+str(account["search_url"]))
    return 0

def cmd_verify_links(args):
    data=read_manifest(Path(args.manifest)); results=[]
    for company in data["companies"]:
        name=str(company.get("name","(unnamed)"))
        for platform,profile in (company.get("socials") or {}).items():
            if not isinstance(profile,dict): continue
            accounts=profile.get("accounts") if isinstance(profile.get("accounts"),list) else [profile]
            for account in accounts:
                if not isinstance(account,dict) or not account.get("url"): continue
                item=check_link(name,platform,account["url"],timeout=args.timeout).to_dict(); results.append(item)
                print(f"{name} | {platform} | {item['status']} | HTTP {item.get('http_status') or '-'} | {item['url']}")
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"Saved {len(results)} checks to {out}")
    return 0

def cmd_inspect_public_page(args):
    result=inspect_public_page(
        args.url,
        headed=args.headed,
        timeout_ms=args.timeout_ms,
        keep_open_seconds=args.keep_open_seconds,
        debug=args.debug,
        debug_dir=args.debug_dir,
    )
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(result,indent=2,ensure_ascii=False))
    print(f"\nSaved inspection JSON: {output}")
    return 0 if result["status"]=="ok" else 2

def cmd_analyze_media(args):
    result = analyze_media_report(
        input_path=args.input,
        output_path=args.output,
        model=args.model,
        max_posts=args.max_posts,
        max_images_per_post=args.max_images_per_post,
    )
    print(json.dumps({
        "status": result["status"],
        "model": result["model"],
        "posts_considered": result["posts_considered"],
        "posts_analyzed": result["posts_analyzed"],
        "posts_skipped_or_failed": result["posts_skipped_or_failed"],
        "output": args.output,
    }, indent=2))
    return 0 if result["status"] == "ok" else 1

def cmd_x_preview(args):
    data=read_manifest(Path(args.manifest)); total=0
    for company in data["companies"]:
        for account in _accounts(company,"x"):
            if not isinstance(account,dict) or not account.get("handle"): continue
            total+=1
            print(f"{company.get('name')} | @{account['handle']} | {account.get('status','candidate')} | {account.get('url')}")
    print(f"X profile candidates found: {total}")
    print("Preview only: no API calls, no website scraping, and no database writes.")
    return 0

def cmd_x_collect(args):
    data=read_manifest(Path(args.manifest))
    client=XAPIClient()
    collected=0; failures=0; results=[]; stop=False; total_reads=0
    read_budget=args.max_total_posts
    for company in data["companies"]:
        if stop or read_budget < 5: break
        for account in _accounts(company,"x"):
            if stop or read_budget < 5: break
            if not isinstance(account,dict) or not account.get("handle"): continue
            if account.get("status") not in {"official_link_verified","regional_only"}:
                print(f"SKIP @{account['handle']}: status={account.get('status','candidate')} is not approved for collection")
                continue
            limit=min(args.max_posts,read_budget)
            try:
                record=collect_official_profile(client,account["handle"],max_posts=limit)
                record["company"]=company.get("name")
                results.append(record)
                if record.get("status")=="not_found":
                    failures+=1
                    print(f"NOT FOUND @{account['handle']}")
                else:
                    n=len(record.get("posts") or [])
                    collected+=n; total_reads+=n; read_budget-=n
                    print(f"OK @{record['handle']}: {n} public posts")
            except XAPIError as exc:
                print(f"ERROR @{account['handle']}: {exc}")
                results.append({"company":company.get("name"),"handle":account["handle"],"status":"error","error":str(exc)})
                failures+=1
                if exc.status_code==401:
                    print("Stopping: invalid X API credentials.")
                    stop=True
                    break
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"Saved {len(results)} profile result(s); posts={collected}; per-run post budget={args.max_total_posts}; output={out}")
    return 1 if failures else 0

def main():
    parser=argparse.ArgumentParser(prog="socialscraper")
    sub=parser.add_subparsers(dest="command",required=True)
    preview=sub.add_parser("seed-preview",help="Preview profiles in the JSON manifest.")
    preview.add_argument("--manifest",default=str(DEFAULT_MANIFEST)); preview.set_defaults(handler=cmd_seed_preview)
    verify=sub.add_parser("verify-links",help="Check URL syntax/reachability, not ownership.")
    verify.add_argument("--manifest",default=str(DEFAULT_MANIFEST)); verify.add_argument("--output",default="output/link_checks.json"); verify.add_argument("--timeout",type=float,default=8); verify.set_defaults(handler=cmd_verify_links)
    inspect=sub.add_parser("inspect-public-page",help="Inspect public HTTPS page and dismiss ordinary UI.")
    inspect.add_argument("--url",required=True); inspect.add_argument("--headed",action="store_true",help="Show the Chromium window.")
    inspect.add_argument("--debug",action="store_true",help="Enable verbose logs, save a Playwright trace and screenshot.")
    inspect.add_argument("--debug-dir",default="output/debug",help="Directory for local debug artifacts.")
    inspect.add_argument("--output-json",default="output/public_page_inspection.json",help="Path for the structured inspection report.")
    inspect.add_argument("--timeout-ms",type=int,default=30000); inspect.add_argument("--keep-open-seconds",type=float,default=0); inspect.set_defaults(handler=cmd_inspect_public_page)
    analyze=sub.add_parser("analyze-media",help="Opt-in AI analysis of public images/posters captured in an inspection JSON.")
    analyze.add_argument("--input",default="output/public_page_inspection.json",help="Inspection JSON produced by inspect-public-page.")
    analyze.add_argument("--output",default="output/media_intelligence.json",help="Path for structured media intelligence JSON.")
    analyze.add_argument("--model",default=None,help="Vision-capable model override (or set OPENAI_VISION_MODEL).")
    analyze.add_argument("--max-posts",type=int,default=5,help="Analyze up to five already-captured posts.")
    analyze.add_argument("--max-images-per-post",type=int,default=2,help="Maximum public images/posters per post.")
    analyze.set_defaults(handler=cmd_analyze_media)
    xp=sub.add_parser("x-preview",help="Preview X profiles from the manifest without making requests.")
    xp.add_argument("--manifest",default=str(DEFAULT_MANIFEST)); xp.set_defaults(handler=cmd_x_preview)
    xc=sub.add_parser("x-collect",help="Collect approved profiles via official X API only.")
    xc.add_argument("--manifest",default=str(DEFAULT_MANIFEST)); xc.add_argument("--max-posts",type=int,default=10); xc.add_argument("--max-total-posts",type=int,default=100)
    xc.add_argument("--output",default="output/x_posts.json"); xc.set_defaults(handler=cmd_x_collect)
    args=parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if getattr(args,"debug",False) else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try: raise SystemExit(args.handler(args))
    except (ValueError,FileNotFoundError,json.JSONDecodeError) as exc: parser.error(str(exc))
if __name__=="__main__": main()
