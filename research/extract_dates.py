from __future__ import annotations

import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

INDEX = Path(__file__).resolve().parent / "raw_community" / "index.json"
urls = [x["requested_url"] for x in json.loads(INDEX.read_text(encoding="utf-8")) if "tradingview.com/script/" in x["requested_url"]]
s = requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36","Accept-Language":"en-US,en;q=0.9"})
for url in urls:
    html = s.get(url, timeout=45).text
    soup = BeautifulSoup(html, "html.parser")
    times = []
    for t in soup.find_all("time"):
        times.append({"text":t.get_text(" ",strip=True),"datetime":t.get("datetime"),"title":t.get("title")})
    jsonld=[]
    for node in soup.find_all("script", attrs={"type":"application/ld+json"}):
        try:
            data=json.loads(node.string or "")
            if isinstance(data,dict):
                jsonld.append({k:data.get(k) for k in ("datePublished","dateModified","uploadDate","name") if data.get(k)})
        except Exception:
            pass
    print(url)
    print(" times=", json.dumps(times[:20],ensure_ascii=False))
    print(" jsonld=",json.dumps(jsonld,ensure_ascii=False))
