#!/usr/bin/env python3
"""
棠溪 · Dune Analytics 链上数据采集器 v1.0
免费 API Key · 40req/min 限速

查询:
  3485694 — BTC 全网流入/流出（月度）
  1621987 — CEX 交易所净流入流出
  4159727 — 稳定币供应量 (USDT/USDC/DAI)
  (可扩展更多公开查询)

输出: 链上信号 → 交易所余额变化 / 稳定币供应 / 鲸鱼动向
"""

import json, time, os, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

DUNE_KEY = os.environ.get("DUNE_API_KEY", "") or "43Fsk9VjjoU0G9pZzeDCZCMehXeB4iWx"
DUNE_BASE = "https://api.dune.com/api/v1"
TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
CACHE_FILE = ROOT / "data" / "dune_cache.json"
CACHE_TTL = 900  # 15分钟缓存

# 公开查询 ID
QUERIES = {
    "btc_flow": 3485694,      # BTC inflow/outflow monthly
    "cex_netflow": 1621987,   # CEX exchange netflow
    "stablecoin_supply": 4159727,  # Stablecoin supply (may not exist, fallback)
}


def _dune_request(path: str) -> dict:
    """Dune API 请求"""
    url = f"{DUNE_BASE}/{path}"
    headers = {"x-dune-api-key": DUNE_KEY}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _get_query_results(query_id: int, limit: int = 10) -> dict:
    """获取 Dune 查询结果（从缓存读取最新执行）"""
    try:
        # 先获取最新执行结果
        data = _dune_request(f"query/{query_id}/results?limit={limit}")
        return data.get("result", {}).get("rows", [])
    except Exception as e:
        return {"_error": str(e)[:150]}


def get_btc_flow() -> dict:
    """BTC 全网流入流出（月度）"""
    rows = _get_query_results(QUERIES["btc_flow"], limit=6)
    if isinstance(rows, dict) and "_error" in rows:
        return rows
    # 提取最近月份数据
    result = {"source": "Dune #3485694", "type": "BTC on-chain flow"}
    if rows:
        latest = rows[-1]
        result["period"] = latest.get("formatted_time", "")
        result["inflow_btc"] = latest.get("inflow")
        result["inflow_usd"] = latest.get("inflow_usd")
        # 趋势：比较最近两期
        if len(rows) >= 2:
            prev_inflow = rows[-2].get("inflow", 0) or 0
            curr_inflow = latest.get("inflow", 0) or 0
            if curr_inflow > prev_inflow * 1.1:
                result["trend"] = "↑ 流入加速"
            elif curr_inflow < prev_inflow * 0.9:
                result["trend"] = "↓ 流入减速"
            else:
                result["trend"] = "→ 稳定"
        result["ok"] = True
    else:
        result["ok"] = False
    return result


def get_cex_netflow() -> dict:
    """CEX 交易所净流入流出"""
    rows = _get_query_results(QUERIES["cex_netflow"], limit=15)
    if isinstance(rows, dict) and "_error" in rows:
        return rows
    result = {"source": "Dune #1621987", "type": "CEX netflow"}
    if rows:
        # 聚合所有交易所净流量
        total_netflow = 0
        exchanges = []
        for r in rows:
            nf = r.get("netflow", 0) or 0
            total_netflow += nf
            exchanges.append({
                "exchange": r.get("exchange", ""),
                "inflow": r.get("inflow"),
                "netflow": nf,
            })
        result["total_netflow"] = total_netflow
        result["exchanges"] = exchanges[:8]
        if total_netflow > 0:
            result["signal"] = "⚠ 净流入交易所（潜在抛压）"
        else:
            result["signal"] = "✅ 净流出交易所（积累信号）"
        result["ok"] = True
    else:
        result["ok"] = False
    return result


def get_stablecoin_supply() -> dict:
    """稳定币供应量"""
    rows = _get_query_results(QUERIES["stablecoin_supply"], limit=5)
    if isinstance(rows, dict) and "_error" in rows:
        # 静默失败 - 查询可能不存在
        return {"ok": False, "source": "Dune #4159727", "_note": "query may not exist"}
    result = {"source": "Dune #4159727", "type": "Stablecoin supply"}
    if rows:
        result["rows"] = rows[:5]
        result["ok"] = True
    else:
        result["ok"] = False
    return result


def gather_onchain() -> dict:
    """统一采集链上数据（带缓存）"""
    # 读缓存
    cache = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if time.time() - cache.get("ts", 0) < CACHE_TTL:
                return cache.get("data", {})
        except Exception:
            pass

    result = {
        "fetched_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }

    # 逐个采集（避免同时触发限速）
    for name, fn in [
        ("btc_flow", get_btc_flow),
        ("cex_netflow", get_cex_netflow),
    ]:
        try:
            result[name] = fn()
            time.sleep(0.5)  # 避免撞限速
        except Exception as e:
            result[name] = {"ok": False, "_error": str(e)[:100]}

    # 稳定币供应（可选，失败不阻塞）
    try:
        time.sleep(0.5)
        result["stablecoin"] = get_stablecoin_supply()
    except Exception:
        result["stablecoin"] = {"ok": False}

    # 写缓存
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps({"ts": time.time(), "data": result}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return result


def get_onchain_summary_line() -> str:
    """生成链上数据摘要行（用于分析卡）"""
    data = gather_onchain()
    parts = []

    btc = data.get("btc_flow", {})
    if btc.get("ok"):
        inflow = btc.get("inflow_btc", 0) or 0
        trend = btc.get("trend", "")
        parts.append(f"BTC链上流入: {inflow:.1f} BTC ({trend})")

    cex = data.get("cex_netflow", {})
    if cex.get("ok"):
        nf = cex.get("total_netflow", 0) or 0
        signal = cex.get("signal", "")
        parts.append(f"CEX净流: {nf:+,.0f} ({signal})")

    if parts:
        return "链上: " + " · ".join(parts)
    return "链上: 数据不可用"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--line":
        print(get_onchain_summary_line())
    elif len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps(gather_onchain(), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(gather_onchain(), indent=2, ensure_ascii=False, default=str))
