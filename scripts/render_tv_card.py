#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 · TV双指标Telegram卡 v9.9

主指标：SVP+ICT+VWAP+CVD = 结构/关键位/执行/失效
副指标：Volume Aggregated Spot & Futures = OI/CVD/覆盖/Composite/爆仓

v9.9 修正：快速卡也必须显示结构位前置、多周期、双指标，不再把能力压没。
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


def _now_chinese() -> str:
    return datetime.now(TZ).strftime("%Y年%m月%d日%H：%M")


def _clean_text(text: object, limit: int | None = None) -> str:
    s = "" if text is None else str(text)
    for old, new in {
        "🟢": "", "🟡": "", "🔴": "", "⚪": "", "🔥": "",
        "🔵": "", "✅": "", "⚠️": "⚠", "⚡": "",
        "📺": "TV ", "❌": "✗", "✔": "✓",
    }.items():
        s = s.replace(old, new)
    s = s.replace("|", "／")
    s = re.sub(r"\s+", " ", s).strip(" ·")
    return s[:limit].rstrip(" ·") if limit else s


def _fmt_num(v):
    if v is None or v == "":
        return "—"
    try:
        f = float(str(v).replace(",", "").replace("`", ""))
        return f"{f:,.0f}" if f >= 1000 else f"{f:.2f}"
    except (TypeError, ValueError):
        return str(v).replace("`", "")


def _dir_icon(direction: str) -> str:
    if "多" in str(direction):
        return "🟢"
    if "空" in str(direction):
        return "🔴"
    return "🔵"


def _grade_icon(grade: str) -> str:
    g = str(grade or "")
    if g.startswith("A"):
        return "🟢"
    if g.startswith("B"):
        return "🔵"
    if g.startswith("C"):
        return "🟡"
    if g.startswith("X"):
        return "⚠️"
    return "⚪"


def _tf_mini(main: dict, symbol: str = "") -> str:
    kl = main.get("_klines") or main.get("klines") or {}
    main_tf = ""
    try:
        from pipeline_router import timeframe_info
        if symbol:
            main_tf = timeframe_info(symbol).get("main", "")
    except Exception:
        pass
    if not isinstance(kl, dict) or not kl:
        return "5m⚪ · 15m⚪ · 1h⚪ · 4h⚪ · D⚪"
    out = []
    for tf in TF_ORDER:
        k = kl.get(tf, {}) if isinstance(kl, dict) else {}
        desc = str(k.get("description") or k.get("svp") or k.get("direction") or "") if isinstance(k, dict) else ""
        emo = "🟢" if any(x in desc for x in ("多", "涨", "long")) else "🔴" if any(x in desc for x in ("空", "跌", "short")) else "⚠️" if "禁" in desc else "🔵" if desc else "⚪"
        mark = "⭐" if tf == main_tf else ""
        out.append(f"{tf}{mark}{emo}")
    return " · ".join(out)


def _level_table(vwap, vah, val, poc, price) -> str:
    """结构位前置：真管道表（上沿 / 现价 / 下沿）。替代旧的全角竖线伪表格行。"""
    try:
        px = float(price or 0)
    except Exception:
        px = 0
    if not px:
        return "| 结构 | 价格 | 距现价 |\n|:---|:---:|---:|\n| ⚠现价 | 待采集 | — |"
    vals = []
    for lab, v in (("VAH", vah), ("VWAP", vwap), ("POC", poc), ("VAL", val)):
        if v:
            try:
                vals.append((lab, float(str(v).replace(",", ""))))
            except Exception:
                pass
    if not vals:
        return f"| 结构 | 价格 | 距现价 |\n|:---|:---:|---:|\n| ⚠现价 | `{_fmt_num(px)}` | — |"
    above = sorted([x for x in vals if x[1] > px], key=lambda x: x[1])
    below = sorted([x for x in vals if x[1] < px], key=lambda x: -x[1])
    a = above[0] if above else None
    b = below[0] if below else None
    rows = []
    if a:
        dist = f"{(a[1] - px) / px * 100:+.2f}%"
        rows.append(f"| 🔴{a[0]} 上 | `{_fmt_num(a[1])}` | {dist} |")
    rows.append(f"| ⚖**现价** | `{_fmt_num(px)}` | — |")
    if b:
        dist = f"{(b[1] - px) / px * 100:+.2f}%"
        rows.append(f"| 🟢{b[0]} 下 | `{_fmt_num(b[1])}` | {dist} |")
    return "| 结构 | 价格 | 距现价 |\n|:---|:---:|---:|\n" + "\n".join(rows)


def render_tv_card(main: dict | None = None, sub: dict | None = None, symbol: str = "BTCUSDT", price: float = 0, mode: str = "push") -> str:
    main = main or {}
    sub = sub or {}

    grade = main.get("grade", "C等待")
    treatment = main.get("treatment", "")
    vwap = main.get("vwap")
    vah = main.get("vah")
    val = main.get("val")
    poc = main.get("poc")
    entry = main.get("entry") or main.get("进场") or main.get("position")
    stop = main.get("stop") or main.get("止损")
    target = main.get("target") or main.get("目标")
    magnet_up = main.get("magnet_up") or main.get("磁吸↑")
    magnet_down = main.get("magnet_down") or main.get("磁吸↓")
    check = main.get("check") or main.get("核对")
    dual = main.get("_dual") or {}

    signal = sub.get("signal", "")
    conclusion = sub.get("conclusion", "")
    htf = sub.get("htf", "")
    oi_status = sub.get("oi", "")
    cvd_flow = sub.get("cvd_flow", "")
    vol_status = sub.get("volume", "")
    share_data = sub.get("share", "") or sub.get("coverage", "") or sub.get("risk", "")
    liq_data = sub.get("liquidation", "")
    operation = sub.get("operation", "")

    direction = "观望"
    if str(grade).startswith(("A多", "B多", "C反多")):
        direction = "做多"
    elif str(grade).startswith(("A空", "B空", "C反空")):
        direction = "做空"

    if mode == "push":
        return _render_push(symbol, price, grade, direction, treatment, signal, conclusion, htf, oi_status, cvd_flow, vol_status, share_data, liq_data, vwap, vah, val, poc, operation, entry, stop, target, magnet_up, magnet_down, check, main, sub, dual)
    return _render_full(symbol, price, grade, direction, treatment, signal, conclusion, htf, oi_status, cvd_flow, vol_status, share_data, liq_data, vwap, vah, val, poc, operation, entry, stop, target, magnet_up, magnet_down, check, main, sub, dual)


def _render_push(symbol, price, grade, direction, treatment, signal, conclusion, htf, oi_status, cvd_flow, vol_status, share_data, liq_data, vwap, vah, val, poc, operation, entry, stop, target, magnet_up, magnet_down, check, main, sub, dual) -> str:
    short_sym = symbol.replace("USDT", "").replace(".P", "")
    tf_line = _tf_mini(main, symbol)
    conclusion_clean = _clean_text(conclusion or signal or treatment, 28) or "待确认"
    entry_clean = _clean_text(entry, 22) if entry else _fmt_num(price)
    stop_clean = _clean_text(stop, 18) if stop else "—"

    target_clean = _clean_text(target, 22) if target else "—"
    magnet_up_clean = _clean_text(magnet_up, 18) if magnet_up and magnet_up != "--" else "—"
    magnet_down_clean = _clean_text(magnet_down, 18) if magnet_down and magnet_down != "--" else "—"
    dual_verdict = _clean_text(dual.get("direction_verdict") or dual.get("flow_verdict") or "主副待读", 18) if isinstance(dual, dict) else "主副待读"

    lines = [
        f"📊 {short_sym} · {_now_chinese()}",
        _level_table(vwap, vah, val, poc, price),
        f"{_dir_icon(direction)}{direction} · {_grade_icon(grade)}{grade} · {conclusion_clean}",
        tf_line,
        "",
        "| 优先级 | 触发价 | 操作 |",
        "|:---|:---:|:---|",
    ]
    if direction == "做多":
        lines.append(f"| ⭐主推 多 | {entry_clean} | 多 损{stop_clean} 标{target_clean} |")
        lines.append(f"| 🔁备选 空 | {magnet_up_clean} | 主推失效后再看空 |")
    elif direction == "做空":
        lines.append(f"| ⭐主推 空 | {entry_clean} | 空 损{stop_clean} 标{target_clean} |")
        lines.append(f"| 🔁备选 多 | {magnet_down_clean} | 主推失效后再看多 |")
    else:
        lines.append(f"| 🔵主推 等 | {entry_clean} | 等结构位确认 |")
        lines.append(f"| 🔁备选 | {magnet_up_clean} | 只作失效路径 |")
    lines.append("| ⚠️禁止 | 追单/冲突 | 主副不共振不做 |")
    lines.append("")
    lines.append(f"SVP {_clean_text(str(grade) + ' ' + (treatment or operation or ''), 34)}")
    lines.append(f"HALDRO {_clean_text((signal or '') + ' ' + (operation or ''), 38)} · {dual_verdict}")
    verify_parts = []
    if oi_status:
        verify_parts.append(f"持仓{_clean_text(oi_status, 12)}")
    if cvd_flow:
        verify_parts.append(f"CVD{_clean_text(cvd_flow, 12)}")
    if vol_status:
        verify_parts.append(f"量{_clean_text(vol_status, 10)}")
    if share_data:
        verify_parts.append(f"覆盖{_clean_text(share_data, 12)}")
    lines.append(" · ".join(verify_parts[:4]) if verify_parts else "订单流待采集")
    return "\n".join(lines) + "\n"


def _render_full(symbol, price, grade, direction, treatment, signal, conclusion, htf, oi_status, cvd_flow, vol_status, share_data, liq_data, vwap, vah, val, poc, operation, entry, stop, target, magnet_up, magnet_down, check, main, sub, dual) -> str:
    level_tbl = _level_table(vwap, vah, val, poc, price)
    lines = [
        f"📊 {symbol} · {_now_chinese()} · {_grade_icon(grade)}{grade}",
        "【结构位】",
        level_tbl,
        f"【主推】{_dir_icon(direction)}{direction} · {_clean_text(treatment or operation or conclusion, 34)}",
        "",
        "① 多周期定位（5m→15m→1h→4h→D）",
        _tf_mini(main, symbol),

        "② 双指标",
        "| 指标 | 读数 | 裁决 |",
        "|:---|:---|:---|",
        f"| SVP主驾驶 | {_clean_text(str(grade) + ' ' + (treatment or ''), 34)} | 结构/执行优先 |",
        f"| HALDRO副驾驶 | {_clean_text((signal or '') + ' ' + (operation or ''), 38)} | {_clean_text(dual.get('direction_verdict') if isinstance(dual, dict) else '待判', 18)} |",
        "",
        "③ 结构位",
        "| 结构 | 价格 | 用法 |",
        "|:---|:---:|:---|",
        f"| VAH | `{_fmt_num(vah)}` | 上沿/阻力 |",
        f"| VWAP | `{_fmt_num(vwap)}` | 均价锚 |",
        f"| POC | `{_fmt_num(poc)}` | 成交密集 |",
        f"| VAL | `{_fmt_num(val)}` | 下沿/支撑 |",
        "",
        "④ 最推荐方案",
        "| 优先级 | 条件 | 动作 |",
        "|:---|:---|:---|",
    ]
    if direction == "做多":
        lines.append(f"| ⭐主推 多 | {entry or '—'} | 多 损{stop or '—'} 标{target or '—'} |")
        lines.append(f"| 🔁备选 空 | {magnet_up or '主推失效'} | 只作失效路径 |")
    elif direction == "做空":
        lines.append(f"| ⭐主推 空 | {entry or '—'} | 空 损{stop or '—'} 标{target or '—'} |")
        lines.append(f"| 🔁备选 多 | {magnet_down or '主推失效'} | 只作失效路径 |")
    else:
        lines.append(f"| 🔵主推 等 | {entry or _fmt_num(price)} | 等结构位确认 |")
        lines.append("| 🔁备选 | 反向破位 | 只作失效路径 |")
    lines.append("| ⚠️禁止 | 追单/主副冲突 | 不做 |")
    lines.append("")
    lines.append(f"【裁决】{_dir_icon(direction)}{direction} · 主副指标已纳入 · 不再只看单行信号")
    return "\n".join(lines) + "\n"


def _unwrap_tv_tables(raw: dict) -> list:
    tables_flat = []
    studies = raw.get("studies", []) if isinstance(raw, dict) else []
    if isinstance(studies, list):
        for s in studies:
            s_name = s.get("name", "")
            for t in s.get("tables", []) or []:
                rows = t.get("rows", []) if isinstance(t, dict) else []
                if rows:
                    tables_flat.append({"name": s_name, "rows": rows})
    if not tables_flat and isinstance(raw, dict):
        for t in raw.get("tables", []) or []:
            rows = t.get("rows", []) if isinstance(t, dict) else []
            if rows:
                tables_flat.append({"name": t.get("name", ""), "rows": rows})
    return tables_flat


def _parse_table_rows(rows: list) -> dict:
    result = {}
    for row_text in rows:
        row_str = str(row_text)
        if " | " in row_str:
            parts = row_str.split(" | ", 1)
        elif "｜" in row_str:
            parts = row_str.split("｜", 1)
        elif "：" in row_str:
            parts = row_str.split("：", 1)
        else:
            continue
        if len(parts) == 2:
            result[parts[0].strip()] = parts[1].strip()
    return result


def extract_from_tv_data(tv_data: dict) -> tuple[dict, dict]:
    main, sub = {}, {}
    for s in tv_data.get("studies", []) if isinstance(tv_data, dict) else []:
        name = s.get("name", "")
        vals = s.get("values", {}) or {}
        if "SVP" in name or "ICT" in name or "CVD" in name or "VWAP" in name:
            for k, v in vals.items():
                kk = k.lower().replace(" ", "_").replace("%", "pct")
                try:
                    main[kk] = float(str(v).replace("−", "-").replace(",", ""))
                except Exception:
                    main[kk] = str(v)
        if "Volume" in name and ("Aggregated" in name or "Spot" in name):
            for k, v in vals.items():
                kk = k.lower().replace(" ", "_").replace("%", "pct")
                sub[kk] = v
    for src_key, dst_key in [("s_vwap", "vwap"), ("vah_price", "vah"), ("val_price", "val"), ("poc_price", "poc")]:
        if src_key in main and dst_key not in main:
            main[dst_key] = main[src_key]
    for t in _unwrap_tv_tables(tv_data):
        parsed = _parse_table_rows(t.get("rows", []))
        if ("结论" in parsed and ("方向" in parsed or "进场" in parsed)) or "等级" in parsed:
            main.update(parsed)
            grade_raw = main.get("等级", "")
            if not grade_raw:
                conc = main.get("结论", "")
                for p in ("A多", "A空", "B多", "B空", "C反多", "C反空", "C等待", "X"):
                    if str(conc).startswith(p):
                        grade_raw = p
                        break
            main["grade"] = grade_raw or "C等待"
            main.setdefault("treatment", main.get("结论", ""))
            main.setdefault("entry", main.get("进场", ""))
            main.setdefault("stop", main.get("止损", ""))
            main.setdefault("target", main.get("目标", ""))
            main.setdefault("magnet_up", main.get("磁吸↑", ""))
            main.setdefault("magnet_down", main.get("磁吸↓", ""))
            main.setdefault("check", main.get("核对", ""))
        elif "信号" in parsed and "操作" in parsed:
            sub.update(parsed)
            sub.setdefault("signal", sub.get("信号", ""))
            sub.setdefault("conclusion", sub.get("结论", ""))
            sub.setdefault("htf", sub.get("高周", ""))
            sub.setdefault("oi", sub.get("持仓", ""))
            sub.setdefault("cvd_flow", sub.get("流向", ""))
            sub.setdefault("volume", sub.get("量能", ""))
            sub.setdefault("coverage", sub.get("覆盖", ""))
            sub.setdefault("risk", sub.get("风险", ""))
            sub.setdefault("share", sub.get("覆盖", ""))
            sub.setdefault("liquidation", sub.get("爆仓", ""))
            sub.setdefault("operation", sub.get("操作", ""))
    return main, sub


if __name__ == "__main__":
    demo_main = {"grade":"A空","treatment":"反抽失败优先空","vwap":63342,"vah":63194,"val":62558,"poc":62876,"entry":"62,880反抽不过","stop":"63,380","target":"61,780","magnet_down":"62,558","_klines":{"D":{"description":"偏空"},"4h":{"description":"偏空"},"1h":{"description":"偏空"},"15m":{"description":"偏空"},"5m":{"description":"等待"}},"_dual":{"direction_verdict":"主副同向"}}
    demo_sub = {"signal":"🔴 偏空 · 4/4共振","conclusion":"真实下跌 · 新空进场","oi":"新空进场","cvd_flow":"卖盘占优","volume":"放量","coverage":"聚合5/5","operation":"配合主指标 A空 = 可做"}
    print(render_tv_card(demo_main, demo_sub, "BTCUSDT", 62880, "push"))
