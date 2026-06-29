#!/usr/bin/env python3
"""
DeFiLlama 稳定币供应监控 v1.0
免费API: https://stablecoins.llama.fi/stablecoins?includePrices=true
追踪 USDT/USDC/DAI 流通量变化 → 加密市场资金流入/流出先行指标
"""
import json, sys, os, time
from datetime import datetime, timezone, timedelta
import urllib.request
from pathlib import Path

TZ = timezone(timedelta(hours=8))
UA = "Hermes/1.0"
API = "https://stablecoins.llama.fi/stablecoins?includePrices=true"
DATA_DIR = os.path.expanduser("~/AppData/Local/hermes/data")
os.makedirs(DATA_DIR, exist_ok=True)

WATCH = ["USDT", "USDC", "DAI", "USDe"]


def _fetch(url, timeout=15):
    """代理回退"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        pass
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with opener.open(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def load_prev():
    fp = os.path.join(DATA_DIR, "stablecoin_snapshot.json")
    try:
        with open(fp) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_snapshot(data):
    fp = os.path.join(DATA_DIR, "stablecoin_snapshot.json")
    with open(fp, "w") as f:
        json.dump(data, f)


def main():
    now = datetime.now(TZ)
    ts = now.strftime("%Y-%m-%d %H:%M BJT")
    
    data = _fetch(API)
    if not data:
        print(f"稳定币 {ts} | API获取失败")
        return 1
    
    pegged = data.get("peggedAssets", [])
    prev = load_prev()
    
    # 提取关注币种
    current = {}
    for p in pegged:
        sym = p.get("symbol", "")
        if sym in WATCH:
            circ = p.get("circulating", {})
            if isinstance(circ, dict):
                circ = circ.get("peggedUSD", 0)
            current[sym] = round(circ, 0)
    
    # 计算变化
    prev_data = prev.get("data", {})
    changes = {}
    total_now = 0
    total_prev = prev.get("total", 0)
    
    for sym in WATCH:
        val = current.get(sym, 0)
        total_now += val
        pv = prev_data.get(sym, val)
        delta = val - pv
        pct = (delta / pv * 100) if pv else 0
        changes[sym] = {"now": val, "prev": pv, "delta": delta, "pct": round(pct, 2)}
    
    total_delta = total_now - total_prev
    
    # 输出
    total_b = total_now / 1e9
    delta_b = total_delta / 1e9
    
    direction = "↑流入" if total_delta > 0 else "↓流出" if total_delta < 0 else "→持平"
    lines = [f"稳定币 {ts} | 总市值${total_b:.1f}B {direction}{delta_b:+.1f}B"]
    
    for sym in WATCH:
        c = changes.get(sym, {})
        val_b = c.get("now", 0) / 1e9
        delta_m = c.get("delta", 0) / 1e6
        pct = c.get("pct", 0)
        arrow = "↑" if c.get("delta", 0) > 0 else "↓" if c.get("delta", 0) < 0 else "→"
        lines.append(f"  {sym}: ${val_b:.1f}B {arrow}{delta_m:+.0f}M({pct:+.1f}%)")
    
    output = "\n".join(lines)
    
    # 去重：显著变化(>100M)始终发送，否则抑制
    significant = abs(delta_b) > 0.1  # 100M
    if significant:
        print(output)
    else:
        try:
            from alert_dedup import dedup_wrapper
            dedup_wrapper("stablecoin", output, force_seconds=3600)
        except ImportError:
            print(output)
    
    # 保存快照
    save_snapshot({"total": total_now, "data": current, "ts": now.isoformat()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
