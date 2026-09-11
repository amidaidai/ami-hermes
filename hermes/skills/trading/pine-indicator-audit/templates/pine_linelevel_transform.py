#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""3000+ 行 Pine 大文件的「安全变换」骨架 —— 拷走改成自己的修复。

为什么不用 patch/write_file：
  * 手敲 patch 在 3400 行文件上容易上下文漂移；
  * 整文件 write_file 无法逐处审阅、无法断言"我删对了地方"。
本骨架的三层纪律：
  A 行级编辑（1-based 行号 + 首末行 needle 断言，降序应用）
  B 字符串级编辑（唯一子串 + 期望命中次数）
  C 残留/接回检查（去注释后计数）

用法：
  1) cp 本文件为 fix_<指标>_<日期>.py
  2) 先自己读一遍原文件，把要改的行号填进 LINE_EDITS
  3) 跑：python fix_xxx.py 原文件.pine 新文件.pine
  4) 跑后必须 diff 人工过一遍 + 服务器编译 + docs/verify 脚本

注意（实测踩过）：
  * 行号来自"你刚读的那份原文"，不要复用上一轮的旧行号。
  * 写完必须 write_bytes + LF 归一，Windows 下 write_text 会把 \\n 写成 \\r\\n。
  * 残留检查先 l.split("//")[0] 去注释，否则自己写的说明性注释会把断言打挂。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "source.pine")
DST = Path(sys.argv[2] if len(sys.argv) > 2 else "fixed.pine")

text = SRC.read_text(encoding="utf-8")
NL = "\r\n" if "\r\n" in text else "\n"


def L(*rows: str) -> str:
    """把若干行拼成带本地换行符的块（替换块统一用它生成，避免混入裸 \\n）。"""
    return NL.join(rows)


# ------------------------------------------------------------------ A 行级编辑
# (起始行, 结束行(含), 首行必须包含, 末行必须包含, 替换块；空串块 = 删除这些行)
LINE_EDITS: list[tuple[int, int, str, str, str]] = [
    # 示例：删一个死变量
    # (232, 232, "float aggContractSource", "aggContractSource", ""),
    # 示例：替换一个返回元组
    # (759, 759, "[obBull, obBear", "[obBull, obBear", L("    [obBull[1], obBear[1]]")),
]

# 断言先行：任何一条不符立刻中断，并打印实际内容切片便于定位
for (a, b, fneedle, lneedle, _repl) in LINE_EDITS:
    lines = text.split(NL)
    assert fneedle in lines[a - 1], f"L{a} 首行不符: 期望含 {fneedle!r} 实际 {lines[a-1][:110]!r}"
    assert lneedle in lines[b - 1], f"L{b} 末行不符: 期望含 {lneedle!r} 实际 {lines[b-1][:110]!r}"

# 降序应用（单条也走这条路径，保持语义一致）
lines = text.split(NL)
for (a, b, _f, _l, repl) in sorted(LINE_EDITS, key=lambda e: -e[0]):
    lines[a - 1:b] = [] if repl == "" else repl.split(NL)
stage1 = NL.join(lines)

# --------------------------------------------------------------- B 字符串级编辑
# (旧串, 新串[, 期望命中次数=1])；返回行与解构行同时命中时显式写 2
STRING_EDITS: list[tuple] = [
    # 示例：
    # ("[posText, rdyGauge, rdyPctV]", "[posText, rdyPctV]", 2),
]

for item in STRING_EDITS:
    old, new = item[0], item[1]
    expect = item[2] if len(item) > 2 else 1
    n = stage1.count(old)
    assert n == expect, f"字符串替换命中 {n} 次（应为 {expect}）: {old[:90]!r}"
    stage1 = stage1.replace(old, new)

# ------------------------------------------------- C 残留 / 接回检查（去注释）
code = "\n".join(l.split("//")[0] for l in stage1.split(NL))
for v in ():  # 应被删除的标识符：断言为 0
    assert code.count(v) == 0, f"残留标识符 {v} 出现 {code.count(v)} 次"
for v in ():  # 应被接回消费的标识符：断言 >= 2（声明 + 消费）
    assert code.count(v) >= 2, f"{v} 未被接回（仅 {code.count(v)} 次出现）"

# 落盘：必须 write_bytes，且 LF 归一。（Windows 下 write_text 会把 \n 翻译成 \r\n，
# 而 read_text 又把它规范化回去，本地自检看不出差异，直到比对 read_bytes 的哈希才暴露。）
DST.write_bytes(stage1.replace("\r\n", "\n").encode("utf-8"))
print(f"行数 {len(text.split(NL))} -> {len(stage1.split(NL))}")
print(f"字符 {len(text)} -> {len(stage1)}  (Δ{len(stage1) - len(text)})")
print("SHA256(LF 归一) " + hashlib.sha256(stage1.replace("\r\n", "\n").encode()).hexdigest())
