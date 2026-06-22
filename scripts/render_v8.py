#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8.0 叙事渲染引擎"""


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
    """v8.0 完整分析卡 · 叙事风格。"""
    from datetime import datetime, timezone, timedelta
    TZ = timezone(timedelta(hours=8))
    SEP = ""

    _R = lambda v: f"`{v:,.0f}`" if isinstance(v, (int, float)) else str(v)

    # ① 今日结构
    parts = []
    for tf in ("4h", "1h", "15m"):
        k = (klines or {}).get(tf, {})
        if not k: continue
        o, c, h, l = k.get("open"), k.get("close"), k.get("high"), k.get("low")
        if o and c:
            chg_pct = (c - o) / o * 100
            d = "阳" if c >= o else "阴"
            hl = f" 高{h:.0f} 低{l:.0f}" if h and l else ""
            parts.append(f"{tf}收{d}{chg_pct:+.1f}%{hl}")
    struct = " → ".join(parts) if parts else "待采集"
    ctx = f"CVD {cvd_dir}" if cvd_dir and cvd_dir not in ("?", "N/A") else ""
    kz = kill_zone if kill_zone else ""
    extras = " · ".join(filter(None, [ctx, kz]))
    struct = f"{struct}\n{extras}" if extras else struct

    # ② 关键位
    res = sorted([l for l in levels if l.get("side") == "resistance"], key=lambda x: x.get("level", 0))
    sup = sorted([l for l in levels if l.get("side") == "support"], key=lambda x: x.get("level", 0), reverse=True)

    r_txt = "待刷新"
    if res:
        r_lines = []
        for i, l in enumerate(res[:2]):
            name = l.get("display_name", l.get("name", f"R{i+1}"))
            lvl = l.get("level", 0)
            d = abs(lvl - price) / price * 100 if price else 0
            r_lines.append(f"R{i+1}: {lvl:.0f} — {name} 距{d:.1f}%")
        r_txt = "\n".join(r_lines)

    s_txt = "待刷新"
    if sup:
        s_lines = []
        for i, l in enumerate(sup[:3]):
            name = l.get("display_name", l.get("name", f"S{i+1}"))
            lvl = l.get("level", 0)
            d = abs(lvl - price) / price * 100 if price else 0
            s_lines.append(f"S{i+1}: {lvl:.0f} — {name} 距{d:.1f}%")
        s_txt = "\n".join(s_lines)

    # ④ 方向标签
    dir_a = "空" if bearish else "多"
    dir_b = "多" if bearish else "空"
    status_label = status if status.startswith(("A", "B", "X", "C")) else "观望"

    # Entry/target logic: B/C等待用现价作为观察锚，不能把止损价当入场。
    entry_a = price
    entry_b = price

    # ⑤ 评分
    score = "\n".join([
        f"流动性扫荡 · {sweep_state or '待判'}",
        f"CVD确认 · {cvd_dir}·{cvd_quality}" if cvd_dir else "CVD确认 · 待判",
        f"动能位移 · {displacement or '待判'}",
        f"Kill Zone · {kill_zone or '非主盘'}",
        f"数据质量 · {data_grade}级",
        f"风控门 · {prot_status}",
    ])

    lines_vol = [
        "③ 量价分析",
        "",
        f"CVD {cvd_dir} · {cvd_quality}级" if cvd_dir and cvd_dir not in ("?", "N/A") else "CVD 待确认",
        f"Taker {taker_dir} {taker_ratio}" if taker_dir and str(taker_ratio) not in ("N/A", "", "None") else f"Taker {taker_dir or '待采集'}",
        f"Funding {funding_rate}" if funding_rate and str(funding_rate) not in ("N/A", "") else "",
    ]
    
    # TV DMI 决策表注入
    if tv_dmi and tv_dmi.get("grade"):
        dmi = tv_dmi
        lines_vol.append("")
        lines_vol.append(f"📺 TV DMI：{dmi.get('grade','?')} · {dmi.get('action','?')}")
        lines_vol.append(f"   背景{dmi.get('bias_4h','?')} · CVD{dmi.get('cvd','?')} · {dmi.get('position','?')}")
        lines_vol.append(f"   执行{dmi.get('execute','?')} · 风控{dmi.get('risk','?')}")
    
    lines_vol.append("")

    lines = [
        f"`{symbol}` 日内分析 · {status_label}",
        "",
        f"现价 {_R(price)} ({float(chg or 0):+.2f}%) · 高 {_R(high)} 低 {_R(low)}",
        "",
        "① 今日结构",
        "",
        struct,
        "",
        "② 关键位",
        "",
        "— 阻力 —",
        r_txt,
        "",
        "— 支撑 —",
        s_txt,
        "",
    ] + lines_vol + [
        "④ 交易方案",
        "",
        f"{status_label} · {one_reason}",
        "",
        f"— A方案（{dir_a}）",
        f"  入场 {_R(entry_a)} 止损 {_R(st_a['stop'])}",
        f"  止盈 {_R(st_a['target'])} R:R 1:{rr_a:.1f}{rr_a_note}",
        "",
        f"— B方案（{dir_b}）",
        f"  入场 {_R(entry_b)} 止损 {_R(st_b['stop'])}",
        f"  止盈 {_R(st_b['target'])} R:R 1:{rr_b:.1f}{rr_b_note}",
        "",
        f"防守： 失效 {_R(inv_line) if inv_line else '待确认'}",
        f"仓位： {_R(risk_amt)}U {leverage_text}",
        "",
        SEP,
        "",
        "⑤ 综合评分",
        "",
        score,
        "",
        f"总结： {one_reason or '待确认'}",
    ]

    return "\n".join(lines) + "\n"
