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

import math
import re
import sys
from datetime import datetime, timezone, timedelta

# 棠溪看盘顺序：从上往下（D背景 → 4h → 1h → 15m → 5m主执行层）
TF_ORDER = ("D", "4h", "1h", "15m", "5m")

# 结构位名称里的周期前缀（"D VAL" / "15m VAH" …）必须保留到卡面标签，
# 否则跨周期价值区会被压成同一层，出现 VAL 在 VAH 上方的伪结构。
_LEVEL_TF_RE = re.compile(r"^\s*(D|W|M|4h|1h|15m|5m)\b", re.IGNORECASE)
_LEVEL_TF_CANON = {"d": "D", "w": "W", "m": "M", "4h": "4h", "1h": "1h", "15m": "15m", "5m": "5m"}

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
    a = abs(f)
    if 0.01 <= a < 10:
        # 2026-09-13 FX 精度修复：2 位小数不够——EURUSD 1.1638 曾显示成 "1.16"。
        # |v|∈[0.01,10)（外汇/小额价格）保留 4 位小数。
        return f"{f:.4f}"
    if 0 < a < 0.01:
        # 极小值（小市值币种）：6 位小数并去掉尾部零。
        return f"{f:.6f}".rstrip("0").rstrip(".")
    return f"{f:.2f}"


def _finite_rr(value):
    """Return a finite float R:R, else None. Never raises on malformed input.

    「缺失/非法」与「有值但不足2」是两种事实：前者不得写成「R:R不足」，
    也不能回落到旧计划里的 rr_a 兜底（2026-09-13 加固）。
    """
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


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
    # v9.7: 优先读逐层CVD（_collect_binance_data 注入的独立值），使五层CVD各自不同
    cvd = tf_data.get("cvd")
    if isinstance(cvd, dict) and cvd.get("value") is not None:
        _dir = cvd.get("direction") or "?"
        _val = cvd.get("value") or 0
        _emoji = "🟢" if _dir == "买" else "🔴" if _dir == "卖" else "🔵"
        return f"CVD{_emoji}{_dir} {_val:,.0f}·近≈"
    for key in ("sub_indicator", "sub", "volume_agg", "oi", "sub_composite", "composite"):
        v = tf_data.get(key)
        if v:
            return _cell(v)[:22]
    return "待刷新"


def _sub_tf_text_for_asset(tf_data: dict, dual_indicator: dict | None) -> str:
    if isinstance(dual_indicator, dict) and dual_indicator.get("asset_is_crypto") is False:
        return "不适用"
    return _sub_tf_text(tf_data)


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


def _level_kind(name: str, side: str, level: float, price: float | None) -> tuple[str, str, str]:
    raw = f"{side} {name}".lower()
    cn = f"{side} {name}"
    # 周期标注必须保留：历史缺陷（2026-09-12 实测）把 "D VAL"(77,388.5，日级价值区)
    # 与 "15m VAH"(77,334，执行层) 都压成无周期的 VAL/VAH，卡面因此出现
    # 「VAL 上 / VAH 下」的价值区倒挂伪结构。→ 现在标签与用法都带周期前缀。
    tf = ""
    try:
        m = _LEVEL_TF_RE.match(str(name or ""))
        if m:
            tf = _LEVEL_TF_CANON.get(m.group(1).lower(), m.group(1))
    except Exception:
        tf = ""
    if "fvg" in raw:
        label = "FVG"
        use = "FVG缺口"
    elif "vwap" in raw:
        label = "VWAP"
        use = "VWAP均价锚"
    elif "vah" in raw or "上沿" in cn:
        label = "VAH"
        use = "VAH上沿阻力"
    elif "val" in raw or "下沿" in cn:
        label = "VAL"
        use = "VAL下沿支撑"
    elif "poc" in raw:
        label = "POC"
        use = "POC密集区"
    elif "npoc" in raw:
        label = "nPOC"
        use = "nPOC裸区"
    elif "高" in cn or "res" in raw or "阻" in cn:
        label = "阻"
        use = "阻力位"
    elif "低" in cn or "sup" in raw or "支" in cn:
        label = "支"
        use = "支撑位"
    else:
        label = "位"
        use = "关键位"
    if tf:
        label = f"{tf}·{label}"
        use = f"{tf}·{use}"
    if price is None:
        icon = "⚖"
    elif level > float(price):
        icon = "🔴"
    elif level < float(price):
        icon = "🟢"
    else:
        icon = "⚖"
    return label, icon, use


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
                    clean.append({"level": float(v), "side": typ, "name": f"{tf} {typ}"})
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
        # 去重桶必须与**显示精度**一致。
        # 历史缺陷：桶用 round(lvl,2)，而卡面 _num() 对 ≥1000 的值显示 0 位小数 →
        # 77258.57 与 77258.58 是两个桶、都显示 77,258，卡面出现两行一模一样的 VWAP。
        # 现在按显示精度归并：≥1000 取整数桶，否则保留 2 位。
        bucket = round(lvl) if abs(lvl) >= 1000 else round(lvl, 2)
        if bucket in seen:
            continue
        seen.add(bucket)
        side = item.get("side", "level")
        name = item.get("display_name") or item.get("name") or side
        kind, icon, use = _level_kind(str(name), str(side), lvl, price)
        if price:
            dist = (lvl - float(price)) / float(price) * 100
            dist_txt = f"{dist:+.2f}%"
        else:
            dist_txt = "—"
        clean.append({"level": lvl, "side": side, "name": name, "kind": kind, "icon": icon, "dist": dist_txt, "use": use})
    clean.sort(key=lambda x: abs(x["level"] - float(price or 0)))
    clean = _demote_inconsistent_value_area(clean)
    return clean[:7]


def _nearest_trigger_names(levels_prepared: list[dict], price: float | None) -> tuple[str | None, str | None]:
    """取现价上方/下方最近的结构位名称（等待条件具名化；只给名不给价）。"""
    try:
        px = float(price or 0)
    except (TypeError, ValueError):
        return None, None
    if px <= 0 or not levels_prepared:
        return None, None
    up = down = None
    for lv in levels_prepared:
        try:
            v = float(lv.get("level") or 0)
        except (TypeError, ValueError):
            continue
        nm = str(lv.get("kind") or lv.get("name") or "").strip()
        if not nm:
            continue
        if v > px and up is None:
            up = nm
        elif 0 < v < px and down is None:
            down = nm
        if up and down:
            break
    return up, down


def _demote_inconsistent_value_area(rows: list[dict]) -> list[dict]:
    """同周期价值区一致性断言：同 TF 内 VAL 价位高于 VAH = 数据自相矛盾。

    历史缺陷（2026-09-12）：跨周期 VAL/VAH 被压成同层后卡面出现「VAL 在 VAH 上方」。
    现在周期前缀已保留，此处再做兜底：同 TF 的 VAL>VAH 时把该 VAL 降为普通关键位，
    不允许它继续以「VAL下沿支撑」的名义出现在卡面。
    """
    by_tf: dict[str, dict[str, dict]] = {}
    for item in rows:
        kind = str(item.get("kind") or "")
        tf = kind.split("·")[0] if "·" in kind else ""
        base = kind.split("·")[-1]
        if base in ("VAL", "VAH"):
            by_tf.setdefault(tf, {})[base] = item
    for tf, pair in by_tf.items():
        val, vah = pair.get("VAL"), pair.get("VAH")
        if val and vah and float(val["level"]) > float(vah["level"]):
            val["kind"] = f"{tf}·位" if tf else "位"
            val["use"] = "关键位（同周期价值区数据不一致·不按VAL用）"
    return rows


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
    rows.append(f"| ⚖现价 | `{_num(price)}` | — |")
    if b:
        rows.append(f"| {b['icon']}{b['kind']} 下 | `{_num(b['level'])}` | {b['dist']} |")
    return "| 结构位 | 价格 | 距现价 |\n|:---|:---:|---:|\n" + "\n".join(rows)


def _ema_disclosure_line(vwap_ema: dict | None) -> str:
    """VWAP/EMA 环境行（2026-09-13 接入，双 schema 兼容）。

    EMA 引擎（vwap_ema_cvd_engine）自 v1.0 起计算 9/21/34/55 + EMA云，
    但此前只在终端打印、卡面无展示（用户 2026-09-13 指标盘点发现的缺口）。
    兼容两种来源：
      - summary 引擎: {"available", "vwap": {"vwap","price_vs_vwap","in_band"}, "ema", "ema_cloud"}
      - TV MCP fallback: {"vwap": {"value","price_above"}, "ema", "source"}
    有数据即输出；无数据返回空串（卡面不出现占位行）。
    """
    if not isinstance(vwap_ema, dict):
        return ""
    vwap = vwap_ema.get("vwap") or {}
    ema = vwap_ema.get("ema") or {}
    cloud = vwap_ema.get("ema_cloud") or {}
    parts = []
    vwap_val = vwap.get("vwap")
    if vwap_val is None:
        vwap_val = vwap.get("value")
    if vwap_val:
        vs = vwap.get("price_vs_vwap")
        if not vs and vwap.get("price_above") is not None:
            vs = "上" if vwap.get("price_above") else "下"
        pair = "·".join(x for x in ((f"价在{vs}" if vs else ""), str(vwap.get("in_band") or "")) if x)
        parts.append(f"VWAP `{_num(vwap_val)}`（{pair}）" if pair else f"VWAP `{_num(vwap_val)}`")
    fast, slow = ema.get("9"), ema.get("55")
    if fast and slow:
        parts.append(f"EMA9/55 `{_num(fast)}`/`{_num(slow)}`")
    strength = str(cloud.get("trend_strength") or "").strip()
    if strength:
        parts.append(strength)
    if not parts:
        return ""
    return "VWAP/EMA：" + " · ".join(parts)


def _dual_short(dual: dict | None, ac: str) -> tuple[str, str, str]:
    if not isinstance(dual, dict):
        if ac == "加密":
            return "SVP待读", "HALDRO待读", "双指标未注入"
        return "SVP/市场数据", "副驾驶不适用", "按本市场源验证"
    svp = dual.get("svp_state") or dual.get("svp_direction") or "SVP待判"
    hal = dual.get("haldro_direction") or "HALDRO待判"
    # 精简 HALDRO：去掉冗余的"配合主指标"等前缀
    hal = _cell(hal)[:24]
    verdict = dual.get("direction_verdict") or dual.get("flow_verdict") or "待裁决"
    return _cell(svp)[:28], hal, _cell(verdict)[:18]


def _final_dual_verdict(dual: dict | None, final: dict | None) -> str:
    dual = dual if isinstance(dual, dict) else {}
    final = final if isinstance(final, dict) else {}
    reason = str(final.get("reason") or "")
    if dual.get("hard_conflict") or "dual_indicator" in reason:
        # 2026-09-13 审计修复：S3 场景优先用精确文案（副S3冲突·CVD/OI背离）。
        _dv = str(dual.get("direction_verdict") or "")
        return _dv if _dv.startswith("副S3") else "主副强冲突"
    if dual.get("conflict"):
        return "主副冲突·等待"
    return str(dual.get("direction_verdict") or dual.get("flow_verdict") or "待裁决")


def _header_line(display, now, session_name, s_emoji, status, bias) -> str:
    """卡片首行（2026-09-13：支持时段标注；空值不显示）。"""
    _sess_seg = f" · {session_name}时段" if session_name else ""
    return f"📊 {display} · {now}{_sess_seg} · {s_emoji}{status} · {bias}"


def _multi_source_line(cvd_dir, cvd_quality, taker_dir, taker_ratio, funding_rate, fg_v, kill_zone, dual: dict | None) -> str:
    parts = []
    if cvd_dir:
        cvd_emoji = "🟢" if cvd_dir in ("买", "buy", "多", "long") else "🔴" if cvd_dir in ("卖", "sell", "空", "short") else "🔵"
        # 2026-09-13：XAU 非加密场景必须标明数据来源（Binance XAUUSDT 黄金合约，
        # 非 OANDA 现货）——不冒充身份。
        _gold_note = "·Binance黄金合约" if isinstance(dual, dict) and dual.get("gold_contract_cvd") else ""
        parts.append(f"CVD{cvd_emoji}{cvd_dir}{_gold_note}")
    # 2026-09-13：CVD 锚值 + 背景（v13 独立字段接入；dual 由 _dual_indicator_verdict 组装）
    _anchor_note = dual.get("cvd_anchor_text") if isinstance(dual, dict) else ""
    if _anchor_note:
        parts.append(str(_anchor_note))
    if taker_dir:
        parts.append(f"主动{taker_dir}")
    if funding_rate:
        parts.append(f"费{funding_rate}")
    if fg_v:
        parts.append(f"恐贪{fg_v}")
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
    risk_backed: bool = True,
    klines: dict = None,
    tv_dmi: dict = None,
    dual_indicator: dict | None = None,
    final_verdict: dict | None = None,
    source_matrix: list[dict] | None = None,
    session_name: str = "",
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
    dual_verdict = _final_dual_verdict(dual_indicator, final_verdict)

    dir_a = "空" if bearish else "多"
    dir_b = "多" if bearish else "空"
    s_emoji = _status_emoji(status)
    dir_emoji = _dir_emoji(direction)

    # FinalVerdict is mandatory for executable rendering. Legacy ``status``
    # and st_a values are display context only and cannot authorize a card.
    final_state = str((final_verdict or {}).get("state") or ("WAIT" if final_verdict is None else status) or "").upper()
    from render_tv_card import final_is_executable
    final_executable = final_is_executable(final_verdict or {})
    final_side = (final_verdict or {}).get("side")
    if final_side in {"long", "short", "neutral"}:
        # Directional text and the primary/backup side must follow the same
        # authority as execution prices; callers may still pass legacy values.
        direction = final_side
        bearish = final_side == "short"
        bias = _bias_label(direction, status)
        dir_a = "空" if bearish else "多"
        dir_b = "多" if bearish else "空"
        dir_emoji = _dir_emoji(direction)
    # FinalVerdict is the only execution authority.  The legacy ``st_a`` plan
    # is still accepted for backward-compatible callers, but it must never
    # leak into a GO-A card after the decision loop has selected/recomputed a
    # different plan.  A malformed GO-A payload fails closed instead of
    # falling back to stale prices.
    execution_entry = None
    execution_stop = None
    execution_target = None
    canonical = final_verdict or {}
    execution_rr = canonical["rr"] if "rr" in canonical else rr_a
    if final_state == "GO-A" and final_executable:
        execution_entry = (final_verdict or {}).get("entry")
        execution_stop = (final_verdict or {}).get("stop")
        execution_target = (final_verdict or {}).get("target")
        # Missing legacy rr is derived only from the canonical tuple, never st_a.
        canonical = final_verdict or {}
        actual_rr = abs(float(canonical["target"]) - float(canonical["entry"])) / abs(float(canonical["entry"]) - float(canonical["stop"]))
        execution_rr = float(canonical["rr"]) if "rr" in canonical else actual_rr
        if any(value in (None, "", "—", "--") for value in (execution_entry, execution_stop, execution_target)):
            final_executable = False
            final_state = "WAIT"
    if final_executable and final_state == "GO-A":
        st_a = dict(st_a)
        st_a["entry"] = execution_entry
        st_a["stop"] = execution_stop
        st_a["target"] = execution_target
        st_a["rr"] = execution_rr
        rr_a = execution_rr
    if not final_executable:
        final_state = "NO-GO" if final_state == "NO-GO" else "WAIT"
    # 2026-09-13：R:R「缺失/非法」与「有值但不足2」必须分开陈述，且都 fail-closed。
    # 旧实现直接比较 execution_rr < 2，遇到 None/字符串会抛异常，或把缺失写成「R:R不足」。
    _rr_num = _finite_rr(execution_rr)
    _rr_b_num = _finite_rr(rr_b)
    # 2026-09-13：等待条件具名化 —— 引用最近上下结构位（只给名不给价）
    _up_name, _down_name = _nearest_trigger_names(levels_prepared, price)
    _wait_ref = " / ".join([n for n in (_up_name, _down_name) if n]) or "结构位"
    if final_state == "NO-GO" or str(status).startswith("X") or (_rr_num is not None and _rr_num < 2):
        # 2026-09-12：结论文案必须与真实约束一致。旧实现无论 NO-GO 的真实原因
        # 是副指标冲突还是高级门控否决，一律写「R:R不足」，与 R:R 闸门自身
        # 的输出自相矛盾（实测同卡出现「🟢主线R:R 1:3.3」+「R:R不足」）。
        if _rr_num is not None and _rr_num < 2:
            action_summary = "⚠禁做 — 主线R:R不足(<1:2)"
        elif final_state == "NO-GO":
            action_summary = "⚠禁做 — 主副指标/门控未通过·等确认后重算"
        else:
            action_summary = "⚠禁做 — 结构禁做"
        recommend_name = "⚠️主推 禁做"
        recommend_trigger = f"等 {_wait_ref} 方向确认后重算；现价无优势"
        recommend_exec = "不下单；等R:R≥1:2且主副指标重新共振"
        recommend_rr = "—"
        backup_name = f"🔁备选/观察 {dir_a}"
        if dir_a == "多" and _up_name:
            backup_trigger = f"重新站回 {_up_name} 后再算"
        elif dir_a == "空" and _down_name:
            backup_trigger = f"跌破 {_down_name} 后再算"
        else:
            backup_trigger = "重新站回/跌破结构位后再算"
        backup_exec = "仅观察条件；确认后重新计算，不显示候选价"
        backup_rr = "重算"
    elif final_state == "GO-A" and final_executable:
        action_summary = f"{dir_emoji} {bias}可执行 — 只做最推荐方案"
        recommend_name = f"⭐主推 {dir_a}"
        recommend_trigger = f"{_price(st_a.get('entry'))}确认"
        recommend_exec = f"{dir_a} {_price(st_a.get('entry'))} 损{_price(st_a.get('stop'))} 标{_price(st_a.get('target'))}"
        recommend_rr = f"1:{_rr_num:.1f}"
        backup_name = f"🔁备选 {dir_b}"
        backup_trigger = "主推失效后反向确认"
        backup_exec = f"{dir_b}失效路径；不与主推平权"
        backup_rr = f"1:{_rr_b_num:.1f}" if _rr_b_num is not None and _rr_b_num >= 2 else "观察"
    else:
        # WAIT：B/C 观察候选只从 FinalVerdict 的 watch 元组来（与推送卡同一实现），
        # 未授权就必须写明「未授权」，且绝不回落到原始 entry/stop/target。
        _local = (final_verdict or {}).get("state") or ""
        _lgrade = str((final_verdict or {}).get("grade") or "")
        cand = {}
        if str(_local).upper() == "WAIT" and _lgrade.startswith(("B多", "B空", "C反多", "C反空")):
            try:
                from render_tv_card import candidate_view as _candidate_view
                cand = _candidate_view(final_verdict or {})
            except Exception:  # pragma: no cover - 独立调用时退回「无候选」
                cand = {}
        _wait_ref2 = _up_name if dir_a == "多" else _down_name
        action_summary = (f"🔵 {bias}等确认 — 先等 {_wait_ref2} 触发" if _wait_ref2
                          else f"🔵 {bias}等确认 — 先等结构位触发")
        recommend_name = "🔵主推 等确认"
        recommend_trigger = f"待 {_wait_ref2} 确认" if _wait_ref2 else "未到最优触发"
        if cand.get("entry"):
            recommend_exec = (f"人工候选（未授权）入{_price(cand['entry'])} "
                              f"止{_price(cand['stop'])} 标{_price(cand['target'])}")
            recommend_rr = f"1:{cand['rr']:.2f}"
        elif cand.get("incomplete"):
            recommend_exec = "候选数据不完整；等重新计算"
            recommend_rr = "待确认"
        else:
            recommend_exec = f"等待{dir_a}触发；不追现价；损/标触发后计算"
            recommend_rr = "待确认"
        backup_name = f"🔁备选 {dir_b}"
        backup_trigger = "反向破位后"
        backup_exec = "仅观察条件；确认后重新计算，不显示候选价"
        backup_rr = "待重算"

    tf_emojis = []
    for tf in TF_ORDER:
        tf_emojis.append(f"{tf}{_tf_emoji(klines.get(tf, {}))}")
    mtf_summary = " · ".join(tf_emojis)
    if isinstance(dual_indicator, dict) and dual_indicator.get("asset_is_crypto") is False:
        if dual_indicator.get("gold_contract_cvd"):
            # 2026-09-13：XAU 黄金合约 CVD（Binance XAUUSDT·用户批准的辅助源）
            # 保留 CVD 方向显示；其余加密流字段（主动/费率/恐贪）仍清空。
            taker_dir = taker_ratio = funding_rate = fg_v = ""
        else:
            cvd_dir = taker_dir = taker_ratio = funding_rate = fg_v = ""
    multi_src_line = _multi_source_line(cvd_dir, cvd_quality, taker_dir, taker_ratio, funding_rate, fg_v, kill_zone, dual_indicator)

    lines: list[str] = []
    lines.append(_header_line(display, now, session_name, s_emoji, status, bias))
    lines.append("【现在】结构位")
    lines.append("")
    lines.append(_structure_table(levels_prepared, price))
    rec_name_clean = recommend_name.replace('⭐主推 ', '').replace('⚠️主推 ', '').replace('🔵主推 ', '')
    lines.append("【做法】决策摘要")
    lines.append("")
    lines.append("| 维度 | 内容 |")
    lines.append("|:---|:---|")
    # 2026-09-13 审计修复：NO-GO/等待场景不得套「只执行」执行措辞。
    if "禁做" in rec_name_clean:
        _action_txt = "不做单"
    elif rec_name_clean.startswith("等"):
        _action_txt = rec_name_clean
    else:
        _action_txt = f"只执行{rec_name_clean}"
    lines.append(f"| 做法 | {_action_txt} · {recommend_trigger} · {recommend_rr} |")
    lines.append(f"| 依据 | SVP {svp_short} · HALDRO {haldro_short} · {dual_verdict} |")
    lines.append("")
    # 2026-09-13：VWAP/EMA 环境行（EMA 此前只算不上卡——用户指标盘点的缺口修复）
    _ve_line = _ema_disclosure_line(vwap_ema)
    if _ve_line:
        lines.append(_ve_line)
        lines.append("")

    lines.append("① 周期体温 / 多周期定位（D→4h→1h→15m→5m）")
    lines.append("")
    lines.append("| 周期 | SVP主指标 | HALDRO副指标 | 位置 |")
    lines.append("|:---:|:---|:---|:---|")
    main_tf = _main_tf(symbol)
    for tf in TF_ORDER:
        k = klines.get(tf, {}) if isinstance(klines, dict) else {}
        mark = " ⭐主" if tf == main_tf else ""
        lines.append(f"| {tf}{mark} | {_tf_emoji(k)} {_short_tf_text(k)} | {_sub_tf_text_for_asset(k, dual_indicator)} | {_vwap_pos(k, price)} |")
    lines.append(f"→ 主执行{main_tf} · 自上而下确认（D背景→{main_tf}执行）")
    lines.append("")

    lines.append("② 关键位 / 结构关键位")
    lines.append("")
    lines.append("| 结构位 | 价格 | 用法 | 距现价 |")
    lines.append("|:---|:---:|:---|---:|")
    for item in levels_prepared[:6]:
        use = item.get("use") or item.get("name") or item.get("side") or "关键位"
        lines.append(f"| {item['icon']}{item['kind']} | {_price(item['level'])} | {_cell(use)[:20]} | {item['dist']} |")
    if not levels_prepared:
        lines.append("| 待刷新 | `—` | TV结构位未注入，禁追 | — |")
    lines.append("")

    lines.append("③ 多源验证 / 双指标")
    lines.append("")
    lines.append("| 能力 | 读数 | 裁决 |")
    lines.append("|:---|:---|:---|")
    lines.append(f"| SVP主驾驶 | {_cell(svp_short)} | 结构/入场/止损/目标优先 |")
    lines.append(f"| HALDRO副驾驶 | {_cell(haldro_short)} | {_cell(dual_verdict)} |")
    lines.append(f"| 订单流 | {_cell(multi_src_line)} | CVD/OI不配则降级 |")
    if isinstance(dual_indicator, dict) and dual_indicator.get("haldro_quality"):
        lines.append(f"| 质量 | {_cell(dual_indicator.get('haldro_quality'))[:56]} | 覆盖不足不追 |")
    if isinstance(source_matrix, list):
        for source in source_matrix:
            if not isinstance(source, dict):
                continue
            label = _cell(source.get("label") or source.get("id") or "来源")
            status = _cell(source.get("status") or "not_run")
            evidence = _cell(source.get("evidence") or "—")[:24]
            usage = "已入FinalVerdict" if source.get("entered_final_verdict") else "仅展示/辅助"
            impact = _cell(source.get("impact") or usage)[:28]
            lines.append(f"| {label} | {status}·{evidence} | {usage}·{impact} |")
    lines.append("")

    lines.append("④ 最推荐方案")
    lines.append("")
    lines.append("| 优先级 | 条件 | 动作 | R:R |")
    lines.append("|:---|:---|---|---:|")
    lines.append(f"| {recommend_name} | {_cell(recommend_trigger)} | {_cell(recommend_exec)} | {recommend_rr} |")
    lines.append(f"| {backup_name} | {_cell(backup_trigger)} | {_cell(backup_exec)} | {backup_rr} |")
    lines.append("| ⚠️禁止（通用规则） | 不追单；数据或主副证据失效时不执行 | 执行须R:R≥2 | — |")
    lines.append("")

    # 风控额度必须标出来源：没接真实账户时不能把兜底默认值写成看似的真实额度。
    if risk_backed:
        _risk_txt = f"风控{_num(risk_amt, 2)}U"
    else:
        _risk_txt = "风控 —（未接账户余额·非真实额度）"
    lines.append(f"【裁决】{action_summary} · {_risk_txt} · {leverage_text or ''}")
    # 未授权裁决不得展示计划失效价：失效价=止损价，与 Entry/Stop/Target 同一道闸。
    inv_display = _price(execution_stop) if final_executable else '`—`'
    lines.append(f"失效 {inv_display} · 价格共识{data_grade}（非全源健康度） · 来源状态见多源验证")
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
        use = item.get("use") or item.get("name") or item.get("side") or "关键位"
        rows.append(f"| {item['icon']}{item['kind']} | {_price(item['level'])} | {_cell(use)[:20]} | {_cell(item['dist'])} |")
    if not rows:
        rows.append("| 待刷新 | `—` | TV/数据桥 | 无关键位则禁追 |")
    return rows