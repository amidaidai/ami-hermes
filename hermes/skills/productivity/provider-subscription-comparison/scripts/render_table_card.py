# -*- coding: utf-8 -*-
"""provider-subscription-comparison · 竖版对比表卡片渲染器（1080px，中文优先）。

为什么单独放脚本：本技能的核心产物就是「真表格卡片」而不是 Markdown 管道表。
每次手搓渲染器容易犯两个错——列宽总和不等于表宽导致最后一列溢出边框、
以及忘记用 CJK 字体导致中文变方块。这里把两件事都固化下来。

用法：
    from render_table_card import render_card
    render_card(
        name="sub-compare-1.png",
        title="标题",
        subtitle="北京时间 2026年9月13日 · 官网价核实",
        headers=["序", "方案", "实付/月", "为什么买它"],
        rows=[["1", "OpenCode Go", "$10", "长文本会自动换行……"]],
        widths=[64, 240, 150, 538],   # 可省略；省略则按内容自动分配
        notes=["· 脚注一", "· 脚注二"],
        highlight=0,                  # 高亮行下标（推荐项）
        out_dir="C:/Users/<user>/AppData/Local/hermes/outputs/<topic>",
    )

渲染后**必须**用 vision_analyze 抽查至少一张，确认无溢出/重叠/截断再交付。
"""

import os

from PIL import Image, ImageDraw, ImageFont

W = 1080
PAD = 44
BG = (250, 250, 252)
HDR = (17, 24, 39)
SUB = (107, 114, 128)
TXT = (31, 41, 55)
LINE = (229, 231, 235)
ACCENT = (4, 120, 87)
ACCENT_BG = (236, 253, 245)
ALT = (249, 250, 251)
BORDER = (209, 213, 219)

FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"

TABLE_W = W - 2 * PAD


def _font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def _tw(d, t, f):
    return d.textbbox((0, 0), t, font=f)[2]


def _wrap(d, t, f, maxw):
    lines, cur = [], ""
    for ch in t:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if _tw(d, cur + ch, f) <= maxw:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    lines.append(cur)
    return lines


def _normalize_widths(widths, headers):
    """列宽总和必须是 TABLE_W，否则最后一列会静默溢出圆角边框。"""
    n = len(headers)
    if not widths:
        return [TABLE_W // n] * (n - 1) + [TABLE_W - (TABLE_W // n) * (n - 1)]
    if len(widths) != n:
        raise ValueError("widths 长度必须等于 headers 长度")
    total = sum(widths)
    if total != TABLE_W:
        scale = TABLE_W / total
        scaled = [int(x * scale) for x in widths]
        scaled[-1] = TABLE_W - sum(scaled[:-1])
        widths = scaled
    return widths


def render_card(name, title, subtitle, headers, rows, widths=None, notes=None,
                highlight=0, out_dir=".", width=W):
    global W, PAD, TABLE_W
    W = width
    TABLE_W = W - 2 * PAD
    widths = _normalize_widths(widths, headers)

    fT, fS, fH = _font(40, True), _font(20), _font(21, True)
    fC, fN = _font(22), _font(18)

    tmp = Image.new("RGB", (W, 100))
    dt = ImageDraw.Draw(tmp)

    body = []
    for r in rows:
        cells, h = [], 62
        for i, c in enumerate(r):
            ls = _wrap(dt, c, fC, widths[i] - 20)
            cells.append(ls)
            h = max(h, len(ls) * 30 + 26)
        body.append((cells, h))

    note_lines = []
    for n in (notes or []):
        note_lines += _wrap(dt, n, fN, TABLE_W - 40)

    head_h = 150 + (60 if subtitle else 0)
    total_h = head_h + 26 + 56 + sum(h for _, h in body) + (
        len(note_lines) * 28 + 60 if note_lines else 40) + 30

    img = Image.new("RGB", (W, total_h), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, head_h], fill=HDR)
    d.text((PAD, 42), title, font=fT, fill=(255, 255, 255))
    if subtitle:
        d.text((PAD, 98), subtitle, font=fS, fill=(156, 163, 175))

    y = head_h + 26
    d.rounded_rectangle([PAD, y, W - PAD, y + 56], radius=10, fill=(243, 244, 246),
                        outline=BORDER, width=1)
    x = PAD
    for i, htxt in enumerate(headers):
        d.text((x + 14, y + 15), htxt, font=fH, fill=(55, 65, 81))
        x += widths[i]
    y += 56

    for idx, (cells, h) in enumerate(body):
        if idx == highlight:
            d.rectangle([PAD, y, W - PAD, y + h], fill=ACCENT_BG)
            d.rectangle([PAD, y, PAD + 6, y + h], fill=ACCENT)
        elif idx % 2 == 1:
            d.rectangle([PAD, y, W - PAD, y + h], fill=ALT)
        x = PAD
        for i, ls in enumerate(cells):
            fnt = _font(23, True) if (idx == highlight and i == 0) else fC
            col = ACCENT if (idx == highlight and i == 0) else TXT
            ty = y + 13
            for ln in ls:
                d.text((x + 14, ty), ln, font=fnt, fill=col)
                ty += 30
            x += widths[i]
        d.line([PAD, y + h, W - PAD, y + h], fill=LINE, width=1)
        y += h

    d.rounded_rectangle([PAD, head_h + 26, W - PAD, y], radius=10, outline=BORDER, width=1)

    if note_lines:
        y += 26
        for ln in note_lines:
            d.text((PAD + 10, y), ln, font=fN, fill=SUB)
            y += 28

    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, name)
    img.save(out, "PNG")
    print(out, img.size)
    return out


if __name__ == "__main__":
    render_card(
        name="demo.png",
        title="示例卡",
        subtitle="北京时间 2026年9月13日 · 官网价核实",
        headers=["序", "方案", "实付/月", "为什么买它"],
        rows=[["1", "OpenCode Go", "$10", "单位美元算力最高，长文本自动换行验证一二三四五六七八九十。"]],
        widths=[64, 240, 150, 538],
        notes=["· 脚注示例。"],
        highlight=0,
        out_dir=".",
    )
