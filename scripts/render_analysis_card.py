"""
棠溪分析卡 PIL PNG 渲染器 v7
- 数字用 Consolas（等宽，对齐美观）
- 中文用微软雅黑/黑体
- 字号体系：KPI 64 / 标题 42 / 表格 26 / 标签 22
- 表格行高 60
- 段间距 22（呼吸感）
- 配色：高对比 蓝/红/绿/橙
- 去掉内嵌 TV 截图（改成单独推图）
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import List, Tuple, Optional

# ---- 字体（按角色分） ----
FONT_CN_REG  = r"C:/Windows/Fonts/msyh.ttc"
FONT_CN_BLD  = r"C:/Windows/Fonts/simhei.ttf"   # 粗黑体
FONT_NUM_REG = r"C:/Windows/Fonts/consola.ttf"
FONT_NUM_BLD = r"C:/Windows/Fonts/consolab.ttf"
FONT_NUM_LGT = r"C:/Windows/Fonts/consolai.ttf"

def _f(path, size, idx=0):
    return ImageFont.truetype(path, size, index=idx)

# 数字/英文/标点 → Consolas
# 中文 → 微软雅黑
# 标题/徽章/评级 → 粗体
F_TITLE  = lambda: _f(FONT_CN_REG, 42, 0)   # 标题
F_KPI_N  = lambda: _f(FONT_NUM_BLD, 60)     # KPI 数字（等宽粗体 60）
F_KPI_L  = lambda: _f(FONT_CN_REG, 22, 0)   # KPI 标签
F_SECT   = lambda: _f(FONT_CN_BLD, 30)      # section 标题（粗黑体）
F_HDR    = lambda: _f(FONT_CN_BLD, 26)      # 表头（粗黑体 26）
F_LBL    = lambda: _f(FONT_CN_REG, 26, 0)   # label（中文 26）
F_VAL    = lambda: _f(FONT_NUM_REG, 26)     # 数值（等宽 26）
F_VALB   = lambda: _f(FONT_NUM_BLD, 26)     # 数值粗体
F_BAD    = lambda: _f(FONT_CN_BLD, 30)      # 粗体
F_NOTE   = lambda: _f(FONT_CN_REG, 22, 0)   # 脚注
F_VERD   = lambda: _f(FONT_CN_BLD, 34)      # 裁决粗体
F_RISK   = lambda: _f(FONT_CN_REG, 28, 0)   # 风险行
F_CALLO  = lambda: _f(FONT_CN_REG, 28, 0)
F_CALLO_T= lambda: _f(FONT_CN_BLD, 32)      # callout 标题粗体
F_BADGE  = lambda: _f(FONT_CN_BLD, 38)      # 徽章
F_STATUS = lambda: _f(FONT_NUM_REG, 24)     # 状态条（等宽 24）

# ---- 配色 ----
W = 1080
BG     = "#0E0E12"
HEAD_B = "#2563EB"
LBL_C  = "#C8CCD2"
VAL_C  = "#FFFFFF"
DIV_C  = "#1F1F26"
SECT_C = "#4ADE80"
GOOD   = "#4ADE80"
WARN   = "#F59E0B"
BAD    = "#EF4444"
MID    = "#9CA3AF"
ACC    = "#60A5FA"
RED_BG = "#3A0808"
GRN_BG = "#062812"
BLU_BG = "#0B1F3A"     # 截图缩略图底
HDR_BG = "#1A2433"     # 蓝色表头区域

def _c(level):
    return {
        "good": GOOD, "warn": WARN, "bad": BAD,
        "mid": MID, "accent": ACC, "white": VAL_C
    }.get(level, VAL_C)

def _tw(draw, text, font):
    b = draw.textbbox((0,0), text, font=font)
    return b[2]-b[0], b[3]-b[1]

RATING_BULLETS = {
    "good": ("●", GOOD), "warn": ("●", WARN), "bad":  ("●", BAD),
    "mid":  ("●", MID),  "accent":("●", ACC),  "white":("●", VAL_C),
}

# ===========================================================
# 顶部状态条（数据源 ✓ + 倒计时 + 关键提示）
# ===========================================================
def _draw_status_bar(draw, y, items):
    """items: [(text, level)] 横向平铺；level: good/warn/bad/mid/white"""
    pad = 24
    h = 36
    draw.rectangle([pad, y, W - pad, y + h], fill="#0B1A2E", outline="#1F1F26", width=1)
    x = pad + 14
    for text, level in items:
        color = _c(level)
        tw, _ = _tw(draw, text, F_STATUS())
        draw.text((x, y + 8), text, font=F_STATUS(), fill=color)
        x += tw + 28
    return y + h + 10

# ===========================================================
# 顶部：标题 + 信心度徽章
# ===========================================================
def _draw_header(draw, y, title, badge_text, badge_level):
    pad = 24
    # 标题
    draw.text((pad, y), title, font=F_TITLE(), fill=VAL_C)
    # 徽章 — 圆角矩形
    bt_w, bt_h = _tw(draw, badge_text, F_BADGE())
    bx = W - pad - bt_w - 28
    by = y + 4
    color = _c(badge_level)
    bg = {"good": GRN_BG, "warn": "#3A2A08", "bad": RED_BG}.get(badge_level, "#1F1F26")
    draw.rectangle([bx, by, bx + bt_w + 28, by + bt_h + 16], fill=bg, outline=color, width=2)
    draw.text((bx + 14, by + 8), badge_text, font=F_BADGE(), fill=color)
    return y + 44 + 10

# ===========================================================
# 4 KPI（无 sparkline，留空间给 TV 截图）
# ===========================================================
def _draw_kpi_row(draw, y, kpis: List[Tuple[str,str,str]]):
    pad = 24
    inner_w = W - pad*2
    cell_w = (inner_w - 30) // 4
    x = pad
    for i, (label, value, level) in enumerate(kpis):
        vw, vh = _tw(draw, value, F_KPI_N())
        draw.text((x + (cell_w - vw)//2, y), value, font=F_KPI_N(), fill=_c(level))
        lw, lh = _tw(draw, label, F_KPI_L())
        draw.text((x + (cell_w - lw)//2, y + vh + 8), label, font=F_KPI_L(), fill=MID)
        if i < len(kpis) - 1:
            draw.line([(x + cell_w + 5, y + 4), (x + cell_w + 5, y + vh + 8 + lh)],
                      fill=DIV_C, width=1)
        x += cell_w + 10
    return y + 46 + 20 + 8

# ===========================================================
# Section 标题（绿字 + 📊 + 左 3px 绿条）
# ===========================================================
def _draw_section_title(draw, y, text):
    draw.rectangle([24, y, 27, y + 30], fill=SECT_C)
    draw.text((34, y), f"📊  {text}", font=F_SECT(), fill=SECT_C)
    b = draw.textbbox((0,0), f"📊  {text}", font=F_SECT())
    return y + (b[3]-b[1]) + 14

# ===========================================================
# 通用三列表格
# ===========================================================
def _draw_table(draw, y, headers, rows, col_w=None, row_h=60):
    """headers: list[str]; rows: list of list[tuple]
    cell tuple 接受 (val, level) / (label, val, level) / (label, val, level, status)
    """
    pad = 24
    n = len(headers)
    inner_w = W - pad * 2
    if col_w is None:
        cw = [inner_w // n] * n
        cw[-1] = inner_w - sum(cw[:-1])
    else:
        cw = col_w
    head_h = 50
    x = pad
    for i, h in enumerate(headers):
        tw, _ = _tw(draw, h, F_HDR())
        draw.rectangle([x, y, x + cw[i], y + head_h], fill=HEAD_B)
        draw.text((x + (cw[i] - tw)//2, y + 14), h, font=F_HDR(), fill="#FFFFFF")
        x += cw[i]
    y += head_h
    for row in rows:
        x = pad
        cells = []
        for i, cell in enumerate(row):
            if isinstance(cell, tuple):
                if len(cell) == 4:
                    lbl, val, level, _ = cell; cells.append((lbl, val, level))
                elif len(cell) == 3:
                    lbl, val, level = cell; cells.append((lbl, val, level))
                elif len(cell) == 2:
                    val, level = cell; cells.append(('', val, level))
            else:
                cells.append(('', str(cell), 'white'))
        for i, (lbl, val, level) in enumerate(cells):
            w = cw[i] if i < len(cw) else cw[-1]
            tw, _ = _tw(draw, val, F_VAL())
            if i == 0 and lbl:
                draw.text((x + 12, y + 16), lbl, font=F_LBL(), fill=LBL_C)
            elif i == len(cells) - 1 and not lbl:
                bullet, color = RATING_BULLETS.get(level, RATING_BULLETS["mid"])
                draw.text((x + 14, y + 14), bullet, font=F_BAD(), fill=color)
                draw.text((x + 38, y + 16), val, font=F_VAL(), fill=color)
            else:
                draw.text((x + (w - tw)//2, y + 16), val, font=F_VAL(), fill=_c(level))
            x += w
        draw.line([(pad, y + row_h), (W - pad, y + row_h)], fill=DIV_C, width=1)
        y += row_h
    return y

# ===========================================================
# 红色风险 Banner
# ===========================================================
def _draw_risk_banner(draw, y, text, pad_top=12, pad_bot=12):
    font = F_RISK()
    tw, th = _tw(draw, text, font)
    h = th + pad_top + pad_bot
    draw.rectangle([24, y, W-24, y + h], outline=BAD, width=2)
    draw.rectangle([26, y+2, W-26, y+h-2], fill=RED_BG)
    draw.rectangle([24, y, 28, y + h], fill=BAD)
    draw.text((24 + 18, y + pad_top), text, font=font, fill=BAD)
    return y + h + 14

# ===========================================================
# 绿色 callout
# ===========================================================
def _draw_callout(draw, y, title, lines, pad_top=14, line_gap=8):
    font_t = F_CALLO_T()
    font_l = F_CALLO()
    n = len(lines)
    h = pad_top*2 + 36 + n * 36
    draw.rectangle([24, y, W-24, y + h], outline=GOOD, width=2)
    draw.rectangle([26, y+2, W-26, y+h-2], fill=GRN_BG)
    draw.rectangle([24, y, 28, y + h], fill=GOOD)
    draw.text((24 + 18, y + pad_top), title, font=font_t, fill=GOOD)
    yy = y + pad_top + 36
    for text, level in lines:
        draw.text((24 + 18, yy), text, font=font_l, fill=_c(level))
        yy += 36
    return y + h + 14

# ===========================================================
# A/B 方案并排对比（两个深色块）
# ===========================================================
def _draw_ab_compare(draw, y, plan_a, plan_b):
    pad = 24
    h = 180
    col_w = (W - pad*2 - 16) // 2

    # A 方案（左）— 绿系
    ax = pad
    draw.rectangle([ax, y, ax + col_w, y + h], outline=GOOD, width=2)
    draw.rectangle([ax+2, y+2, ax+col_w-2, y+h-2], fill=GRN_BG)
    draw.rectangle([ax, y, ax+4, y+h], fill=GOOD)
    # A 标题
    draw.text((ax + 16, y + 12), plan_a["title"], font=F_CALLO_T(), fill=GOOD)
    # A 行
    yy = y + 56
    for k, v, level in plan_a["lines"]:
        draw.text((ax + 16, yy), k, font=F_NOTE(), fill=MID)
        draw.text((ax + 16, yy + 22), v, font=F_BAD(), fill=_c(level))
        yy += 56

    # B 方案（右）— 蓝系（待定/反向）
    bx = pad + col_w + 16
    draw.rectangle([bx, y, bx + col_w, y + h], outline=ACC, width=2)
    draw.rectangle([bx+2, y+2, bx+col_w-2, y+h-2], fill=BLU_BG)
    draw.rectangle([bx, y, bx+4, y+h], fill=ACC)
    draw.text((bx + 16, y + 12), plan_b["title"], font=F_CALLO_T(), fill=ACC)
    yy = y + 56
    for k, v, level in plan_b["lines"]:
        draw.text((bx + 16, yy), k, font=F_NOTE(), fill=MID)
        draw.text((bx + 16, yy + 22), v, font=F_BAD(), fill=_c(level))
        yy += 56
    return y + h + 14

# (v7 改单独推图，已删除嵌入函数)
def render_card(
    out_path: str,
    title: str,
    badge_text: str,                    # "C级 · 等待" / "A级 · 做空" / "B级 · 反抽"
    badge_level: str,                   # good/warn/bad
    kpis: List[Tuple[str, str, str]],
    multi_tf: Optional[List[Tuple[str, str, str, str]]] = None,
    # multi_tf: [(周期, 结论, 关键位, 评级), ...] × 3-4
    signal: Optional[dict] = None,        # {headers, rows} 信号矩阵（主指标行动格）
    monitor: Optional[List[Tuple[str, str, str]]] = None,
    # monitor: [(价格, 含义, 触发动作), ...] × 5-7
    ab_plan: Optional[dict] = None,     # {"a": {...}, "b": {...}}
    risk_text: Optional[str] = None,
    callout: Optional[Tuple[str, List[Tuple[str, str]]]] = None,
    footer: str = "",
    binance: Optional[List[Tuple[str, str, str]]] = None,  # Binance 票 4-5 行
    status: Optional[List[Tuple[str, str]]] = None,        # 顶部状态条 [(text, level), ...]
):
    pad = 24
    img  = Image.new("RGB", (W, 5000), BG)
    draw = ImageDraw.Draw(img)

    y = 20
    # 1) 标题 + 徽章
    y = _draw_header(draw, y, title, badge_text, badge_level)

    # 1.5) 状态条（数据源 + 倒计时）
    if status:
        y = _draw_status_bar(draw, y, status)

    # 2) KPI
    y = _draw_kpi_row(draw, y, kpis) + 8
    draw.line([(pad, y), (W-pad, y)], fill=DIV_C, width=1)
    y += 14

    # 3) 多周期简表
    if multi_tf:
        y = _draw_section_title(draw, y, "多周期定位")
        y = _draw_table(draw, y, ["周期", "结论", "关键位", "评级"],
                        [[(c, "mid"), (v, "white"), (k, "accent"), (r, "good" if r=="good" else "warn")]
                         for c, v, k, r in multi_tf],
                        row_h=44) + 10

    # 4) 信号矩阵（主指标行动格，无嵌入图）
    if signal:
        y = _draw_section_title(draw, y, "信号矩阵 · 主指标行动格")
        y = _draw_table(draw, y, signal["headers"],
                        signal["rows"], row_h=60) + 10

    # 5) Binance 票
    if binance:
        y = _draw_section_title(draw, y, "Binance 方向票")
        y = _draw_table(draw, y, ["指标", "数值", "状态"],
                        [[(l, v, s) for l, v, s in binance]],
                        row_h=44) + 10

    # 6) 监控检查单
    if monitor:
        y = _draw_section_title(draw, y, "监控检查单 · 价位 × 动作")
        y = _draw_table(draw, y, ["价格", "含义", "触发动作"],
                        [[(p, m, a, lv) for p, m, a, lv in monitor]],
                        row_h=46) + 10

    # 7) A/B 方案对比
    if ab_plan:
        y = _draw_section_title(draw, y, "A/B 方案对比")
        y = _draw_ab_compare(draw, y, ab_plan["a"], ab_plan["b"])

    # 8) 风险 Banner
    if risk_text:
        y = _draw_risk_banner(draw, y, risk_text)

    # 9) Callout
    if callout:
        title_c, lines = callout
        y = _draw_callout(draw, y, title_c, lines)

    # 10) 脚注
    if footer:
        draw.text((pad, y + 6), footer, font=F_NOTE(), fill=MID)

    final_h = y + 50 if footer else y + 20
    img = img.crop((0, 0, W, final_h))
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_p, "PNG", optimize=True)
    return str(out_p), img.size


# ===========================================================
# self-test
# ===========================================================
if __name__ == "__main__":
    out, size = render_card(
        out_path=r"D:/Hermes agent/outputs/test_card_v5.png",
        title="BTC 78,541 \u00b7 15m \u00b7 2026\u5e748\u670831\u65e5 19:05",
        badge_text="C \u7ea7 \u00b7 \u7b49\u5f85",
        badge_level="warn",
        kpis=[
            ("\u73b0\u4ef7 USDT", "78,541", "white"),
            ("24h \u6da8\u8dcc",  "+0.45%", "good"),
            ("\u8d44\u91d1\u8d39\u7387",   "0.01%",  "mid"),
            ("OI \u4f30\u7b97",    "106.8K", "mid"),
        ],
        multi_tf=[
            ("15m", "\u504f\u591a\u00b71/10", "VWAP 78,014", "warn"),
            ("1h",  "\u89c2\u671b\u00b7\u7b49\u89e3\u9664", "78,774 \u6446\u52a8\u9ad8", "warn"),
            ("4h",  "\u7a7a\u8d8b\u52bf\u00b7BOS\u2193",    "78,950 \u8d85\u635f",    "bad"),
            ("1D",  "\u504f\u591a\u00b7\u5468\u6708",          "79,384 \u5468\u65e5\u9ad8",   "good"),
        ],
        signal={
            "image": r"D:/Hermes agent/tools/tradingview-mcp/screenshots/tv_full_2026-08-31T11-29-11-084Z.png",
            "headers": ["\u7ef4\u5ea6", "\u6570\u503c", "\u8bc4\u7ea7"],
            "rows": [
                [("\u4f4d\u7f6e", "mid"), ("VA\u4e0a\u00b7VWAP\u65e5\u00b7\u5468\u6708\u504f\u591a", "mid")],
                [("\u7ed3\u8bba", "mid"), ("\u26a0\u51b2\u7a81\u00b7\u26a0\u672a\u6536\u7ebf", "warn")],
                [("\u65b9\u5411", "mid"), ("\u504f\u591a\u00b71/10", "good")],
                [("\u8def\u5f84", "mid"), ("\u7ad9\u56deVA\u8fc7\u671f\u00d7", "warn")],
                [("OI",     "mid"), ("\u25b2\u65b0\u7a7a 0.2% \u5171\u8bc650%", "warn")],
                [("\u7ed3\u6784", "mid"), ("\u7a7a\u8d8b\u52bf\u00b7BOS\u2193", "bad")],
            ],
            "max_h": 280,
        },
        binance=[
            ("\u73b0\u4ef7", "78,540.85 \u00b7 \u2460 \u4e2d\u6027", "white"),
            ("\u8d44\u91d1\u8d39\u7387", "0.01% (19:00) \u00b7 \u26a0 \u504f\u591a", "warn"),
            ("\u6807\u8bb0\u4ef7", "78,508.46", "mid"),
            ("\u6307\u6570\u4ef7", "78,538.27", "mid"),
        ],
        monitor=[
            ("79,400", "\u6b62\u635f\u4e0a\u9650", "\u6536\u76d8\u4e0a\u7834\u5373\u4e2d\u67a2\u7ad9\u8fd0\u4ed3", "bad"),
            ("78,774", "\u6446\u52a8\u9ad8", "\u4e0a\u7834\u00b7\u4e3a\u4ec0\u4e48\u505a\u591a", "warn"),
            ("78,014", "VWAP \u591a\u7a7a\u5206\u6c34", "\u4e0a\u7834\u591a\u4e0b\u7834\u7a7a", "good"),
            ("77,940", "\u521d\u7ea7\u652f\u6491", "\u6536\u76d8\u4e0d\u8dcc\u7834\u89c2\u671b\u53cd\u52a8", "warn"),
            ("77,000", "\u76ee\u6807\u4e0b\u9650", "\u5230\u4f4d\u5206\u6279\u51fa\u5c40", "good"),
        ],
        ab_plan={
            "a": {
                "title": "\u2460 A \u8ffd\u7a7a\u65b9\u6848",
                "lines": [
                    ("\u5165\u573a",  "78,000\u00b71.5A",   "good"),
                    ("\u6b62\u635f",  "78,250",            "bad"),
                    ("\u76ee\u6807",  "77,000 \u00b7 76,500", "good"),
                ],
            },
            "b": {
                "title": "\u2461 B \u7b49\u53cd\u62bd\u65b9\u6848",
                "lines": [
                    ("\u5165\u573a",  "78,950\u00b71.5A",   "good"),
                    ("\u6b62\u635f",  "78,500",            "bad"),
                    ("\u76ee\u6807",  "79,384 \u00b7 80,000", "good"),
                ],
            },
        },
        risk_text="\ud83d\udea8 \u8b66\u60d5\uff1a\u526fS3\u51b2\u7a81\u672a\u89e3\u9664 + OI \u65b0\u7a7a + \u5468\u672b\u6d41\u52a8\u6027\u771f\u7a7a \u2014 \u4e0d\u62a2\u8dd1",
        callout=(
            "\ud83d\udccb \u63a8\u8350\u64cd\u4f5c \u00b7 \u7a7a\u4ed3\u7b49\u5f85",
            [
                ("\u4e0b\u4e00\u8282\u70b9 19:20 MSS \u65b9\u5411\u786e\u8ba4", "mid"),
                ("\u4e0a\u8f66\u8981\u6c42\uff1a\u4e0a\u7834 78,774 OR \u4e0b\u7834 78,014 \u4e14 15m \u6536\u76d8", "white"),
            ],
        ),
        footer="TV\u2705 / Binance\u2705 \u00b7 L2\u6807\u51c6\u6863 \u00b7 \u68a2\u6eaa\u5206\u6790\u5361 v5 \u00b7 1080\u00d7\u6df1\u8272\u7ec8\u7aef\u5f0f",
    )
    print(f"OK: {out} \u00b7 {size}")
