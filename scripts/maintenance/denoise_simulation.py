#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""降噪前后对比模拟 — 用真实 config 的 8 个位跑同一条价格路径，数推送条数。

这是"关键位不能太频繁"这条需求的量化验收：
  旧逻辑 = 每位 30min 冷却、全位推送（enabled=false 时无位可推，故同时给出"若 8 位全开"的旧口径）
  新逻辑 = push_tier 分级 + 同key冷却 + 幅度门 + 迟滞带 + 全局限流 + 同轮聚合
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("kg", ROOT / "scripts" / "keylevel_guard.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

cfg = json.loads((ROOT / "data" / "keylevels_config.json").read_text(encoding="utf-8"))
BLOCK = cfg["symbols"]["BTCUSDT"]
print("真实配置的位：")
for lv in BLOCK["levels"]:
    print(f"   {lv['name']:18s} {lv['price']:>9} enabled={lv.get('enabled')} tier={G.level_push_tier(lv) or 'silent'}")

# ── 构造一条真实感的 BTC 价格路径：围绕价值区密集带上下扫，含贴线抖动 ──
# 77240-77800 正是 8 个位聚集区（VAH 77310/DO 77400/M-VWAP 77520/nPOC 77800/POC 76600/VAL 76450）
path = []
p = 77250.0
def seg(start, end, steps):
    for i in range(steps):
        path.append(start + (end - start) * (i + 1) / steps)
seg(77250, 77360, 12)      # 上穿 VAH 区
seg(77360, 77290, 8)       # 回落贴线抖动
seg(77290, 77335, 5)       # 再上穿（抖动）
seg(77335, 77260, 7)       # 又回落
seg(77260, 77460, 16)      # 连续上穿 DO/M-VWAP
seg(77460, 77300, 14)      # 大幅回落，下穿多个位
seg(77300, 77560, 20)      # 再上冲
seg(77560, 77180, 24)      # 大跌横扫
seg(77180, 77300, 10)

POLL = 0.5  # 守卫轮询间隔（秒）
NOW0 = 1_760_000_000.0

def run_new(block):
    """新逻辑：走生产同一套 evaluate_symbol + 全局限流 + 同轮聚合。"""
    trig = {}
    recent = []
    pushes = []
    digest = []
    last = None
    for i, price in enumerate(path):
        now = NOW0 + i * POLL
        d, cands = G.evaluate_symbol("BTCUSDT", block, last, price, now, trig)
        digest.extend(d)
        if cands:
            ok, reason, recent = G.global_rate_limit_ok(recent, now)
            if ok:
                pushes.append({"t": i, "price": price, "hits": [c["name"] for c in cands]})
                recent.append(now)
                for c in cands:
                    trig[c["key"]] = {**trig.get(c["key"], {}), "dir": c["cross"],
                                      "armed": False, "anchor_price": price,
                                      "cool_until": now + float(c["policy"]["cooldown"])}
            else:
                for c in cands:
                    digest.append({"reason": reason, "level": c["name"]})
        last = price
    return pushes, digest

def run_old_30min_allpush(block):
    """旧口径：8 位全推、每位独立 30min 冷却、无幅度门无迟滞无全局限制。"""
    trig = {}
    pushes = []
    last = None
    for i, price in enumerate(path):
        now = NOW0 + i * POLL
        for lv in block["levels"]:
            if lv.get("enabled", True) is False:
                continue
            lvl = float(lv["price"])
            crossed = None
            if last is not None:
                if last < lvl <= price: crossed = "up"
                elif last >= lvl > price: crossed = "down"
            if not crossed: continue
            key = lv["name"]
            if now < float(trig.get(key, {}).get("cool_until", 0.0)): continue
            pushes.append({"t": i, "price": price, "level": lv["name"]})
            trig[key] = {"cool_until": now + 1800}
        last = price
    return pushes

# 旧口径需要 enabled=true 才有位可推 → 用"全开"版本代表历史行为
block_all_on = {**BLOCK, "levels": [{**lv, "enabled": True} for lv in BLOCK["levels"]]}

old_pushes = run_old_30min_allpush(block_all_on)
new_pushes, digest = run_new(BLOCK)

span_min = len(path) * POLL / 60
print()
print("=" * 62)
print(f"模拟区间：{span_min:.1f} 分钟 · {len(path)} 个价格点 · 价格 {min(path):,.0f}–{max(path):,.0f}")
print("=" * 62)
print(f"旧逻辑（8位全开·每位30min冷却·无幅度门·无迟滞·无聚合）: {len(old_pushes):>3} 条推送")
print(f"新逻辑（分级+冷却+幅度门+迟滞+全局限流+同轮聚合）      : {len(new_pushes):>3} 条推送")
if old_pushes:
    print(f"降噪幅度: {100 * (1 - len(new_pushes) / len(old_pushes)):.0f}%")
print()
print("新逻辑实际会推的事件：")
for p in new_pushes:
    print(f"   第{p['t']:>3}点 现价 {p['price']:>9,.0f}  命中 {len(p['hits'])} 位 → {p['hits']}")
print()
from collections import Counter
print("新逻辑被抑制的原因分布：", dict(Counter(d.get("reason", "?") for d in digest)))
print()
print(f"说明：全局限流=任意两次推送≥{G.GLOBAL_MIN_GAP_SECONDS//60}分钟、每小时≤{G.GLOBAL_MAX_PER_HOUR}条；"
      f"silent 位只写 digest（{sum(1 for d in digest if d.get('reason')=='silent_tier')} 条痕迹，0 条推送）")
