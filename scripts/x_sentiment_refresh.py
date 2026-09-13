#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X 情绪上下文刷新（本地、不外发）。

背景（2026-09-13 审计）
----------------------
`data/x_sentiment_context.json` 是分析链 X情绪 步骤的输入，但**生产者早已消失**：
文件自 2026-07-15 起没再更新，卡面却仍在用 ✅ 打印那时的恐贪 25 / 市占 56.3%，
比没有更容易误导。router 对这一步的声明是「x_search 实时X/Twitter情绪」。

本脚本只做**客观可抓**的部分（恐贪 + BTC/ETH 市占 + 热门），X 上的舆情叙述由
agent 用 x_search 拉到后经 `--x-note` 写入 —— 脚本本身不联网社交平台、不外发。

用法
----
    python scripts/x_sentiment_refresh.py                 # 刷新客观部分
    python scripts/x_sentiment_refresh.py --x-note "…"    # 附带本轮 X 舆情摘要
    python scripts/x_sentiment_refresh.py --json          # 打印结果

失败即如实标注：某个子项这轮取不到就保留旧值并标 stale，绝不把旧值洗成新值。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = ROOT / "data" / "x_sentiment_context.json"
TZ = timezone(timedelta(hours=8))
UA = "TangXi-XSent/1.0"
TIMEOUT = 12


def _now() -> str:
    return datetime.now(TZ).isoformat()


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def fetch_fear_greed() -> dict:
    """alternative.me 恐惧贪婪（免费、无 key）。"""
    data = _get_json("https://api.alternative.me/fng/?limit=1")
    item = (data.get("data") or [{}])[0]
    value = item.get("value")
    if value in (None, ""):
        raise ValueError("empty fear_greed payload")
    return {"value": int(value), "classification": item.get("value_classification", ""),
            "ts": _now()}


def fetch_global_market() -> dict:
    """CoinGecko 免费 /global：BTC/ETH 市占 + 总市值 24h 变化。"""
    data = _get_json("https://api.coingecko.com/api/v3/global").get("data") or {}
    pct = data.get("market_cap_percentage") or {}
    if not pct:
        raise ValueError("empty global payload")
    return {
        "btc_dominance": round(float(pct.get("btc", 0)), 4),
        "eth_dominance": round(float(pct.get("eth", 0)), 4),
        "market_cap_change_24h_pct": data.get("market_cap_change_percentage_24h_usd"),
        "active_cryptocurrencies": data.get("active_cryptocurrencies"),
        "ts": _now(),
    }


def fetch_trending(limit: int = 5) -> list[dict]:
    """CoinGecko 免费 /search/trending。"""
    data = _get_json("https://api.coingecko.com/api/v3/search/trending")
    rows = []
    for entry in (data.get("coins") or [])[:limit]:
        item = entry.get("item") or {}
        rows.append({"symbol": item.get("symbol", "?"), "name": item.get("name", "?"),
                     "rank": item.get("market_cap_rank")})
    if not rows:
        raise ValueError("empty trending payload")
    return rows


DEFAULT_QUERIES = [
    "crypto market sentiment BTC ETH",
    "Bitcoin ETF flows bullish bearish",
    "BTC 关键位 多空 讨论",
]


def build_context(previous: dict, args: argparse.Namespace) -> tuple[dict, dict]:
    """返回 (新上下文, 本轮各子项状态)。取不到的保留旧值并标 stale。"""
    context = dict(previous) if isinstance(previous, dict) else {}
    status: dict[str, str] = {}

    for name, fetcher, key in (("fear_greed", fetch_fear_greed, "fear_greed"),
                               ("global_market", fetch_global_market, "global_market")):
        try:
            context[key] = fetcher()
            status[name] = "live"
        except Exception as exc:  # 网络/限速/空载荷：保留旧值但明确标 stale
            if not isinstance(context.get(key), dict) or not context[key]:
                context.pop(key, None)
            status[name] = f"stale_cache:{type(exc).__name__}"

    try:
        context["coingecko_trending"] = fetch_trending()
        status["coingecko_trending"] = "live"
    except Exception as exc:
        status["coingecko_trending"] = f"stale_cache:{type(exc).__name__}"

    if args.x_note:
        context["x_note"] = {"text": args.x_note.strip(), "ts": _now(),
                             "source": "x_search", "label": "仅情绪·不改裁决",
                             "status": "live"}
        status["x_note"] = "live"
    else:
        note = context.get("x_note")
        status["x_note"] = "kept_previous" if isinstance(note, dict) and note.get("text") else "absent"

    if args.queries:
        context["suggested_x_queries"] = [q.strip() for q in args.queries if q.strip()]
    else:
        context.setdefault("suggested_x_queries", list(DEFAULT_QUERIES))

    context["ts"] = _now()
    context["time_cn"] = datetime.now(TZ).strftime("%Y年%m月%d日%H:%M")
    # 清理历史遗留：本文件曾把逐子项状态写在 `source_status`（dict），与 source_health
    # 约定的「单一状态字符串」冲突（实测让状态判定抛 unhashable 而整条降级）。
    if not isinstance(context.get("source_status"), str):
        context.pop("source_status", None)
    # 字段名刻意不用 source_status：那是 source_health 约定的「单一状态字符串」，
    # 这里放的是逐子项字典，混用会让状态判定读到一个 dict（实测 unhashable 崩溃）。
    context["refresh_status"] = status
    context["producer"] = "x_sentiment_refresh.py"
    return context, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="刷新 X 情绪上下文（本地，不外发）")
    parser.add_argument("--x-note", default="", help="本轮 X 舆情摘要（由 agent 提供）")
    parser.add_argument("--query", action="append", default=[], dest="queries",
                        help="建议的 X 查询，可重复")
    parser.add_argument("--json", action="store_true", help="打印 JSON 结果")
    parser.add_argument("--output", type=Path, default=CONTEXT_PATH)
    args = parser.parse_args(argv)

    previous = {}
    if args.output.exists():
        try:
            previous = json.loads(args.output.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            previous = {}

    context, status = build_context(previous, args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, args.output)

    fg = context.get("fear_greed") or {}
    gm = context.get("global_market") or {}
    print(f"X情绪上下文已刷新 → {args.output}")
    print(f"  恐贪: {fg.get('value', '—')} ({fg.get('classification') or '—'}) [{status.get('fear_greed')}]")
    print(f"  BTC市占: {gm.get('btc_dominance', '—')}% · 总市值24h {gm.get('market_cap_change_24h_pct', '—')}% [{status.get('global_market')}]")
    print(f"  热门: {len(context.get('coingecko_trending') or [])} 条 [{status.get('coingecko_trending')}]")
    print(f"  X叙述: {status.get('x_note')}")
    if args.json:
        print(json.dumps(context, ensure_ascii=False, indent=2))
    # 全部子项都失败才报错，避免 cron 把「部分降级」当事故
    live = [v for v in status.values() if str(v).startswith("live")]
    return 0 if live else 2


if __name__ == "__main__":
    raise SystemExit(main())
