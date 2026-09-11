from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

URLS = [
    # TradingView official
    "https://www.tradingview.com/pine-script-docs/writing/limitations/",
    "https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/",
    "https://www.tradingview.com/pine-script-docs/release-notes/",
    "https://www.tradingview.com/pine-script-docs/concepts/repainting/",
    "https://www.tradingview.com/pine-script-docs/writing/profiling-and-optimization/",
    "https://www.tradingview.com/pine-script-docs/concepts/alerts/",
    "https://www.tradingview.com/support/solutions/43000725058-cumulative-volume-delta/",
    "https://www.tradingview.com/support/solutions/43000725057-volume-delta/",
    "https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/",
    "https://www.tradingview.com/support/solutions/43000685269-open-interest/",
    "https://www.tradingview.com/support/solutions/43000726164-volume-footprint-charts-a-complete-guide/",
    "https://www.tradingview.com/support/solutions/43000762399-long-short-ratio-accounts/",
    "https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/",
]


def slug(url: str) -> str:
    p = urlparse(url)
    s = (p.netloc + p.path).strip("/")
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s[:180]


def extract_meta(soup: BeautifulSoup, key: str) -> str | None:
    node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    if node and node.get("content"):
        return str(node["content"]).strip()
    return None


def fetch(url: str, session: requests.Session) -> dict:
    response = session.get(url, timeout=45, allow_redirects=True)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    canonical = ""
    can = soup.find("link", rel="canonical")
    if can and can.get("href"):
        canonical = str(can["href"])
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    dates = {
        "article_published_time": extract_meta(soup, "article:published_time"),
        "article_modified_time": extract_meta(soup, "article:modified_time"),
        "date": extract_meta(soup, "date"),
        "last_modified_header": response.headers.get("Last-Modified"),
    }
    return {
        "requested_url": url,
        "final_url": response.url,
        "status": response.status_code,
        "title": title,
        "canonical": canonical,
        "dates": dates,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "text": text,
    }


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }
    )
    index: list[dict] = []
    for i, url in enumerate(URLS, 1):
        try:
            result = fetch(url, session)
            stem = slug(url)
            (out_dir / f"{stem}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / f"{stem}.txt").write_text(result["text"], encoding="utf-8")
            index.append({k: result[k] for k in result if k != "text"})
            print(f"OK {i}/{len(URLS)} {result['status']} {url} chars={len(result['text'])}")
        except Exception as exc:
            index.append({"requested_url": url, "error": repr(exc), "retrieved_utc": datetime.now(timezone.utc).isoformat()})
            print(f"ERR {i}/{len(URLS)} {url}: {exc}", file=sys.stderr)
        time.sleep(0.4)
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all("error" not in x for x in index) else 1


if __name__ == "__main__":
    raise SystemExit(main())
