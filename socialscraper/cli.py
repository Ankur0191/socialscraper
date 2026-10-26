"""SocialScraper CLI."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
from socialscraper.browser import inspect_public_page
from socialscraper.link_verifier import check_link
from socialscraper.x_api import XAPIClient, XAPIError, collect_official_profile
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST=ROOT/"data"/"competitor_socials.json"

def read_manifest(path:Path)->dict[str,Any]:
 if not path.exists(): raise FileNotFoundError("Manifest not found: "+str(path))
 data=json.loads(path.read_text(encoding="utf-8"))
 if not isinstance(data,dict) or not isinstance(data.get("companies"),list): raise ValueError("Manifest must contain a companies array.")
 return data

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
 result=inspect_public_page(args.url,headed=args.headed,timeout_ms=args.timeout_ms,keep_open_seconds=args.keep_open_seconds)
 print(json.dumps(result,indent=2,ensure_ascii=False))
 return 0 if result["status"]=="ok" else 2

def cmd_x_preview(args):
 data=read_manifest(Path(args.manifest))
 total=0
 for company in data["companies"]:
  profile=(company.get("socials") or {}).get("x") or {}
  accounts=profile.get("accounts") if isinstance(profile.get("accounts"),list) else [profile]
  for account in accounts:
   if not isinstance(account,dict) or not account.get("handle"): continue
   total+=1
   print(f"{company.get('name')} | @{account['handle']} | {account.get('status','candidate')} | {account.get('url')}")
 print(f"X profile candidates found: {total}")
 print("Preview only: no API calls, no website scraping, and no database writes.")
 return 0

def cmd_x_collect(args):
 data=read_manifest(Path(args.manifest))
 client=XAPIClient()
 collected=0; failures=0; results=[]
 for company in data["companies"]:
  profile=(company.get("socials") or {}).get("x") or {}
  accounts=profile.get("accounts") if isinstance(profile.get("accounts"),list) else [profile]
  for account in accounts:
   if not isinstance(account,dict) or not account.get("handle"): continue
   if account.get("status") not in {"official_link_verified","regional_only"}:
    print(f"SKIP @{account['handle']}: status={account.get('status','candidate')} is not approved for collection")
    continue
   try:
    user=client.user_by_username(account["handle"])
    if not user:
     print(f"NOT FOUND @{account['handle']}")
     results.append({"company":company.get("name"),"handle":account["handle"],"status":"not_found"})
     failures+=1
     continue
    posts=client.user_posts(user["id"],max_results=args.max_posts)
    results.extend([{"company":company.get("name"),"handle":account["handle"],"profile":user,"post":post} for post in posts])
    collected+=len(posts)
    print(f"OK @{account['handle']}: {len(posts)} public posts")
   except XAPIError as exc:
    print(f"ERROR @{account['handle']}: {exc}")
    results.append({"company":company.get("name"),"handle":account["handle"],"status":"error","error":str(exc)})
    failures+=1
 out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
 print(f"Saved {len(results)} records; posts={collected}; failures={failures}; output={out}")
 return 1 if failures else 0

def main():
 parser=argparse.ArgumentParser(prog="socialscraper"); sub=parser.add_subparsers(dest="command",required=True)
 preview=sub.add_parser("seed-preview",help="Preview profiles in the JSON manifest."); preview.add_argument("--manifest",default=str(DEFAULT_MANIFEST)); preview.set_defaults(handler=cmd_seed_preview)
 verify=sub.add_parser("verify-links",help="Check URL syntax/reachability, not ownership."); verify.add_argument("--manifest",default=str(DEFAULT_MANIFEST)); verify.add_argument("--output",default="output/link_checks.json"); verify.add_argument("--timeout",type=float,default=8); verify.set_defaults(handler=cmd_verify_links)
 inspect=sub.add_parser("inspect-public-page",help="Inspect public HTTPS page and dismiss ordinary UI."); inspect.add_argument("--url",required=True); inspect.add_argument("--headed",action="store_true"); inspect.add_argument("--timeout-ms",type=int,default=30000); inspect.add_argument("--keep-open-seconds",type=float,default=0); inspect.set_defaults(handler=cmd_inspect_public_page)
 xp=sub.add_parser("x-preview",help="Preview the X profiles in the manifest without making requests.")
 xp.add_argument("--manifest",default=str(DEFAULT_MANIFEST)); xp.set_defaults(handler=cmd_x_preview)
 xc=sub.add_parser("x-collect",help="Collect from approved profiles via the official X API only.")
 xc.add_argument("--manifest",default=str(DEFAULT_MANIFEST)); xc.add_argument("--max-posts",type=int,default=10); xc.add_argument("--output",default="output/x_posts.json"); xc.set_defaults(handler=cmd_x_collect)
 args=parser.parse_args()
 try: raise SystemExit(args.handler(args))
 except (ValueError,FileNotFoundError,json.JSONDecodeError) as exc: parser.error(str(exc))
if __name__=="__main__": main()
