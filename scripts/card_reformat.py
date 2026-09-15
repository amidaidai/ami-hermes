"""分析卡重排器：把 auto_card 的原生卡（data/auto_card_<SYM>_full.md）重排成三层结构。

设计依据（2026-09-14 联网对标）：
- NN/g 渐进披露：首屏只放「用户最先要用」的核心；次要项按需展开，而且“出现在首屏”本身就是重要性信号。
- Tufte data-ink：能删而不损失信息的“墨”一律删；对齐做对了，框线就是冗余。
- Mission Log 数据表：数字用等宽/tabular 字形，文本左对齐；**居中会行列参差**，最难扫。
- NN/g 指标/校验/通知：只有“需要动作”的信息才配打断用户——同一裁决重复 9 次属于噪音。

输出三层：
L1 决策层（首屏，必读，≤6 行）
L2 操作层（扫读：体温 / 三态 / 价位阶梯 / 验证）
L3 附录（默认不必读：多源质量、方案、订单流、闸门、审计）

用法：python scripts/card_reformat.py [data/auto_card_BTCUSDT_full.md]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from card_panel import pad, render_ladder, visual_width  # noqa: E402

LEVEL_RE = re.compile(r"`?([\d,]{6,12})`?")
NUM_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def _rows(md: str) -> list[list[str]]:
    out = []
    for line in md.split("\n"):
        if line.strip().startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append(cells)
    return out


def _first_number(text: str) -> float | None:
    m = NUM_RE.search(text or "")
    return float(m.group(0).replace(",", "")) if m else None


def _remote_levels(line: str) -> list[dict]:
    """解析原生卡「远端：4h·VAH 79,323 ／ 1h·VAL 77,442 ／ …」为 [{price,mid,label}]。"""
    body = line.split("：", 1)[-1].replace(":", "", 1)
    out = []
    for seg in re.split(r"[／/|]", body):
        nums = [float(x.replace(",", "")) for x in NUM_RE.findall(seg)]
        nums = [n for n in nums if n > 100]
        if not nums:
            continue
        lo, hi = min(nums), max(nums)
        toks = seg.split()
        label = " ".join(toks[:-1]).strip(" ·-—") if len(toks) > 1 else ""
        out.append({"price": f"{lo:,.0f}" if lo == hi else f"{lo:,.0f}–{hi:,.0f}",
                    "mid": (lo + hi) / 2, "label": label, "hi": hi, "lo": lo})
    return out


def parse(card_path: Path) -> dict:
    lines = card_path.read_text(encoding="utf-8").split("\n")
    d: dict = {"raw_lines": lines}
    d["header"] = lines[0].replace("📊", "").strip() if lines else ""
    for l in lines[:6]:
        if l.startswith("⚠️") or l.startswith("🔵") or l.startswith("⭐"):
            d["main_push"] = l.strip()
        if l.startswith("结构："):
            d["structure"] = l.replace("结构：", "").strip()
    for l in lines:
        if l.startswith("①"):
            d["temp"] = l.replace("①", "").replace("周期体温", "").strip()
        elif l.startswith("副读"):
            d["sub_read"] = l.replace("副读", "").strip()
        elif l.startswith("远端"):
            d["remote"] = _remote_levels(l)
        elif l.startswith("VWAP/EMA/DO"):
            d["vwapline"] = l.replace("VWAP/EMA/DO：", "").strip()
        elif l.startswith("【裁决】"):
            d["verdict"] = l.replace("【裁决】", "").strip()
        elif l.startswith("管线路由"):
            d["route"] = l.strip()
        elif l.startswith("**裁决**"):
            d["gate_verdict"] = l.replace("**裁决**:", "").strip()
    # 关键位表（② 下第一张表）
    blocks = re.split(r"\n(?=[①-④⓪#])", "\n".join(lines))
    key_tbl = next((b for b in blocks if b.lstrip().startswith("②")), "")
    d["key_levels"] = _rows(key_tbl)[1:]
    d["multi"] = _rows(next((b for b in blocks if b.lstrip().startswith("③")), ""))[1:]
    d["plan"] = _rows(next((b for b in blocks if b.lstrip().startswith("④")), ""))[1:]
    d["appendix"] = "\n".join(b.strip() for b in blocks[3:] if b.strip())
    return d


def build_levels(key_levels: list[list[str]], price: float) -> list[dict]:
    rows = []
    for cells in key_levels:
        if len(cells) < 3:
            continue
        role, price_cell, dist = cells[0], cells[1], cells[2]
        nums = [float(x.replace(",", "")) for x in NUM_RE.findall(price_cell)]
        if not nums:
            continue
        lo, hi = min(nums), max(nums)
        shown = f"{lo:,.0f}" if lo == hi else f"{lo:,.0f}–{hi:,.0f}"
        mid = (lo + hi) / 2
        rows.append({"role": role, "lo": lo, "hi": hi, "price": shown, "mid": mid,
                     "dist": dist})
    # 主观察位 = 角色里带「主观察」的那一行
    for r in rows:
        r["mark"] = "主观察" in r["role"]
        r["name"] = r["role"].replace("·", " ").replace("–", "-")
    rows.sort(key=lambda r: -r["mid"])
    return rows


def watch_lines(rows: list[dict], remote: list[dict] | None = None) -> list[str]:
    """从关键位表机械推导三态：主观察位为决策线，上下取相邻位做目标。

    不做任何主观判断——只重排原生卡已有的价位与角色，避免“重排时偷偷改结论”。
    下方无近位时，退回原生卡「远端」行里已有的更低结构位做目标（仍是卡面原文）。
    """
    if not rows:
        return []
    main = next((r for r in rows if r["mark"]), rows[len(rows) // 2])
    below = [r for r in rows if r["mid"] < main["mid"]]
    above = [r for r in rows if r["mid"] > main["mid"]]
    out = [f"盯 {main['price']}（{main['name']}）"]
    down = [r["price"] for r in sorted(below, key=lambda r: -r["mid"])][:2]
    if not down and remote:
        down = [r["price"] for r in sorted(remote, key=lambda r: -r["mid"]) if r["mid"] < main["mid"]][:2]
    if down:
        out.append(_fit(f"  ↓ 收破 {main['price']} → ", down))
    if above:
        nearest = above[-1]
        targets = [r["price"] for r in above[:-1]][::-1][:2]
        out.append(_fit(f"  ↑ 收上 {nearest['price']} → ", targets) if targets
                   else f"  ↑ 收上 {nearest['price']} → 上看区间外")
    out.append("  ○ 两线之间 → 不动手")
    return out


def _fit(prefix: str, items: list[str], limit: int = 44) -> str:
    """按视觉宽度挑目标价位，装不下就少放一个（不硬切数字）。"""
    tail = ""
    for it in items:
        cand = f"{tail} / {it}" if tail else it
        if visual_width(prefix + cand) > limit:
            break
        tail = cand
    return prefix + (tail or "远端")

def _clip(text: str, cols: int = 12) -> str:
    """按视觉宽度裁剪（中文算 2 列），保证面板不超宽。"""
    out = ""
    for ch in text:
        if visual_width(out + ch) > cols:
            break
        out += ch
    return out


def _short_temp(text: str) -> str:
    """五周期体温压到一行 ≤44 列：去掉重复的「等BOS」冗余、用单字方向词。"""
    x = text.replace("·等BOS", "").replace("等BOS", "")
    x = (x.replace("空趋势", "空").replace("多趋势", "多")
          .replace("转多", "多").replace("转空", "空")
          .replace("BOS↓", "↓").replace("BOS↑", "↑").replace("⭐", ""))
    x = re.sub(r"\s*·\s*", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return _clip("体温 " + x, 44)


def _short_role(role: str) -> str:
    """角色名压缩：① 去掉「/支撑」等冗词 ② 只保留一个结构标签（VAH/VAL/VWAP/POC）。"""
    base = role.split("·")[0].strip().lstrip("⚖").strip()
    base = (base.replace("现价所在带", "现价带").replace("失效/支撑带", "失效带")
                .replace("上沿阻力簇", "上沿阻力").replace("近端转撑", "近端转撑"))
    tag = next((t for t in ("VAH", "VAL", "VWAP", "POC") if t in role), "")
    return f"{base} {tag}".strip()


def render(card_path: Path) -> str:
    d = parse(card_path)
    price = _first_number((d.get("structure") or "").replace("现价", "")) or 0.0
    levels = build_levels(d.get("key_levels") or [], price)

    head = d.get("header", "")
    sym = head.split("·")[0].strip() if "·" in head else head.split()[0]
    parts = [p.strip() for p in head.split("·")]
    stamp = next((p for p in parts if "年" in p and "日" in p), "")
    session = next((p for p in parts if "时段" in p), "")
    badge = next((p for p in parts if "NO-GO" in p or "GO" in p), "")
    clock = re.sub(r"^.*?(\d{1,2}[：:]\d{2}).*$", r"\1", stamp) or stamp
    # 首屏不带冗余结构行：上/下位已由价位阶梯给出，避免同一事实写两遍
    panel = [
        f"{sym} {price:,.0f}   {clock} {session}   {badge}",
        d.get("main_push", ""),
    ]
    if d.get("temp"):
        panel.append(_short_temp(d["temp"]))
    panel += [""] + watch_lines(levels, d.get("remote"))
    panel.append("")
    panel += render_ladder([
        {"price": r["price"], "name": _short_role(r["role"]), "dist": r["dist"], "mark": r["mark"]}
        for r in levels
    ], gap=1)
    panel = [p for p in panel if p is not None]

    # 验证行：只留主/副/合约三条最硬的（其余下沉附录）
    mrows = d.get("multi") or []
    picks = []
    for key in ("主驾驶", "副驾驶", "订单流", "质量"):
        for c in mrows:
            if len(c) >= 2 and key in c[0]:
                cell = c[1]
                if key == "订单流":
                    cell = " · ".join(cell.split(" · ")[:2])
                picks.append(f"{c[0].replace('SVP主驾驶','主').replace('HALDRO副驾驶','副')} {cell}")
                break
    out = ["```text", *panel, "```", ""]
    out.append("**验证**　" + " ｜ ".join(picks[:3]))
    out.append("")
    out.append("<details><summary>附录：多源质量 · 方案 · 订单流 · 闸门 · 审计（不必读）</summary>")
    out.append("")
    appendix = d.get("appendix", "")
    # 附录取自 ② 之后的全部原文；③ 多源表已在上方“验证”层压缩呈现，这里保留完整原文供审计
    out.append(appendix)
    out.append("")
    out.append("</details>")
    if d.get("vwapline"):
        out.append("")
        out.append("注　" + _clip(d["vwapline"], 60))
    if d.get("route"):
        out.append("　　" + d["route"])
    return "\n".join(out), max((visual_width(l) for l in panel), default=0)


_PLAIN_MAP = [
    ("⚠️主推 禁做", "等待，不做单"),
    ("⚠主推 禁做", "等待，不做单"),
    ("主推 禁做", "等待，不做单"),
    ("🔵主推 等确认", "等待确认后再动"),
    ("主推 等确认", "等待确认后再动"),
    ("⭐主推", "主推"),
    ("副S3冲突", "副指标 S3 冲突（主副方向不一致）"),
    ("副S4降权", "副指标 S4 降权（主副方向不一致）"),
    ("CVD/OI背离", "CVD 与 OI 背离（量价不一致）"),
    ("R:R不足(<1:2)", "盈亏比不足 1:2"),
    ("R:R不足", "盈亏比不足"),
    ("·", "、"),
    ("／", "、"),
    ("—", "，"),
]
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F"
                       "\u2190-\u21FF\u25A0-\u25FF\u2699\u2696\u26A0\u2B50]")


def _plain(text: str) -> str:
    """把原生卡的符号串换成人话（只换措辞，不改数字与结论方向）。"""
    s = text or ""
    for k, v in _PLAIN_MAP:
        s = s.replace(k, v)
    s = _EMOJI_RE.sub("", s)
    s = re.sub(r"[，、；]\s*[，、；]", "，", s)
    return re.sub(r"\s{2,}", " ", s).strip(" ，、；")


def _edge(r: dict, side: str = "hi") -> str:
    """区间位取触发边：上方阻力用上沿、下方支撑用下沿；单价原样。"""
    if r.get("lo") is not None and r.get("hi") is not None and r["lo"] != r["hi"]:
        return f"{r[side]:,.0f}"
    return r["price"]


def _tag(r: dict) -> str:
    """远端位带结构标签：79,323 → 79,323（4h·VAH）。"""
    return f"{r['price']}（{r['label']}）" if r.get("label") else r["price"]


def render_tables(card_path: Path) -> str:
    """表格版（v7，用户 2026-09-14 选定）：① 盯什么 ② 关键位 ③ 多源 + 末尾【总结】。

    与面板版共用 parse/levels，只是换成 markdown 窄表；数字一律搬运原生卡，不改写。
    三态锚点=现价：上方最近位=收上看什么，下方最近位=失守看什么，中间不动手。
    """
    d = parse(card_path)
    price = _first_number((d.get("structure") or "").replace("现价", "")) or 0.0
    levels = build_levels(d.get("key_levels") or [], price)
    remote = d.get("remote") or []

    head = d.get("header", "")
    parts = [p.strip() for p in head.split("·")]
    sym = parts[0] if parts else head
    stamp = next((p for p in parts if "年" in p and "日" in p), "")
    session = next((p for p in parts if "时段" in p), "")
    badge = next((p for p in parts if "NO-GO" in p or "GO" in p), "")
    clock = re.sub(r"^.*?(\d{1,2}[：:]\d{2}).*$", r"\1", stamp) or stamp
    sess_word = session.replace("时段", "").strip()
    out = [f"**{sym} {price:,.0f} · {clock} · {sess_word} · {badge}**", d.get("main_push", ""), ""]

    # ① 盯什么（以现价为锚；现价所在的带既不当触发也不当目标）
    band_zone = next((r for r in levels if r["lo"] <= price <= r["hi"]), None)
    cand = [r for r in levels if r is not band_zone]
    below = sorted([r for r in cand if r["mid"] < price], key=lambda r: -r["mid"])
    above = sorted([r for r in cand if r["mid"] > price], key=lambda r: r["mid"])
    up_trig = above[0] if above else None
    dn_trig = below[0] if below else None
    dn_next = [r["price"] for r in below[1:]][:2]
    if not dn_next:
        dn_next = [_tag(r) for r in sorted(remote, key=lambda r: -r["mid"]) if r["mid"] < price][:2]
    up_next = [r["price"] for r in above[1:]][:2]
    if not up_next:
        up_next = [_tag(r) for r in sorted(remote, key=lambda r: r["mid"]) if r["mid"] > price][:1]
    out += ["**① 盯什么**", "", "| 状态 | 触发 | 动作 |", "|:--|:--|:--|"]
    dn_label = _edge(dn_trig, "lo") if dn_trig else "主观察位"
    up_label = _edge(up_trig, "hi") if up_trig else "上沿"
    out.append(f"| ↓ | 失守 {dn_label} | "
               f"下看 {' → '.join(dn_next) if dn_next else '区间外'} |")
    out.append(f"| ↑ | 收上 {up_label} | "
               f"上看 {' → '.join(up_next) if up_next else '区间外'} |")
    if dn_trig and up_trig:
        out.append(f"| ○ | {dn_label}–{up_label} 之间横盘 | 不动手（现价在此） |")
    out.append("")

    # ② 关键位（按距现价排序，主观察位加 ⭐）
    out += ["**② 关键位**", "", "| 角色 | 价位 | 距现价 |", "|:--|--:|--:|"]
    for r in levels:
        mark = "⭐" if r["mark"] else ""
        out.append(f"| {mark}{r['role'].strip()} | {r['price']} | {r['dist']} |")
    out.append("")
    if remote:
        out.append("远端 " + "／".join(f"{r['price']}（{r['label']}）" for r in remote))
        out.append("")

    # ③ 多源（原生 ③ 表原文）
    mrows = d.get("multi") or []
    out += ["**③ 多源**", "", "| 源 | 读数 | 裁决 |", "|:--|:--|:--|"]
    for c in mrows:
        if len(c) >= 3:
            out.append(f"| {c[0]} | {c[1]} | {c[2]} |")
    out.append("")

    # 总结（大白话三段：最推荐 / 看哪里 / 怎么做 —— 不带符号串、不做术语堆叠）
    band = band_zone or next((r for r in levels if "现价所在带" in r["role"] or "现价带" in r["role"]), None)
    push = (d.get("main_push") or "").strip()
    act = push.split("—")[0].strip() if "—" in push else push
    reason = push.split("—", 1)[1].strip() if "—" in push else ""
    out += ["**总结**", ""]
    reason = _plain(reason)
    if reason and not reason.endswith(("。", "！", "？")):
        reason += "。"
    zone = (f"现价就在 {band['price']} 这个窄带里，没有优势位置。"
            if band else "现价就夹在这两条线之间，没有优势位置。")
    out.append(f"- **最推荐**：{_plain(act)}。{reason}{zone if dn_trig and up_trig else ''}")
    dn_txt = dn_label if dn_trig else "主观察位"
    up_txt = up_label if up_trig else "上沿"
    out.append(f"- **看哪里**：看 {up_txt}（上方）和 {dn_txt}（下方）这两个价格。"
               f"收上 {up_txt} 才谈 {'、'.join(up_next) if up_next else '上方空间'}；"
               f"跌回 {dn_txt} 以下就看向 {'、'.join(dn_next) if dn_next else '下方空间'}。")
    if dn_trig and up_trig:
        out.append(f"- **怎么做**：{dn_txt} 到 {up_txt} 之间不动作；"
                   f"等 15 分钟收线给出方向、主副指标重新共振后再重算。当前不给入场价，只作人工观察。")
    out.append("")
    if d.get("vwapline"):
        out.append("注　" + d["vwapline"])
    if d.get("route"):
        out.append("　　" + d["route"])
    return "\n".join(out)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    style = "tables" if "--style=tables" in sys.argv or "--tables" in sys.argv else "panel"
    p = Path(args[0] if args else "data/auto_card_BTCUSDT_full.md")
    if style == "tables":
        print(render_tables(p))
    else:
        text, w = render(p)
        print(text)
        print(f"\n[面板最大宽度 {w} 列]", file=sys.stderr)
