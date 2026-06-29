#!/usr/bin/env python3
"""
爆仓/清算压力监控 v1.2 — 表格化输出
"""
import json, sys, os, time
from datetime import datetime, timezone, timedelta
import urllib.request

TZ = timezone(timedelta(hours=8))
UA = "Hermes/1.0"
BASE = "https://fapi.binance.com"
DATA_DIR = os.path.expanduser("~/AppData/Local/hermes/data")
os.makedirs(DATA_DIR, exist_ok=True)
SYMBOLS = ["BTCUSDT", "ETHUSDT"]


def _fetch(url, timeout=10):
    for ph in [None, {}]:
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler(ph)) if ph is not None else urllib.request.build_opener()
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:
            continue
    return None


def fetch_oi_and_price(symbol: str) -> dict:
    oi_data = _fetch(f"{BASE}/fapi/v1/openInterest?symbol={symbol}", timeout=5)
    price_data = _fetch(f"{BASE}/fapi/v1/ticker/price?symbol={symbol}", timeout=5)
    result = {"symbol": symbol, "oi": 0, "price": 0}
    if oi_data: result["oi"] = float(oi_data.get("openInterest", 0))
    if price_data: result["price"] = float(price_data.get("price", 0))
    return result


def load_prev(symbol: str) -> dict:
    fp = os.path.join(DATA_DIR, f"oi_snapshot_{symbol}.json")
    try:
        with open(fp) as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_snapshot(symbol: str, data: dict):
    with open(os.path.join(DATA_DIR, f"oi_snapshot_{symbol}.json"), "w") as f:
        json.dump(data, f)


def analyze(symbol: str, current: dict, prev: dict) -> dict:
    oi_now, price_now = current.get("oi", 0), current.get("price", 0)
    oi_prev, price_prev = prev.get("oi", oi_now), prev.get("price", price_now)
    if not oi_now: return {"symbol": symbol, "status": "no_data"}
    oi_delta_pct = (oi_now - oi_prev) / oi_prev * 100 if oi_prev else 0
    price_delta_pct = (price_now - price_prev) / price_prev * 100 if price_prev else 0
    
    if oi_delta_pct < -2 and price_delta_pct < -1: squeeze, detail = "多头爆仓", f"OI{oi_delta_pct:+.1f}% 价{price_delta_pct:+.1f}%→多杀多"
    elif oi_delta_pct < -2 and price_delta_pct > 1: squeeze, detail = "空头爆仓", f"OI{oi_delta_pct:+.1f}% 价{price_delta_pct:+.1f}%→轧空"
    elif oi_delta_pct < -1: squeeze, detail = "OI缩减", f"OI{oi_delta_pct:+.1f}%"
    elif oi_delta_pct > 5: squeeze, detail = "OI扩张", f"OI{oi_delta_pct:+.1f}%·拥挤"
    else: squeeze, detail = "正常", f"OI{oi_delta_pct:+.1f}%"
    
    return {"symbol": symbol, "oi": oi_now, "price": price_now, "oi_delta_pct": round(oi_delta_pct, 2), "price_delta_pct": round(price_delta_pct, 2), "squeeze": squeeze, "detail": detail}


def main():
    now = datetime.now(TZ); ts = now.strftime("%Y-%m-%d %H:%M BJT")
    results = []
    for sym in SYMBOLS:
        current = fetch_oi_and_price(sym)
        if not current["oi"]: results.append({"symbol": sym, "status": "api_error"}); continue
        prev = load_prev(sym)
        analysis = analyze(sym, current, prev)
        results.append(analysis)
        save_snapshot(sym, {"oi": current["oi"], "price": current["price"], "ts": now.isoformat()})
    
    lines = [f"清算压力 {ts}"]
    lines.append("")
    lines.append("| 品种 | 现价 | OI | OI变化 | 清算信号 |")
    lines.append("|------|------|-----|--------|----------|")
    
    has_squeeze = False
    for r in results:
        if r.get("status") == "api_error": lines.append(f"| {r['symbol']} | - | - | - | 获取失败 |"); continue
        if r.get("status") == "no_data": lines.append(f"| {r['symbol']} | - | - | - | 等待数据 |"); continue
        oi_m = r["oi"] / 1e6
        squeeze_icon = "🟡" if "爆仓" in r.get("squeeze", "") else ""
        lines.append(f"| {r['symbol']} | ${r['price']:,.1f} | ${oi_m:.1f}M | {r['oi_delta_pct']:+.1f}% | {squeeze_icon}{r['squeeze']} |")
        if "爆仓" in r.get("squeeze", ""): has_squeeze = True
    
    if has_squeeze:
        lines.append("")
        for r in results:
            if "爆仓" in r.get("squeeze", ""): lines.append(f"{r['symbol']}: {r['detail']}")
    
    output = "\n".join(lines)
    if has_squeeze: print(output)
    else:
        try:
            from alert_dedup import dedup_wrapper
            dedup_wrapper("liquidation", output, force_seconds=1800)
        except ImportError:
            print(output)
    
    # 保存 — 双落盘
    result_json = {"ts": now.isoformat(), "results": results}
    
    with open(os.path.join(DATA_DIR, "liquidation_pressure.json"), "w") as f:
        json.dump(result_json, f, ensure_ascii=False)
    
    # 落盘2: 项目data（cron_read 读取）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    proj_data = os.path.join(script_dir, "..", "data")
    os.makedirs(proj_data, exist_ok=True)
    with open(os.path.join(proj_data, "liquidation_pressure.json"), "w") as f:
        json.dump(result_json, f, ensure_ascii=False)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
