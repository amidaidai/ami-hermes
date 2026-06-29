#!/usr/bin/env python3
"""
棠溪 · Dune Analytics 链上数据采集器 v1.1 — 表格化输出
"""
import json, time, os, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DUNE_KEY = os.environ.get("DUNE_API_KEY", "") or "43Fsk9VjjoU0G9pZzeDCZCMehXeB4iWx"
DUNE_BASE = "https://api.dune.com/api/v1"
TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
CACHE_FILE = ROOT / "data" / "dune_cache.json"
CACHE_TTL = 900

QUERIES = {"btc_flow": 3485694, "cex_netflow": 1621987, "stablecoin_supply": 4159727}


def _dune_request(path: str) -> dict:
    url = f"{DUNE_BASE}/{path}"
    req = urllib.request.Request(url, headers={"x-dune-api-key": DUNE_KEY})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _get_query_results(query_id: int, limit: int = 10) -> dict:
    try:
        data = _dune_request(f"query/{query_id}/results?limit={limit}")
        return data.get("result", {}).get("rows", [])
    except Exception as e:
        return {"_error": str(e)[:150]}


def get_btc_flow() -> dict:
    rows = _get_query_results(QUERIES["btc_flow"], limit=6)
    if isinstance(rows, dict) and "_error" in rows: return rows
    result = {"source": "Dune #3485694", "type": "BTC on-chain flow"}
    if rows:
        latest = rows[-1]
        result["period"] = latest.get("formatted_time", "")
        result["inflow_btc"] = latest.get("inflow")
        result["inflow_usd"] = latest.get("inflow_usd")
        if len(rows) >= 2:
            prev_inflow = rows[-2].get("inflow", 0) or 0
            curr_inflow = latest.get("inflow", 0) or 0
            result["trend"] = "↑ 流入加速" if curr_inflow > prev_inflow * 1.1 else "↓ 流入减速" if curr_inflow < prev_inflow * 0.9 else "→ 稳定"
        result["ok"] = True
    else: result["ok"] = False
    return result


def get_cex_netflow() -> dict:
    rows = _get_query_results(QUERIES["cex_netflow"], limit=15)
    if isinstance(rows, dict) and "_error" in rows: return rows
    result = {"source": "Dune #1621987", "type": "CEX netflow"}
    if rows:
        total_netflow, exchanges = 0, []
        for r in rows:
            nf = r.get("netflow", 0) or 0
            total_netflow += nf
            exchanges.append({"exchange": r.get("exchange", ""), "inflow": r.get("inflow"), "netflow": nf})
        result["total_netflow"] = total_netflow
        result["exchanges"] = exchanges[:8]
        result["signal"] = "⚠ 净流入交易所（潜在抛压）" if total_netflow > 0 else "✅ 净流出交易所（积累信号）"
        result["ok"] = True
    else: result["ok"] = False
    return result


def get_stablecoin_supply() -> dict:
    rows = _get_query_results(QUERIES["stablecoin_supply"], limit=5)
    if isinstance(rows, dict) and "_error" in rows:
        return {"ok": False, "source": "Dune #4159727", "_note": "query may not exist"}
    result = {"source": "Dune #4159727", "type": "Stablecoin supply"}
    if rows: result["rows"], result["ok"] = rows[:5], True
    else: result["ok"] = False
    return result


def gather_onchain() -> dict:
    cache = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if time.time() - cache.get("ts", 0) < CACHE_TTL:
                return cache.get("data", {})
        except Exception: pass
    result = {"fetched_at": datetime.now(TZ).isoformat(timespec="seconds")}
    for name, fn in [("btc_flow", get_btc_flow), ("cex_netflow", get_cex_netflow)]:
        try: result[name] = fn(); time.sleep(0.5)
        except Exception as e: result[name] = {"ok": False, "_error": str(e)[:100]}
    try: time.sleep(0.5); result["stablecoin"] = get_stablecoin_supply()
    except Exception: result["stablecoin"] = {"ok": False}
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps({"ts": time.time(), "data": result}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return result


def get_onchain_summary_line() -> str:
    data = gather_onchain(); parts = []
    btc = data.get("btc_flow", {})
    if btc.get("ok"): parts.append(f"BTC链上流入: {btc.get('inflow_btc', 0) or 0:.1f} BTC ({btc.get('trend', '')})")
    cex = data.get("cex_netflow", {})
    if cex.get("ok"): parts.append(f"CEX净流: {cex.get('total_netflow', 0) or 0:+,.0f} ({cex.get('signal', '')})")
    return "链上: " + " · ".join(parts) if parts else "链上: 数据不可用"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--line":
        print(get_onchain_summary_line())
    elif len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps(gather_onchain(), indent=2, ensure_ascii=False, default=str))
    else:
        data = gather_onchain()
        now = datetime.now(TZ)
        ts = now.strftime("%Y-%m-%d %H:%M BJT")
        lines = [f"Dune链上 {ts}"]
        lines.append("")
        
        btc = data.get("btc_flow", {})
        if btc.get("ok"):
            lines.append("| BTC链上流 | 数值 |")
            lines.append("|-----------|------|")
            lines.append(f"| 月度流入 | {btc.get('inflow_btc', 0):.1f} BTC |")
            lines.append(f"| 趋势 | {btc.get('trend', '?')} |")
            lines.append("")
        
        cex = data.get("cex_netflow", {})
        if cex.get("ok"):
            nf = cex.get("total_netflow", 0) or 0
            lines.append("| CEX净流量 | " + f"{'${:+,.0f}'.format(nf)}" + " |")
            lines.append("| 信号 | " + cex.get("signal", "") + " |")
            lines.append("")
            ex_list = cex.get("exchanges", [])[:5]
            if ex_list:
                lines.append("| 交易所 | 净流量 |")
                lines.append("|--------|--------|")
                for ex in ex_list:
                    nf_ex = ex.get("netflow", 0) or 0
                    lines.append("| " + ex.get("exchange", "?") + " | " + f"{'${:+,.0f}'.format(nf_ex)}" + " |")
        
        print("\n".join(lines))
