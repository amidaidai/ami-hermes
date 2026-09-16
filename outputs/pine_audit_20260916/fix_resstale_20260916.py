#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2026-09-16 修复：resStale 接回（F13 对称性补全）

背景：20260910 修复(F13) 为「稳定位」增加 48h 年龄上限 —— 支撑侧已接线
（supStale 进 supBroken/supExpired/supImproved/supStale 条件 + 原因码 3），
but 阻力侧 resStale 只声明未消费 → 超龄阻力位永不因「超龄」退役。

改动（仅 2 处逻辑 + 1 行注释，全部为已存在变量的接线）：
  1) L1894: else if resBroken or resExpired or resImproved
         →  else if resBroken or resExpired or resImproved or resStale
  2) L1900: lastWatchReason := resBroken ? 1 : resExpired ? 3 : 2
         →  lastWatchReason := resBroken ? 1 : resExpired or resStale ? 3 : 2
  3) F13 注释块补一行 20260916 说明。

纪律：读 fixed17 → 逐条断言锚点命中数 == 1 → 写新版本 fixed18 → 打印统计。
不原地改；版本链即回滚点。
"""
from pathlib import Path
import hashlib

BASE = Path(r"D:/Hermes agent/outputs/pine_20260905")
SRC = BASE / "SVP_audit_fixed17_20260910.pine"
DST = BASE / "SVP_audit_fixed18_20260916.pine"

t = SRC.read_text(encoding="utf-8")
orig = t

def apply(old: str, new: str, label: str) -> str:
    cnt = t.count(old)
    assert cnt == 1, f"[{label}] 锚点命中 {cnt} 次（期望 1）—— 中止，不做部分替换"
    return t.replace(old, new)

# 1) 阻力侧退役条件
t = apply(
    "else if resBroken or resExpired or resImproved\n",
    "else if resBroken or resExpired or resImproved or resStale\n",
    "A1-条件",
)
# 2) 阻力侧原因码（与支撑侧 L1875 逐字对称）
t = apply(
    "        lastWatchReason := resBroken ? 1 : resExpired ? 3 : 2\n",
    "        lastWatchReason := resBroken ? 1 : resExpired or resStale ? 3 : 2\n",
    "A2-原因码",
)
# 3) 注释补记（注释不进 IL，仅维护性）
t = apply(
    "// 增加年龄上限：超龄即退役到「前位」（保留历史参考，不再冒充活跃位）。\n",
    "// 增加年龄上限：超龄即退役到「前位」（保留历史参考，不再冒充活跃位）。\n"
    "// 20260916 修复：resStale 接回——F13 落地时仅支撑侧接线，阻力侧漏接（声明未消费）。\n",
    "A3-注释",
)

DST.write_text(t, encoding="utf-8")

# —— 统计 ——
def stat(s: str):
    return len(s.split("\n")), len(s), len(s.encode("utf-8")), hashlib.sha256(s.replace("\r\n", "\n").encode("utf-8")).hexdigest()

l0, c0, b0, h0 = stat(orig)
l1, c1, b1, h1 = stat(t)
print(f"fixed17: {l0} 行 / {c0} 字符 / {b0} B / sha={h0[:24]}")
print(f"fixed18: {l1} 行 / {c1} 字符 / {b1} B / sha={h1[:24]}")
print(f"Δ: 行 {l1-l0:+d} / 字符 {c1-c0:+d} / 字节 {b1-b0:+d}")

# —— 断言接线成功 ——
assert "resImproved or resStale" in t
assert "resExpired or resStale ? 3 : 2" in t
assert t.count("resStale") == 4, f"resStale 出现次数 {t.count('resStale')}（期望 4：声明 + 条件 + 原因码 + 注释）"
print("✓ 断言通过：resStale 命中 4 处（原 1 处）")

# —— 确认无其它漂移 ——
import difflib
diff = list(difflib.unified_diff(orig.split("\n"), t.split("\n"), lineterm="", n=1))
adds = [x for x in diff if x.startswith("+") and not x.startswith("+++")]
dels = [x for x in diff if x.startswith("-") and not x.startswith("---")]
print("--- DIFF ---")
for x in diff:
    print(x)
print(f"总计: +{len(adds)} 行 / -{len(dels)} 行")
print("DONE →", DST)
