#!/usr/bin/env python3
"""Deribit Options Collector v1.0 — 加密期权持仓/偏斜采集
取 BTC/ETH 期权总 OI、Call/Put 比、Max Pain、关键行权价集中度
免费 · 无需 API Key · Deribit 公开 API

用法:
    python scripts/deribit_options.py                 # 摘要
    python scripts/deribit_options.py --line           # 单行（嵌入分析卡）
    python scripts/deribit_options.py --full           # 完整JSON
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from datetime import datetime, timedelta
import urllib.request
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import trading_system as ts

CACHE_FILE = ts.DATA_DIR / "deribit_options.json"
CACHE_MINUTES = 15
BASE = "https://www.deribit.com/api/v2/public"


def _api(path: str) -> dict:
    url = f"{BASE}/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_options() -> dict:
    results = {}
    for coin in ["BTC", "ETH"]:
        try:
            # 获取未到期期权汇总
            summary = _api(f"get_book_summary_by_currency?currency={coin}&kind=option")
            instruments = summary.get("result", [])

            total_oi_usd = 0.0
            call_oi_usd = 0.0
            put_oi_usd = 0.0
            strike_oi = {}  # strike -> {call_oi, put_oi}

            for inst in instruments:
                name = inst.get("instrument_name", "")
                oi = float(inst.get("open_interest", 0) or 0)
                underlying = float(inst.get("underlying_price", 0) or 0)
                # 近似 USD：合约数 × 标的价格（实际应乘 mark_price，但 mark 在 summary 中单位不一）
                oi_notional = oi * underlying if underlying > 0 else 0

                # 提取行权价
                parts = name.split("-")
                strike = 0
                if len(parts) >= 4:
                    try:
                        strike = int(parts[2])
                    except ValueError:
                        pass

                if strike > 0:
                    if strike not in strike_oi:
                        strike_oi[strike] = {"call_oi": 0.0, "put_oi": 0.0, "call_notional": 0.0, "put_notional": 0.0, "expiry": parts[1]}

                    if name.endswith("-C"):
                        strike_oi[strike]["call_oi"] += oi
                        strike_oi[strike]["call_notional"] += oi_notional
                        call_oi_usd += oi_notional
                    elif name.endswith("-P"):
                        strike_oi[strike]["put_oi"] += oi
                        strike_oi[strike]["put_notional"] += oi_notional
                        put_oi_usd += oi_notional

                total_oi_usd += oi_notional

            # 寻找 Max Pain（OI 最大的行权价）
            max_pain_strike = 0
            max_pain_oi = 0
            for strike, data in strike_oi.items():
                total = data["call_oi"] + data["put_oi"]
                if total > max_pain_oi:
                    max_pain_oi = total
                    max_pain_strike = strike

            # Top 3 行权价集中度
            top_strikes = sorted(strike_oi.items(), key=lambda x: x[1]["call_oi"] + x[1]["put_oi"], reverse=True)[:3]

            # Call/Put 比率
            cp_ratio = call_oi_usd / put_oi_usd if put_oi_usd > 0 else 0

            results[coin] = {
                "total_oi_usd": round(total_oi_usd, 0),
                "call_oi_usd": round(call_oi_usd, 0),
                "put_oi_usd": round(put_oi_usd, 0),
                "cp_ratio": round(cp_ratio, 2),
                "max_pain": max_pain_strike,
                "max_pain_oi": round(max_pain_oi, 1),
                "options_count": len(instruments),
                "top_strikes": [
                    {"strike": s, "expiry": d["expiry"], "call_oi": round(d["call_oi"], 1), "put_oi": round(d["put_oi"], 1)}
                    for s, d in top_strikes
                ],
            }

        except Exception as e:
            results[f"error_{coin}"] = str(e)

    return results


def line_summary(data: dict) -> str:
    parts = []
    for coin in ["BTC", "ETH"]:
        d = data.get(coin, {})
        if not d or "total_oi_usd" not in d:
            continue
        cp = d["cp_ratio"]
        signal = "偏多" if cp > 1.5 else "偏空" if cp < 0.7 else "中性"
        mp = d.get("max_pain", "?")
        total_m = d["total_oi_usd"] / 1_000_000
        parts.append(f"{coin}OI${total_m:.0f}M C/P={cp} {signal} MaxPain={mp}")
    return "期权: " + " | ".join(parts) if parts else "期权: 取数失败"


def full_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _load_cache():
    if not CACHE_FILE.exists():
        return None
    try:
        cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        ts_str = cached.get("_fetched_at", "")
        if ts_str and datetime.now() - datetime.fromisoformat(ts_str) < timedelta(minutes=CACHE_MINUTES):
            return cached
    except Exception:
        pass
    return None


def _save_cache(data: dict):
    data["_fetched_at"] = datetime.now().isoformat()
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")


def _print_table(data: dict):
    """表格化输出期权数据"""
    lines = []
    for coin in ["BTC", "ETH"]:
        d = data.get(coin, {})
        if not d or "total_oi_usd" not in d:
            continue
        total_b = d['total_oi_usd'] / 1e9
        call_m = d['call_oi_usd'] / 1e6
        put_m = d['put_oi_usd'] / 1e6
        cp = d['cp_ratio']
        signal = "偏多" if cp > 1.5 else "偏空" if cp < 0.7 else "中性"
        mp = d.get("max_pain", "?")
        lines.append(f"Deribit期权 {coin}")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 总OI | ${total_b:.2f}B |")
        lines.append(f"| Call OI | ${call_m:.0f}M |")
        lines.append(f"| Put OI | ${put_m:.0f}M |")
        lines.append(f"| C/P比 | {cp} {signal} |")
        lines.append(f"| MaxPain | ${mp} |")
        lines.append(f"| 合约数 | {d['options_count']} |")
        top = d.get("top_strikes", [])[:3]
        if top:
            lines.append("")
            lines.append("| 行权价 | Call OI | Put OI | 到期 |")
            lines.append("|--------|---------|--------|------|")
            for t in top:
                lines.append(f"| {t['strike']} | {t['call_oi']} | {t['put_oi']} | {t['expiry']} |")
        lines.append("")
    print("\n".join(lines))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Deribit 期权数据采集")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--line", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not args.force:
        cached = _load_cache()
        if cached:
            if args.full:
                print(full_json(cached))
            elif args.line:
                print(line_summary(cached))
            else:
                _print_table(cached)
            sys.exit(0)

    print("拉取 Deribit 期权数据...", file=sys.stderr)
    data = fetch_options()
    _save_cache(data)

    if args.full:
        print(full_json(data))
    elif args.line:
        print(line_summary(data))
    else:
        _print_table(data)
