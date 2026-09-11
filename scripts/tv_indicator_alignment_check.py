#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""契约 ↔ 指标源码 对齐核查（改指标后必跑）。

为什么要有这个
--------------
契约 `scripts/tv_indicator_contract.py` 是唯一权威，但它是**手写**的；
指标侧改一行 plot 标题或行动格行名，如果契约没跟上，消费方会**静默丢字段**
（历史事故：主指�13 行里只有 4 行被卡片吃到）。

判定规则（不靠手写白名单）
--------------------------
每个 plot 调用按 `display=` 参数分三类：
  · `display.data_window`  → **DW 字段**，必须出现在契约里（否则静默丢）
  · `display.price_scale`  → **价格轴/结构线**，必须在契约里（卡片读关键位）
  · 其它（默认 display.all）→ **纯视觉**（柱状/线形/模式切换用），不进契约，不算漂移
反向也查：契约里的名字如果在源码里一个 plot 都找不到 = 死字段。

行动格行名：
  · `array.push(rowLabs, "位置")` 直接取字面量
  · `array.push(rowLabs, riskLabelText)` 这类动态标签，改用契约里的
    RISK_ROW_VARIANTS 字面量做存在性校验（标签是动态的，值不是）

用法：
    python scripts/tv_indicator_alignment_check.py      # 退出码 0=对齐 1=有缺口
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import tv_indicator_contract as C  # noqa: E402

# 定版指标源（与契约 docstring 里的 sha 一一对应）
PINE_DIR = REPO / "outputs" / "pine_20260905"
MAIN_PINE = PINE_DIR / "SVP_audit_fixed17_20260910.pine"      # = SVP_主指标_空格修正_20260911.pine
SUB_PINE = PINE_DIR / "AggVol_audit_fixed14_20260910.pine"    # = AggVol_副指标_最终版_20260911.pine

_PLOT_CALL = re.compile(r"\bplot(?:shape|char|candle|arrow)?\s*\(")
_ROW_PUSH = re.compile(r"array\.push\(\s*rowLabs\s*,")
_CELL_LABEL = re.compile(r"table\.cell\(\s*\w+\s*,\s*0\s*,\s*\d+\s*,")


def _strip_comments(src: str) -> str:
    return re.sub(r"//[^\n]*", "", src)


def _split_args(text: str, start: int) -> tuple[list[str], int]:
    """从 `text[start] == '('` 起，按顶层逗号切参数（尊重引号与嵌套括号）。"""
    args: list[str] = []
    depth = 0
    quote = ""
    buf: list[str] = []
    i = start
    while i < len(text):
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == "\\":
                i += 1
                if i < len(text):
                    buf.append(text[i])
            elif ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == "(":
            depth += 1
            if depth > 1:
                buf.append(ch)
        elif ch == ")":
            depth -= 1
            if depth == 0:
                args.append("".join(buf))
                return args, i + 1
            buf.append(ch)
        elif ch == "," and depth == 1:
            args.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    return args, i


def _literal(arg: str) -> str | None:
    """参数是纯字符串字面量时返回其内容，否则 None。"""
    s = arg.strip()
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        return s[1:-1].replace('\\"', '"').replace("\\'", "'")
    return None


def _title_of(args: list[str]) -> str | None:
    """plot 的标题：优先 `title=`，否则第 2 个位置参数。"""
    for arg in args:
        m = re.match(r"\s*title\s*=\s*(.+)$", arg, re.S)
        if m:
            return _literal(m.group(1))
    if len(args) >= 2:
        return _literal(args[1])
    return None


def _display_of(args: list[str]) -> str:
    for arg in args:
        if "display.data_window" in arg:
            return "data_window"
        if "display.price_scale" in arg:
            return "price_scale"
    return "visual"


def scan_plots(src: str) -> dict[str, list[str]]:
    """{标题: [类别, ...]}；类别 ∈ data_window / price_scale / visual。"""
    body = _strip_comments(src)
    out: dict[str, list[str]] = {}
    for m in _PLOT_CALL.finditer(body):
        args, _ = _split_args(body, m.end() - 1)
        title = _title_of(args)
        if not title:
            continue
        out.setdefault(title, []).append(_display_of(args))
    return out


def _call_args(body: str, match: re.Match) -> list[str]:
    """取 `match` 对应的调用参数：从该调用的 '(' 开始按顶层逗号切。"""
    return _split_args(body, body.index("(", match.start()))[0]


def scan_rows(src: str) -> tuple[list[str], int]:
    """返回（字面量行名列表, 动态行名个数）。动态标签由契约字面量单独校验。"""
    body = _strip_comments(src)
    literal: list[str] = []
    dynamic = 0
    for m in _ROW_PUSH.finditer(body):
        # array.push(rowLabs, <label>) → 第 2 个参数
        args = _call_args(body, m)
        name = _literal(args[1]) if len(args) > 1 else None
        if name:
            literal.append(name)
        else:
            dynamic += 1
    for m in _CELL_LABEL.finditer(body):
        # table.cell(<table>, 0, <row>, <label>, ...) → 第 4 个参数
        args = _call_args(body, m)
        name = _literal(args[3]) if len(args) > 3 else None
        if name and name not in literal:
            literal.append(name)
    return literal, dynamic


def _check_pairs(tag: str, fname: str, fields: dict[str, list[str]],
                 contract: list[str]) -> bool:
    exported = {name for name, kinds in fields.items()
                if "data_window" in kinds or "price_scale" in kinds}
    visual = sorted(set(fields) - exported)
    contract_set = set(contract)
    missing = sorted(exported - contract_set)
    stale = sorted(contract_set - set(fields))
    print(f"=== {tag}（{fname}）===")
    print(f"  导出型 plot {len(exported)} ｜ 纯视觉 plot {len(visual)} ｜ 契约 {len(contract_set)}")
    if missing:
        print(f"  ✗ 源码导出、契约缺（消费方会静默丢）{len(missing)}：")
        for item in missing:
            print(f"      {item}")
    if stale:
        print(f"  ✗ 契约有、源码已无（死字段）{len(stale)}：")
        for item in stale:
            print(f"      {item}")
    if not missing and not stale:
        print("  ✓ 字段完全一致")
    if visual:
        print(f"  · 纯视觉（不进契约，正常）：{'、'.join(visual)}")
    print()
    return not missing and not stale


def _check_rows(tag: str, fname: str, literal: list[str], dynamic: int,
                contract: list[str]) -> bool:
    contract_set = set(contract)
    observed = set(literal) | {r for r in C.RISK_ROW_VARIANTS if r in contract_set and dynamic}
    missing = sorted(contract_set - observed)
    extra = sorted(set(literal) - contract_set)
    ordered = [r for r in literal if r in contract_set]
    print(f"=== {tag} 行动格（{fname}）===")
    print(f"  字面量行名 {len(literal)} ｜ 动态行名 {dynamic} ｜ 契约 {len(contract_set)}")
    if missing:
        print(f"  ✗ 契约有、源码渲染不出：{missing}")
    if extra:
        print(f"  ✗ 源码渲染了契约外的行：{extra}")
    if not missing and not extra:
        print("  ✓ 行名完全一致")
    expected_order = [r for r in contract if r in ordered]
    if ordered and ordered != expected_order:
        print(f"  ✗ 渲染顺序与契约不符：{ordered}")
        return False
    print(f"  ✓ 渲染顺序一致：{ordered}")
    print()
    return not missing and not extra


def main() -> int:
    for path in (MAIN_PINE, SUB_PINE):
        if not path.exists():
            print(f"✗ 找不到定版指标源码：{path}")
            return 1
    main_src = MAIN_PINE.read_text(encoding="utf-8")
    sub_src = SUB_PINE.read_text(encoding="utf-8")

    ok = True
    ok &= _check_pairs("主指标 DW", MAIN_PINE.name, scan_plots(main_src), C.DW_MAIN)
    ok &= _check_pairs("副指标 DW", SUB_PINE.name, scan_plots(sub_src), C.DW_SUB)

    m_rows, m_dyn = scan_rows(main_src)
    s_rows, s_dyn = scan_rows(sub_src)
    ok &= _check_rows("主指标", MAIN_PINE.name, m_rows, m_dyn, C.MAIN_ROW_LABELS)
    ok &= _check_rows("副指标", SUB_PINE.name, s_rows, s_dyn, C.SUB_ROW_LABELS)

    # 授权态字面量必须在指标源码里真实存在（Python 侧按它做 fail-closed 判定）。
    for token in (C.SVP_AUTHORIZATION_LABEL, C.SVP_OBSERVATION_LABEL,
                  C.SVP_UNAUTHORIZED_LABEL, C.SVP_FORBIDDEN_VALUE):
        if token not in main_src:
            print(f"✗ 契约授权态字面量在源码里找不到：{token}")
            ok = False

    print("✓ 契约与定版指标完全对齐" if ok
          else "✗ 存在缺口：先改 scripts/tv_indicator_contract.py，再改消费方")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
