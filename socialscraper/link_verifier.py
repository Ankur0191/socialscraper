"""Social URL syntax and reachability checks; not proof of company ownership."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from urllib.parse import urlparse
import requests

SOCIAL_HOSTS = {
 "x":{"x.com","www.x.com","twitter.com","www.twitter.com"},
 "linkedin":{"linkedin.com","www.linkedin.com"},
 "facebook":{"facebook.com","www.facebook.com","fb.me","m.facebook.com"},
 "instagram":{"instagram.com","www.instagram.com"},
 "youtube":{"youtube.com","www.youtube.com","youtu.be"},
 "threads":{"threads.net","www.threads.net"},
 "tiktok":{"tiktok.com","www.tiktok.com"},
}
@dataclass
class LinkCheck:
 company:str; platform:str; url:str; status:str
 http_status:int|None=None; final_url:str|None=None; note:str|None=None
 def to_dict(self): return asdict(self)

def validate_social_url(platform:str,url:str)->tuple[bool,str]:
 p=urlparse((url or "").strip())
 if p.scheme!="https": return False,"Only HTTPS social profile URLs are accepted."
 allowed=SOCIAL_HOSTS.get(platform.lower()); host=(p.hostname or "").lower()
 if not allowed: return False,"Unknown platform: "+platform
 if host not in allowed: return False,"Unexpected host for "+platform+": "+(host or "(missing)")
 if not p.path or p.path=="/": return False,"URL does not identify a specific profile/page."
 return True,"URL format accepted."

def check_link(company:str,platform:str,url:str,*,timeout:float=8.0,session:requests.Session|None=None)->LinkCheck:
 valid,note=validate_social_url(platform,url)
 if not valid: return LinkCheck(company,platform,url,"invalid_url",note=note)
 own=session is None; client=session or requests.Session()
 try:
  r=client.get(url,allow_redirects=True,timeout=timeout,headers={"User-Agent":"SocialScraper/0.1 (+public-link-verification)"})
  final_host=(urlparse(r.url).hostname or "").lower()
  if r.status_code==404: status,detail="not_found","HTTP 404; confirm manually before classifying as deleted."
  elif r.status_code in (401,403,429): status,detail="access_limited","Platform restricted this request; do not retry with bypass techniques."
  elif 200<=r.status_code<300 and final_host in SOCIAL_HOSTS[platform.lower()]: status,detail="reachable","Reachable; this does not verify company ownership."
  else: status,detail="redirected_or_unclear","Response/redirect is inconclusive; review the final URL manually."
  return LinkCheck(company,platform,url,status,r.status_code,r.url,detail)
 except requests.RequestException as exc:
  return LinkCheck(company,platform,url,"network_error",note=type(exc).__name__)
 finally:
  if own: client.close()
