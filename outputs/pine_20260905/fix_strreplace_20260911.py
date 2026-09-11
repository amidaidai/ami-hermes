#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修 str.replace 误用：Pine 的 str.replace 只替换【第一处】，全替换要用 str.replace_all。

现场证据：图表磁吸↑ 渲染成 `周四纽 高 77518.6` —— 只有第一个空格被去掉。
档位名是 `"周四 纽 高"`（st.dayName + " " + shortName + " 高"，两个空格），
`str.replace(name," ","")` 只吃掉了第一个 → 完全吻合。

同类（既有缺陷，只是碰巧没暴露）：
  L3246 现位行的回踩/反抽档位名 `str.replace(pullbackLevelText," ","")` ×4
  —— 档位名如 "VAH 76837.8" 只有一个空格，所以一直看着正常；
     一旦档位名自带空格（如 "周四 纽 高"）就会露出同样的半个空格。

不动的三处（本就只有一处目标，语义正确）：
  L806  str.replace(syminfo.tickerid, ".P", "")   —— ticker 里只有一个 ".P"
  L1174/1176/1178 str.replace(name, "亚洲盘", "亚") —— 会话名只出现一次
  L3475 str.replace(guideActionWord, "等", "")    —— 三个取值各只含一个「等」
"""
from __future__ import annotations

import hashlib
from pathlib import Path

BASE = Path(r"D:\Hermes agent\outputs\pine_20260905")
SRC = BASE / "SVP_audit_fixed16_20260910.pine"
DST = BASE / "SVP_audit_fixed17_20260910.pine"

t = SRC.read_text(encoding="utf-8")
orig = t
log = []


def sub_all(old, new, tag, expect):
    global t
    n = t.count(old)
    assert n == expect, f"[{tag}] 命中 {n} 次，应为 {expect}"
    t = t.replace(old, new)
    log.append(f"{tag} ×{n}")


# 1) 磁吸行（本轮引入）
sub_all('str.replace(name, " ", "")', 'str.replace_all(name, " ", "")', "磁吸档位名全去空格", 1)

# 2) 现位行回踩/反抽档位名（既有缺陷）
sub_all('str.replace(pullbackLevelText, " ", "")', 'str.replace_all(pullbackLevelText, " ", "")', "回踩档位名全去空格", 2)
sub_all('str.replace(reboundLevelText, " ", "")', 'str.replace_all(reboundLevelText, " ", "")', "反抽档位名全去空格", 2)

body = t.replace("\r\n", "\n")
DST.write_bytes(body.encode("utf-8"))
saved = 229285 - len(body)
est = 100490 - round(saved * 0.43827)
print("改动:")
for x in log:
    print("  -", x)
print(f"\n字符 {len(orig)} -> {len(body)}  ({len(orig) - len(body):+d})")
print(f"行数 {len(orig.splitlines())} -> {len(body.splitlines())}")
print(f"CE10117 推算 {est} / 100256 → 余量 {100256 - est}")
print(f"sha256[:24] = {hashlib.sha256(body.encode()).hexdigest()[:24]}")
print()
print("效果对比（磁吸↑，档位名「周四 纽 高」）：")
print("  修复前: 周四纽 高 77518.6·3.9A·分69★HTF·40%    ← 只剩一个空格")
print("  修复后: 周四纽高 77518.6·3.9A·分69★HTF·40%")
print("现位行（档位名「VAH 76837.8」）：两者相同（原本只有一个空格），但以后带空格的名不会再漏。")
