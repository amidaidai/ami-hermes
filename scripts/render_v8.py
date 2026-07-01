#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 v9.6 表格驾驶舱渲染器。

保持旧函数名 ``render_v8_card``，避免大范围调用方改动；实际输出已升级为
v9.6 表格格式：多周期定位、关键位矩阵、多源交叉验证、执行预案、风控闸门。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
    return f"`{_num(v)}`" if _num(v) != "—" else "`—`"


def _cell(v) -> str:
    text = "—" if v is None else str(v)
    return text.replace("|", "／").replace(chr(13), " ").replace(chr(10), " ")


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
    ac = _asset_cn(symbol)
    return {"加密": "15m", "贵金属": "5m", "外汇": "15m", "股票": "1h", "期货": "15m", "期权": "跟底层"}.get(ac, "15m")


def _tf_row(tf: str, k: dict, fallback: str = "") -> str:
    if not isinstance(k, dict) or not k:
        return f"| {tf} | 待刷新 | 待刷新 | 缺现场数据，降级参考 |"
    desc = k.get("description") or fallback or k.get("direction") or "待判"
    pos = []
    for key, label in (("vwap", "VWAP"), ("poc", "POC"), ("vah", "VAH"), ("val", "VAL")):
        if k.get(key) not in (None, "", 0):
            pos.append(f"{label} {_price(k.get(key))}")
    if k.get("ema21"):
        pos.append(f"EMA21 {_price(k.get('ema21'))}")
    if k.get("change_pct") is not None:
        try:
            pos.append(f"变动 {float(k.get('change_pct')):+.2f}%")
        except Exception:
            pass
    ind = " · ".join(pos) if pos else "待刷新"
    meaning = "主执行" if tf in {"15m", "5m"} else "背景继承" if tf in {"D", "4h"} else "结构确认"
    return f"| {_cell(tf)} | {_cell(desc)} | {_cell(ind)} | {_cell(meaning)} |"


def _level_rows(levels: list[dict], price: float | None, klines: dict | None = None) -> list[str]:
    rows: list[str] = []
    clean = []
    for item in levels or []:
        try:
            lvl = float(item.get("level"))
        except (TypeError, ValueError):
            continue
        if not lvl:
            continue
        side = item.get("side") or "level"
        name = item.get("display_name") or item.get("name") or side
        clean.append({"level": lvl, "side": side, "name": name})
    if not clean and klines:
        for tf in ("4h", "1h", "15m", "5m"):
            k = klines.get(tf, {}) if isinstance(klines, dict) else {}
            for key, typ in (("vah", "上沿/阻力"), ("poc", "POC"), ("val", "下沿/支撑"), ("high", "高点"), ("low", "低点")):
                if k.get(key):
                    try:
                        clean.append({"level": float(k.get(key)), "side": typ, "name": f"{tf}{typ}"})
                    except Exception:
                        pass
    clean = sorted(clean, key=lambda x: abs((x["level"] or 0) - float(price or 0)))[:5]
    for item in clean:
        lvl = item["level"]
        if price:
            rel = "上方" if lvl > price else "下方" if lvl < price else "当前"
            dist = abs(lvl - price) / price * 100
            use = f"{rel}{dist:.2f}% · 触及后等CVD/主动买卖确认"
        else:
            use = "等价格确认"
        rows.append(f"| {_cell(item['side'])} | {_price(lvl)} | {_cell(item['name'])} | {_cell(use)} |")
    if not rows:
        rows.append("| 待刷新 | `—` | TV/数据桥 | 无关键位则禁追 |")
    return rows


def _bias_label(direction: str, status: str) -> str:
    if status.startswith("X"):
        return "禁做观察"
    if direction == "short":
        return "偏空"
    if direction == "long":
        return "偏多"
    return "观望"


def render_v8_card(symbol: str, status: str, direction: str, price: float,
                   high, low, chg, tf_lines: str, cvd_dir: str, cvd_quality: str,
                   taker_dir: str, taker_ratio, funding_rate, kill_zone: str,
                   vwap_ema: dict, fg_v: str, levels: list[dict],
                   bearish: bool, st_a: dict, st_b: dict, rr_a: float, rr_b: float,
                   rr_a_note: str, rr_b_note: str, risk_amt: float,
                   leverage_text: str, inv_line, prot_status: str,
                   data_grade: str, sweep_state: str, displacement: str,
                   one_reason: str, model_id: str, n5, eng_conf,
                   klines: dict = None, tv_dmi: dict = None) -> str:
    """v9.6 完整分析卡 · 表格驾驶舱。"""
    klines = klines or {}
    now = datetime.now(TZ).strftime("%Y年%m月%d日%H：%M")
    ac = _asset_cn(symbol)
    bias = _bias_label(direction, status)
    main_tf = _main_tf(symbol)
    display = _display_symbol(symbol)

    tv_summary = "待现场读取"
    tv_bias = "观望"
    tv_action = "主驾驶"
    if tv_dmi:
        tv_summary = " · ".join(str(tv_dmi.get(k, "")) for k in ("grade", "action", "position") if tv_dmi.get(k)) or "已读行动格"
        tv_bias = tv_dmi.get("bias_4h") or tv_dmi.get("cvd") or bias
    elif vwap_ema.get("available"):
        v = vwap_ema.get("vwap", {}) or {}
        tv_summary = f"本地VWAP {v.get('vwap', '—')} · {v.get('price_vs_vwap', '待判')}"

    flow_summary = f"CVD {cvd_dir or '待确认'}{cvd_quality or ''} · 主动买卖 {taker_dir or '待采集'} {taker_ratio or ''} · Funding {funding_rate or '—'}"
    macro_summary = f"恐惧贪婪 {fg_v} · {kill_zone or '非主窗口'}"
    orderflow_action = "确认突破真假" if cvd_dir not in ("N/A", "?", "") else "等待订单流"

    dir_a = "空" if bearish else "多"
    dir_b = "多" if bearish else "空"
    rr_a_state = "可执行" if rr_a >= 2 else "观察"
    rr_b_state = "可执行" if rr_b >= 2 else "观察"
    if status.startswith("X"):
        rr_a_state = rr_b_state = "禁做"

    st_a = st_a or {"stop": None, "target": None}
    st_b = st_b or {"stop": None, "target": None}

    bull_evidence = []
    bear_evidence = []
    if direction == "long":
        bull_evidence.append(f"主方向{bias}")
    elif direction == "short":
        bear_evidence.append(f"主方向{bias}")
    if cvd_dir in ("买", "buy", "多", "long"):
        bull_evidence.append(f"CVD{cvd_dir}{cvd_quality or ''}")
    elif cvd_dir in ("卖", "sell", "空", "short"):
        bear_evidence.append(f"CVD{cvd_dir}{cvd_quality or ''}")
    if rr_a >= 2:
        bull_evidence.append(f"主线R:R 1:{rr_a:.1f}")
    else:
        bear_evidence.append(f"主线R:R不足 1:{rr_a:.1f}")
    if "通过" in str(prot_status):
        bull_evidence.append("Protections通过")
    else:
        bear_evidence.append(f"风控{prot_status}")
    if tv_bias and tv_bias not in ("观望", bias):
        bear_evidence.append(f"TV偏向{tv_bias}")
    verdict = "主线可等触发" if rr_a >= 2 and "通过" in str(prot_status) and not status.startswith("X") else "先观察，等关键位+CVD共振"
    bull_text = " · ".join(bull_evidence) if bull_evidence else "无强多头证据"
    bear_text = " · ".join(bear_evidence) if bear_evidence else "无强空头证据"

    lines = [
        f"{display} · {ac} · {status} · {bias} · {now}",
        f"现价 {_price(price)} · 主周期 `{main_tf}` · 数据质量 `{data_grade}`",
        f"结论：{one_reason or bias}。R:R不足或风控过期时只观察，不追单。",
        "",
        "### 多周期定位",
        "",
        "| 周期 | SVP/结构 | VWAP/EMA/CVD/OI | 交易含义 |",
        "|---|---|---|---|",
        _tf_row("D", klines.get("D", {}), "日线背景"),
        _tf_row("4h", klines.get("4h", {})),
        _tf_row("1h", klines.get("1h", {})),
        _tf_row("15m", klines.get("15m", {})),
        _tf_row("5m", klines.get("5m", {})),
        "",
        "### 关键位矩阵",
        "",
        "| 类型 | 价位 | 来源 | 用法 |",
        "|---|---:|---|---|",
    ]
    lines.extend(_level_rows(levels, price, klines))
    lines.extend([
        "",
        "### 多源交叉验证",
        "",
        "| 来源 | 当前读数 | 偏向 | 处理 |",
        "|---|---|---|---|",
        f"| TV SVP v10 | {tv_summary} | {tv_bias} | {tv_action} |",
        f"| 订单流/CVD | {flow_summary} | {cvd_dir or '待判'} | {orderflow_action} |",
        f"| 量价健康度 | 吸收{'待判' if not vwap_ema else '正常'} · 扫荡{sweep_state or '待判'} · 位移{displacement or '待判'} | 中性 | CVD不配不追 |",
        f"| 宏观/事件 | {macro_summary} | 中性验证 | 事件窗口降级 |",
        f"| 社区/情绪 | F&G {fg_v} · 市场热度待核 | 反指辅助 | 不覆盖结构 |",
        f"| 风控/Protections | {prot_status} | {'通过' if '通过' in str(prot_status) else '降级'} | 不通过则禁做 |",
        "",
        "### 矛盾点",
        "",
        "| 项目 | 证据 | 裁决 |",
        "|---|---|---|",
        f"| 多头证据 | {bull_text} | {'保留' if bull_evidence else '不足'} |",
        f"| 空头证据 | {bear_text} | {'压制' if bear_evidence else '不足'} |",
        f"| 裁决 | {verdict} | {status} |",
        "",
        "### 执行预案",
        "",
        "| 方案 | 条件 | 入场 | 止损 | 目标 | R:R | 仓位 |",
        "|---|---|---:|---:|---:|---:|---|",
        f"| 主线 {dir_a} | {one_reason or '等关键位确认'} | {_price(price)} | {_price(st_a.get('stop'))} | {_price(st_a.get('target'))} | 1:{rr_a:.1f} | {rr_a_state} · {_num(risk_amt, 2)}U |",
        f"| 反向 {dir_b} | 反向突破/回收确认 | {_price(price)} | {_price(st_b.get('stop'))} | {_price(st_b.get('target'))} | 1:{rr_b:.1f} | {rr_b_state} · {_num(risk_amt, 2)}U |",
        f"| 等待/禁做 | 数据过期、SVP冲突、R:R<1:2 | - | - | - | - | {status} |",
        "",
        "### 风控闸门",
        "",
        "| 闸门 | 状态 | 处理 |",
        "|---|---|---|",
        f"| 数据新鲜度 | {data_grade} | 低于B级降级观察 |",
        f"| R:R | 主线1:{rr_a:.1f} / 反向1:{rr_b:.1f} | <1:2不执行 |",
        f"| 单笔风险 | {_num(risk_amt, 2)}U · {leverage_text} | 单笔≤1%，硬上限10U |",
        f"| 事件窗口 | {kill_zone or '非主窗口'} | 重大数据前后降级 |",
        f"| 订单流确认 | 扫荡{sweep_state or '待判'} · 位移{displacement or '待判'} | CVD不配不追 |",
        f"| 保护状态 | {prot_status} | 拦截则禁做 |",
        "",
        f"总结：{bias}但以关键位确认执行；不到位不追，失效线 { _price(inv_line) if inv_line else '`—`'}。",
    ])
    return "\n".join(lines) + "\n"
