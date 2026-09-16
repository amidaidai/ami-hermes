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
from price_format import fmt_price  # noqa: E402  价格精度唯一实现（与原生卡 render_v96 同源）
# 资产分类与主执行周期沿用原生卡口径（单点），避免重排层自写一套「加密/非加密」判断。
from render_v96 import _asset_cn, _main_tf  # noqa: E402

LEVEL_RE = re.compile(r"`?([\d,]{6,12})`?")
NUM_RE = re.compile(r"[\d,]+(?:\.\d+)?")
# 远端行里的周期标记（「4h·支」「1h·VAL」「5m·阻」）含数字，必须先从数字抽取里剔除，
# 否则「4h·支 4,276」会被读成 4~4,276 的区间（旧实现用 `n > 100` 硬过滤糊过去，
# 代价是外汇/小价位远端位（1.1480）被整条丢掉）。2026-09-16 起按周期标记剔除代替。
_TF_TOKEN_RE = re.compile(r"\b\d{1,2}[mhdw]\b|\b[DWM]\b", re.IGNORECASE)
# 「另6带」= 「还有 6 个带」的数量描述，不是价位。旧实现靠 `n > 100` 顺带滤掉它，
# 代价是外汇价位一起被滤；现在按语义显式剔除数量词（无价格段直接跳过）。
_COUNT_TOKEN_RE = re.compile(r"另?\s*\d+\s*[带个]")


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
    """解析原生卡「远端：4h·VAH 79,323 ／ 1h·VAL 77,442 ／ …」为 [{price,mid,label}]。

    2026-09-16：数字抽取前先剔除周期标记（`4h`/`1h`/`5m`/`D`…），不再用
    `n > 100` 过滤 —— 那条规则会把外汇/小价位远端位（1.1480）整条丢掉，
    导致三态退化成「上看 区间外」。
    """
    body = line.split("：", 1)[-1].replace(":", "", 1)
    # 兼容无冒号写法（`远端 78,666（15m·阻）／…`）：否则「远端」会被当成第一个标签。
    body = re.sub(r"^\s*远端\s*", "", body)
    out = []
    for seg in re.split(r"[／/|]", body):
        nums = [float(x.replace(",", ""))
                for x in NUM_RE.findall(_COUNT_TOKEN_RE.sub(" ", _TF_TOKEN_RE.sub(" ", seg)))]
        nums = [n for n in nums if n > 0]
        if not nums:
            continue
        lo, hi = min(nums), max(nums)
        # 标签优先取括号里的结构名（`77,522–77,679（15m·VAL–1h·POC）`）；没有括号才退回
        # 「价格前的最后一个 token」（`4h·支 4,276` → `4h·支`）。
        paren = re.search(r"[（(]([^）)]+)[）)]", seg)
        if paren:
            label = paren.group(1).strip(" ·-—")
        else:
            toks = seg.split()
            label = " ".join(toks[:-1]).strip(" ·-—") if len(toks) > 1 else ""
        out.append({"price": fmt_price(lo) if lo == hi else f"{fmt_price(lo)}–{fmt_price(hi)}",
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
        elif l.startswith("主因 "):
            d["primary_blocker"] = l.replace("主因 ", "").strip()
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
    # 人工方案（PLAN-B）区块（2026-09-15）：「不能自动执行」不等于「不能给方案」，
    # 这块必须原样搬进 v7 卡，只留在附录等于用户还是看不到。
    _plan_block = next((b for b in blocks if "人工方案" in b[:24]), "")
    _plan_rows = _rows(_plan_block) if _plan_block else []
    d["manual_plan"] = _plan_rows[1:] if len(_plan_rows) > 1 else []
    d["manual_plan_prereq"] = next(
        (l.replace("升级前置：", "").strip() for l in lines if l.startswith("升级前置：")), "")
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
        shown = fmt_price(lo) if lo == hi else f"{fmt_price(lo)}–{fmt_price(hi)}"
        mid = (lo + hi) / 2
        rows.append({"role": role, "lo": lo, "hi": hi, "price": shown, "mid": mid,
                     "dist": dist})
    # 主观察位 = 角色里带「主观察」的那一行
    for r in rows:
        r["mark"] = "主观察" in r["role"]
        r["name"] = r["role"].replace("·", " ").replace("–", "-")
    # 2026-09-16：按「距现价」排序（文档与用户口径），最近的位排最前；
    # 原实现按价格降序排，最远的上方位反而排第一（表头注释却写「按距现价排序」）。
    # 现价取不到时退回价格降序（阶梯），保证退化时仍是可读的结构序列。
    if price:
        rows.sort(key=lambda r: (abs(r["mid"] - price), -r["mid"]))
    else:
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
        f"{sym} {fmt_price(price)}   {clock} {session}   {badge}",
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
    """区间位取触发边：上方阻力用上沿、下方支撑用下沿；单价原样。

    2026-09-16：改用 ``fmt_price``（与原生卡同源）—— 此前重排层自写 ``:,.0f``，
    外汇区间边 1.1660 被打成 ``1``。
    """
    if r.get("lo") is not None and r.get("hi") is not None and r["lo"] != r["hi"]:
        return fmt_price(r[side])
    return r["price"]


def _card_main_tf(sym: str, temp: str = "") -> str:
    """主执行周期：优先读原生卡体温行里的 ⭐ 标记（卡面自身口径），退回资产画像。

    2026-09-16：重排层的「怎么做」曾硬编码「等 15 分钟收线」，而黄金主周期是 5m
    —— 不同资产被套了同一句话。
    """
    m = re.search(r"(D|W|\d{1,2}[mhd])\s*⭐", temp or "")
    if m:
        return m.group(1)
    return _main_tf(sym)


def _reason_text(d: dict, raw: str) -> str:
    """把「本模块不适用」这类来源说明换成同卡【裁决】的主拦因。

    2026-09-16：黄金卡首行曾写「非加密不套HALDRO」，而真正拦下它的是
    `risk_constitution/advanced_confluence`。这里只搬同一张卡已有的主因，
    不改结论、不编新原因；老卡（修复前生成的）也因此能被救回一致口径。
    """
    if raw and (("不适用" in raw) or ("非加密不套" in raw)):
        pb = d.get("primary_blocker") or ""
        # 主因行是「码（家族） · N 类 / M 条拦因（明细见证据层）」——首屏只取前半段。
        return pb.split(" · ")[0].strip()
    return raw


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
    ac = _asset_cn(sym)
    stamp = next((p for p in parts if "年" in p and "日" in p), "")
    session = next((p for p in parts if "时段" in p), "")
    badge = next((p for p in parts if "NO-GO" in p or "GO" in p), "")
    clock = re.sub(r"^.*?(\d{1,2}[：:]\d{2}).*$", r"\1", stamp) or stamp
    sess_word = session.replace("时段", "").strip()
    # 首屏第二行＝原生卡「主推 禁做 — 理由」。理由若是「本模块不适用」这类来源说明，
    # 换成同一张卡【裁决】的主拦因 —— 首屏、总结、主因行三处引用同一组原因（2026-09-16）。
    push = (d.get("main_push") or "").strip()
    act = push.split("—")[0].strip() if "—" in push else push
    reason = push.split("—", 1)[1].strip() if "—" in push else ""
    reason = _reason_text(d, reason)
    _push_line = f"{act} — {reason}" if reason else act
    out = [f"**{sym} {fmt_price(price)} · {clock} · {sess_word} · {badge}**", _push_line, ""]

    # ① 盯什么（以现价为锚；现价所在的带当「区间边界」，不当触发也不当目标）
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
    # 2026-09-16：触发价必须有数。现价已在该侧最外层（无更远的相邻结构位）时，
    # 退回「现价所在带」的上下沿 —— 旧实现在这种情况下印出「收上 上沿」「上看 区间外」
    # 这种占位词，读者拿不到可核对的价位，且横盘行与「怎么做」会整段消失。
    dn_label = _edge(dn_trig, "lo") if dn_trig else (
        f"{fmt_price(band_zone['lo'])}（现价带下沿）" if band_zone else "")
    up_label = _edge(up_trig, "hi") if up_trig else (
        f"{fmt_price(band_zone['hi'])}（现价带上沿）" if band_zone else "")
    if dn_label:
        out.append(f"| ↓ | 失守 {dn_label} | "
                   f"下看 {' → '.join(dn_next) if dn_next else '下方暂无具名结构位'} |")
    else:
        out.append("| ↓ | 下方无具名结构位 | 不预判；等新结构位生成后再算 |")
    if up_label:
        out.append(f"| ↑ | 收上 {up_label} | "
                   f"上看 {' → '.join(up_next) if up_next else '上方暂无具名结构位'} |")
    else:
        out.append("| ↑ | 上方无具名结构位 | 不预判；等新结构位生成后再算 |")
    if band_zone:
        out.append(f"| ○ | {fmt_price(band_zone['lo'])}–{fmt_price(band_zone['hi'])} 之间横盘 | "
                   f"不动手（现价在此） |")
    elif dn_label and up_label:
        out.append(f"| ○ | {dn_label}–{up_label} 之间横盘 | 不动手（现价在此） |")
    out.append("")

    # ② 关键位（按距现价排序；观察位用文字标注 —— ⭐ 只代表唯一授权 GO-A，
    # 2026-09-16 前这里给「主观察」打 ⭐，与「⭐ 只在 GO-A 点亮」的卡面规则冲突）
    out += ["**② 关键位**", "", "| 角色 | 价位 | 距现价 |", "|:--|--:|--:|"]
    for r in levels:
        out.append(f"| {r['role'].strip()} | {r['price']} | {r['dist']} |")
    out.append("")
    if remote:
        out.append("远端 " + "／".join(_tag(r) for r in remote))
        out.append("")

    # ③ 多源（原生 ③ 表原文；不适用 / 无读数的行不占正文，缺席原因见末尾「来源说明」）
    mrows = d.get("multi") or []
    out += ["**③ 多源**", "", "| 源 | 读数 | 裁决 |", "|:--|:--|:--|"]
    haldro_na = False
    for c in mrows:
        if len(c) < 3:
            continue
        reading = c[1].strip()
        if "HALDRO" in c[0] and ("不适用" in reading or "非加密不套" in c[2]):
            haldro_na = True
            continue
        if reading in ("—", "-", "", "待刷新"):
            continue
        out.append(f"| {c[0]} | {c[1]} | {c[2]} |")
    out.append("")

    # ④ 人工方案（PLAN-B）：结构成立+方向明确但缺辅证确认 —— 给方案，不给授权。
    # 没有 PLAN-B 时这一段整块不出现，v7 版式与旧卡完全一致。
    plan_rows = d.get("manual_plan") or []
    if plan_rows:
        out += ["**④ 人工方案（非授权·需人工确认）**", "",
                "| 方向 | 参考进场区 | 失效位 | 参考目标区 | R:R |",
                "|:--|--:|--:|--:|--:|"]
        for c in plan_rows:
            if len(c) >= 5:
                out.append(f"| {c[0]} | {c[1]} | {c[2]} | {c[3]} | {c[4]} |")
        out.append("")
        if d.get("manual_plan_prereq"):
            out.append("升级前置：" + d["manual_plan_prereq"])
            out.append("")

    # 2026-09-16：GO-A 卡的首屏已写「可执行」，④ 的执行三件套必须一并搬到重排卡上。
    # 此前 tables 模式整块丢掉 ④ 执行价（`d["plan"]` 解析后从不消费），总结却仍写
    # 「当前不给入场价、只作人工观察」—— 同一张卡自相矛盾。
    executable = ("GO-A" in head) and ("可执行" in push) and not plan_rows
    exec_rows = d.get("plan") or []
    if executable and exec_rows:
        out += ["**④ 执行方案（GO-A·原生卡原值）**", "",
                "| 优先级 | 条件 | 动作 |", "|:--|:--|:--|"]
        for c in exec_rows:
            if len(c) >= 3:
                out.append(f"| {c[0]} | {c[1]} | {c[2]} |")
        out.append("")

    # 总结（大白话三段：最推荐 / 看哪里 / 怎么做 —— 不带符号串、不做术语堆叠）
    band = band_zone or next((r for r in levels if "现价所在带" in r["role"] or "现价带" in r["role"]), None)
    out += ["**总结**", ""]
    reason = _plain(reason)
    if reason and not reason.endswith(("。", "！", "？")):
        reason += "。"
    if plan_rows:
        # 有 PLAN-B 时不能说「当前不给入场价」——那会和自己刚给出的方案打架。
        pr = plan_rows[0]
        out.append(f"- **最推荐**：按上面的人工方案准备。{reason}"
                   f"这不是授权单，需要你自己确认后才动手。")
        out.append(f"- **看哪里**：参考进场区 {pr[1]}、失效位 {pr[2]}、参考目标区 {pr[3]}；"
                   f"价格走到 {pr[2]} 方案作废。")
        out.append(f"- **怎么做**：方案价是区间不是指令；等升级前置解除、主副指标重新共振后"
                   f"再重算成可执行。在此之前只按区间人工判读，系统不自动下单。")
    else:
        zone = (f"现价就在 {band['price']} 这个窄带里，没有优势位置。"
                if band else "现价就夹在这两条线之间，没有优势位置。")
        if executable:
            # GO-A 卡不能同时写「可执行」和「没有优势位置」——那是自相矛盾的首屏。
            out.append(f"- **最推荐**：{_plain(act)}。{reason}执行三件套见 ④（原生卡原值为准）。")
        else:
            out.append(f"- **最推荐**：{_plain(act)}。{reason}{zone if dn_label and up_label else ''}")
        dn_txt = dn_label or "下方结构位"
        up_txt = up_label or "上方结构位"
        out.append(f"- **看哪里**：看 {up_txt}（上方）和 {dn_txt}（下方）这两个价格。"
                   f"收上 {up_txt} 才谈 {'、'.join(up_next) if up_next else '上方空间'}；"
                   f"跌回 {dn_txt} 以下就看向 {'、'.join(dn_next) if dn_next else '下方空间'}。")
        if dn_label and up_label:
            # 主周期取卡面体温行的 ⭐（黄金 5m / 加密 15m …），不再硬编码「15 分钟」；
            # 非加密没有 HALDRO 授权链，不能要求「主副指标重新共振」。
            tf = _card_main_tf(sym, d.get("temp", ""))
            tf_txt = f"等 {tf} 收线" if tf else "等收线"
            confirm = "主副指标重新共振" if ac == "加密" else "结构与来源方向确认"
            tail = ("按 ④ 的三件套执行（入场/止损/目标为原生卡原值，不追现价）"
                    if executable else "当前不给入场价，只作人工观察")
            out.append(f"- **怎么做**：{dn_txt} 到 {up_txt} 之间不动作；"
                       f"{tf_txt}给出方向且{confirm}后再动；{tail}。")
    out.append("")
    if d.get("vwapline"):
        out.append("注　" + d["vwapline"])
    # 主因单列一行：让人一眼看出「为什么不做」，而不是从一串符号里自己拼。
    if d.get("primary_blocker"):
        out.append("　　主因：" + d["primary_blocker"])
    if d.get("route"):
        out.append("　　" + d["route"])
    if haldro_na:
        out.append("　　来源说明：HALDRO 副驾驶不适用于本市场（不参与裁决·占位让给本市场源）")
    return "\n".join(out)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    # 2026-09-16：默认＝表格版 v7（用户选定的交付形态，docs/分析卡模板-v7.md 与技能
    # 一直这么写，代码却默认 panel —— 口径统一到文档一侧）。面板式仍可用：
    # `python scripts/card_reformat.py --style=panel <卡>`。
    style = "panel" if "--style=panel" in sys.argv or "--panel" in sys.argv else "tables"
    p = Path(args[0] if args else "data/auto_card_BTCUSDT_full.md")
    if style == "tables":
        print(render_tables(p))
    else:
        text, w = render(p)
        print(text)
        print(f"\n[面板最大宽度 {w} 列]", file=sys.stderr)
