"""Minimal official X API v2 adapter. Never scrapes the X website."""
from __future__ import annotations
import json, os, time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

BASE_URL="https://api.x.com/2"

class XAPIError(RuntimeError):
    def __init__(self,status_code:int|None,message:str):
        self.status_code=status_code
        super().__init__(message)

class XAPIClient:
    def __init__(self,bearer_token:str|None=None,*,timeout:float=25,max_retries:int=2,base_url:str=BASE_URL):
        self.bearer_token=(bearer_token or os.getenv("X_BEARER_TOKEN","")).strip()
        if not self.bearer_token:
            raise ValueError("X_BEARER_TOKEN is not configured.")
        self.timeout=timeout
        self.max_retries=max(0,min(max_retries,4))
        self.base_url=base_url.rstrip("/")

    def _get(self,path:str,params:dict[str,Any]|None=None)->dict[str,Any]:
        clean={k:v for k,v in (params or {}).items() if v is not None and v!=""}
        url=f"{self.base_url}/{path.lstrip('/')}"
        if clean: url+="?"+urlencode(clean,doseq=True)
        req=Request(url,headers={"Authorization":"Bearer "+self.bearer_token,"Accept":"application/json","User-Agent":"SocialScraper/0.1"},method="GET")
        for attempt in range(self.max_retries+1):
            try:
                with urlopen(req,timeout=self.timeout) as response:
                    payload=json.loads(response.read().decode("utf-8"))
                if not isinstance(payload,dict):
                    raise XAPIError(None,"Unexpected X API response.")
                if payload.get("errors") and not payload.get("data"):
                    first=payload["errors"][0] if isinstance(payload["errors"],list) and payload["errors"] else {}
                    raise XAPIError(None,str(first.get("detail") or first.get("title") or "X API request failed.")[:400])
                return payload
            except HTTPError as exc:
                body=exc.read().decode("utf-8",errors="replace")
                try:
                    parsed=json.loads(body)
                    detail=parsed.get("detail") or parsed.get("title") or "request rejected"
                except Exception:
                    detail="request rejected"
                if exc.code in (429,500,502,503,504) and attempt<self.max_retries:
                    try: delay=float(exc.headers.get("retry-after") or min(2**attempt,8))
                    except (TypeError,ValueError): delay=min(2**attempt,8)
                    time.sleep(max(1,min(delay,30)))
                    continue
                raise XAPIError(exc.code,f"X API HTTP {exc.code}: {str(detail)[:400]}") from None
            except (URLError,TimeoutError,json.JSONDecodeError) as exc:
                if attempt<self.max_retries:
                    time.sleep(min(2**attempt,8))
                    continue
                raise XAPIError(None,f"X API request failed: {type(exc).__name__}") from None
        raise XAPIError(None,"X API retry budget exhausted.")

    def user_by_username(self,username:str)->dict[str,Any]|None:
        handle=normalize_handle(username)
        try:
            result=self._get("users/by/username/"+quote(handle,safe=""),{"user.fields":"id,name,username,description,verified,public_metrics,created_at,url"})
        except XAPIError as exc:
            if exc.status_code==404: return None
            raise
        value=result.get("data")
        return value if isinstance(value,dict) else None

    def user_posts(self,user_id:str,*,max_results:int=10)->list[dict[str,Any]]:
        limit=max(5,min(int(max_results),100))
        result=self._get("users/"+quote(str(user_id),safe="")+"/tweets",{
            "max_results":limit,
            "tweet.fields":"id,text,author_id,created_at,lang,public_metrics,conversation_id,referenced_tweets",
            "exclude":"retweets"
        })
        return [row for row in (result.get("data") or []) if isinstance(row,dict)]

def normalize_handle(value:str)->str:
    handle=(value or "").strip()
    for prefix in ("https://x.com/","https://twitter.com/"):
        if handle.startswith(prefix): handle=handle[len(prefix):]
    handle=handle.split("/",1)[0].split("?",1)[0].lstrip("@")
    if not handle or len(handle)>15 or not all(ch.isalnum() or ch=="_" for ch in handle):
        raise ValueError("Invalid X username: "+repr(value))
    return handle

def post_url(post_id:str,username:str|None=None)->str:
    if username: return "https://x.com/"+normalize_handle(username)+"/status/"+quote(str(post_id),safe="")
    return "https://x.com/i/web/status/"+quote(str(post_id),safe="")

def collect_official_profile(client:XAPIClient,handle:str,*,max_posts:int=10)->dict[str,Any]:
    user=client.user_by_username(handle)
    if user is None:
        return {"handle":normalize_handle(handle),"status":"not_found","user":None,"posts":[]}
    posts=client.user_posts(str(user["id"]),max_results=max_posts)
    normalized=[]
    for row in posts:
        normalized.append({
            "id":str(row.get("id") or ""),
            "url":post_url(str(row.get("id") or ""),str(user.get("username") or handle)),
            "author_username":user.get("username"),
            "text":str(row.get("text") or "")[:25000],
            "created_at":row.get("created_at"),
            "lang":row.get("lang"),
            "public_metrics":row.get("public_metrics") if isinstance(row.get("public_metrics"),dict) else {}
        })
    return {"handle":user.get("username") or normalize_handle(handle),"status":"profile_exists","user":{
        "id":str(user.get("id") or ""),"name":user.get("name"),"username":user.get("username"),
        "description":str(user.get("description") or "")[:1000],"verified":user.get("verified"),
        "public_metrics":user.get("public_metrics") if isinstance(user.get("public_metrics"),dict) else {}
    },"posts":normalized}
