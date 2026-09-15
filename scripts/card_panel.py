"""终端面板式行情卡渲染器（2026-09-14 用户选定格式 A）。

为什么要脚本：中文在等宽字体里占 2 个字符宽，纯手写空格对不齐「距现价」列。
本模块用 CJK 感知的视觉宽度对齐，输出可直接贴进 ```text 代码块。

用法：
    python scripts/card_panel.py panel.json        # 渲染并打印
面板 JSON 结构（缺项自动跳过）：
{
  "title":  "BTC 77,769   24h +1.27%   ○ 等待",
  "meta":   "9月14日 21:18 · 伦敦盘 · 不下单（副S4降权）",
  "notes":  ["今天冲高 78,344 被打回", "多头持续减仓 → 反弹乏力"],
  "watch":  {"level": "77,618", "name": "成交密集价 POC",
             "down": "收破 77,618 → 77,433 → 77,146",
             "up":   "收上 77,789 → 77,953   (修复线)",
             "mid":  "77,618–77,789 之间 → 不动手"},
  "ladder": [{"price": "78,032", "name": "价值区上沿 VAH", "dist": "+0.34%", "mark": False}, ...],
  "verify": "多平仓 -0.33% · Taker 0.72 · OI 4h -0.25%",
  "action": "等 15m 收线；破 77,618 看 77,433，回上 77,789 才谈修复"
}
"""
from __future__ import annotations

import json
import sys
import unicodedata


def visual_width(text: str) -> int:
    """东亚全角字符按 2 列计（等宽终端/手机代码块的常见渲染）。"""
    width = 0
    for ch in text:
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def pad(text: str, target: int, align: str = "left") -> str:
    fill = max(0, target - visual_width(text))
    if align == "right":
        return " " * fill + text
    if align == "center":
        left = fill // 2
        return " " * left + text + " " * (fill - left)
    return text + " " * fill


def render_ladder(rows: list[dict], gap: int = 2) -> list[str]:
    """价位阶梯：价位 | 结构名 | 距现价（右对齐）。主观察位前置 → 标记。"""
    if not rows:
        return []
    w_price = max(visual_width(str(r.get("price", ""))) for r in rows)
    w_name = max(visual_width(str(r.get("name", ""))) for r in rows)
    w_dist = max(visual_width(str(r.get("dist", ""))) for r in rows)
    out = []
    for r in rows:
        marker = "→ " if r.get("mark") else "  "
        out.append(
            f"{marker}{pad(str(r.get('price','')), w_price)}"
            f"{' ' * gap}{pad(str(r.get('name','')), w_name)}"
            f"{' ' * gap}{pad(str(r.get('dist','')), w_dist, 'right')}"
        )
    return out


def render(panel: dict, width: int = 46) -> str:
    lines: list[str] = []
    if panel.get("title"):
        lines.append(str(panel["title"]))
    if panel.get("meta"):
        lines.append(str(panel["meta"]))
    if panel.get("notes"):
        if lines:
            lines.append("")
        lines.extend(f"- {n}" if str(n).startswith("-") else str(n) for n in panel["notes"])

    watch = panel.get("watch") or {}
    if watch:
        lines.append("")
        head = f"盯 {watch.get('level','')}"
        if watch.get("name"):
            head += f"（{watch['name']}）"
        lines.append(head)
        if watch.get("down"):
            lines.append(f"  ↓ {watch['down']}")
        if watch.get("up"):
            lines.append(f"  ↑ {watch['up']}")
        if watch.get("mid"):
            lines.append(f"  ○ {watch['mid']}")

    ladder = render_ladder(panel.get("ladder") or [])
    if ladder:
        lines.append("")
        lines.extend(ladder)

    if panel.get("verify"):
        lines.append("")
        lines.append(str(panel["verify"]))
    if panel.get("action"):
        lines.append("")
        lines.append(str(panel["action"]))

    # 宽度守卫：超过 width 视觉列的行给出告警（不静默截断，让人自己收字）
    too_long = [ln for ln in lines if visual_width(ln) > width]
    if too_long and panel.get("_strict"):
        raise SystemExit(f"面板超宽 {width} 列：{too_long[:2]}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        panel = json.load(fh)
    text = render(panel, width=int(panel.get("_width", 46)))
    print("```text")
    print(text)
    print("```")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
