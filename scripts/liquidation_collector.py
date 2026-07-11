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
ORION_URL = "https://screener.orionterminal.com/api/screener?exchange=binance"
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


def _orion_current(row: dict) -> dict:
    """Normalize Orion's Binance futures snapshot to the collector contract."""
    tf1h = row.get("tf1h") if isinstance(row.get("tf1h"), dict) else {}
    return {
        "symbol": str(row.get("symbol") or ""),
        "oi": float(row.get("openInterest") or 0),
        "price": float(row.get("price") or row.get("markPrice") or 0),
        "oi_delta_pct": float(tf1h.get("oiChange") or 0),
        "price_delta_pct": float(tf1h.get("changePercent") or 0),
        "source": "Orion/Binance",
    }


def _fetch_orion_map() -> dict[str, dict]:
    payload = _fetch(ORION_URL, timeout=15)
    rows = payload.get("tickers") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("symbol") or "").upper(): row
        for row in rows
        if isinstance(row, dict) and row.get("symbol")
    }


def fetch_oi_and_price(symbol: str, orion_rows: dict[str, dict] | None = None) -> dict:
    # Orion exposes Binance's live futures OI/mark data in one request and is the
    # preferred public path on hosts where fapi TLS is unavailable.
    if orion_rows and symbol in orion_rows:
        current = _orion_current(orion_rows[symbol])
        if current.get("oi") and current.get("price"):
            return current
    oi_data = _fetch(f"{BASE}/fapi/v1/openInterest?symbol={symbol}", timeout=5)
    price_data = _fetch(f"{BASE}/fapi/v1/ticker/price?symbol={symbol}", timeout=5)
    result = {"symbol": symbol, "oi": 0, "price": 0, "source": "Binance Futures"}
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
    oi_delta_pct = float(current.get("oi_delta_pct")) if current.get("oi_delta_pct") is not None else ((oi_now - oi_prev) / oi_prev * 100 if oi_prev else 0)
    price_delta_pct = float(current.get("price_delta_pct")) if current.get("price_delta_pct") is not None else ((price_now - price_prev) / price_prev * 100 if price_prev else 0)

    if oi_delta_pct < -2 and price_delta_pct < -1: squeeze, detail = "多头爆仓", f"OI{oi_delta_pct:+.1f}% 价{price_delta_pct:+.1f}%→多杀多"
    elif oi_delta_pct < -2 and price_delta_pct > 1: squeeze, detail = "空头爆仓", f"OI{oi_delta_pct:+.1f}% 价{price_delta_pct:+.1f}%→轧空"
    elif oi_delta_pct < -1: squeeze, detail = "OI缩减", f"OI{oi_delta_pct:+.1f}%"
    elif oi_delta_pct > 5: squeeze, detail = "OI扩张", f"OI{oi_delta_pct:+.1f}%·拥挤"
    else: squeeze, detail = "正常", f"OI{oi_delta_pct:+.1f}%"

    # 决策：爆仓信号→提示方向；OI扩张→提示杠杆拥挤风险
    if "多头爆仓" in squeeze:
        verdict, action = "↓空方占优", "反弹不过前低做空/不接刀"
    elif "空头爆仓" in squeeze:
        verdict, action = "↑多方轧空", "回踩做多/追高慎"
    elif oi_delta_pct > 5:
        verdict, action = "⚠杠杆拥挤", "警惕插针清算"
    else:
        verdict, action = "○常态", "按结构交易"
    return {"symbol": symbol, "oi": oi_now, "price": price_now, "oi_delta_pct": round(oi_delta_pct, 2), "price_delta_pct": round(price_delta_pct, 2), "squeeze": squeeze, "detail": detail, "verdict": verdict, "action": action, "source": current.get("source", "unknown")}



def _overall_conclusion(results: list[dict]) -> tuple[str, bool]:
    valid = [r for r in results if r.get("status") not in ("api_error", "no_data")]
    if not valid:
        return "**数据源全部失败**，当前**不能判断清算压力**，禁止按‘无爆仓’处理", False
    if any("爆仓" in str(r.get("squeeze", "")) for r in valid):
        return "**检测到爆仓**，顺势跟随方向、**不接刀**", True
    if any("杠杆拥挤" in str(r.get("verdict", "")) for r in valid):
        return "**OI拥挤**，警惕**插针清算**", True
    return "无爆仓信号，市场常态", True


def main():
    now = datetime.now(TZ); ts = f"{now.year}年{now.month}月{now.day}日{now.hour:02d}：{now.minute:02d}"
    results = []
    orion_rows = _fetch_orion_map()
    for sym in SYMBOLS:
        current = fetch_oi_and_price(sym, orion_rows)
        if not current["oi"]: results.append({"symbol": sym, "status": "api_error"}); continue
        prev = load_prev(sym)
        analysis = analyze(sym, current, prev)
        results.append(analysis)
        save_snapshot(sym, {"oi": current["oi"], "price": current["price"], "ts": now.isoformat()})
    
    lines = [f"💥 清算压力 {ts}"]
    lines.append("")
    lines.append("| 品种 | 现价 | OI | OI变化 | 价格变化 | 清算信号 | 数据源 | 决策 |")
    lines.append("|:----|:----:|:----:|:----:|:----:|:----|:----|:----|")

    has_squeeze = False
    for r in results:
        if r.get("status") == "api_error": lines.append(f"| {r['symbol']} | - | - | - | - | 获取失败 | - | - |"); continue
        if r.get("status") == "no_data": lines.append(f"| {r['symbol']} | - | - | - | - | 等待数据 | - | - |"); continue
        oi_m = r["oi"] / 1e6
        squeeze_icon = "🟡" if "爆仓" in r.get("squeeze", "") else ""
        oi_dir = "📈" if r["oi_delta_pct"] > 0 else "📉" if r["oi_delta_pct"] < 0 else "➡️"
        px_dir = "📈" if r["price_delta_pct"] > 0 else "📉" if r["price_delta_pct"] < 0 else "➡️"
        lines.append(f"| {r['symbol']} | ${r['price']:,.1f} | {oi_m:.2f}M币 | {oi_dir}{r['oi_delta_pct']:+.1f}% | {px_dir}{r['price_delta_pct']:+.1f}% | {squeeze_icon}{r['squeeze']} | {r.get('source','-')} | {r.get('verdict','○')} |")
        if "爆仓" in r.get("squeeze", ""): has_squeeze = True

    lines.append("")
    lines.append("| 方向 | 触发条件 | 动作 |")
    lines.append("|:---:|:----|:----|")
    for r in results:
        if r.get("status") in ("api_error", "no_data"): continue
        lines.append(f"| {r.get('verdict','○')} | {r.get('detail','')} | {r.get('action','按结构交易')} |")

    if has_squeeze:
        lines.append("")
        for r in results:
            if "爆仓" in r.get("squeeze", ""): lines.append(f"⚠ {r['symbol']}: {r['detail']} → {r.get('action','')}")

    # 总体结论：数据全失效时不得伪装成“市场常态”。
    concl, data_ok = _overall_conclusion(results)
    lines.append("")
    lines.append(f"**总体结论**: {concl}。")

    output = "\n".join(lines)
    if not data_ok:
        print(output)
        return 1
    if has_squeeze:
        print(output)
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from telegram_reliable import push_tg_rich
            push_tg_rich("telegram:-1003733144325:846", output)
        except Exception as _te:
            print(f"⚠ 清算压力RichMarkdown推送失败: {_te}", file=sys.stderr)
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
