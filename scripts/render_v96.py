#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 v9.9 Telegram 驾驶舱渲染器。

v9.9 目标：手机端好看，但不牺牲棠溪双指标/多周期能力。
- 结构位前置：价格前必须带 POC/VWAP/VAH/VAL/FVG/阻支标签。
- 多周期必须显式：D/4h/1h/15m/5m 全部出现，按看盘顺序 D→4h→1h→15m→5m（自上而下，背景→执行层）。
- 双指标必须显式：SVP 主驾驶 + HALDRO 副驾驶，不再压成一句散文。
- 裁决唯一主推：⭐主推只给一个，🔁备选只是失效路径。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone, timedelta

# 棠溪看盘顺序：从上往下（D背景 → 4h → 1h → 15m → 5m主执行层）
TF_ORDER = ("D", "4h", "1h", "15m", "5m")

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (OSError, ValueError):
    pass


TZ = timezone(timedelta(hours=8))


def _num(v, digits=0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    if f >= 1000:
        return f"{f:,.0f}"
    if digits:
        return f"{f:,.{digits}f}"
    return f"{f:.2f}"


def _price(v):
    n = _num(v)
    return f"`{n}`" if n != "—" else "`—`"


def _raw_price(v):
    return _num(v).replace(",", "") if _num(v) != "—" else "—"


def _cell(v) -> str:
    text = "—" if v is None or v == "" else str(v)
    return text.replace("|", "／").replace(chr(13), " ").replace(chr(10), " ").strip()


def _asset_cn(symbol: str) -> str:
    su = symbol.upper()
    if "XAU" in su or "GOLD" in su:
        return "贵金属"
    if "CALL" in su or "PUT" in su or "OPTION" in su:
        return "期权"
    if su.endswith("USDT") or "BTC" in su or "ETH" in su or "SOL" in su:
        return "加密"
    if any(x in su for x in ("EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF")) and "USDT" not in su:
        return "外汇"
    if su.rstrip("1!") in {"ES", "NQ", "CL", "GC", "SI", "NG", "YM", "RTY", "MES", "MNQ"}:
        return "期货"
    if su.isalpha() and len(su) <= 5:
        return "股票"
    return "多资产"


def _display_symbol(symbol: str) -> str:
    su = symbol.upper()
    ac = _asset_cn(su)
    if ac == "加密":
        return f"{su if su.endswith('.P') else su + '.P'} · BINANCE"
    if ac == "贵金属":
        return f"{su} · OANDA"
    if ac == "外汇":
        return f"{su} · OANDA"
    if ac == "股票":
        return f"{su} · NASDAQ"
    if ac == "期货":
        return f"{su} · CME"
    if ac == "期权":
        return f"{su} · OPRA"
    return su


def _main_tf(symbol: str) -> str:
    return {"加密": "15m", "贵金属": "5m", "外汇": "15m", "股票": "1h", "期货": "15m", "期权": "跟底层"}.get(_asset_cn(symbol), "15m")


def _bias_label(direction: str, status: str) -> str:
    if str(status).startswith("X"):
        return "禁做观察"
    if direction == "short":
        return "偏空"
    if direction == "long":
        return "偏多"
    return "观望"


def _status_emoji(status: str) -> str:
    s = str(status or "")
    if s.startswith("A"):
        return "🟢"
    if s.startswith("B"):
        return "🔵"
    if s.startswith("X"):
        return "⚠️"
    if s.startswith("C"):
        return "🟡"
    return "⚪"


def _dir_emoji(direction: str) -> str:
    if direction == "long":
        return "🟢"
    if direction == "short":
        return "🔴"
    return "🔵"


def _tf_emoji(tf_data: dict) -> str:
    if not isinstance(tf_data, dict) or not tf_data:
        return "⚪"
    desc = str(tf_data.get("description") or tf_data.get("direction") or tf_data.get("svp") or "")
    if any(w in desc for w in ("禁", "X")):
        return "⚠️"
    if any(w in desc for w in ("多", "long", "涨")):
        return "🟢"
    if any(w in desc for w in ("空", "short", "跌")):
        return "🔴"
    return "🔵"


def _short_tf_text(tf_data: dict) -> str:
    if not isinstance(tf_data, dict) or not tf_data:
        return "待刷新"
    for key in ("description", "svp", "direction", "grade", "action"):
        v = tf_data.get(key)
        if v:
            return _cell(v)[:18]
    return "待判"


def _sub_tf_text(tf_data: dict) -> str:
    if not isinstance(tf_data, dict) or not tf_data:
        return "待刷新"
    for key in ("sub_indicator", "sub", "volume_agg", "oi", "sub_composite", "composite"):
        v = tf_data.get(key)
        if v:
            return _cell(v)[:22]
    return "待刷新"


def _vwap_pos(tf_data: dict, price: float | None) -> str:
    if not isinstance(tf_data, dict):
        return "—"
    vwap = tf_data.get("vwap") or tf_data.get("S VWAP") or tf_data.get("s_vwap")
    px = tf_data.get("close") or tf_data.get("price") or price
    try:
        if vwap and px:
            diff = (float(px) - float(vwap)) / float(vwap) * 100
            side = "上方" if diff > 0 else "下方" if diff < 0 else "贴合"
            return f"VWAP{side}{diff:+.2f}%"
    except Exception:
        pass
    return "—"


def _level_kind(name: str, side: str, level: float, price: float | None) -> tuple[str, str]:
    raw = f"{side} {name}".lower()
    cn = f"{side} {name}"
    if "fvg" in raw:
        label = "FVG"
    elif "vwap" in raw:
        label = "VWAP"
    elif "vah" in raw or "上沿" in cn:
        label = "VAH"
    elif "val" in raw or "下沿" in cn:
        label = "VAL"
    elif "poc" in raw:
        label = "POC"
    elif "npoc" in raw:
        label = "nPOC"
    elif "高" in cn or "res" in raw or "阻" in cn:
        label = "阻"
    elif "低" in cn or "sup" in raw or "支" in cn:
        label = "支"
    else:
        label = "位"
    if price is None:
        icon = "⚖"
    elif level > float(price):
        icon = "🔴"
    elif level < float(price):
        icon = "🟢"
    else:
        icon = "⚖"
    return label, icon


def _klines_to_levels(klines: dict, price: float | None) -> list[dict]:
    clean = []
    if not isinstance(klines, dict):
        return clean
    for tf in ("D", "4h", "1h", "15m", "5m"):
        k = klines.get(tf, {}) if isinstance(klines, dict) else {}
        if not isinstance(k, dict):
            continue
        for key, typ in (
            ("vah", "VAH"), ("poc", "POC"), ("val", "VAL"),
            ("high", "高点"), ("low", "低点"), ("vwap", "VWAP"),
            ("bull_fvg_ce", "FVG多CE"), ("bear_fvg_ce", "FVG空CE"),
        ):
            v = k.get(key)
            if v:
                try:
                    clean.append({"level": float(v), "side": typ, "name": f"{tf}{typ}"})
                except Exception:
                    pass
    return clean


def _prepare_levels(levels: list[dict], klines: dict, price: float | None) -> list[dict]:
    all_levels = list(levels or []) + _klines_to_levels(klines or {}, price)
    seen = set()
    clean = []
    for item in all_levels:
        try:
            lvl = float(item.get("level"))
        except (TypeError, ValueError, AttributeError):
            continue
        if not lvl:
            continue
        bucket = round(lvl, 2)
        if bucket in seen:
            continue
        seen.add(bucket)
        side = item.get("side", "level")
        name = item.get("display_name") or item.get("name") or side
        kind, icon = _level_kind(str(name), str(side), lvl, price)
        if price:
            dist = (lvl - float(price)) / float(price) * 100
            dist_txt = f"{dist:+.2f}%"
        else:
            dist_txt = "—"
        clean.append({"level": lvl, "side": side, "name": name, "kind": kind, "icon": icon, "dist": dist_txt})
    clean.sort(key=lambda x: abs(x["level"] - float(price or 0)))
    return clean[:7]


def _structure_table(levels: list[dict], price: float | None) -> str:
    """结构位前置：真管道表（上结构位 / 现价 / 下结构位）。替代旧的全角竖线伪表格行。"""
    if not price:
        return "| 结构位 | 价格 | 距现价 |\n|:---|:---:|---:|\n| ⚠现价 | 待采集 | — |"
    above = [x for x in levels if x["level"] > float(price)]
    below = [x for x in levels if x["level"] < float(price)]
    a = above[0] if above else None
    b = below[0] if below else None
    rows = []
    if a:
        rows.append(f"| {a['icon']}{a['kind']} 上 | `{_num(a['level'])}` | {a['dist']} |")
    rows.append(f"| ⚖**现价** | `{_num(price)}` | — |")
    if b:
        rows.append(f"| {b['icon']}{b['kind']} 下 | `{_num(b['level'])}` | {b['dist']} |")
    return "| 结构位 | 价格 | 距现价 |\n|:---|:---:|---:|\n" + "\n".join(rows)


def _dual_short(dual: dict | None, ac: str) -> tuple[str, str, str]:
    if not isinstance(dual, dict):
        if ac == "加密":
            return "SVP待读", "HALDRO待读", "双指标未注入"
        return "SVP/市场数据", "副驾驶不适用", "按本市场源验证"
    svp = dual.get("svp_state") or dual.get("svp_direction") or "SVP待判"
    hal = dual.get("haldro_direction") or "HALDRO待判"
    verdict = dual.get("direction_verdict") or dual.get("flow_verdict") or "待裁决"
    return _cell(svp)[:28], _cell(hal)[:34], _cell(verdict)[:18]


def _multi_source_line(cvd_dir, cvd_quality, taker_dir, taker_ratio, funding_rate, fg_v, kill_zone, dual: dict | None) -> str:
    parts = []
    if cvd_dir:
        cvd_emoji = "🟢" if cvd_dir in ("买", "buy", "多", "long") else "🔴" if cvd_dir in ("卖", "sell", "空", "short") else "🔵"
        parts.append(f"CVD{cvd_emoji}{cvd_dir}{cvd_quality or ''}")
    if taker_dir:
        parts.append(f"主动买卖{taker_dir} {taker_ratio or ''}")
    if funding_rate:
        parts.append(f"Funding {funding_rate}")
    if isinstance(dual, dict) and dual.get("haldro_confirm"):
        parts.append(str(dual.get("haldro_confirm"))[:18])
    if fg_v:
        parts.append(f"恐贪{fg_v}")
    if kill_zone:
        parts.append(f"时段{kill_zone}")
    return " · ".join(parts) if parts else "待采集"


def render_v96_card(
    symbol: str,
    status: str,
    direction: str,
    price: float,
    high,
    low,
    chg,
    tf_lines: str,
    cvd_dir: str,
    cvd_quality: str,
    taker_dir: str,
    taker_ratio,
    funding_rate,
    kill_zone: str,
    vwap_ema: dict,
    fg_v: str,
    levels: list[dict],
    bearish: bool,
    st_a: dict,
    st_b: dict,
    rr_a: float,
    rr_b: float,
    rr_a_note: str,
    rr_b_note: str,
    risk_amt: float,
    leverage_text: str,
    inv_line,
    prot_status: str,
    data_grade: str,
    sweep_state: str,
    displacement: str,
    one_reason: str,
    model_id: str,
    n5,
    eng_conf,
    klines: dict = None,
    tv_dmi: dict = None,
    dual_indicator: dict | None = None,
) -> str:
    klines = klines or {}
    st_a = st_a or {"stop": None, "target": None}
    st_b = st_b or {"stop": None, "target": None}
    now = datetime.now(TZ).strftime("%Y年%m月%d日%H：%M")
    ac = _asset_cn(symbol)
    bias = _bias_label(direction, status)
    display = _display_symbol(symbol)
    levels_prepared = _prepare_levels(levels or [], klines, price)
    svp_short, haldro_short, dual_verdict = _dual_short(dual_indicator, ac)

    dir_a = "空" if bearish else "多"
    dir_b = "多" if bearish else "空"
    s_emoji = _status_emoji(status)
    dir_emoji = _dir_emoji(direction)

    if str(status).startswith("X") or rr_a < 2:
        action_summary = "⚠禁做 — 主线无优势或R:R不足"
        recommend_name = "⚠️主推 禁做"
        recommend_trigger = "现价无优势"
        recommend_exec = "不下单；等R:R≥1:2且主副指标重新共振"
        recommend_rr = "—"
        backup_name = f"🔵观察 {dir_a}"
        backup_trigger = "重新站回/跌破结构位后再算"
        backup_exec = "只做提醒，不做执行"
        backup_rr = "重算"
    elif str(status).startswith("A"):
        action_summary = f"{dir_emoji} {bias}可执行 — 只做最推荐方案"
        recommend_name = f"⭐主推 {dir_a}"
        recommend_trigger = f"{_price(price)}确认"
        recommend_exec = f"{dir_a} {_price(price)} 损{_price(st_a.get('stop'))} 标{_price(st_a.get('target'))}"
        recommend_rr = f"1:{rr_a:.1f}"
        backup_name = f"🔁备选 {dir_b}"
        backup_trigger = "主推失效后反向确认"
        backup_exec = f"{dir_b}失效路径；不与主推平权"
        backup_rr = f"1:{rr_b:.1f}" if rr_b >= 2 else "观察"
    else:
        action_summary = f"🔵 {bias}等确认 — 先等结构位触发"
        recommend_name = "🔵主推 等确认"
        recommend_trigger = "未到最优触发"
        recommend_exec = f"等待{dir_a}触发；不追现价；损/标触发后计算"
        recommend_rr = "待确认"
        backup_name = f"🔁备选 {dir_b}"
        backup_trigger = "反向破位后"
        backup_exec = f"{dir_b}方案仅作失效预案"
        backup_rr = f"1:{rr_b:.1f}" if rr_b >= 2 else "观察"

    tf_emojis = []
    for tf in TF_ORDER:
        tf_emojis.append(f"{tf}{_tf_emoji(klines.get(tf, {}))}")
    mtf_summary = " · ".join(tf_emojis)
    multi_src_line = _multi_source_line(cvd_dir, cvd_quality, taker_dir, taker_ratio, funding_rate, fg_v, kill_zone, dual_indicator)

    lines: list[str] = []
    lines.append(f"📊 {display} · {now} · {s_emoji}{status} · {bias}")
    lines.append("【现在】结构位")
    lines.append(_structure_table(levels_prepared, price))
    rec_name_clean = recommend_name.replace('⭐主推 ', '').replace('⚠️主推 ', '').replace('🔵主推 ', '')
    lines.append("【决策摘要】")
    lines.append("| 维度 | 内容 |")
    lines.append("|:---|:---|")
    lines.append(f"| 做法 | 只执行{rec_name_clean} · {recommend_trigger} · {recommend_rr} |")
    lines.append(f"| 依据 | SVP {svp_short} · HALDRO {haldro_short} · {dual_verdict} |")
    lines.append("")

    lines.append("① 周期体温 / 多周期定位（D→4h→1h→15m→5m）")
    lines.append("| 周期 | SVP主指标 | HALDRO副指标 | 位置 |")
    lines.append("|:---:|:---|:---|:---|")
    main_tf = _main_tf(symbol)
    for tf in TF_ORDER:
        k = klines.get(tf, {}) if isinstance(klines, dict) else {}
        mark = " ⭐主" if tf == main_tf else ""
        lines.append(f"| {tf}{mark} | {_tf_emoji(k)} {_short_tf_text(k)} | {_sub_tf_text(k)} | {_vwap_pos(k, price)} |")
    lines.append(f"→ 主执行{main_tf} · 自上而下确认（D背景→{main_tf}执行）")
    lines.append("")

    lines.append("② 关键位 / 结构关键位")
    lines.append("| 结构位 | 价格 | 用法 | 距现价 |")
    lines.append("|:---|:---:|:---|---:|")
    for item in levels_prepared[:6]:
        use = item.get("name") or item.get("side") or "关键位"
        lines.append(f"| {item['icon']}{item['kind']} | {_price(item['level'])} | {_cell(use)[:26]} | {item['dist']} |")
    if not levels_prepared:
        lines.append("| 待刷新 | `—` | TV结构位未注入，禁追 | — |")
    lines.append("")

    lines.append("③ 多源验证 / 双指标")
    lines.append("| 能力 | 读数 | 裁决 |")
    lines.append("|:---|:---|:---|")
    lines.append(f"| SVP主驾驶 | {_cell(svp_short)} | 结构/入场/止损/目标优先 |")
    lines.append(f"| HALDRO副驾驶 | {_cell(haldro_short)} | {_cell(dual_verdict)} |")
    lines.append(f"| 订单流 | {_cell(multi_src_line)} | CVD/OI不配则降级 |")
    if isinstance(dual_indicator, dict) and dual_indicator.get("haldro_quality"):
        lines.append(f"| 质量 | {_cell(dual_indicator.get('haldro_quality'))[:34]} | 覆盖不足不追 |")
    lines.append("")

    lines.append("④ 最推荐方案")
    lines.append("| 优先级 | 条件 | 动作 | R:R |")
    lines.append("|:---|:---|---|---:|")
    lines.append(f"| {recommend_name} | {_cell(recommend_trigger)} | {_cell(recommend_exec)} | {recommend_rr} |")
    lines.append(f"| {backup_name} | {_cell(backup_trigger)} | {_cell(backup_exec)} | {backup_rr} |")
    lines.append("| ⚠️禁止 | 追单/数据过期/主副冲突 | 夹击+去杠杆+R:R不足 | — |")
    lines.append("")

    lines.append(f"【裁决】{action_summary} · 风控{_num(risk_amt, 2)}U · {leverage_text or ''}")
    lines.append(f"失效 {_price(inv_line) if inv_line else '`—`'} · 数据{data_grade} · 主副指标已纳入")
    return "\n".join(lines) + "\n"


render_v8_card = render_v96_card


def _dual_indicator_rows(dual: dict | None, asset_cn: str) -> list[str]:
    if not isinstance(dual, dict):
        return []
    return [
        f"| SVP | {_cell(dual.get('svp_state'))} | {_cell(dual.get('svp_execution'))} |",
        f"| HALDRO | {_cell(dual.get('haldro_direction'))} | {_cell(dual.get('direction_verdict'))} |",
    ]


def _tf_row(tf: str, k: dict, fallback: str = "") -> str:
    if not isinstance(k, dict) or not k:
        return f"| {tf} | 待刷新 | 待刷新 | — | 待刷新 |"
    return f"| {_cell(tf)} | {_cell(_short_tf_text(k))} | {_cell(_sub_tf_text(k))} | {_cell(k.get('sub_composite') or k.get('composite') or '—')} | {_cell(_vwap_pos(k, k.get('close') or k.get('price')))} |"


def _level_rows(levels: list[dict], price: float | None, klines: dict | None = None) -> list[str]:
    rows: list[str] = []
    for item in _prepare_levels(levels or [], klines or {}, price)[:6]:
        use = item.get("name") or item.get("side") or "关键位"
        rows.append(f"| {item['icon']}{item['kind']} | {_price(item['level'])} | {_cell(use)} | {_cell(item['dist'])} |")
    if not rows:
        rows.append("| 待刷新 | `—` | TV/数据桥 | 无关键位则禁追 |")
    return rows
