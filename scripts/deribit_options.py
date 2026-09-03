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
_stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(_stdout_reconfigure):
    _stdout_reconfigure(encoding="utf-8", errors="replace")
_stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if callable(_stderr_reconfigure):
    _stderr_reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import trading_system as ts
from source_contract import write_source_artifact

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
            underlying = 0.0

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

            # Max Pain 是“总持仓量最大行权价”之外的另一件事：
            # 应取使所有 Call/Put 买方到期赔付最小的结算价。
            # 旧逻辑把 max OI strike 冒充 Max Pain，容易产生数量级错误。
            strikes = sorted(strike_oi)
            pain_by_settlement = {}
            for settlement in strikes:
                pain = 0.0
                for strike, oi_data in strike_oi.items():
                    pain += max(settlement - strike, 0) * oi_data["call_oi"]
                    pain += max(strike - settlement, 0) * oi_data["put_oi"]
                pain_by_settlement[settlement] = pain
            max_pain_strike = sorted(pain_by_settlement, key=lambda s: pain_by_settlement[s])[0] if pain_by_settlement else 0
            max_pain_valid = bool(
                max_pain_strike and underlying > 0
                and abs(max_pain_strike - underlying) / underlying <= 0.15
            )

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
                "max_pain_valid": max_pain_valid,
                "max_pain_method": "min_total_settlement_payout",
                "max_oi_strike": max(strike_oi, key=lambda s: strike_oi[s]["call_oi"] + strike_oi[s]["put_oi"]) if strike_oi else 0,
                "underlying_price": underlying,
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
        mp = d.get("max_pain") if d.get("max_pain_valid") else "—"
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
    fetched_at = datetime.now()
    data["_fetched_at"] = fetched_at.isoformat()
    valid = any(
        isinstance(data.get(coin), dict) and "total_oi_usd" in data[coin]
        for coin in ("BTC", "ETH")
    )
    write_source_artifact(
        str(CACHE_FILE),
        "deribit_options",
        data,
        status="live" if valid else "unavailable",
        captured_at=fetched_at,
        symbol="BTC/ETH",
        error=None if valid else "empty_payload",
    )


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
        signal = "🟢偏多(看涨需求强)" if cp > 1.5 else "🔴偏空(看跌保护重)" if cp < 0.7 else "⚪中性"
        mp = d.get("max_pain") if d.get("max_pain_valid") else "—"
        # 决策：MaxPain 通常价格磁吸；C/P高=情绪偏多但需防过热
        verdict = f"γ区上方·偏{cp:.1f}" if cp > 1.1 else f"γ区下方·偏{cp:.1f}" if cp < 0.9 else "γ中性"
        lines.append(f"📊 Deribit期权 {coin}")
        lines.append("")
        lines.append("| 指标 | 数值 | 信号 |")
        lines.append("|:----|:----:|:----|")
        lines.append(f"| 总OI | ${total_b:.2f}B | {signal} |")
        lines.append(f"| Call OI | ${call_m:.0f}M | — |")
        lines.append(f"| Put OI | ${put_m:.0f}M | — |")
        lines.append(f"| C/P比 | {cp} | {verdict} |")
        lines.append(f"| MaxPain | ${mp} | 🧲价格磁吸位 |")
        lines.append(f"| 合约数 | {d['options_count']} | — |")
        top = d.get("top_strikes", [])[:3]
        if top:
            lines.append("")
            lines.append("| 行权价 | Call OI | Put OI | 到期 |")
            lines.append("|--------|---------|--------|------|")
            for t in top:
                lines.append(f"| {t['strike']} | {t['call_oi']} | {t['put_oi']} | {t['expiry']} |")
        lines.append("")

    # 总体结论（取BTC为主）
    btc = data.get("BTC", {})
    if btc and "cp_ratio" in btc:
        cp = btc["cp_ratio"]
        concl = f"BTC期权C/P={cp}，**{'情绪偏多但防过热回踩' if cp>1.5 else '看跌保护重、偏空' if cp<0.7 else '多空均衡'}**"
    else:
        concl = "期权数据不足"
    lines.append(f"**总体结论**: {concl}。")
    output = "\n".join(lines)
    print(output)
    # v9.8: 加 dedup 限频——内容变化或每1小时强制推一次，避免每30分无脑轰炸
    try:
        should_send = __import__("alert_dedup").should_send
        if should_send("deribit_options", output, force_every_seconds=3600):
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from telegram_reliable import push_tg_rich
            push_tg_rich("telegram:-1003733144325:846", output)
    except ImportError:
        # alert_dedup 不可用时退化为直接推（不丢报告）
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from telegram_reliable import push_tg_rich
            push_tg_rich("telegram:-1003733144325:846", output)
        except Exception as _te:
            print(f"⚠ Deribit期权RichMarkdown推送失败: {_te}", file=sys.stderr)
    except Exception as _te:
        print(f"⚠ Deribit期权RichMarkdown推送失败: {_te}", file=sys.stderr)


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
