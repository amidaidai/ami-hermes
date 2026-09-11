#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""棠溪双指标静态审计扫描器 (只读).

用法: python pine_static_audit_scan.py SVP.pine AggVol.pine [...]
输出: 每个文件一份 JSON 到 stdout, 汇总到 static_scan_result.json (cwd).

覆盖 20260813 变体B + 20260910 增量两项:
  * TV 六项和 = input + plot + alertcondition + request + input.source + input.timeframe
  * series-color plot / data_window / price_scale 分类, 算最坏 plot 预算
  * 死变量(声明后零读取) —— 注意 tuple 返回元素(如 rdyGauge)不会被本扫描抓到, 需手工 grep
  * type 前向引用 / lookahead_off 无偏移(重绘风险, 非未来泄漏)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


def mask(src: str) -> str:
    """把注释/字符串替换为空格, 保留行结构, 避免字符串里的关键字干扰计数."""
    out = []
    i = 0
    n = len(src)
    in_s = None
    while i < n:
        ch = src[i]
        if in_s:
            if ch == "\\" and i + 1 < n:
                out.append(" ")
                out.append(" ")
                i += 2
                continue
            if ch == in_s:
                in_s = None
            out.append(" " if ch != "\n" else "\n")
            i += 1
            continue
        if ch in ('"', "'"):
            in_s = ch
            out.append(" ")
            i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


SKIP = {
    "i", "j", "k", "m", "s", "e", "v", "w", "t", "b", "f", "n", "x", "y", "z",
    "h", "l", "c", "o", "p", "q", "r", "cnt", "sz", "txt", "tmp", "res", "ret",
    "val", "col", "src", "idx", "bar", "len", "arr", "ex", "k1", "k2", "d", "oo", "cc", "vv", "ll",
}
TYPES = r"float|int|bool|string|color|table|line|label|box|polyline|linefill|array"


def scan(path: str, name: str) -> dict:
    raw = Path(path).read_text(encoding="utf-8")
    code = mask(raw)
    lines = code.split("\n")
    rawlines = raw.split("\n")
    r: dict = {"name": name, "path": path}
    r["lines"] = len(rawlines)
    r["chars"] = len(raw)
    r["bytes"] = len(raw.encode("utf-8"))
    r["sha256"] = hashlib.sha256(raw.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    r["est_tokens_div233"] = round(len(raw) / 2.33)

    def cnt(pat: str, s: str = code) -> int:
        return len(re.findall(pat, s))

    r["request_any"] = cnt(r"request\.\w+\(")
    r["request_security"] = cnt(r"request\.security\(")
    r["request_lower_tf"] = cnt(r"request\.security_lower_tf\(")
    r["plot_"] = cnt(r"(?m)^\s*plot\s*\(")
    r["alertcondition"] = cnt(r"alertcondition\(")
    r["alert_dyn"] = cnt(r"(?<!alertcondition)alert\(")
    r["input_any"] = cnt(r"input\.\w+\(")
    for kind in ("source", "timeframe", "session", "int", "float", "bool", "string", "color"):
        r[f"input_{kind}"] = cnt(rf"input\.{kind}\(")
    r["table_new"] = cnt(r"table\.new\(")
    r["table_cell"] = cnt(r"table\.cell\(")
    r["type_defs"] = cnt(r"(?m)^type\s+\w+")
    r["udf_defs"] = cnt(r"(?m)^[a-zA-Z_]\w*\s*\([^)]*\)\s*=>")
    r["method_defs"] = cnt(r"(?m)^method\s+\w+\(")
    r["lookahead_on"] = cnt(r"lookahead\s*=\s*barmerge\.lookahead_on")
    r["lookahead_off"] = cnt(r"lookahead\s*=\s*barmerge\.lookahead_off")
    r["dw_plots"] = cnt(r"display\s*=\s*display\.data_window")
    r["price_scale_plots"] = cnt(r"display\s*=\s*display\.price_scale")

    # plot 分类 + series-color
    nplot = series = fill = bg = dw = ps = 0
    series_lines = []
    for i, l in enumerate(rawlines):
        s = l.strip()
        if re.match(r"plot\s*\(", s):
            nplot += 1
            m = re.search(r"color\s*=\s*([^,\)]+)", s)
            c = (m.group(1).strip() if m else "")
            if c and ("?" in c or "color." in c or re.match(r"^[a-zA-Z_]\w*$", c)):
                series += 1
                series_lines.append(i + 1)
            if "display.data_window" in s:
                dw += 1
            if "display.price_scale" in s:
                ps += 1
        if re.match(r"fill\s*\(", s):
            fill += 1
        if re.match(r"bgcolor\s*\(", s):
            bg += 1
    r["plot_total"] = nplot
    r["series_color_plots"] = series
    r["series_color_lines"] = series_lines
    r["fill"] = fill
    r["bgcolor"] = bg
    r["plot_budget_worst"] = nplot + series + fill * 2 + bg

    # TV 六项和 (保守预算)
    r["tv_six_sum"] = (r["input_any"] + r["plot_"] + r["alertcondition"]
                       + r["request_any"] + r["input_source"] + r["input_timeframe"])

    # 死变量: 声明后零读取
    declared = set(re.findall(rf"(?:var\s+)?(?:{TYPES})\s+(\w+)\s*=", code))
    declared |= set(re.findall(r"(?m)^\s*(\w+)\s*:=", code))
    dead = []
    for v in sorted(declared):
        if len(v) <= 2 or v.startswith("_") or v in SKIP:
            continue
        reads = 0
        for l in lines:
            if not re.search(rf"\b{re.escape(v)}\b", l):
                continue
            if re.search(rf"(?:var\s+)?(?:{TYPES})\s+{re.escape(v)}\s*=", l):
                continue
            if re.match(rf"\s*{re.escape(v)}\s*:=", l):
                continue
            reads += 1
        if reads == 0:
            dead.append(v)
    r["dead_vars"] = dead

    # type 前向引用
    fwd = []
    for t in sorted(set(re.findall(r"(?m)^type\s+(\w+)", code))):
        dline = next((i + 1 for i, l in enumerate(rawlines) if re.match(rf"\s*type\s+{t}\b", l)), None)
        if not dline:
            continue
        for j in range(0, dline - 1):
            if re.search(rf"\b{t}\.", rawlines[j]) or re.search(rf"array<{t}>", rawlines[j]):
                fwd.append((t, j + 1, dline))
                break
    r["type_forward_refs"] = fwd

    # lookahead_off 无偏移 => 重绘(读到未收线 HTF 值), 不是未来泄漏
    risk = []
    for i, l in enumerate(rawlines):
        if "request.security" in l and "lookahead_off" in l:
            if not re.search(r"\[\d+\]", l.split("lookahead")[0]):
                risk.append(i + 1)
    r["lookahead_off_no_offset_lines"] = risk

    # 括号平衡
    for a, b in (("(", ")"), ("[", "]"), ("{", "}")):
        r[f"bal_{a}{b}"] = code.count(a) - code.count(b)

    print(json.dumps(r, ensure_ascii=False, indent=1))
    return r


if __name__ == "__main__":
    out = {}
    for p in sys.argv[1:]:
        out[Path(p).name] = scan(p, Path(p).stem)
    Path("static_scan_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
