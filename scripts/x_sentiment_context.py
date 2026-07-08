#!/usr/bin/env python3
"""X/社交情绪 LLM 分析上下文采集脚本。

只采集结构化上下文，不直接做结论；stdout 注入 agent cron，让 LLM 结合 x_search 做中文交易解读。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
UA = "Hermes/1.0 (+https://github.com/amidaidai/ami-hermes)"
ROOT = Path("D:/Hermes agent")
DATA_DIR = ROOT / "data"
HERMES_DATA = Path(os.path.expanduser("~/AppData/Local/hermes/data"))
HISTORY = DATA_DIR / "x_sentiment_history.jsonl"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "HYPEUSDT"]


def fetch_json(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def safe_fetch(name: str, fn, default):
    try:
        return fn()
    except Exception as exc:
        return {"error": f"{name}: {type(exc).__name__}: {str(exc)[:120]}", **default}


def fetch_fear_greed() -> dict:
    data = fetch_json("https://api.alternative.me/fng/?limit=1", 8)
    item = data.get("data", [{}])[0]
    return {
        "value": int(item.get("value", 50)),
        "classification": item.get("value_classification", "Neutral"),
        "timestamp": item.get("timestamp"),
    }


def fetch_trending() -> dict:
    data = fetch_json("https://api.coingecko.com/api/v3/search/trending", 10)
    rows = []
    for c in data.get("coins", [])[:10]:
        item = c.get("item", {})
        rows.append({
            "symbol": str(item.get("symbol", "?")).upper(),
            "name": item.get("name", "?"),
            "rank": item.get("market_cap_rank"),
            "score": item.get("score"),
            "price_btc": item.get("price_btc"),
        })
    return {"coins": rows}


def fetch_global() -> dict:
    data = fetch_json("https://api.coingecko.com/api/v3/global", 10).get("data", {})
    return {
        "market_cap_change_24h_pct": data.get("market_cap_change_percentage_24h_usd"),
        "btc_dominance": data.get("market_cap_percentage", {}).get("btc"),
        "eth_dominance": data.get("market_cap_percentage", {}).get("eth"),
        "active_cryptocurrencies": data.get("active_cryptocurrencies"),
    }


def fetch_binance_24h(symbol: str) -> dict:
    q = urllib.parse.urlencode({"symbol": symbol})
    data = fetch_json(f"https://api.binance.com/api/v3/ticker/24hr?{q}", 8)
    return {
        "symbol": symbol,
        "price": float(data.get("lastPrice", 0)),
        "chg_24h_pct": float(data.get("priceChangePercent", 0)),
        "quote_volume": float(data.get("quoteVolume", 0)),
        "high": float(data.get("highPrice", 0)),
        "low": float(data.get("lowPrice", 0)),
    }


def fetch_market_snapshot() -> list[dict]:
    rows = []
    for s in SYMBOLS:
        rows.append(safe_fetch(s, lambda sym=s: fetch_binance_24h(sym), {"symbol": s}))
    return rows


def load_orion_top() -> list[dict]:
    p = DATA_DIR / "orion_radar.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        rows = data.get("candidates", [])[:8]
        return [{
            "symbol": r.get("symbol"),
            "confidence": r.get("confidence"),
            "chg_1h": r.get("chg_1h"),
            "oi_chg": r.get("oi_chg"),
            "funding": r.get("funding"),
        } for r in rows]
    except Exception:
        return []


def append_history(snapshot: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HERMES_DATA.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    # keep last 500 lines
    try:
        lines = HISTORY.read_text(encoding="utf-8").splitlines()[-500:]
        HISTORY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass
    (DATA_DIR / "x_sentiment_context.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    (HERMES_DATA / "x_sentiment_context.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    now = datetime.now(TZ)
    fg = safe_fetch("fear_greed", fetch_fear_greed, {"value": 50, "classification": "Error"})
    trending = safe_fetch("coingecko_trending", fetch_trending, {"coins": []})
    glob = safe_fetch("coingecko_global", fetch_global, {})
    market = fetch_market_snapshot()
    orion = load_orion_top()

    snapshot = {
        "ts": now.isoformat(),
        "time_cn": now.strftime("%Y年%m月%d日%H：%M"),
        "fear_greed": fg,
        "coingecko_trending": trending.get("coins", []),
        "global_market": glob,
        "market_snapshot": market,
        "orion_candidates": orion,
        "suggested_x_queries": [
            "crypto market sentiment BTC ETH SOL",
            "Bitcoin ETF crypto bearish bullish",
            "Solana HYPE crypto narrative",
        ] + [f"{c.get('symbol','').replace('USDT','')} crypto sentiment" for c in orion[:3] if c.get("symbol")],
    }
    append_history(snapshot)

    print(json.dumps(snapshot, ensure_ascii=False, indent=2))

    # v9.7: 额外生成结构化情绪快照表，走 RichMarkdown 真表格通道推 TG
    # （LLM 解读卡经 agent 通道走 MarkdownV2 退化，此表保证真表格渲染）
    try:
        fg = snapshot.get("fear_greed", {})
        glob = snapshot.get("global_market", {})
        market = snapshot.get("market_snapshot", [])
        mrows = "\n".join(
            f"| {m.get('symbol','?')} | `{m.get('price',0):.2f}` | {('🟢' if m.get('chg_24h_pct',0)>0 else '🔴' if m.get('chg_24h_pct',0)<0 else '⚪')}`{m.get('chg_24h_pct',0):+.2f}%` | `{m.get('quote_volume',0)/1e9:.2f}B` |"
            for m in market
        )
        # Orion共振候选（联动交易信号）
        orion = snapshot.get("orion_candidates", []) or []
        orows = "\n".join(
            f"| {o.get('symbol','?')} | `{o.get('confidence',0):.1f}` | `{o.get('chg_1h',0):+.2f}%` | `{o.get('oi_chg',0):+.1f}%` | `{o.get('funding',0)*100:.3f}%` |"
            for o in orion[:6]
        ) or "| — | — | — | — | — |"
        ts = snapshot.get("time_cn", "")
        fgv = fg.get("value", "?")
        fgcls = fg.get("classification", "?")
        # 恐惧贪婪分层解读 + 符号
        fg_note = "中性"
        fg_icon = "😐"
        try:
            fgi = int(fgv)
            if fgi <= 25: fg_note, fg_icon = "极度恐惧·潜在抄底区", "😱"
            elif fgi <= 45: fg_note, fg_icon = "恐惧·偏谨慎", "😟"
            elif fgi <= 55: fg_note, fg_icon = "中性·观望", "😐"
            elif fgi <= 75: fg_note, fg_icon = "贪婪·防回调", "😀"
            else: fg_note, fg_icon = "极度贪婪·高风区", "🤪"
        except Exception:
            pass
        # 市值变化方向符号
        mcap = glob.get('market_cap_change_24h_pct', '?')
        try:
            mcap_v = float(mcap)
            mcap_icon = "📈" if mcap_v > 0 else "📉" if mcap_v < 0 else "➡️"
        except Exception:
            mcap_icon = ""
        rich = f"""📊 X情绪/市场快照 · {ts}

| 指标 | 数值 |
|:----|:----:|
| 恐惧贪婪 | {fg_icon}{fgv} · {fgcls}（{fg_note}） |
| BTC占比 | {glob.get('btc_dominance','?')}% |
| ETH占比 | {glob.get('eth_dominance','?')}% |
| 24h市值变化 | {mcap_icon}{mcap}% |
| 活跃币种 | {glob.get('active_cryptocurrencies','?')} |

| 品种 | 现价 | 24h | 成交量 |
|:----|:----:|:----:|:----:|
{mrows}

| 共振候选 | 置信 | 1h | OI | 费率 |
|:----|:----:|:----:|:----:|:----:|
{orows}

**总体结论**: {fg_icon}情绪**{fgcls}**（{fg_note}）· 恐惧贪婪{fgv} · **{'🔥资金偏热FOMO' if (trending.get('fomo_score',0) or 0)>=4 else '❄️热度冷清' if (trending.get('fomo_score',0) or 0)<2 else '🌡️温和关注'}**{' · 有Orion共振候选可跟' if orion else ''}。"""
        sys.path.insert(0, "D:/Hermes agent/scripts")
        from telegram_reliable import push_tg_rich
        push_tg_rich("telegram:-1003733144325:846", rich)
    except Exception as _te:
        print(f"⚠ X情绪快照RichMarkdown推送失败: {_te}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
