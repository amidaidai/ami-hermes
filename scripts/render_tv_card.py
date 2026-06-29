#!/usr/bin/env python3
"""
棠溪 · TV指标直出分析卡 v1.0
基于两个TV自定义指标的实时数据，直接输出简洁分析卡。

两个指标：
  主指标: SVP+ICT+VWAP+EMA+CVD (3000+行，含DMI决策引擎+行动格)
  副指标: Volume Aggregated Spot & Futures (含OI/CVD/量能/爆仓行动格)

输出模式：
  - push: 推送决策卡 (6-8行，电报/飞书)
  - full:  完整分析卡 (15-20行，手动分析)

用法：
  from render_tv_card import render_tv_card
  card = render_tv_card(main_indicator, sub_indicator, mode="push")
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import re
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))

# ═══════════════════ 字段映射：副指标(Volume)行动格 → 分析卡 ═══════════════════
# 副指标源码字段 (参考上传文件 副指标.txt L286-420):
#   signalA    = 信号灯 + 方向 + X/4共振
#   actText    = OI综合结论
#   htfTxtA    = 高周期方向
#   oiTxtA     = OI持仓变化
#   cvdTxtA    = CVD流向
#   volTxtA    = 量能状态
#   shareTxtA  = 现货/永续占比
#   liqTxtA    = 爆仓状态
#   comboTxt   = 操作建议

# 主指标(DMI)行动格源码字段:
#   grade      = A多/A空/B多/B空/C反多/C反空/X/C等待
#   treatment  = 处理建议
#   background = 高周期背景
#   position   = 相对关键位位置
#   volume_state = 量能状态
#   cvd_state  = CVD状态
#   execution  = 执行计划
#   risk       = 风控


def _now() -> str:
    return datetime.now(TZ).strftime("%m-%d %H:%M")


def _dir_icon(direction: str) -> str:
    """方向→图标"""
    if "多" in direction:
        return "↑"
    if "空" in direction:
        return "↓"
    return "○"


def _clean_text(text: object, limit: int | None = None) -> str:
    """卡片输出清洗：去 emoji/勾叉图标，保留 ↑↓○× 方向符号。"""
    s = "" if text is None else str(text)
    for old, new in {
        "🟢": "", "🟡": "", "🔴": "", "⚪": "", "🔥": "",
        "🔵": "", "✅": "", "⚠️": "⚠", "⚡": "",
        "📺": "TV ", "❌": "✗", "✔": "✓",
    }.items():
        s = s.replace(old, new)
    s = re.sub(r"\s+", " ", s).strip(" ·")
    return s[:limit].rstrip(" ·") if limit else s


def _line(label: str, value: str) -> str:
    return f"{label} {value}" if value else label


def _grade_token(grade: str) -> str:
    grade = str(grade or "C等待")
    return grade if grade else "C等待"


def render_tv_card(
    main: dict | None = None,
    sub: dict | None = None,
    symbol: str = "BTCUSDT",
    price: float = 0,
    mode: str = "push",
) -> str:
    """基于TV双指标数据渲染分析卡。

    Args:
        main: 主指标(DMI)数据 {
            grade, treatment, background, position,
            vwap, vah, val, poc, cvd_value, cvd_slope,
            ema9, ema21, ema_state, kill_zone, atr,
            stop_long, stop_short, target_up, target_down,
        }
        sub: 副指标(Volume行动格)数据 {
            signal, conclusion, htf, oi, cvd_flow,
            volume, share, liquidation, operation,
        }
        symbol: 品种代码
        price: 当前价格
        mode: "push"(决策卡) / "full"(分析卡)
    """
    main = main or {}
    sub = sub or {}

    # ── 从副指标提取 ──
    signal = sub.get("signal", "")
    conclusion = sub.get("conclusion", "")
    htf = sub.get("htf", "")
    oi_status = sub.get("oi", "")
    cvd_flow = sub.get("cvd_flow", "")
    vol_status = sub.get("volume", "")
    share_data = sub.get("share", "")
    liq_data = sub.get("liquidation", "")
    operation = sub.get("operation", "")

    # ── 从主指标提取 ──
    grade = main.get("grade", "C等待")
    treatment = main.get("treatment", "")
    background = main.get("background", "")
    position = main.get("position", "")
    vwap = main.get("vwap")
    vah = main.get("vah")
    val = main.get("val")
    poc = main.get("poc")
    cvd_value = main.get("cvd_value")
    cvd_slope = main.get("cvd_slope")
    cvd_state = main.get("cvd_state", "")
    vol_state = main.get("volume_state", "")
    ema9 = main.get("ema9")
    ema21 = main.get("ema21")
    ema_state = main.get("ema_state", "")
    kill_zone = main.get("kill_zone", "")
    entry = main.get("entry") or main.get("进场") or main.get("position")
    stop = main.get("stop") or main.get("止损")
    target = main.get("target") or main.get("目标")
    magnet_up = main.get("magnet_up") or main.get("磁吸↑")
    magnet_down = main.get("magnet_down") or main.get("磁吸↓")
    check = main.get("check") or main.get("核对")

    # ── 方向判定 ──
    direction = "观望"
    if grade.startswith("A多") or grade.startswith("B多"):
        direction = "做多"
    elif grade.startswith("A空") or grade.startswith("B空"):
        direction = "做空"
    elif grade.startswith("C反多"):
        direction = "反转多"
    elif grade.startswith("C反空"):
        direction = "反转空"

    # ── 价格格式化 ──
    def _p(v, dec=0):
        if v is None:
            return "—"
        try:
            f = float(v)
            if dec == 0:
                return f"{f:,.0f}"
            return f"{f:,.{dec}f}"
        except (TypeError, ValueError):
            return str(v)

    if mode == "push":
        return _render_push(
            symbol, price, grade, direction, treatment,
            signal, conclusion, htf,
            oi_status, cvd_flow, cvd_state, cvd_value, cvd_slope,
            vol_status, share_data, liq_data,
            vwap, vah, val, poc, operation,
            entry, stop, target, magnet_up, magnet_down, check,
        )
    else:
        return _render_full(
            symbol, price, grade, direction, treatment,
            signal, conclusion, htf,
            oi_status, cvd_flow, cvd_state, cvd_value, cvd_slope,
            vol_status, vol_state, share_data, liq_data,
            vwap, vah, val, poc, ema9, ema21, ema_state,
            background, position, kill_zone,
            entry, stop, target, magnet_up, magnet_down, check,
            operation,
        )


def _render_push(
    symbol, price, grade, direction, treatment,
    signal, conclusion, htf,
    oi_status, cvd_flow, cvd_state, cvd_value, cvd_slope,
    vol_status, share_data, liq_data,
    vwap, vah, val, poc, operation,
    entry, stop, target, magnet_up, magnet_down, check,
) -> str:
    """推送决策卡（6-8行，电报适配）。

    棠溪推送铁律：不用 emoji，不加 Markdown 粗体，不用表格/竖线；
    行动格给出的进场/止损/目标/R:R 优先于脚本自行推导。
    """
    _p = lambda v, d=0: f"{float(v):,.{d}f}" if v else "—"

    dir_icon = _dir_icon(direction)
    price_str = _p(price) if price else "—"
    vwap_str = _p(vwap) if vwap else "—"
    vah_str = _p(vah) if vah else "—"
    val_str = _p(val) if val else "—"

    grade = _grade_token(grade)
    signal_clean = _clean_text(signal)
    conclusion = _clean_text(conclusion)
    oi_status = _clean_text(oi_status, 18)
    cvd_flow = _clean_text(cvd_flow, 18)
    vol_status = _clean_text(vol_status, 20)
    liq_data = _clean_text(liq_data, 30)
    operation = _clean_text(operation, 48).replace("配合主指标", "").strip()
    entry = _clean_text(entry, 38)
    stop = _clean_text(stop, 28)
    target = _clean_text(target, 38)
    magnet_up = _clean_text(magnet_up, 34)
    magnet_down = _clean_text(magnet_down, 34)
    check = _clean_text(check, 42)

    lines = [
        f"{dir_icon}{direction} {grade} {price_str} · VWAP {vwap_str} · {_now()}",
    ]

    conc = conclusion or signal_clean or "待判"
    lines.append(f"① {conc}")

    evidence = []
    if oi_status:
        evidence.append(oi_status[:18])
    if cvd_flow:
        evidence.append(cvd_flow[:18])
    if vol_status:
        evidence.append(vol_status[:20])
    if evidence:
        lines.append(f"② {' · '.join(evidence)}")

    parts = [f"VAH {vah_str}", f"VAL {val_str}"]
    if poc:
        parts.append(f"POC {_p(poc)}")
    lines.append(f"③ {' · '.join(parts)}")

    plan_parts = []
    if entry:
        plan_parts.append(f"进 {entry}")
    if stop and stop != "—":
        plan_parts.append(f"损 {stop}")
    if target and target != "—":
        plan_parts.append(f"标 {target}")
    if plan_parts:
        lines.append(f"④ {' · '.join(plan_parts)}")
    elif operation:
        lines.append(f"④ {operation}")

    magnets = []
    if magnet_up and magnet_up != "--":
        magnets.append(f"上 {magnet_up}")
    if magnet_down and magnet_down != "--":
        magnets.append(f"下 {magnet_down}")
    if magnets:
        lines.append(f"⑤ 磁吸 {' · '.join(magnets)}")
    elif check and check != "—":
        lines.append(f"⑤ 核对 {check}")

    if liq_data and "无" not in liq_data:
        lines.append(f"⑥ 爆仓 {liq_data[:30]}")

    return "\n".join(lines) + "\n"


def _render_full(
    symbol, price, grade, direction, treatment,
    signal, conclusion, htf,
    oi_status, cvd_flow, cvd_state, cvd_value, cvd_slope,
    vol_status, vol_state, share_data, liq_data,
    vwap, vah, val, poc, ema9, ema21, ema_state,
    background, position, kill_zone,
    entry, stop, target, magnet_up, magnet_down, check,
    operation,
) -> str:
    """完整分析卡（15-20行）"""
    _p = lambda v, d=0: f"{float(v):,.{d}f}" if v else "—"

    dir_icon = _dir_icon(direction)
    price_str = _p(price) if price else "—"
    vwap_str = _p(vwap) if vwap else "—"
    vah_str = _p(vah) if vah else "—"
    val_str = _p(val) if val else "—"
    poc_str = _p(poc) if poc else "—"

    lines = [
        f"◷ {_now()} · {symbol} · {grade}",
        "",
        f"现价 `{price_str}` · VWAP `{vwap_str}`",
        f"{_dir_icon(direction)} {direction} · {treatment or operation or '等确认'}",
        "",
    ]

    # ① 信号与结论
    signal_clean = _clean_text(signal)
    lines.extend([
        "① 信号",
        f"   {signal_clean}",
        f"   结论：{conclusion or '待判'}",
        "",
    ])

    # ② 多维度证据
    lines.append("② 证据")
    evidence_rows = []
    if oi_status:
        evidence_rows.append(f"   OI  {oi_status}")
    if cvd_flow:
        cvd_line = f"   CVD {cvd_flow}"
        if cvd_value is not None:
            cvd_line += f" `{_p(cvd_value)}`"
        if cvd_state:
            cvd_line += f" · {cvd_state}"
        evidence_rows.append(cvd_line)
    if vol_status:
        evidence_rows.append(f"   量  {vol_status}")
    if htf:
        evidence_rows.append(f"   高周 {htf}")
    if share_data:
        evidence_rows.append(f"   占比 {share_data}")
    if liq_data and "无" not in liq_data:
        evidence_rows.append(f"   爆仓 {liq_data}")
    lines.extend(evidence_rows)
    lines.append("")

    # ③ 关键位
    lines.extend([
        "③ 关键位",
        f"   VAH `{vah_str}` · VAL `{val_str}` · POC `{poc_str}`",
    ])
    if ema9 and ema21:
        lines.append(f"   EMA9 `{_p(ema9)}` · EMA21 `{_p(ema21)}` · {ema_state or ''}")
    if kill_zone:
        lines.append(f"   时段 {kill_zone}")
    lines.append("")

    # ④ 操作
    lines.append("④ 操作")
    if entry:
        lines.append(f"   进场：{_clean_text(entry)}")
    if stop:
        lines.append(f"   止损：{_clean_text(stop)}")
    if target:
        lines.append(f"   目标：{_clean_text(target)}")
    if magnet_up or magnet_down:
        lines.append(f"   磁吸：↑{_clean_text(magnet_up or '--')} · ↓{_clean_text(magnet_down or '--')}")
    if check:
        lines.append(f"   核对：{_clean_text(check)}")
    if operation:
        lines.append(f"   {_clean_text(operation)}")
    lines.append("")

    # ⑤ 风控
    lines.extend([
        "⑤ 风控",
        f"   等级 {grade} · {background or '待确认'} · {position or ''}",
    ])

    return "\n".join(lines) + "\n"


# ═══════════════════ 辅助：从TV MCP数据提取字段 ═══════════════════

def extract_from_tv_data(tv_data: dict) -> tuple[dict, dict]:
    """从TradingView MCP原始数据提取双指标字段。

    Args:
        tv_data: TV MCP返回的原始数据，应包含:
            - studies: [{name, values: {...}}, ...]
            - tables: [{name, rows: [...]}, ...]

    Returns:
        (main_indicator_data, sub_indicator_data)
    """
    main = {}
    sub = {}

    # ── 解析 study_values ──
    studies = tv_data.get("studies", [])
    for s in studies:
        name = s.get("name", "")
        vals = s.get("values", {})

        # 主指标字段
        if "SVP" in name or "ICT" in name or "CVD" in name or "VWAP" in name:
            for k, v in vals.items():
                try:
                    fv = float(str(v).replace(",", "").replace("K", "000").replace("M", "000000"))
                    # 按量级过滤非价格字段
                    if "EMA" in k or "VWAP" in k or "VAH" in k or "VAL" in k or "POC" in k:
                        if fv > 1:  # 合理价格
                            main[k.lower().replace(" ", "_")] = fv
                    elif "CVD" in k:
                        main[k.lower().replace(" ", "_")] = fv
                except (ValueError, TypeError):
                    main[k.lower().replace(" ", "_")] = str(v)

        # 副指标字段: OI
        if "Open Interest" in name or "OI" in name:
            for k, v in vals.items():
                main["oi_value"] = str(v)

    # ── 解析 tables (行动格) ──
    tables = tv_data.get("tables", [])
    for t in tables:
        t_name = t.get("name", "")
        rows = t.get("rows", [])

        # 主指标行动格 (DMI)
        if "DMI" in t_name or "行动格" in t_name or "Action" in t_name:
            for row in rows:
                parts = row.split("|", 1) if "|" in row else row.split("：", 1)
                if len(parts) == 2:
                    key, val = parts[0].strip(), parts[1].strip()
                    main[key] = val
            # 标准字段映射
            main.setdefault("grade", main.get("等级", ""))
            main.setdefault("treatment", main.get("处理", main.get("结论", "")))
            main.setdefault("background", main.get("背景", ""))
            main.setdefault("position", main.get("位置", ""))
            main.setdefault("cvd_state", main.get("CVD", ""))
            main.setdefault("volume_state", main.get("量能", ""))

        # 副指标行动格 (Volume)
        if "Volume" in t_name or "ACT" in t_name or "行动" in t_name:
            for row in rows:
                parts = row.split("|", 1) if "|" in row else row.split("：", 1)
                if len(parts) == 2:
                    key, val = parts[0].strip(), parts[1].strip()
                    sub[key] = val
            # 标准字段映射
            sub.setdefault("signal", sub.get("信号", ""))
            sub.setdefault("conclusion", sub.get("结论", ""))
            sub.setdefault("htf", sub.get("高周", ""))
            sub.setdefault("oi", sub.get("持仓", ""))
            sub.setdefault("cvd_flow", sub.get("流向", ""))
            sub.setdefault("volume", sub.get("量能", ""))
            sub.setdefault("share", sub.get("占比", ""))
            sub.setdefault("liquidation", sub.get("爆仓", ""))
            sub.setdefault("operation", sub.get("操作", ""))

    return main, sub


# ═══════════════════ 演示 ═══════════════════
if __name__ == "__main__":
    # 模拟数据演示
    demo_main = {
        "grade": "A空",
        "treatment": "配合主指标A空=可做",
        "background": "4h偏空",
        "position": "VWAP下方",
        "cvd_state": "卖盘占优",
        "volume_state": "放量",
        "vwap": 64720,
        "vah": 65200,
        "val": 63800,
        "poc": 64550,
        "cvd_value": -3240,
        "cvd_slope": -485,
        "ema9": 64800,
        "ema21": 65050,
        "ema_state": "空头排列",
        "kill_zone": "伦敦盘",
    }
    demo_sub = {
        "signal": "🔴 偏空 · 3/4共振",
        "conclusion": "真实下跌 · 新空进场 ✅",
        "htf": "▼偏空",
        "oi": "▼新空进场",
        "cvd_flow": "▼卖盘占优",
        "volume": "▲放量 · ⚠永续主导",
        "share": "42%现 / 58%合",
        "liquidation": "无明显爆仓",
        "operation": "配合主指标 A空 = 可做",
    }

    print("═══ Push 推送决策卡 ═══")
    print(render_tv_card(demo_main, demo_sub, "BTCUSDT", 64600, "push"))

    print("═══ Full 完整分析卡 ═══")
    print(render_tv_card(demo_main, demo_sub, "BTCUSDT", 64600, "full"))
