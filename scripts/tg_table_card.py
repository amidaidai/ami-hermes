#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 · TG 真表格图片卡生成器 v1.0

把 Markdown 管道表渲染成深色主题 PNG（手机窄列真表格），再经
telegram_reliable.send_telegram_photo 发到 TG。统一替代退化的
MarkdownV2 文本表（客户端不渲染管道表）。

用法:
  from tg_table_card import render_and_send
  render_and_send("telegram:-1003733144325:846",
                  md_text, title="棠溪全任务实测报告")
或命令行:
  python tg_table_card.py <target> <md_file> [title]
"""
from __future__ import annotations
import sys, os, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Iterable

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow 未安装 (pip install pillow)", file=sys.stderr)
    raise

ROOT = Path("D:/Hermes agent")
TZ = timezone(timedelta(hours=8))
FONT_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%/hermes/hermes-agent/venv/Lib/site-packages"))

# 深色主题
BG = (13, 17, 23)
PANEL = (22, 27, 34)
BORDER = (48, 54, 61)
HEADER_BG = (22, 27, 34)
HEADER_FG = (88, 166, 255)
ROW_EVEN = (22, 27, 34)
ROW_ODD = (13, 17, 23)
TEXT = (230, 237, 243)
MUTED = (139, 148, 158)
OK = (63, 185, 80)
WARN = (210, 153, 34)
BAD = (248, 81, 73)
TG = (210, 153, 34)


def _load_font(size: int, bold: bool = False):
    """尽量用系统中文字体，失败回退默认。"""
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",          # 微软雅黑
        "C:/Windows/Fonts/msyhbd.ttc",        # 微软雅黑粗
        "C:/Windows/Fonts/simhei.ttf",        # 黑体
        "C:/Windows/Fonts/simsun.ttc",        # 宋体
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _parse_tables(md: str) -> list[list[list[str]]]:
    """解析 markdown 文本中的管道表（多个表用空行分隔）。"""
    tables: list[list[list[str]]] = []
    cur: list[list[str]] = []
    for line in md.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if cur:
                tables.append(cur)
                cur = []
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        # 跳过分隔行 |:--:|:--:|
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        cur.append(cells)
    if cur:
        tables.append(cur)
    return tables


def _color_for(cell: str) -> tuple:
    if "✅" in cell or "成功" in cell or "正常" in cell:
        return OK
    if "❌" in cell or "失败" in cell or "FAILED" in cell:
        return BAD
    if "⚠" in cell or "降级" in cell or "缺失" in cell:
        return WARN
    if "TG" in cell:
        return TG
    return TEXT


def _text_w(draw, text, font) -> int:
    try:
        return draw.textlength(text, font=font)
    except Exception:
        return len(text) * font.size // 2


def render_png(md: str, title: str | None = None, out_path: Path | None = None) -> Path:
    """渲染 markdown 表格为 PNG，返回文件路径。"""
    tables = _parse_tables(md)
    if not tables:
        raise ValueError("未找到管道表")

    font_h = 22
    font_t = 26
    font_hd = _load_font(font_h, bold=True)
    font_cell = _load_font(font_h)
    font_title = _load_font(font_t, bold=True)
    pad_x = 14
    pad_y = 9
    gap = 22  # 表间距
    max_w = 760  # 手机窄列宽度上限

    # 预计算每张表的列宽
    table_layouts = []
    total_h = 0
    if title:
        total_h += font_t + 18
    for tbl in tables:
        n_cols = max(len(r) for r in tbl)
        # 归一化每行列数
        norm = [r + [""] * (n_cols - len(r)) for r in tbl]
        col_w = [0] * n_cols
        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        for r in norm:
            for i, c in enumerate(r):
                w = _text_w(draw, c, font_cell if r is not tbl[0] else font_hd) + pad_x * 2
                col_w[i] = max(col_w[i], w)
        tbl_w = sum(col_w) + 1
        tbl_w = min(tbl_w, max_w)
        row_h = font_h + pad_y * 2
        tbl_h = row_h * len(norm) + 1
        table_layouts.append((norm, col_w, tbl_w, tbl_h, row_h))
        total_h += tbl_h + gap

    img_w = min(max_w, max((tl[2] for tl in table_layouts), default=max_w))
    img_w = int(img_w)
    img = Image.new("RGB", (img_w, int(total_h)), BG)
    draw = ImageDraw.Draw(img)
    y = 10
    if title:
        draw.text((pad_x, y), title, font=font_title, fill=HEADER_FG)
        y += font_t + 14

    for (norm, col_w, tbl_w, tbl_h, row_h) in table_layouts:
        x0 = (img_w - tbl_w) // 2 if tbl_w < img_w else 0
        # 表边框
        draw.rectangle([x0, y, x0 + tbl_w, y + tbl_h], outline=BORDER, width=1)
        cy = y
        for ri, row in enumerate(norm):
            # 行底色
            if ri == 0:
                draw.rectangle([x0, cy, x0 + tbl_w, cy + row_h], fill=HEADER_BG)
            elif ri % 2 == 0:
                draw.rectangle([x0, cy, x0 + tbl_w, cy + row_h], fill=ROW_EVEN)
            # 单元格
            cx = x0
            for ci, cell in enumerate(row):
                cw = col_w[ci]
                if ri == 0:
                    draw.text((cx + pad_x, cy + pad_y), cell, font=font_hd, fill=HEADER_FG)
                else:
                    color = _color_for(cell)
                    draw.text((cx + pad_x, cy + pad_y), cell, font=font_cell, fill=color)
                # 列分隔
                if ci < len(row) - 1:
                    draw.line([cx + cw, cy, cx + cw, cy + row_h], fill=BORDER, width=1)
                cx += cw
            # 行分隔
            draw.line([x0, cy + row_h, x0 + tbl_w, cy + row_h], fill=BORDER, width=1)
            cy += row_h
        y += tbl_h + gap

    if out_path is None:
        out_path = ROOT / "data" / f"tg_card_{datetime.now(TZ).strftime('%Y%m%d_%H%M%S')}.png"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def render_and_send(target: str, md_text: str, title: str | None = None,
                    token: str | None = None) -> tuple[bool, str]:
    """渲染表格为 PNG 并发送到 TG。返回 (成功, 原因)。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    from telegram_reliable import send_telegram_photo
    try:
        png = render_png(md_text, title=title)
    except Exception as e:
        return False, f"render_failed: {e}"
    ok, reason = send_telegram_photo(target, str(png), caption=title, token=token, retries=3)
    return ok, reason


def main():
    if len(sys.argv) < 3:
        print("用法: python tg_table_card.py <target> <md_file> [title]")
        return 1
    target = sys.argv[1]
    md_file = sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else None
    md = Path(md_file).read_text(encoding="utf-8")
    ok, reason = render_and_send(target, md, title=title)
    print(f"OK={ok} REASON={reason}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
