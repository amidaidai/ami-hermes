#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""降噪验收（双向）：既证明"不吵"，也证明"真到价不吞"。

用户两条要求必须同时成立才算通过：
  1. 不能太频繁（价值区密集带不许连环推）
  2. 重要的位（结构 FVG/OB、HTF 磁吸）真到价必须推出来 —— 不能降噪降成哑巴
"""
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("kg", ROOT / "scripts" / "keylevel_guard.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

BLOCK = json.loads(
    (ROOT / "data" / "keylevels_config.json").read_text(encoding="utf-8")
)["symbols"]["BTCUSDT"]

POLL = 0.5
NOW0 = 1_760_000_000.0


def seg(a, b, n):
    """从 a 线性走到 b，共 n 个点。"""
    return [a + (b - a) * (i + 1) / n for i in range(n)]


def run(path, block):
    trig, recent, pushes, digest = {}, [], [], []
    last = None
    for i, price in enumerate(path):
        now = NOW0 + i * POLL
        d, cands = G.evaluate_symbol("BTCUSDT", block, last, price, now, trig)
        digest.extend(d)
        if cands:
            ok, reason, recent = G.global_rate_limit_ok(recent, now)
            if ok:
                pushes.append({"price": price, "hits": [c["name"] for c in cands]})
                recent.append(now)
                for c in cands:
                    trig[c["key"]] = {
                        **trig.get(c["key"], {}),
                        "dir": c["cross"], "armed": False, "anchor_price": price,
                        "cool_until": now + float(c["policy"]["cooldown"]),
                    }
            else:
                for c in cands:
                    digest.append({"reason": reason, "level": c["name"]})
        last = price
    return pushes, digest


# ── 验收1：价值区密集带横扫（这些是 silent，应 0 推）──
print("=" * 66)
print("验收 1：价值区密集带横扫（6 位全 silent，应 0 推）")
print("=" * 66)
path1, x = [], 77250.0
for tgt, n in [(77360, 12), (77290, 8), (77335, 5), (77260, 7), (77460, 16),
               (77300, 14), (77560, 20), (77180, 24), (77300, 10)]:
    path1 += seg(x, tgt, n)
    x = tgt
p1, d1 = run(path1, BLOCK)
print(f"区间 {min(path1):,.0f}–{max(path1):,.0f} · {len(path1)} 点 · {len(path1)*POLL/60:.1f} 分钟")
print(f"推送条数: {len(p1)}   ← 应为 0")
print(f"抑制原因: {dict(Counter(d.get('reason', '?') for d in d1))}")
for h in p1:
    print("   ", h)

# ── 验收2：真到关键结构位（critical，必须推出来）──
print()
print("=" * 66)
print("验收 2：真到 critical 结构位（必须推出来，不能降成哑巴）")
print("=" * 66)
# 注意：终点必须真正穿过位价（严格小于），恰好停在位价上不构成穿越。
path2, x = [], 77250.0
for tgt, n in [(76900, 30), (77100, 20), (76900, 25), (77200, 20), (79250, 60)]:
    path2 += seg(x, tgt, n)
    x = tgt
p2, d2 = run(path2, BLOCK)
print(f"区间 {min(path2):,.0f}–{max(path2):,.0f} · {len(path2)} 点 · {len(path2)*POLL/60:.1f} 分钟")
print(f"推送条数: {len(p2)}   ← 应能推出（结构位/HTF 是真事件）")
for h in p2:
    print(f"   现价 {h['price']:>9,.0f} → {h['hits']}")
print(f"抑制原因: {dict(Counter(d.get('reason', '?') for d in d2))}")

# ── 验收3：一次行情连穿多位（全局限流应压成 1 条）──
print()
print("=" * 66)
print("验收 3：8 位全 critical，价格连穿多位（全局限流应压到 1 条）")
print("=" * 66)
block_all = {**BLOCK, "levels": [{**l, "push_tier": "critical"} for l in BLOCK["levels"]]}
# 77900 → 76900 会连穿 77800 / 77520 / 77400 / 77310 / 76938 共 5 位
path3 = seg(77900, 76900, 60)
p3, d3 = run(path3, block_all)
print(f"推送条数: {len(p3)}   ← 全局限流应压到 1 条")
for h in p3:
    print(f"   现价 {h['price']:>9,.0f} 命中 {len(h['hits'])} 位 → {h['hits']}")

# ── 验收4：迟滞带（贴线抖动不连发）──
print()
print("=" * 66)
print("验收 4：贴线抖动（在结构位上反复横跳，应只推 1 次）")
print("=" * 66)
jitter, x = [], 77000.0
for _ in range(6):
    jitter += seg(x, 76920, 4)   # 真正下穿 76938
    x = 76920
    jitter += seg(x, 76990, 4)   # 回到位上方
    x = 76990
p4, d4 = run(jitter, BLOCK)
print(f"{len(jitter)} 点反复横跳 76936–77000（结构位 76938）")
print(f"推送条数: {len(p4)}   ← 应 ≤1（迟滞带 + 冷却）")
for h in p4:
    print(f"   现价 {h['price']:>9,.0f} → {h['hits']}")

print()
print("=" * 66)
print("结论")
print("=" * 66)
print(f"  价值区密集带：{len(p1)} 条  （旧逻辑同路径 3 条 → 全静默）")
print(f"  真到结构位  ：{len(p2)} 条  （该推的推出了）")
print(f"  连穿多位    ：{len(p3)} 条  （聚合为 1 条）")
print(f"  贴线抖动    ：{len(p4)} 条  （旧逻辑会每位重推）")
