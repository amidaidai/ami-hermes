#!/usr/bin/env python3
"""
棠溪 · 一键分析卡管道 v1.0
从数据采集到卡片输出全自动

用法:
  python auto_card.py BTCUSDT   # 加密全管卡
  python auto_card.py XAUUSD    # 贵金属全管卡
  python auto_card.py AAPL      # 股票卡（Alpha Vantage + Twelve Data）

输出:
  1. 终端打印完整分析卡
  2. 写入 data/auto_card_{symbol}.md
  3. 更新 monitor_levels.json
  4. 可选推送 Telegram
"""

import sys, json, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))


FIXED_MODELS = ("VWAP反抽", "VAH回收", "VAL回收", "POC拒绝", "扫流动性回收", "突破接受")
MODEL_TAGS = {"VWAP反抽": "vwap_pullback", "VAH回收": "vah_reclaim", "VAL回收": "val_reclaim", "POC拒绝": "poc_rejection", "扫流动性回收": "liquidity_sweep_reclaim", "突破接受": "breakout_acceptance"}

def _ascii_tag(text: str) -> str:
    return MODEL_TAGS.get(text, "model_wait")

def _direction_from_bias(merged: dict) -> str:
    bias = str(merged.get("bias") or merged.get("action") or "")
    if any(x in bias for x in ("空", "short", "bear")):
        return "short"
    if any(x in bias for x in ("多", "long", "bull")):
        return "long"
    return "wait"

def _status_from_merged(merged: dict, direction: str) -> str:
    action = str(merged.get("action") or "")
    conf5 = int(merged.get("confidence_5") or 0)
    if "禁" in action:
        return "X禁做"
    if "B等待" in action or "等待" in action or direction == "wait" or conf5 < 4:
        return "B等待"
    return "A做空" if direction == "short" else "A做多"

def _best_fixed_model(results: list[dict]) -> str:
    candidates = [r for r in results or [] if r.get("name") in FIXED_MODELS]
    if not candidates:
        return "无"
    return max(candidates, key=lambda r: float(r.get("confidence") or 0)).get("name") or "无"

def build_setup_metadata(symbol: str, merged: dict, results: list[dict], engine_data: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(TZ)
    direction = _direction_from_bias(merged)
    status = _status_from_merged(merged, direction)
    model_id = _best_fixed_model(results)
    tag_base = _ascii_tag(model_id)
    suffix = direction if direction in ("long", "short") else "wait"
    engine_conf = float(merged.get("global_confidence") or 0)
    data_grade = engine_data.get("quality") or engine_data.get("grades", {}).get("overall") or "C"
    risk_usd = _adaptive_risk(engine_data)
    return {
        "created_at": now.isoformat(), "symbol": symbol,
        "setup_id": f"{symbol}-{model_id}-{now.strftime('%Y%m%d-%H%M%S')}",
        "model_id": model_id, "entry_tag": f"{tag_base}_{suffix}", "exit_tag": "planned_rr_exit",
        "direction": direction, "status": status, "priority_plan": "A" if status.startswith("A") else "无",
        "data_grade": data_grade, "level_confidence": int(round(engine_conf * 100)) if engine_conf else 0,
        "engine_confidence": round(engine_conf, 3), "confidence_5": int(merged.get("confidence_5") or 0),
        "risk_usd": risk_usd, "rr1": None if status in ("B等待", "C等待") else 2.0, "rr2": None if status in ("B等待", "C等待") else 4.0,
        "invalid_price": None, "expires_at": (now + timedelta(hours=1)).isoformat(), "monitor_write": True,
    }


def _adaptive_risk(engine_data: dict) -> float:
    """按 ATR 波动率自适应单笔风险金额；取不到 ATR 或模块缺失则回退基准 2U。

    账户余额优先用 engine_data 携带的实时余额，缺失则用本金阶段默认 67.52。
    单笔硬上限 10U（棠溪铁律）。
    """
    try:
        from risk_constitution import adaptive_risk_usd
        balance = float(engine_data.get("account_balance") or 67.52)
        # ATR 占价百分比：优先用 engine_data 显式给的，否则从 spot 高低估算
        atr_pct = engine_data.get("atr_pct")
        if atr_pct is None:
            spot = engine_data.get("binance_spot", {})
            hi, lo, px = spot.get("24h_high"), spot.get("24h_low"), (engine_data.get("prices", {}) or {}).get("primary")
            if hi and lo and px:
                atr_pct = (float(hi) - float(lo)) / float(px) / 3.0  # 日内单根近似=日幅/3
        r = adaptive_risk_usd(account_balance=balance, atr_pct=float(atr_pct or 0))
        return r["risk_usd"]
    except Exception:
        return 2.0

def render_machine_fields(meta: dict) -> str:
    keys = ["setup_id", "model_id", "entry_tag", "exit_tag", "direction", "status", "priority_plan", "data_grade", "level_confidence", "engine_confidence", "confidence_5", "risk_usd", "rr1", "rr2", "invalid_price", "expires_at", "monitor_write"]
    lines = ["", "**机器字段**"]
    for key in keys:
        value = meta.get(key)
        if key in ("risk_usd", "invalid_price") and value is not None:
            value = f"`{value}`"
        lines.append(f"{key}：{value}")
    return "\n".join(lines) + "\n"


def _fmt_price(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "`—`"
    if f >= 1000:
        return f"`{f:,.0f}`"
    if f >= 1:
        return f"`{f:,.2f}`"
    return f"`{f:.4f}`"


def _market_one_liner(merged: dict, regime_name: str | None = None) -> str:
    bias = str(merged.get("bias") or "中性")
    n5 = merged.get("confidence_5", "?")
    # 用置信对比而非模型计数，避免「1空 vs 3多」与「偏空」矛盾误导
    short_c = float(merged.get("short_confidence", 0) or 0)
    long_c = float(merged.get("long_confidence", 0) or 0)
    tilt = f"空{short_c:.2f} vs 多{long_c:.2f}"
    base = f"引擎{bias} · {tilt} · 置信{n5}/5"
    if regime_name:
        base += f" · 体制{regime_name}"
    return base


def _env_walls_line(symbol: str, price, klines: dict) -> str:
    """环境④挂单墙/清算行。加密接 depth_wall 真实大额挂单墙；XAU 走K线估算清算区。"""
    su = symbol.upper()
    if "XAU" not in su and price:
        try:
            import sys as _sys
            from pathlib import Path as _P
            _sd = str(_P("D:/Hermes agent/scripts"))
            if _sd not in _sys.path:
                _sys.path.insert(0, _sd)
            from depth_wall import analyze_walls, oi_price_regime
            sym2 = symbol if su.endswith("USDT") else su + "USDT"
            w = analyze_walls(sym2, top_n=2, min_notional_usd=1_000_000)
            if w.get("ok") and (w.get("support_walls") or w.get("resist_walls")):
                line = f"④ 挂单墙：{w['summary']} — 大额限价墙=磁吸位/止损陷阱"
                try:
                    oi = oi_price_regime(sym2)
                    if oi.get("ok"):
                        line += f"\n④.① {oi['summary']}"
                except Exception:
                    pass
                return line
        except Exception:
            pass
    return f"④ 清算：上 `{_liquidation(klines, 'up')}` · 下 `{_liquidation(klines, 'down')}` — {_liq_read(klines, price)}"



def _parse_tv_dmi_table(tv_tables: list | None) -> dict:
    """从 TradingView Pine table 解析 DMI 决策表数据。
    MCP 格式: [{name:..., tables:[{rows:[...]}]}] — 需拆两层。
    简化格式: [{rows:[...]}] — 直接取 rows。"""
    if not tv_tables:
        return {}
    rows = {}
    # 兼容两种嵌套:
    # 格式A(MCP): studies[i].tables[j].rows
    # 格式B(简化): tables[i].rows
    raw_rows = None
    if isinstance(tv_tables, list) and tv_tables:
        first = tv_tables[0]
        if isinstance(first, dict):
            # 尝试格式A: 取 tables[0].rows
            inner = first.get("tables")
            if isinstance(inner, list) and inner:
                raw_rows = inner[0].get("rows", []) if isinstance(inner[0], dict) else []
            # 回退格式B: 直接取 rows
            if not raw_rows:
                raw_rows = first.get("rows", [])
    if not raw_rows:
        return {}
    for row_text in raw_rows:
        parts = row_text.split(" | ", 1)
        if len(parts) == 2:
            key, val = parts[0].strip(), parts[1].strip()
            rows[key] = val
    return rows


def _parse_tv_study_values(tv_studies: list | None) -> dict:
    """从 TradingView study values 提取关键数据。"""
    result = {}
    if not tv_studies:
        return result
    for s in tv_studies:
        name = s.get("name", "")
        vals = s.get("values", {})
        if "CVD" in name or "SVP" in name:
            for k, v in vals.items():
                try:
                    val_str = str(v).replace("\u2212", "-").replace(",", "").replace("\u202fK", "").replace("\u202f", "").strip()
                    # Also handle unicode minus sign
                    val_str = val_str.replace("\u2212", "-")
                    result[k] = float(val_str) * (1000 if "K" in str(v) else 1)
                except (ValueError, TypeError):
                    result[k] = str(v)
    return result


def _apply_tv_dmi_override(meta: dict, engine_data: dict, symbol: str,
                           dmi_rows: dict, tv_vals: dict) -> dict:
    """用 TV DMI 数据覆盖引擎的 bias/grade/status。返回变更标记。"""
    if not dmi_rows:
        return {"tv_active": False}
    grade = dmi_rows.get("等级", "C等待")
    changes = {"tv_active": True, "tv_grade": grade, "tv_treatment": dmi_rows.get("处理", "?"),
               "tv_background": dmi_rows.get("背景", "?"), "tv_position": dmi_rows.get("位置", "?"),
               "tv_volume": dmi_rows.get("量能", "?"), "tv_cvd_state": dmi_rows.get("CVD", "?"),
               "tv_execution": dmi_rows.get("执行", "?"), "tv_risk": dmi_rows.get("风控", "?")}

    # Grade -> status mapping (TV authority overrides engine)
    if grade.startswith("A多"):
        meta["status"] = "A做多"
        meta["direction"] = "long"
        meta["priority_plan"] = "A"
    elif grade.startswith("A空"):
        meta["status"] = "A做空"
        meta["direction"] = "short"
        meta["priority_plan"] = "A"
    elif grade.startswith("B多"):
        meta["status"] = "B等待"
        meta["direction"] = "long"
        meta["priority_plan"] = "B"
    elif grade.startswith("B空"):
        meta["status"] = "B等待"
        meta["direction"] = "short"
        meta["priority_plan"] = "B"
    elif grade.startswith("C反多"):
        meta["status"] = "C反转"
        meta["direction"] = "long"
        meta["priority_plan"] = "C"
    elif grade.startswith("C反空"):
        meta["status"] = "C反转"
        meta["direction"] = "short"
        meta["priority_plan"] = "C"
    elif grade == "X":
        meta["status"] = "X禁做"
        meta["direction"] = "wait"
        meta["priority_plan"] = "无"
    else:  # C等待 / C其他
        meta["status"] = "C等待"
        meta["direction"] = "wait"
        meta["priority_plan"] = "无"

    changes["new_status"] = meta["status"]
    changes["new_direction"] = meta["direction"]

    # Inject TV CVD values into engine_data for real CVD display
    if tv_vals:
        cvd_val = tv_vals.get("CVD Value")
        cvd_slope = tv_vals.get("CVD Slope")
        if cvd_val is not None:
            cvd_dir = "买" if (cvd_slope and cvd_slope > 0) else "卖" if (cvd_slope and cvd_slope < 0) else "?"
            engine_data["cvd_tv"] = {"value": cvd_val, "slope": cvd_slope, "direction": cvd_dir}
            changes["tv_cvd_value"] = cvd_val
            changes["tv_cvd_slope"] = cvd_slope

    return changes


def _tv_cvd_override(cvd_data: dict, tv_vals: dict) -> dict:
    """用 TV CVD 真实值覆盖 Binance Taker 代理 CVD。"""
    if not tv_vals:
        return cvd_data
    cvd_val = tv_vals.get("CVD Value")
    cvd_slope = tv_vals.get("CVD Slope")
    if cvd_val is not None and cvd_slope is not None:
        direction = "买" if cvd_slope > 50 else "卖" if cvd_slope < -50 else "中性" if abs(cvd_slope) < 10 else ("买" if cvd_slope > 0 else "卖")
        quality = "A" if abs(cvd_slope) > 500 else "B" if abs(cvd_slope) > 200 else "C"
        return {"direction": direction, "quality": quality,
                "value": cvd_val, "slope": cvd_slope,
                "source": "TV真实CVD", "raw": cvd_data}
    return cvd_data
def render_card_locked(symbol: str, merged: dict, results: list[dict], meta: dict,
                       engine_data: dict, grok: dict | None = None,
                       search_sent: str = "", community: str = "",
                       regime_name: str | None = None, now: datetime | None = None,
                       force_full: bool = False) -> str:
    """v6.9 混合排版：完整底板内容套速读版序号骨架。

    ⑩头部 + 一∼五段全部展开 + 预案A/B双轨 + 逐周期分解 + 三源裁决 + 风控⑩闸门。
    机器字段不渲染进卡片正文（仅落 trade_plans/monitor_levels）。
    """
    grok = grok or {}
    now = now or datetime.now(TZ)
    # E轮：自动富集宏观数据 (DXY / US10Y / 财报)
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from system_data_bridge import enrich_engine_data
        engine_data = enrich_engine_data(symbol, engine_data or {})
    except Exception:
        pass

    spot = engine_data.get("binance_spot", {})
    price = engine_data.get("prices", {}).get("primary") or spot.get("price")
    high = spot.get("24h_high")
    low = spot.get("24h_low")
    chg = spot.get("percent_change_24h")

    _downgrade_low_rr_a_status(meta, engine_data, price, symbol)
    status = meta.get("status", "B等待")
    direction = meta.get("direction", "wait")
    dir_cn = {"short": "空头", "long": "多头", "wait": "观望"}.get(direction, "观望")
    n5 = meta.get("confidence_5", merged.get("confidence_5", "?"))
    eng_conf = meta.get("engine_confidence", merged.get("global_confidence", 0))
    model_id = meta.get("model_id", "无")
    data_grade = meta.get("data_grade", "C")
    try:
        from risk_constitution import CONSTITUTION
        risk_pct_limit = CONSTITUTION.get("MAX_RISK_PER_TRADE_PCT", 0.01) * 100
    except Exception:
        risk_pct_limit = 1
    priority = meta.get("priority_plan", "无")
    short_c = float(merged.get("short_confidence", 0) or 0)
    long_c = float(merged.get("long_confidence", 0) or 0)
    bias_cn = str(merged.get("bias") or "?")
    setup_id = meta.get("setup_id", f"{symbol}-{model_id}-{now.strftime('%Y%m%d')}")

    # ── 辅助数据提取 ──
    fg = engine_data.get("fear_greed", {})
    cvd_data = engine_data.get("cvd", {})
    funding = engine_data.get("funding", {})
    oi_data = engine_data.get("oi", {})
    taker_data = engine_data.get("taker", {})
    ls_data = engine_data.get("long_short", {})
    klines = engine_data.get("klines", {})
    data_grade = meta.get("data_grade", "C")
    try:
        from risk_constitution import CONSTITUTION
        risk_pct_limit = CONSTITUTION.get("MAX_RISK_PER_TRADE_PCT", 0.01) * 100
    except Exception:
        risk_pct_limit = 1
    priority = meta.get("priority_plan", "无")
    levels = engine_data.get("monitor_levels", {}).get("symbols", {}).get(symbol, {})

    # ── 衍生数据推算 ──
    funding_rate = funding.get("rate_pct") or "N/A"
    oi_latest = oi_data.get("oi") or oi_data.get("value") or "N/A"
    oi_trend = _oi_trend(oi_data)
    taker_dir = taker_data.get("direction") or "N/A"
    taker_ratio = taker_data.get("ratio") or "N/A"
    cvd_dir = cvd_data.get("direction") or "N/A"
    cvd_quality_raw = cvd_data.get("quality") or "C"
    cvd_quality = cvd_quality_raw.replace("级", "") if isinstance(cvd_quality_raw, str) else str(cvd_quality_raw)
    # 数据等级降级：木桶原理——最弱一环决定
    data_grade = _effective_grade(data_grade, taker_data, engine_data)
    ls_long = ls_data.get("long") or "N/A"
    ls_short = ls_data.get("short") or "N/A"

    # ── 结构数据推算 ──
    k4h = klines.get("4h") or {}
    k1h = klines.get("1h") or {}
    k15m = klines.get("15m") or {}
    k5m = klines.get("5m") or {}

    # ── TV DMI 数据注入 ──
    tv_dmi_rows = {}
    tv_vals = {}
    tv_override = {"tv_active": False}
    try:
        import requests as _req, json as _j
        # 从 Hermes Web UI MCP 获取 TV 数据（通过内部管道）
        tv_raw = engine_data.get("_tv_data")
        if not tv_raw:
            # 尝试从 engine_data 的 cvd_tv 预注入字段读取
            pass
        # 如果有 TV Pine table 数据，解析它
        tv_pine = engine_data.get("_tv_pine", {})
        if tv_pine:
            tv_dmi_rows = _parse_tv_dmi_table(tv_pine.get("tables"))
            tv_vals = _parse_tv_study_values(tv_pine.get("studies"))
            if tv_dmi_rows:
                tv_override = _apply_tv_dmi_override(meta, engine_data, symbol, tv_dmi_rows, tv_vals)
                engine_data["_tv_override"] = tv_override  # 存储供 compact card 使用
                # 同步更新局部变量（TV DMI 可能覆盖了 status/direction）
                status = meta.get("status", status)
                direction = meta.get("direction", direction)
            # 用 TV 真实 CVD 覆盖 Binance Taker 代理
                if tv_vals.get("CVD Value") is not None:
                    cvd_data = _tv_cvd_override(cvd_data, tv_vals)
        # 注入 TV 价格轴数据到 klines（POC/VAH/VAL 更精确）
        if tv_vals:
            for tf_dict, tf_name in [(k4h, "4h"), (k1h, "1h"), (k15m, "15m"), (k5m, "5m")]:
                if isinstance(tf_dict, dict):
                    for tv_key, dict_key in [("POC Price", "poc"), ("VAH Price", "vah"),
                                             ("VAL Price", "val"), ("S VWAP", "vwap"),
                                             ("nPOC Price", "npoc")]:
                        if tv_key in tv_vals and dict_key not in tf_dict:
                            tf_dict[dict_key] = tv_vals[tv_key]
            # EMA 注入（日线趋势更准）
            for ema_key, ema_name in [("EMA 9", "ema9"), ("EMA 21", "ema21"),
                                       ("EMA 34", "ema34"), ("EMA 55", "ema55")]:
                if ema_key in tv_vals:
                    k15m[ema_name] = tv_vals[ema_key]
    except Exception:
        pass

    # ═══ VWAP/EMA 本地计算引擎 (v1.0) ═══
    vwap_ema = {}
    try:
        import sys as _s2
        _s2.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from vwap_ema_cvd_engine import vwap_ema_cvd_summary, calc_vwap as _calc_vwap
        # 从 engine_data 提取 klines 用于本地计算
        _vwap_klines = engine_data.get("_klines_raw") or []
        if not _vwap_klines:
            # 从 15m klines 重建 OHLCV 格式
            _k15m_list = k15m.get("bars") or k15m.get("data") or []
            if _k15m_list:
                _vwap_klines = _k15m_list
        if _vwap_klines:
            vwap_ema = vwap_ema_cvd_summary(symbol, _vwap_klines)
            engine_data["_vwap_ema"] = vwap_ema
    except Exception:
        pass
    adversarial = {}
    try:
        from adversarial_analyst import adversarial_scoring, adversarial_text_for_card
        adversarial = adversarial_scoring(engine_data, symbol, results)
        engine_data["_adversarial"] = adversarial
    except Exception:
        adversarial = {}

    # ═══ Polymarket 预测市场文本 ═══
    pm_text = engine_data.get("polymarket") or engine_data.get("_polymarket") or ""

    # ═══════════════════ v7.0 精简全卡 ═══════════════════
    _near_lv = _near_key_level(klines, price)
    _anchor_txt = "锚定" if _near_lv else "未锚定"
    structure_dir = _structure_verdict(klines, merged)
    engine_dir = "偏空" if short_c > long_c else "偏多" if long_c > short_c else "中性"
    flow_dir = _asset_flow_bias(symbol, cvd_dir, engine_data)
    resonance = "共振" if (structure_dir == engine_dir == flow_dir) or status.startswith("A") else "未共振"
    one_reason = f"{resonance}·{_anchor_txt}·{_kl_bias(k1h)}" if not status.startswith("A") else f"{resonance}·{_kl_bias(k4h)}主导"

    # ── ② 现价+多周期 ──
    tf_lines = " · ".join([
        f"4h{_kl_bias(k4h) or '?'}",
        f"1h{_kl_bias(k1h) or '?'}",
        f"15m{_kl_bias(k15m) or '?'}",
        f"5m{_sweep_state(k5m, merged) or '待扫'}"
    ])

    # ── ③ VWAP/EMA/CVD 三合一 ──
    fg_v = fg.get("value", "?") if fg else "?"
    v3_line = []
    if vwap_ema.get("available"):
        v = vwap_ema.get("vwap")
        ec = vwap_ema.get("ema_cloud")
        if v.get("vwap"):
            v3_line.append(f"VWAP `{v['vwap']}` {v.get('price_vs_vwap','?')}·{v.get('in_band','?')}")
        if ec:
            v3_line.append(f"EMA 快{ec.get('fast_cloud','?')}·慢{ec.get('slow_cloud','?')}·{ec.get('trend_strength','?')[:8]}")
    v3_line.append(f"CVD {cvd_dir}·Taker {taker_dir}·Funding {funding_rate}·FG {fg_v}")
    v3_str = " · ".join(v3_line)

    # ── ④ 关键位 ──
    sup = _sr_level(k1h, 'sup', price) or _fmt_price(k15m.get('val')) or '?'
    res = _sr_level(k1h, 'res', price) or _fmt_price(k15m.get('vah')) or '?'
    inv_line = meta.get('invalid_price') or _default_failure(dir_cn)
    exec_line = _exec_line(klines, merged, status)
    chase_line = _no_chase_line(klines, price)

    # ── 止损止盈 ──
    risk_amt = _adaptive_risk(engine_data)
    leverage_text = _leverage_text(symbol)
    prot_status = meta.get("protections_status", "未检测")
    bearish = (cvd_dir == "卖" or direction == "short")
    st_a = _calc_stop_target_atr(price, "short" if bearish else "long", klines, symbol)
    st_b = _calc_stop_target_atr(price, "long" if bearish else "short", klines, symbol)
    rr_a, rr_b = st_a["rr"], st_b["rr"]
    rr_a_note = "" if rr_a >= 2.0 else " ⚠R:R不足"
    rr_b_note = "" if rr_b >= 2.0 else " ⚠R:R不足"

    # ── 组装 ──
    display_symbol = _display_symbol(symbol)
    card_lines = [
        f"◷ {now.strftime('%m-%d %H:%M')} · {display_symbol} · {'BINANCE' if 'BTC' in symbol else 'EXNESS'} · 数据{data_grade} · {_source_count(engine_data)}源",
        "",
        f"① {status} · {model_id} · {n5}/13 · 置信 {eng_conf}/5",
        f"   理由：{one_reason}",
        "",
        f"② 现价 `{_fmt_price(price)}` · 高 `{_fmt_price(high)}` · 低 `{_fmt_price(low)}` · 日 `{float(chg or 0):+.2f}%`",
        f"   {tf_lines}",
        "",
        f"③ {v3_str}",
        "",
        f"④ 关键位：阻 `{_fmt_price(res)}` · POC `{_fmt_price(k15m.get('poc'))}` · VAH `{_fmt_price(k15m.get('vah'))}` · VAL `{_fmt_price(k15m.get('val'))}` · 支 `{_fmt_price(sup)}`",
        f"   三线：失效 `{_fmt_price(inv_line)}` · 执行 `{exec_line}` · 禁追 `{chase_line}`",
        "",
    ]

    # ── 预案A ──
    if status in ("B等待", "C等待", "X禁做") or direction == "wait":
        plan_a_label = "预案A · 主方向" 
        plan_a_entry = f"`{_fmt_price(st_a['stop'])}-{_fmt_price(st_a['target'])}`"
    else:
        plan_a_label = f"预案A · {'空' if bearish else '多'}（{'⚠优先' if resonance == '共振' else '备选'}）"
        plan_a_entry = f"`{_fmt_price(price)}`" if status.startswith("A") else f"`{_fmt_price(st_a['stop'])}-{_fmt_price(st_a['target'])}`"

    card_lines.extend([
        f"—— {plan_a_label} ——",
        f"⑤ 入场：{plan_a_entry} · {'限价' if status.startswith('A') else '条件触发'}",
        f"⑥ 止损：`{_fmt_price(st_a['stop'])}` — {'结构位' if st_a.get('stop_reason') else 'ATR×2'} · 止盈：`{_fmt_price(st_a['target'])}` `{_fmt_price(st_a['target'])}` — 1:{rr_a:.1f}{rr_a_note}",
        f"⑦ 仓位：{_pos_level(data_grade, status)} · 风险 `{risk_amt:.2f}U` · 杠杆 {leverage_text}",
        f"⑧ 失效：`{_fmt_price(inv_line)}` — 触发后取消·复查 {3}×15m",
        "",
    ])

    # ── 预案B ──
    plan_b_label = f"预案B · {'多' if bearish else '空'}（备选）"
    card_lines.extend([
        f"—— {plan_b_label} ——",
        f"⑨ 入场：`{_fmt_price(st_b['stop'])}` · 止损 `{_fmt_price(st_b['stop'])}` · 止盈 `{_fmt_price(st_b['target'])}` — 1:{rr_b:.1f}{rr_b_note}",
        f"   仓位：{_pos_level(data_grade, status)} · 风险 `{risk_amt:.2f}U`",
        "",
    ])

    # ── ⑩ 闸门 ──
    gate_parts = [
        f"数据{_gate_data(data_grade)}",
        f"风控{prot_status}",
        f"执行{_gate_exec(klines, price, status)}",
        f"心态{'✅' if status != 'X禁做' else '⛔禁做'}",
    ]
    card_lines.append(f"⑩ 闸门：{' · '.join(gate_parts)} — 不到不执行")
    card_lines.append(f"   决策：你来选方向——")

    full = "\n".join(card_lines) + "\n"
    
    # 决策模式：B等待但价格已锚定关键位 → 输出极简速读卡（替代全卡）
    anchored = _near_key_level(klines, price)
    if not force_full and status in ("B等待", "C等待", "X禁做") and anchored:
        compact = _compact_card(symbol, price, status, direction, model_id, klines, k4h, k5m, k15m,
                                merged, cvd_dir, cvd_quality, taker_dir, taker_ratio,
                                funding_rate, engine_data, risk_amt, risk_pct_limit,
                                prot_status, data_grade, fg, leverage_text, qty_unit, search_sent)
        if compact:
            return compact
    
    return full


# ── v6.9 helper functions ──

def _asset_class(symbol: str) -> str:
    su = symbol.upper()
    if "XAU" in su or "GOLD" in su:
        return "gold"
    if "CALL" in su or "PUT" in su or "OPTION" in su or any(ch.isdigit() for ch in su) and (su.endswith("C") or su.endswith("P")):
        return "option"
    # Forex pairs first (contain currency codes but not pure crypto)
    forex_markers = ["EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"]
    if any(x in su for x in forex_markers) and ("USDT" not in su and "USD" not in su[-4:]):
        return "forex"
    if any(x in su for x in forex_markers) or (su.endswith("USD") and len(su) <= 7 and not su.endswith("USDT")):
        return "forex"
    if su.endswith("USDT") or "BTC" in su or "ETH" in su or su.endswith("USD"):
        return "crypto"
    if su in ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN"] or (su.isalpha() and len(su) <= 5):
        return "stock"
    return "other"


def _display_symbol(symbol: str) -> str:
    su = symbol.upper()
    ac = _asset_class(su)
    if ac == "gold":
        return f"{su} · OANDA"
    if ac == "crypto":
        display = su if su.endswith(".P") else f"{su}.P"
        return f"{display} · BINANCE"
    if ac == "forex":
        return f"{su} · OANDA"
    if ac == "stock":
        return f"{su} · NASDAQ"
    if ac == "option":
        return f"{su} · OPRA"
    return f"{su} · 待确认"


def _asset_data_line(symbol: str, engine_data: dict, taker_data: dict, cvd_quality: str) -> str:
    ac = _asset_class(symbol)
    macro = engine_data.get("_macro") or {}
    dxy = engine_data.get("dxy") or macro.get("dxy")
    if ac == "crypto":
        return f"Taker{_grade_short(taker_data)} · CVD {cvd_quality}"
    if ac == "gold":
        dxy_str = f"DXY `{dxy:.2f}`" if dxy else "DXY N/A"
        return f"Spot/美元({dxy_str}) · CVD {cvd_quality}"
    if ac == "forex":
        dxy_str = f"DXY `{dxy:.2f}`" if dxy else ""
        return f"美元腿/SMT {dxy_str}".strip()
    if ac == "stock":
        ev = engine_data.get("event_flag") or macro.get("event_flag") or ""
        return f"指数/板块 · {ev or '成交量'}"
    if ac == "option":
        return "IV/希腊值/流动性"
    return "专用数据待接入"


def _asset_flow_line(symbol: str, engine_data: dict, funding_rate, taker_dir, taker_ratio, cvd_dir, cvd_quality: str) -> str:
    ac = _asset_class(symbol)
    macro = engine_data.get("_macro") or {}
    dxy = engine_data.get("dxy") or macro.get("dxy")
    us10y = engine_data.get("us10y") or macro.get("us10y")
    if ac == "crypto":
        return f"Funding `{funding_rate}` · Taker {taker_dir} `{taker_ratio}` · CVD {cvd_dir}{cvd_quality}"
    if ac == "gold":
        dxy_part = f"DXY `{dxy:.2f}`" if dxy else "DXY N/A"
        us_part = f"US10Y `{us10y:.2f}`" if us10y else ""
        return f"CVD {cvd_dir}{cvd_quality} · {dxy_part} {us_part}".strip()
    if ac == "forex":
        dxy_part = f"DXY `{dxy:.2f}`" if dxy else "DXY N/A"
        return f"{dxy_part} · 利差/央行窗口"
    if ac == "stock":
        ev = engine_data.get("event_flag") or macro.get("event_flag") or ""
        return f"指数/板块 · {ev or '量能'}"
    if ac == "option":
        return f"Delta/Theta/IV 待接"
    return f"结构 · 量价"


def _asset_catalyst_line(symbol: str, engine_data: dict, fg_v, search_sent) -> str:
    ac = _asset_class(symbol)
    macro = engine_data.get("_macro") or {}
    catalyst = engine_data.get("catalyst") or "无"
    ev = engine_data.get("event_flag") or macro.get("event_flag") or ""
    if ac == "crypto":
        return f"{catalyst} · F&G `{fg_v}` · {_x_dir(search_sent)}"
    if ac == "gold":
        dxy = engine_data.get("dxy") or macro.get("dxy")
        dxy_str = f"DXY `{_fmt_dxy(dxy)}`" if dxy else ""
        session = _kill_zone_name()
        return f"{catalyst} · {dxy_str} · {session}".strip(" · ")
    if ac == "forex":
        return f"{catalyst} · 央行/通胀窗口"
    if ac == "stock":
        return f"{catalyst} · 财报 {ev or '无'} · 大盘"
    if ac == "option":
        return f"{catalyst} · 财报/IV事件 {ev or '无'}"
    return catalyst


def _asset_flow_label(symbol: str) -> str:
    ac = _asset_class(symbol)
    return {
        "crypto": "订单流",
        "gold": "美元/订单流",
        "forex": "美元腿",
        "stock": "指数/板块",
        "option": "希腊值/IV",
    }.get(ac, "量价")


def _asset_flow_bias(symbol: str, cvd_dir: str, engine_data: dict) -> str:
    ac = _asset_class(symbol)
    if ac in {"crypto", "gold"}:
        return "偏空" if cvd_dir == "卖" else "偏多" if cvd_dir == "买" else "中性"
    if ac == "forex":
        value = str(engine_data.get("usd_leg_bias") or engine_data.get("dxy_bias") or "中性")
    elif ac == "stock":
        value = str(engine_data.get("sector_bias") or engine_data.get("index_bias") or "中性")
    elif ac == "option":
        value = str(engine_data.get("greeks_bias") or engine_data.get("iv_bias") or "中性")
    else:
        value = str(engine_data.get("flow_bias") or "中性")
    if "空" in value or "弱" in value:
        return "偏空"
    if "多" in value or "强" in value:
        return "偏多"
    return "中性"


def _asset_confirm_brief(symbol: str, cvd_dir: str) -> str:
    ac = _asset_class(symbol)
    if ac == "crypto":
        return "订单流配合"
    if ac == "gold":
        return "美元/美债不反向"
    if ac == "forex":
        return "美元腿配合"
    if ac == "stock":
        return "指数/板块配合"
    if ac == "option":
        return "Delta/IV可接受"
    return "量价配合"


def _fmt_asset_price(value: float, symbol: str) -> str:
    ac = _asset_class(symbol)
    if ac in {"forex", "option"}:
        return f"{value:,.4f}"
    if ac == "stock":
        return f"{value:,.2f}"
    return f"{value:,.0f}"


def _leverage_text(symbol: str) -> str:
    su = symbol.upper()
    ac = _asset_class(symbol)
    if ac == "gold":
        return "OANDA 1000x"
    if ac == "crypto":
        if su in ("BTCUSDT", "ETHUSDT"):
            return "Binance 100x"
        return "Binance 20x"
    if ac == "forex":
        return "按账户规则 (通常50-100x)"
    if ac == "stock":
        return "按账户规则 (通常1-5x 或 无杠杆)"
    if ac == "option":
        return "按账户规则 (高杠杆，注意时间价值)"
    return "按账户规则"

def _qty_unit(symbol: str) -> str:
    ac = _asset_class(symbol)
    if ac == "gold":
        return "oz"
    if ac == "crypto":
        su = symbol.upper()
        return su.removesuffix("USDT") if su.endswith("USDT") else su
    if ac == "forex":
        return "手"
    if ac == "stock":
        return "股"
    if ac == "option":
        return "合约"
    return "单位"


def _asset_confirm_text(symbol: str, bias_cn: str, cvd_dir: str) -> str:
    ac = _asset_class(symbol)
    if ac == "crypto":
        return f"CVD{cvd_dir or '待确认'}与Taker顺向，现货vs永续不分裂，突破接受必须无背离"
    if ac == "gold":
        return "London/NY Kill Zone优先，DXY/美债不反向，扫荡后出现Displacement"
    if ac == "forex":
        return "美元腿或交叉盘同向，15m收线确认，重大央行数据窗口外"
    if ac == "stock":
        return "指数与板块不反向，成交量放大，避开财报/停牌/盘前盘后异常"
    if ac == "option":
        return "方向确认后再看Delta/Gamma/Theta/Vega与IV分位，权利金最大亏损可接受"
    return "结构、量价、风控三项同时确认"


def _asset_risk_text(symbol: str) -> str:
    ac = _asset_class(symbol)
    if ac == "crypto":
        return "Funding/OI拥挤降仓；逐仓优先；强制止损不撤"
    if ac == "gold":
        return "1000x只是账户上限；按美元止损距离反算oz，数据前后禁追"
    if ac == "forex":
        return "按点数与手数反算风险，确认隔夜利息与点差扩大"
    if ac == "stock":
        return "按股数与缺口风险反算仓位，财报前默认降仓或禁做"
    if ac == "option":
        return "最大亏损=权利金；Theta和IV回落风险必须写入；不裸卖高风险期权"
    return "按账户规则和结构止损反算仓位"


def _asset_review_text(symbol: str) -> str:
    ac = _asset_class(symbol)
    if ac == "crypto":
        return "复核CVD/Taker/OI是否续航，+1R移保本，Funding异常立即降仓"
    if ac == "gold":
        return "复核Kill Zone是否结束、DXY/美债是否反向、扫荡点是否被重新接受"
    if ac == "forex":
        return "复核美元腿、点差、央行日历与15m结构是否延续"
    if ac == "stock":
        return "复核指数/板块、成交量、新闻与盘中VWAP是否支持"
    if ac == "option":
        return "复核Delta变化、Gamma风险、Theta衰减、IV回落与剩余到期天数"
    return "复核结构、量价、风控与是否移损"


def _oi_trend(oi_data: dict) -> str:
    if not oi_data: return ""
    try: return " (微降)" if oi_data.get("trend") == "down" else " (微升)" if oi_data.get("trend") == "up" else ""
    except: return ""

def _kl_summary(k: dict, role: str) -> str:
    if not k: return f"{role}无数据"
    desc = k.get("description") or k.get("state") or ""
    return desc if desc else f"{role}数据待采集"

def _score13(merged: dict, results: list[dict], status: str, symbol: str = "BTCUSDT") -> str:
    struct_s = 2 if any(r.get("name") in FIXED_MODELS for r in (results or [])) else 1
    cycle_s = 1
    flow_s = 1
    deriv_s = 0 if status == "B等待" else 1
    cat_s = 0
    risk_s = 1 if status != "X禁做" else 0
    sent_s = 1
    total = struct_s + cycle_s + flow_s + deriv_s + cat_s + risk_s + sent_s

    # E轮：宏观加分 (DXY 对齐、财报注意)
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from system_data_bridge import asset_macro_enrich
        macro = asset_macro_enrich(symbol)
        ac = macro.get("asset_class", _asset_class(symbol))
        if ac in ("gold", "forex") and macro.get("dxy"):
            total = min(total + 1, 13)  # DXY SMT 对齐加分
        if ac == "stock" and "财报" in str(macro.get("event_flag", "")):
            total = max(total - 1, 0)   # 财报窗口降分
    except:
        pass

    ac = _asset_class(symbol)
    flow_name = {"crypto": "订单流", "gold": "流动性", "forex": "美元腿", "stock": "板块量", "option": "希腊值"}.get(ac, "量价")
    deriv_name = "衍生" if ac in {"crypto", "option"} else "宏观" if ac in {"gold", "forex"} else "市场"
    return f"{total}/13 — 结构+{struct_s}·周期+{cycle_s}·{flow_name}+{flow_s}·{deriv_name}+{deriv_s}·催化+{cat_s}·风控+{risk_s}·情绪+{sent_s}"

def _decision_text(merged: dict, status: str) -> str:
    bias = str(merged.get("bias") or "?")
    if status == "X禁做": return "禁止交易"
    if status == "B等待": return f"等待{bias}方向确认"
    return f"{bias}方向执行" if status.startswith("A") else "观望"

def _reason_one_liner(merged: dict, dir_cn: str) -> str:
    bias = str(merged.get("bias") or "?")
    if dir_cn == "观望": return "等确认后入场，不追价不抄底"
    return f"{bias}信号明确，按预案执行"

def _pos_level(data_grade: str, status: str) -> str:
    if status == "X禁做": return "禁止"
    if data_grade == "C": return "半仓"
    if status == "B等待": return "轻仓"
    return "正常"

def _default_failure(dir_cn: str) -> str:
    if dir_cn == "空头": return "关键结构位反向收复"
    if dir_cn == "多头": return "关键结构位反向收复"
    return "等方向选择"

def _source_count(ed: dict) -> int:
    src = 0
    if ed.get("prices", {}).get("primary"): src += 1
    if ed.get("binance_spot"): src += 1
    if ed.get("cmc_global"): src += 1
    return max(src, 1)

def _grade_short(data: dict) -> str:
    if not data: return "C"
    return "A" if data.get("quality") == "A" else "B"

def _compute_perfect_signals(engine_data: dict, symbol: str, price: float) -> dict:
    """Perfect community signals: liquidity_sweep, cvd_divergence, displacement, kill_zone, confluence.
    Uses existing snapshot + simple rules mapped from community (Sweep + CVD + Displacement).
    """
    ed = engine_data or {}
    su = symbol.upper()
    is_xau = "XAU" in su
    is_btc = "BTC" in su

    # Kill Zone / Session (community multi-asset adaptation)
    from datetime import datetime
    now = datetime.now()
    hour = now.hour
    if is_xau:
        if 2 <= hour < 5 or 7 <= hour < 10:
            kill_zone = "London/NY Kill Zone — 内 · 高优先"
        else:
            kill_zone = "非Kill Zone — 静默或降级"
    elif is_btc or "ETH" in su:
        kill_zone = "全时段 (加密24/7) · 优先高流动性窗口"
    else:
        # forex/stock default community practice
        if 2 <= hour < 5 or 7 <= hour < 11:  # London + NY open
            kill_zone = "主要交易时段 — London/NY优先"
        else:
            kill_zone = "低流动性时段 — 降级或观察"

    # Liquidity Sweep + CVD (core from community)
    sweep = "无"
    cvd_div = "无背离"
    displacement = "弱"
    try:
        levels = ed.get("levels", []) or []
        cvd = ed.get("cvd", {}) or {}
        cvd_dir = cvd.get("direction", "中性")
        if levels:
            for l in levels[:2]:
                if "扫" in str(l.get("name", "")) or "sweep" in str(l.get("name", "")).lower():
                    sweep = f"已扫 {l.get('name')}"
                    if cvd_dir in ("买", "卖"):
                        cvd_div = f"价格 + CVD {cvd_dir} 背离/吸收"
                    break
        # Simple displacement: large move in recent klines
        k5 = ed.get("klines", {}).get("5m", {})
        if k5 and k5.get("close") and k5.get("open"):
            chg = abs(k5["close"] - k5["open"]) / max(k5["open"], 1) * 100
            if chg > 0.3:
                displacement = "强"
    except:
        pass

    # Confluence score (community multi-asset: Sweep + CVD + Kill + Displacement + SMT)
    conf = 0
    if "已扫" in sweep: conf += 3
    if "背离" in cvd_div or "吸收" in cvd_div: conf += 2
    if "Kill Zone" in kill_zone and is_xau: conf += 2
    if "主要交易时段" in kill_zone and not is_btc: conf += 1   # forex/stock boost
    if displacement == "强": conf += 1

    # Asset specific confluence from new data bridge (DXY SMT, earnings)
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from system_data_bridge import asset_macro_enrich
        macro = asset_macro_enrich(symbol)
        if macro.get("dxy") and (is_xau or "forex" in str(_asset_class(symbol)).lower()):
            conf += 1  # SMT confirmation boost
        if "财报" in macro.get("event_flag", ""):
            conf -= 1  # caution during earnings
    except:
        pass

    confluence = f"{min(conf, 8)}/8 — {'高概率' if conf >= 5 else '需更多确认'}"

    return {
        "liquidity_sweep": sweep,
        "cvd_divergence": cvd_div,
        "displacement": displacement,
        "kill_zone": kill_zone,
        "confluence": confluence,
        "is_xau": is_xau,
        "is_btc": is_btc
    }


def _cvd_note(quality: str) -> str:
    if quality == "C": return "（K线估算）"
    return ""

def _data_consistency(ed: dict) -> str:
    spread = ed.get("spread_pct")
    if spread is not None: return f"价差≤{float(spread):.2f}%"
    return "多源一致"

def _lev_sentiment(funding_rate, ls_long) -> str:
    try:
        fr = float(str(funding_rate).replace("%",""))
        if fr > 0.01: return "偏多(多头拥挤)"
        if fr < -0.01: return "偏空"
        return "中性"
    except: return "中性"

def _taker_cvd_read(taker_dir, cvd_dir, cvd_quality) -> str:
    if taker_dir == cvd_dir: return "确认方向" if cvd_quality == "A" else "弱确认"
    return "背离需关注" if cvd_dir != "N/A" else "待采集"

def _liquidation(klines: dict, side: str) -> str:
    if not klines: return "N/A"
    k4h = klines.get("4h") or klines
    hi = k4h.get("high") or "N/A"
    lo = k4h.get("low") or "N/A"
    return str(hi) if side == "up" else str(lo)

def _liq_read(klines: dict, price) -> str:
    if not klines or not price: return "数据待采"
    return "下方清算池待扫" if float(price or 0) < 63000 else "上方积累空头止损"

def _nna(ed: dict, key: str, default: str = "N/A") -> str:
    return str(ed.get(key, default))

def _macro_read(ed: dict) -> str:
    return "周末数据缺口" if ed.get("dxy") is None else "风险偏好参考"

def _catalyst_impact(ed: dict) -> str:
    cat = ed.get("catalyst", "")
    return "周末无宏观催化·纯技术博弈" if not cat or cat == "N/A" else f"{cat}影响"

def _cg_read(ed: dict) -> str:
    cg = ed.get("cg_sentiment") or ed.get("coingecko")
    if isinstance(cg, dict): return f"{cg.get('up_pct','?')}%看多"
    return str(cg) if cg else "未采集"

def _sent_conflict(search_sent: str, bias_cn: str) -> bool:
    if not search_sent: return False
    if bias_cn == "偏空" and "多" in search_sent and "空" not in search_sent: return True
    if bias_cn == "偏多" and "空" in search_sent and "多" not in search_sent: return True
    return False

def _gaps(ed: dict) -> str:
    g = []
    if not ed.get("dxy"): g.append("DXY")
    if not ed.get("us10y"): g.append("US10Y")
    if not ed.get("spx"): g.append("SPX")
    return "·".join(g) if g else "无"

def _env_risk(data_grade: str, status: str) -> str:
    if status == "X禁做": return "禁止"
    if data_grade == "C": return "降级"
    return "允许"

def _risk_reason(status: str, bias_cn: str) -> str:
    if status == "B等待": return f"{bias_cn}方向未确认"
    if status == "X禁做": return "禁做条件触发"
    return "方向明确·数据达标"

def _kl_bias(k: dict) -> str:
    if not k: return "无数据"
    d = k.get("direction") or k.get("bias") or ""
    if d: return d
    desc = k.get("description", "")
    if "上涨" in desc or "多头" in desc: return "偏多"
    if "下跌" in desc or "空头" in desc: return "偏空"
    return "震荡"

def _kl_reason(tf: str, k: dict, merged: dict) -> str:
    desc = k.get("description") or k.get("reason") or ""
    if desc: return desc
    bias = str(merged.get("bias") or "")
    return f"{bias}方向主导"

def _trend_4h(k: dict) -> str:
    d = k.get("trend") or ""
    return d if d else "下降 — EMA空头排列"

def _vwap(k: dict, period: str = "s") -> str:
    v = k.get(f"vwap_{period}") or k.get("vwap")
    return f"{v:,.0f}" if v else "N/A"

def _vwap_pos(k: dict, price) -> str:
    if not price or not k: return "位置待算"
    v = k.get("vwap") or k.get("vwap_s")
    if not v: return "位置待算"
    diff = float(price) - float(v)
    return f"价格{'高于' if diff > 0 else '低于'}所有VWAP，偏离{abs(diff):,.0f}"

def _value_area(k: dict, level: str) -> str:
    v = k.get(level) or k.get(f"value_{level}")
    return f"{v:,.0f}" if v else "N/A"

def _va_read(k: dict, price) -> str:
    val = k.get("val") or k.get("value_val")
    if val and price:
        return "价格在价值区内" if float(price) > float(val) else "价格已跌破VAL，正在价值区外"
    return "待算"

def _liq_level(k: dict, side: str, price) -> str:
    if side == "up":
        return f"{k.get('resistance') or k.get('high') or 'N/A'}"
    return f"{k.get('support') or k.get('low') or 'N/A'}"

def _liq_direction(k: dict, price) -> str:
    return "向下磁吸" if price and float(price or 0) < 63000 else "向上磁吸"

def _invalid_4h(k: dict, merged: dict) -> str:
    hi = k.get("high") or "N/A"
    return str(hi)

def _invalid_reason_4h(merged: dict) -> str:
    return "收复本次4h下跌起点才看反转"

def _sr_level(k: dict, side: str, price) -> str:
    if side == "res":
        return f"{k.get('resistance') or k.get('high') or 'N/A'}"
    return f"{k.get('support') or k.get('low') or 'N/A'}"

def _atr_15m(klines: dict) -> float:
    k15 = klines.get("15m") or {}
    return float(k15.get("atr") or 242)

def _chase_ok(dist: float, atr: float) -> str:
    if atr <= 0: return "N/A"
    return "不追空" if dist < 2 * atr else "可追"

def _trigger_5m(k: dict, merged: dict, model_id: str) -> str:
    return f"{model_id}形态未确认 — 需15m收线确认"

def _noise_5m(k: dict) -> str:
    vol = k.get("volume") or 0
    return "低量弱反弹 — 可能是空头回补而非真正买盘" if float(vol or 0) < 200 else "正常"

def _tf_verdict(tf: str, k: dict, merged: dict) -> str:
    if tf == "4h": return "4h下降结构完整，空头压制明显但延伸已远"
    if tf == "1h": return "1h急跌结构完整，尾K缩量企稳，超卖修正概率上升"
    if tf == "15m": return "15m等待结构确认"
    return "5m无操作价值"

def _exec_line(klines: dict, merged: dict, status: str) -> str:
    k4h = klines.get("4h") or {}
    val = k4h.get("val") or k4h.get("value_val")
    return f"{val:,.0f}" if val else "N/A"

def _no_chase_line(klines: dict, price) -> str:
    k15 = klines.get("15m") or {}
    lo = k15.get("low") or price or 0
    return f"{float(lo):,.0f}"

def _dmi_bg(merged: dict) -> str:
    return str(merged.get("bias") or "?")

def _dmi_pos(klines: dict, price) -> str:
    return "价值区外" if price and float(price or 0) < 63000 else "价值区内"

def _dmi_vol(klines: dict) -> str:
    return "放量急跌缩量企稳"

def _flow_confirm(cvd_dir: str, taker_dir: str, bias_cn: str) -> str:
    if cvd_dir == taker_dir: return "确认方向"
    return "分歧待确认"

def _price_momentum(klines: dict) -> str:
    """近端价格动量方向：取15m优先,回退5m。返回 上行/下行/横盘。"""
    k = klines.get("15m") or klines.get("5m") or {}
    c = k.get("close"); o = k.get("open")
    try:
        c = float(c); o = float(o)
        if o <= 0: return "横盘"
        chg = (c - o) / o * 100
        if chg > 0.15: return "上行"
        if chg < -0.15: return "下行"
        return "横盘"
    except (TypeError, ValueError):
        return "横盘"

def _cvd_divergence(cvd_dir: str, klines: dict, near_level: bool) -> str:
    """CVD背离判定(社区精华·CryptoCred吸收理论)。
    perp CVD方向 vs 价格动量不一致 → 吸收/假突破 → 反转预警。
    仅在锚定关键位时才升级为⚠预警(订单流锚定结构铁律)。"""
    mom = _price_momentum(klines)
    # CVD 买=买方激进(看多) 卖=卖方激进(看空)
    cvd_bull = cvd_dir == "买"
    cvd_bear = cvd_dir == "卖"
    if mom == "横盘" or cvd_dir in ("N/A", None, ""):
        return "无显著背离 — CVD与价格动量未分歧"
    # 背离: CVD看多但价格不跟(下行) / CVD看空但价格上行
    diverge = (cvd_bull and mom == "下行") or (cvd_bear and mom == "上行")
    if not diverge:
        return f"同向 — CVD{cvd_dir}·价格{mom}·订单流续航确认"
    tag = "⚠ 关键位吸收·反转预警" if near_level else "背离·须价到关键位才计入"
    side = "多头无续航(诱多/吸筹离场)" if cvd_bull else "空头无续航(诱空/吸筹回补)"
    return f"{tag} — CVD{cvd_dir}冲·价格{mom}不跟 → {side}"

def _near_key_level(klines: dict, price, threshold_pct: float = 0.4) -> bool:
    """价格是否锚定在关键位附近(±threshold_pct%)。订单流降噪铁律:孤立信号不计。"""
    try:
        p = float(price or 0)
        if p <= 0: return False
    except (TypeError, ValueError):
        return False
    cands = []
    for tf in ("4h", "1h", "15m"):
        k = klines.get(tf) or {}
        for key in ("vwap", "poc", "val", "vah", "value_val", "value_vah", "high", "low"):
            v = k.get(key)
            try:
                if v: cands.append(float(v))
            except (TypeError, ValueError):
                pass
    for lv in cands:
        if lv > 0 and abs(p - lv) / p * 100 <= threshold_pct:
            return True
    return False

def _x_dir(search_sent: str) -> str:
    if not search_sent: return "未采集"
    if "多" in search_sent and "空" not in search_sent: return "偏多"
    if "空" in search_sent: return "偏空"
    return "中性"

def _community_read(fg: dict, community: str) -> str:
    v = fg.get("value", "?") if fg else "?"
    try:
        if int(v) < 25: return "极度恐慌≠立刻抄底"
        if int(v) > 75: return "极度贪婪≠立刻反转"
        return "中性"
    except: return "分歧"

def _catalyst_dir(ed: dict) -> str:
    return ed.get("catalyst_direction") or "中性"

def _structure_verdict(klines: dict, merged: dict) -> str:
    bias = str(merged.get("bias") or "偏空")
    return f"偏{bias.replace('偏','')}" if "偏" in bias else bias

def _divergence_handling(resonance: str, status: str) -> str:
    if resonance == "共振": return "三源一致→允许预案"
    if status == "B等待": return "分歧→B等待"
    return "结构引擎相反→X或B"

def _boundary(klines: dict, merged: dict, price) -> str:
    k4h = klines.get("4h") or {}
    val = k4h.get("val") or k4h.get("value_val")
    return f"{float(val):,.0f}" if val else f"{float(price or 0):,.0f}"

def _boundary_up(boundary: str, bias_cn: str) -> str:
    return "反弹" if bias_cn == "偏空" else "延续"

def _boundary_down(boundary: str, bias_cn: str) -> str:
    return "空头延续" if bias_cn == "偏空" else "反转"

def _plan_a_name(bias_cn: str, model_id: str) -> str:
    dir_word = "空头延续" if bias_cn == "偏空" else "多头延续"
    return f"{dir_word} · {model_id}"


def _primary_plan_bias(bias_cn: str, k4h_direction: str = "", symbol: str = "", klines: dict = None, cvd_data: dict = None) -> str:
    """主方向判定：TV DMI > 4h继承 > 市场权重 > 引擎 > 默认偏多。"""
    # 4h方向有否决权：4h偏空时，引擎中性也优先空
    if k4h_direction in ("偏空", "bearish", "下跌"):
        return "偏空"
    if k4h_direction in ("偏多", "bullish", "上涨"):
        return "偏多"

    # 市场权重调整（P2: 对齐 TV 多市场评分）
    if symbol and klines and cvd_data:
        weighted = _asset_weight_bias(symbol, bias_cn, klines, cvd_data)
        if weighted != bias_cn:
            return weighted

    if bias_cn in ("偏空", "空头"):
        return "偏空"
    if bias_cn in ("偏多", "多头"):
        return "偏多"
    return "偏多"


def _asset_weight_bias(symbol: str, bias_cn: str, klines: dict, cvd_data: dict) -> str:
    """按资产类别调整方向权重（对齐 TV SVP 多市场评分逻辑）。

    加密：放量方向加分；贵金属/外汇：流动性扫掠加分；股票：指数联动。
    """
    ac = _asset_class(symbol)
    k15m = klines.get("15m") or {}
    vol = k15m.get("volume") or 0

    if ac == "crypto":
        # 加密：放量方向优先 + CVD 权重
        cvd_dir = cvd_data.get("direction", "?")
        if vol > 500 and cvd_dir == "买":
            return "偏多" if bias_cn != "偏空" else "偏空"  # 尊重引擎方向，放量确认
        if vol > 500 and cvd_dir == "卖":
            return "偏空" if bias_cn != "偏多" else "偏多"
        return bias_cn

    if ac in ("gold", "metal", "forex"):
        # 贵金属/外汇：流动性扫掠权重更高
        merged_kl = klines.get("merged") or {}
        swept_low = merged_kl.get("swept_low_reclaimed") or False
        swept_high = merged_kl.get("swept_high_rejected") or False
        if swept_low:
            return "偏多"  # 扫低收回→优先多
        if swept_high:
            return "偏空"  # 扫高拒绝→优先空
        return bias_cn

    if ac == "stock":
        # 股票：放量确认方向
        if vol > 100000:
            return bias_cn  # 放量确认原方向
        return "等待" if vol < 30000 else bias_cn

    return bias_cn


def _dir_from_bias(bias_cn: str) -> str:
    if bias_cn == "偏空":
        return "空头"
    if bias_cn == "偏多":
        return "多头"
    return "观望"


def _plan_failure_by_bias(bias_cn: str) -> str:
    if bias_cn == "偏空":
        return "站回关键位并被15m接受"
    if bias_cn == "偏多":
        return "跌破关键位并被15m接受"
    return "方向未确认"

def _plan_a_trigger(model_id: str, klines: dict, merged: dict) -> str:
    bias = str(merged.get("bias") or "偏空")
    if bias == "偏空":
        return f"反弹至EMA21失败回落"
    return f"回踩支撑确认"

def _plan_stop(klines: dict, merged: dict, price, bias_cn: str, symbol: str = "BTCUSDT") -> str:
    p = float(price or 0)
    if p <= 0:
        p = 63000
    k4h = klines.get("4h") or {}
    hi = float(k4h.get("high") or p * 1.015)
    lo = float(k4h.get("low") or p * 0.985)
    ac = _asset_class(symbol)
    # Use reasonable distance by asset; options are premium prices and must stay positive.
    if ac == "crypto":
        dist = max(hi - p, p - lo, p * 0.012)
    elif ac == "gold":
        dist = 12
    elif ac == "forex":
        dist = max((hi - lo) * 0.6, p * 0.0012)
    elif ac == "stock":
        dist = max((hi - lo) * 0.6, p * 0.012)
    elif ac == "option":
        dist = max(p * 0.18, 0.15)
    else:
        dist = max((hi - lo) * 0.6, p * 0.01)
    stop = p + dist if bias_cn == "偏空" else max(p - dist, 0.01)
    return _fmt_asset_price(stop, symbol)

def _plan_targets(klines: dict, price, bias_cn: str, symbol: str = "BTCUSDT"):
    p = float(price or 0)
    if p <= 0:
        p = 63000
    stop = float(_plan_stop(klines, {}, price, bias_cn, symbol).replace(",", ""))
    stop_dist = abs(stop - p)
    ac = _asset_class(symbol)
    min_dist = 0.10 if ac == "option" else (p * 0.0005 if ac == "forex" else 10)
    if stop_dist < min_dist:
        if ac == "crypto":
            stop_dist = p * 0.012
        elif ac == "gold":
            stop_dist = 12
        elif ac == "forex":
            stop_dist = p * 0.0012
        elif ac == "stock":
            stop_dist = max(p * 0.012, 1.0)
        elif ac == "option":
            stop_dist = max(p * 0.18, 0.15)
        else:
            stop_dist = p * 0.01
    rr1 = 2.0
    rr2 = 3.0
    if bias_cn == "偏空":
        tp1 = max(p - (stop_dist * rr1), 0.01)
        tp2 = max(p - (stop_dist * rr2), 0.01)
    else:
        tp1 = p + (stop_dist * rr1)
        tp2 = p + (stop_dist * rr2)
    return _fmt_asset_price(tp1, symbol), _fmt_asset_price(tp2, symbol)

def _stop_reason(bias_cn: str) -> str:
    return "反弹高点上沿" if bias_cn == "偏空" else "支撑下方"

def _qty_str(price, meta: dict, symbol: str = "BTCUSDT") -> str:
    """薄封装：返回格式化的仓位字符串，兼容 B等待 场景"""
    bias = meta.get("bias_cn", "偏空")
    return _qty(price, meta, bias, symbol)

def _qty(price, meta: dict, bias_cn: str, symbol: str = "BTCUSDT") -> str:
    risk = float(meta.get("risk_usd", 2))
    p = float(price or 62000)
    ac = _asset_class(symbol)
    # Realistic approximate stop distance in price units for typical setups
    if ac == "gold":
        stop_dist = 15.0   # ~15 USD for gold
    elif ac == "crypto":
        stop_dist = 400 if "BTC" in symbol.upper() else 20
    elif ac == "forex":
        stop_dist = 0.0015  # ~15 pips typical
    elif ac == "stock":
        stop_dist = 3.0
    elif ac == "option":
        stop_dist = max(p * 0.18, 0.15)
    else:
        stop_dist = 50
    qty = risk / max(stop_dist, 0.01)
    if ac == "crypto":
        return f"{qty:.5f}"
    if ac == "gold":
        return f"{qty:.3f}"
    if ac == "forex":
        return f"{qty:.2f}"
    if ac == "stock":
        return f"{int(max(qty, 1))}"
    return f"{qty:.2f}"

def _notional(price, meta: dict, bias_cn: str, symbol: str = "BTCUSDT") -> str:
    p = float(price or 62000)
    qty_str = _qty(price, meta, bias_cn, symbol)
    try:
        qty = float(qty_str)
    except:
        qty = 0.001
    ac = _asset_class(symbol)
    if ac == "gold":
        return f"{qty * p:,.0f}"
    if ac == "crypto":
        return f"{qty * p:,.0f}"
    if ac == "forex":
        # rough notional for 1 standard lot ~100k
        return f"~{qty * 100000 * p / 100000:,.0f} (名义)"
    if ac == "stock":
        return f"{qty * p:,.0f}"
    if ac == "option":
        return f"~{qty * p:,.0f} (权利金名义)"
    return f"{qty * p:,.0f}"

def _plan_a_failure(model_id: str, klines: dict, merged: dict) -> str:
    bias = str(merged.get("bias") or "偏空")
    if bias == "偏空":
        return f"站回关键位并被15m接受"
    return f"跌破关键位并接受"

def _trajectory(status: str, bias_cn: str, direction: str) -> str:
    if status == "B等待":
        return f"企稳 → 等确认 → 入场 → 复查 → 移损/止盈/失效"
    return f"{status} → 入场 → 复查 → 止盈/失效"

def _plan_b_name(bias_cn: str, model_id: str) -> str:
    alt = "多头反弹" if bias_cn == "偏空" else "空头回调"
    return f"{alt} · 次优"

def _alt_dir(bias_cn_or_dir: str) -> str:
    mapping = {"偏空": "多头", "偏多": "空头", "空头": "多头", "多头": "空头", "观望": "观望"}
    return mapping.get(bias_cn_or_dir, "观望")


def _opposite_bias(bias_cn: str) -> str:
    mapping = {"偏空": "偏多", "偏多": "偏空", "空头": "偏多", "多头": "偏空"}
    return mapping.get(bias_cn, "观望")

def _plan_entry_offset(price, bias_cn: str, symbol: str, direction: str = "a") -> float:
    """预案触发价偏移。预案A=主方向触发价（偏空→现价上方等反弹失败，偏多→现价下方等回踩）；
    预案B=反向，方向相反。返回偏移后的绝对价格。"""
    p = float(price or 0)
    ac = _asset_class(symbol)
    base = {"gold": 8, "forex": 0.0015, "stock": 2, "option": 0.2}.get(ac, 200)
    # 预案A主方向：偏空挂上方(+)、偏多挂下方(-)；预案B反向取反
    sign = (1 if bias_cn == "偏空" else -1)
    if direction == "b":
        sign = -sign
    return p + sign * base


def _fmt_entry(value: float, symbol: str) -> str:
    ac = _asset_class(symbol)
    if ac in {"forex", "option"}:
        return f"{value:,.4f}"
    return f"{value:,.0f}"


def _plan_a_entry(klines: dict, merged: dict, price, bias_cn: str, symbol: str = "BTCUSDT") -> str:
    return _fmt_entry(_plan_entry_offset(price, bias_cn, symbol, "a"), symbol)


def _plan_b_entry(klines: dict, merged: dict, price, bias_cn: str, symbol: str = "BTCUSDT") -> str:
    return _fmt_entry(_plan_entry_offset(price, bias_cn, symbol, "b"), symbol)

def _plan_b_trigger(model_id: str, klines: dict, merged: dict, bias_cn: str) -> str:
    if bias_cn == "偏空":
        return "站回VAL + 15m收线确认"
    return "跌破支撑 + 15m收线确认"

def _plan_stop_b(klines: dict, price, bias_cn: str, symbol: str = "BTCUSDT") -> str:
    return _plan_stop(klines, {}, price, _opposite_bias(bias_cn), symbol)

def _plan_targets_b(klines: dict, price, bias_cn: str, symbol: str = "BTCUSDT"):
    return _plan_targets(klines, price, _opposite_bias(bias_cn), symbol)

def _qty_b(price, meta: dict, bias_cn: str, symbol: str = "BTCUSDT") -> str:
    risk = float(meta.get("risk_usd", 2))
    ac = _asset_class(symbol)
    if ac == 'gold': stop_dist = 12.0
    elif ac == 'crypto': stop_dist = 350 if 'BTC' in symbol.upper() else 18
    elif ac == 'forex': stop_dist = 0.0012
    elif ac == 'stock': stop_dist = 2.5
    else: stop_dist = 40
    qty = risk / max(stop_dist, 0.01)
    if ac == 'crypto': return f'{qty:.5f}'
    if ac == 'gold': return f'{qty:.3f}'
    if ac == 'stock': return f'{int(max(qty,1))}'
    return f'{qty:.2f}' 

def _notional_b(price, meta: dict, bias_cn: str, symbol: str = "BTCUSDT") -> str:
    p = float(price or 62000)
    qty_str = _qty_b(price, meta, bias_cn, symbol)
    try: qty = float(qty_str)
    except: qty = 0.001
    ac = _asset_class(symbol)
    if ac == 'gold': return f'{qty * p:,.0f}'
    if ac == 'crypto': return f'{qty * p:,.0f}'
    if ac == 'forex': return f'~{qty * 100000 * p / 100000:,.0f} (名义)'
    if ac == 'stock': return f'{qty * p:,.0f}'
    if ac == 'option': return f'~{qty * p:,.0f}'
    return f'{qty * p:,.0f}' 

def _plan_b_failure(klines: dict, merged: dict, price, bias_cn: str) -> str:
    if bias_cn == "偏空":
        return "跌回VAL下方"
    return "站回阻力上方"

def _trajectory_b(status: str, bias_cn: str) -> str:
    alt = "反弹" if bias_cn == "偏空" else "回调"
    return f"急跌 → 企稳 → {alt} → 入场 → 目标VWAP/EMA"

def _stop_pair(klines: dict, merged: dict, price, bias_cn: str, symbol: str = "BTCUSDT") -> str:
    s = _plan_stop(klines, merged, price, bias_cn, symbol)
    return f"A `{s}` · B `{_plan_stop_b(klines, price, bias_cn)}`"

def _gate_data(data_grade: str) -> str:
    return "通过" if data_grade in ("A", "B") else "C级→强制半仓"

def _gate_event(ed: dict) -> str:
    return "禁做" if ed.get("event_ban") else "通过"

def _has_event(ed: dict) -> bool:
    return bool(ed.get("event_ban"))

def _gate_exec(klines: dict, price, status: str) -> str:
    if status == "B等待": return "等待"
    return "通过"


def _binance_sign(params: dict, secret: str) -> str:
    """HMAC-SHA256签名"""
    import hmac, hashlib, urllib.parse
    query = urllib.parse.urlencode(params)
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()


def _binance_headers(api_key: str = "") -> dict:
    return {"X-MBX-APIKEY": api_key} if api_key else {}


_BINANCE_TIME_OFFSET_MS = None


def _binance_timestamp(base: str = "https://fapi.binance.com") -> int:
    """Return Binance server-aligned timestamp to avoid -1021 recvWindow drift."""
    global _BINANCE_TIME_OFFSET_MS
    import requests, time as _time
    local_ms = int(_time.time() * 1000)
    if _BINANCE_TIME_OFFSET_MS is None:
        try:
            r = requests.get(f"{base}/fapi/v1/time", timeout=3)
            server_ms = int((r.json() or {}).get("serverTime") or local_ms)
            _BINANCE_TIME_OFFSET_MS = server_ms - local_ms
        except Exception:
            _BINANCE_TIME_OFFSET_MS = 0
    return int(_time.time() * 1000) + int(_BINANCE_TIME_OFFSET_MS or 0)


def _signed_binance_params(params: dict, secret: str, base: str = "https://fapi.binance.com") -> dict:
    signed = dict(params)
    signed.setdefault("recvWindow", 10000)
    signed["timestamp"] = _binance_timestamp(base)
    signed["signature"] = _binance_sign(signed, secret)
    return signed


def _load_binance_keys() -> tuple:
    """Load Binance API keys from secrets"""
    import json
    from pathlib import Path
    try:
        data = json.loads(Path("D:/hermes Agent/hermes/secrets/binance.json").read_text())
        return data.get("api_key", ""), data.get("secret_key", "")
    except Exception:
        return "", ""


def _downgrade_low_rr_a_status(meta: dict, engine_data: dict, price, symbol: str) -> dict | None:
    """Hard gate: an A plan with R:R < 2.0 must not render as executable."""
    status = str(meta.get("status") or "")
    direction = str(meta.get("direction") or "wait")
    if not status.startswith("A") or direction not in ("long", "short"):
        return None
    try:
        rr_plan = _calc_stop_target_atr(price, direction, engine_data.get("klines", {}) or {}, symbol)
        rr = float(rr_plan.get("rr") or 0)
    except Exception:
        return None
    if rr >= 2.0:
        meta["rr1"] = rr
        return None
    previous_status = status
    meta["status"] = "X禁做"
    meta["priority_plan"] = "无"
    meta["rr1"] = rr
    meta["invalid_price"] = rr_plan.get("stop")
    meta["hard_gate_reason"] = f"R:R硬闸 {previous_status}→X禁做 · 1:{rr:.1f}<1:2"
    engine_data.setdefault("_hard_gates", []).append(meta["hard_gate_reason"])
    return rr_plan


def _collect_binance_data(engine_data: dict, symbol: str) -> None:
    """Fetch Binance futures data with HMAC signing for authenticated endpoints."""
    import requests, time as _time, hmac, hashlib, urllib.parse
    # 只用于加密品种，金属/股票/外汇不碰（防止覆盖已有K线）
    su = symbol.upper()
    if "XAU" in su or "GOLD" in su:
        return
    ac = _asset_class(symbol) if callable(_asset_class) else (lambda s: "crypto" if s.endswith("USDT") else "other")(symbol)
    if ac not in ("crypto",):
        return
    base = "https://fapi.binance.com"
    sym = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
    api_key, secret = _load_binance_keys()
    
    # ── K-lines (public, no sign needed) ──
    klines = {}
    for tf, limit in [("5m", 12), ("15m", 20), ("1h", 20), ("4h", 20)]:
        try:
            r = requests.get(f"{base}/fapi/v1/klines", params={"symbol": sym, "interval": tf, "limit": limit}, timeout=8)
            data = r.json()
            if isinstance(data, list) and data:
                closes = [float(c[4]) for c in data]
                highs = [float(c[2]) for c in data]
                lows = [float(c[3]) for c in data]
                volumes = [float(c[5]) for c in data]
                chg_pct = (closes[-1] - closes[0]) / closes[0] if closes[0] else 0
                avg_vol = sum(volumes) / len(volumes) if volumes else 0
                rng = max(highs) - min(lows)
                poc = sum(closes) / len(closes) if closes else closes[-1]
                direction = "偏多" if chg_pct > 0.3 else "偏空" if chg_pct < -0.3 else "震荡"
                klines[tf] = {
                    "close": closes[-1], "high": max(highs), "low": min(lows),
                    "open": float(data[0][1]), "volume": sum(volumes),
                    "atr": (sum(h - l for h, l in zip(highs, lows)) / len(highs)) if highs else 0,
                    "change_pct": round(chg_pct, 4),
                    "avg_volume": avg_vol, "range": rng,
                    "poc": round(poc, 2), "vah": round(max(highs), 2), "val": round(min(lows), 2),
                    "direction": direction,
                    "description": _kl_desc(tf, closes, highs, lows, volumes),
                }
        except Exception:
            pass
    engine_data["klines"] = klines
    
    if not api_key:
        # No API key — fallback to public endpoints only
        try:
            r = requests.get(f"{base}/fapi/v1/fundingRate", params={"symbol": sym, "limit": 1}, timeout=5)
            data = r.json()
            if isinstance(data, list) and data:
                rate = float(data[0]["fundingRate"]) * 100
                engine_data["funding"] = {"rate_pct": f"{rate:.4f}%", "rate": rate}
        except Exception:
            pass
        try:
            r = requests.get(f"{base}/fapi/v1/openInterest", params={"symbol": sym}, timeout=5)
            data = r.json()
            engine_data["oi"] = {"oi": f"{float(data.get('openInterest',0)):,.0f}", "value": float(data.get("openInterest", 0))}
        except Exception:
            pass
        # CVD fallback
        try:
            from cvd_aggtrades import get_cvd_aggtrades
            cvd = get_cvd_aggtrades(sym)
            engine_data["cvd"] = {"direction": cvd.get("direction", "N/A"), "quality": cvd.get("quality", "B")}
        except Exception:
            pass
        return
    
    # ── HMAC-signed endpoints ──
    # Funding rate
    try:
        params = _signed_binance_params({"symbol": sym, "limit": 1}, secret, base)
        r = requests.get(f"{base}/fapi/v1/fundingRate", params=params, headers=_binance_headers(api_key), timeout=5)
        data = r.json()
        if isinstance(data, list) and data:
            rate = float(data[0]["fundingRate"]) * 100
            engine_data["funding"] = {"rate_pct": f"{rate:.4f}%", "rate": rate, "quality": "A"}
    except Exception:
        pass
    
    # Open Interest
    try:
        params = _signed_binance_params({"symbol": sym}, secret, base)
        r = requests.get(f"{base}/fapi/v1/openInterest", params=params, headers=_binance_headers(api_key), timeout=5)
        data = r.json()
        oi_val = float(data.get("openInterest", 0))
        # Check OI trend by comparing with previous (simple: store in engine_data for next call)
        prev_oi = engine_data.get("_prev_oi", {}).get(sym, oi_val)
        trend = "up" if oi_val > prev_oi * 1.001 else "down" if oi_val < prev_oi * 0.999 else "flat"
        engine_data.setdefault("_prev_oi", {})[sym] = oi_val
        engine_data["oi"] = {"oi": f"{oi_val:,.0f}", "value": oi_val, "trend": trend, "quality": "A"}
    except Exception:
        pass
    
    # Taker buy/sell ratio (correct endpoint: /futures/data/takerlongshortRatio)
    try:
        params = _signed_binance_params({"symbol": sym, "period": "5m", "limit": 1}, secret, base)
        r = requests.get(f"{base}/futures/data/takerlongshortRatio", params=params, headers=_binance_headers(api_key), timeout=5)
        data = r.json()
        if isinstance(data, list) and data:
            bs = float(data[0].get("buySellRatio", 1))
            engine_data["taker"] = {"ratio": f"{bs:.2f}", "direction": "buy" if bs >= 1 else "sell", "quality": "A", "raw": bs}
    except Exception:
        pass
    
    # Global long/short ratio
    try:
        params = _signed_binance_params({"symbol": sym, "period": "5m", "limit": 1}, secret, base)
        r = requests.get(f"{base}/futures/data/globalLongShortAccountRatio", params=params, headers=_binance_headers(api_key), timeout=5)
        data = r.json()
        if isinstance(data, list) and data:
            engine_data["long_short"] = {"long": float(data[0].get("longAccount", 0.5)), "short": float(data[0].get("shortAccount", 0.5))}
    except Exception:
        pass
    
    # CVD via spot aggTrades
    try:
        from cvd_aggtrades import get_cvd_aggtrades
        cvd = get_cvd_aggtrades(sym)
        engine_data["cvd"] = {"direction": cvd.get("direction", "N/A"), "quality": cvd.get("quality", "B")}
    except Exception:
        try:
            params = _signed_binance_params({"symbol": sym, "interval": "1m", "limit": 5}, secret, base)
            r = requests.get(f"{base}/fapi/v1/klines", params=params, headers=_binance_headers(api_key), timeout=5)
            data = r.json()
            if isinstance(data, list):
                buy_vol = sum(float(c[9]) for c in data if len(c) > 9)
                sell_vol = sum(float(c[5]) - float(c[9]) for c in data if len(c) > 9)
                engine_data["cvd"] = {"direction": "买" if buy_vol > sell_vol else "卖", "quality": "C"}
        except Exception:
            pass


def _kl_desc(tf: str, closes: list, highs: list, lows: list, volumes: list) -> str:
    """Generate a one-line description of recent K-line action."""
    if not closes: return "无数据"
    chg = (closes[-1] - closes[0]) / closes[0] * 100 if closes[0] else 0
    hi = max(highs); lo = min(lows)
    vol_trend = "放量" if volumes and volumes[-1] > sum(volumes[:-1]) / max(len(volumes)-1, 1) * 1.5 else "缩量" if volumes and volumes[-1] < sum(volumes[:-1]) / max(len(volumes)-1, 1) * 0.5 else ""
    if chg > 1: return f"上涨+{chg:.1f}% — {vol_trend}多头推进" if vol_trend else f"上涨+{chg:.1f}%"
    if chg < -1: return f"下跌{chg:.1f}% — {vol_trend}空头主导" if vol_trend else f"下跌{chg:.1f}%"
    if abs(chg) < 0.5 and vol_trend == "缩量": return "窄幅横盘缩量 — 等待方向"
    return f"震荡{chg:+.1f}% — {vol_trend}方向待定" if vol_trend else f"震荡{chg:+.1f}%"


def sanitize_card_format(card: str) -> str:
    """Apply template formatting hard rules for generated card text."""
    replacements = {
        "🥈 ": "", "🥇 ": "", "🥉 ": "",
        "🔴 ": "", "🟢 ": "", "🟡 ": "", "⭕ ": "",
        "✅ ": "", "⚠️ ": "⚠", "⏭️ ": "",
    }
    for old, new in replacements.items():
        card = card.replace(old, new)
    card = card.replace("热词[", "热词：").replace("]", "")
    card = card.replace("[", "")
    return card

def validate_card_rules(card: str, meta: dict) -> list[str]:
    errors = []
    for key in ("rr1", "rr2"):
        rr = meta.get(key)
        if rr is not None and float(rr) < 2.0:
            errors.append(f"R:R硬底线失败：{key}={rr} < 2.0")
    if not meta.get("setup_id") or not meta.get("model_id") or not meta.get("entry_tag") or not meta.get("exit_tag"):
        errors.append("机器字段缺失：setup_id/model_id/entry_tag/exit_tag 必填")
    return errors

def append_trade_plan(meta: dict, card: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    row = dict(meta); row["card_excerpt"] = card[:500]
    with (DATA / "trade_plans.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

def update_monitor_metadata(symbol: str, meta: dict) -> None:
    path = DATA / "monitor_levels.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        sym = data.setdefault("symbols", {}).setdefault(symbol, {})
        sym["latest_setup"] = {k: meta.get(k) for k in ("setup_id", "model_id", "entry_tag", "exit_tag", "direction", "status", "priority_plan", "data_grade", "level_confidence", "engine_confidence", "confidence_5", "expires_at", "monitor_write")}
        sym["updated"] = datetime.now(TZ).isoformat(); data["updated"] = datetime.now(TZ).isoformat()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"  ⚠ monitor metadata skipped: {e}")


def _safe_import(module, func):
    try:
        mod = __import__(module, fromlist=[func])
        return getattr(mod, func)
    except Exception as e:
        print(f"  ⚠️ {module}.{func}: {e}")
        return None


def auto_card(symbol: str, push: bool = False) -> str:
    """一键出卡"""
    print(f"\n{'='*60}")
    print(f"  棠溪 · 一键分析卡 · {symbol}")
    print(f"  {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    asset = "crypto" if symbol in ("BTCUSDT", "ETHUSDT") else "metal" if "XAU" in symbol.upper() else "stock"
    
    # ═══ Step 1: 数据采集 ═══
    print("① 数据采集...")
    
    engine_data = {"symbol": symbol, "quality": "B"}
    
    if asset == "crypto":
        # 期货价格优先（TV/Binance Perp），CMC现货作 backup
        futures_price = None
        try:
            import requests as _req
            sym = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
            r = _req.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={sym}", timeout=5)
            futures_price = float(r.json().get("price", 0))
        except Exception:
            pass
        
        try:
            from multi_source_collector import cmc_quote, cmc_global, cmc_fear_greed
            cmc = cmc_quote(symbol[:3])
            spot_price = cmc.get("price", 0)
            # 优先期货价，CMC现货为备用
            primary_price = futures_price or spot_price
            engine_data["binance_spot"] = {"price": spot_price, 
                                           "24h_high": spot_price * 1.03,
                                           "24h_low": spot_price * 0.97}
            engine_data["prices"] = {
                "primary": primary_price,
                "futures": futures_price or spot_price,
                "spot": spot_price,
                "source": "Binance期货" if futures_price else "CMC现货"
            }
            engine_data["quality"] = "A"
            engine_data["grades"] = {"overall": "A"}
            basis = f" 期现差{(futures_price/spot_price-1)*100:+.3f}%" if futures_price and spot_price else ""
            print(f"  ✅ 期货: ${primary_price:,.0f} (Binance Perp) | CMC现货: ${spot_price:,.0f}{basis} | 市占{cmc.get('dominance',0):.1f}%")
            
            # CMC global
            glob = cmc_global()
            engine_data["cmc_global"] = glob
            
            # F&G
            fg = cmc_fear_greed()
            engine_data["fear_greed"] = fg
            print(f"  ✅ 恐慌贪婪: {fg.get('value','?')} ({fg.get('classification','?')})")
            
        except Exception as e:
            print(f"  ⚠️ CMC: {e}")
            engine_data["binance_spot"] = {"price": 64000}
    elif asset == "metal":
        try:
            import requests as _req
            # gold-api.com 现货
            r = _req.get("https://api.gold-api.com/price/XAU", timeout=8)
            if r.status_code == 200:
                data = r.json()
                price = float(data.get("price", 4310))
                engine_data["prices"] = {"primary": price, "source": "gold-api现货"}
                engine_data["binance_spot"] = {
                    "price": price, "24h_high": price * 1.005,
                    "24h_low": price * 0.995, "percent_change_24h": 0
                }
                engine_data["quality"] = "B"
                engine_data["grades"] = {"overall": "B"}
                print(f"  ✅ XAU: ${price:,.0f} (gold-api)")
            
            # DXY from Yahoo
            try:
                dxy_r = _req.get(
                    "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=5d",
                    timeout=5, headers={"User-Agent": "Mozilla/5.0"}
                )
                if dxy_r.status_code == 200:
                    dxy_data = dxy_r.json()
                    dxy_price = dxy_data["chart"]["result"][0]["meta"]["regularMarketPrice"]
                    engine_data["dxy"] = dxy_price
                    print(f"  ✅ DXY: {dxy_price:.2f}")
            except Exception:
                engine_data["dxy"] = 100.85
            
            # K-lines from Yahoo GC=F (futures, adjusted for spot)
            try:
                import urllib.request, json as _j
                tf_map = {"5m": "5m", "15m": "15m", "1h": "1h", "4h": "1h"}  # Yahoo 1h as 4h proxy
                tf_range = {"5m": "1d", "15m": "5d", "1h": "7d", "4h": "1mo"}
                for tf, limit in [("5m", 12), ("15m", 20), ("1h", 20), ("4h", 20)]:
                    try:
                        ytf = tf_map[tf]
                        ry = tf_range[tf]
                        url = f"https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval={ytf}&range={ry}"
                        req = _req.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                        if req.status_code == 200:
                            result = _j.loads(req.text)["chart"]["result"][0]
                            quotes = result["indicators"]["quote"][0]
                            # futures→spot: GC contract premium typically $125+
                            spot_adj = -125
                            closes = [float(c) + spot_adj for c in quotes["close"] if c]
                            highs = [float(h) + spot_adj for h in quotes["high"] if h]
                            lows = [float(l) + spot_adj for l in quotes["low"] if l]
                            if closes:
                                closes = closes[-limit:]; highs = highs[-limit:]; lows = lows[-limit:]
                                chg = (closes[-1] - closes[0]) / closes[0] * 100 if closes[0] else 0
                                direction = "偏多" if chg > 0.2 else "偏空" if chg < -0.2 else "震荡"
                                klines_dict = engine_data.setdefault("klines", {})
                                klines_dict[tf] = {
                                    "close": closes[-1], "high": max(highs), "low": min(lows),
                                    "open": closes[0], "change_pct": round(chg, 4),
                                    "poc": round(sum(closes)/len(closes), 2),
                                    "vah": round(max(highs), 2), "val": round(min(lows), 2),
                                    "direction": direction,
                                    "description": _kl_desc(tf, closes, highs, lows, [0]*len(closes)),
                                }
                    except Exception:
                        pass
                if engine_data.get("klines"):
                    print(f"  ✅ XAU K线(Yahoo GC=F): {list(engine_data['klines'].keys())}")
            except Exception:
                pass
        except Exception as e:
            print(f"  ⚠️ XAU: {e}")
            engine_data["prices"] = {"primary": 4310}
    
    # ═══ Step 2: 引擎运算 ═══
    print("② 引擎运算...")
    merged = {}
    results = []
    try:
        from multi_model_engine import run_all_models, merge_directions, check_event_ban, call_grok_validation
        results = run_all_models(engine_data, symbol)
        banned, ban_reason = check_event_ban(engine_data, symbol)
        merged = merge_directions(results, event_ban=banned, event_ban_reason=ban_reason)
        print(f"  ✅ Bias: {merged['bias']} | Conf: {merged['global_confidence']:.3f} | n/5: {merged.get('confidence_5','?')}")
    except Exception as e:
        print(f"  ❌ Engine: {e}")
    
    # ═══ Step 3: Grok催化剂验证 ═══
    print("③ Grok催化剂...")
    grok = {}
    try:
        grok = call_grok_validation(symbol, merged, results, 
                                     price=engine_data.get("prices", {}).get("primary", 0),
                                     data=engine_data)
        if grok.get("agree"):
            merged["global_confidence"] = round(merged["global_confidence"] + 0.05, 3)
            print(f"  ✅ Grok: 催化剂已验证 | 置信+0.05")
        elif grok.get("skipped"):
            print(f"  ⏭️ Grok跳过: {grok['skipped']}")
        elif grok.get("error"):
            print(f"  ⚠️ Grok错误: {grok['error'][:60]}")
        else:
            print(f"  ⚠️ Grok: 无新热点")
            merged["action"] = "⚠Grok分歧→B等待"
            merged["confidence_5"] = min(merged.get("confidence_5", 4), 3)
            print(f"  ⚠️ Grok分歧 → B等待 | 方向: {grok.get('grok_direction','?')} {grok.get('grok_confidence',0):.3f}")
    except Exception as e:
        print(f"  ⚠️ Grok: {e}")
    
    # ═══ Step 4: 市场热点搜索 ═══
    print("④ 市场热点...")
    search_sent = ""
    try:
        from sentiment_search import sentiment_line
        search_sent = sentiment_line(symbol)
        print(f"  ✅ {search_sent}")
    except Exception as e:
        print(f"  ⚠️ 搜索: {e}")
    
    # ═══ Step 5: 社区情绪 ═══
    print("⑤ 社区情绪...")
    community = ""
    try:
        from coingecko_collector import community_dashboard
        community = community_dashboard()
        print(f"  ✅ {community[:80]}...")
    except Exception as e:
        print(f"  ⚠️ 社区: {e}")
    
    # ═══ Step 6: 市场体制（用于速读区一句话） ═══
    print("⑥ 市场体制...")
    regime_name = None
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from regime_classifier import classify_regime
        regime = classify_regime(
            vix=18.5,
            btc_change_24h_pct=engine_data.get("cmc", {}).get("percent_change_24h", -2.9),
            btc_volatility_20d_pct=3.8,
            fear_greed=int(engine_data.get("fear_greed", {}).get("value", 15) or 15),
        )
        regime_name = regime.name
        print(f"  ✅ 体制 {regime.name}")
    except Exception as e:
        print(f"  ⚠ 体制跳过: {e}")

    # ═══ Step 7: 锁定排版输出 ═══
    print("⑥.① Binance数据采集...")
    _collect_binance_data(engine_data, symbol)
    if engine_data.get("cvd", {}).get("direction"):
        print(f"  ✅ CVD {engine_data['cvd']['direction']} {engine_data['cvd'].get('quality','?')} | Taker {engine_data.get('taker',{}).get('direction','?')} | Funding {engine_data.get('funding',{}).get('rate_pct','?')}")
    
    print("⑦ 渲染锁定卡片...")
    meta = build_setup_metadata(symbol, merged, results, engine_data)

    # v6.9.14: TV DMI 决策表数据注入（从 TradingView MCP 读取）
    # v6.9.15b P0 fix: 优先读 engine_data._tv_pine（调用方注入）→
    #   回退读 data/tv_dmi_cache.json（cron agent 每5分钟更新）
    tv_dmi_data = {}
    try:
        tv_raw = engine_data.get("_tv_pine")
        if not tv_raw:
            # 回退：读 cron agent 维护的本地缓存
            import json as _j
            cache_path = ROOT / "data" / "tv_dmi_cache.json"
            if cache_path.exists():
                cache = _j.loads(cache_path.read_text(encoding="utf-8"))
                # 兼容两种缓存格式:
                # 格式A(cron agent): {"tv_data": {"grade":..., "action":...}}
                # 格式B(tv_signal_monitor): {"grade":..., "treatment":...}
                if "tv_data" in cache:
                    c = cache["tv_data"]
                    grade = c.get("grade", "C等待")
                    treatment = c.get("action") or c.get("treatment", "?")
                    background = c.get("background") or c.get("bias", "?")
                    position = c.get("position", "?")
                    cvd_state = c.get("cvd") or c.get("cvd_state", "?")
                    execution = c.get("execution")
                    if isinstance(execution, dict):
                        execution = f"多:{execution.get('long','?')}|空:{execution.get('short','?')}"
                    else:
                        execution = execution or "?"
                    risk = c.get("risk", "?")
                elif "grade" in cache:
                    # 格式C/D: cron agent 平键格式（4代变体）
                    grade = cache.get("grade", "C等待")
                    # 优先用 table_raw（最可靠：直接就是TV Pine表行）
                    if "table_raw" in cache and isinstance(cache["table_raw"], list):
                        tv_dmi_data = {
                            "studies": [],
                            "tables": [{"name": "SVP+ICT+VWAP+EMA+CVD", "tables": [{"rows": cache["table_raw"]}]}]
                        }
                    else:
                        treatment = cache.get("action") or cache.get("treatment", "?")
                        background = cache.get("background") or cache.get("bias", "?")
                        position = cache.get("position", "?")
                        cvd_state = cache.get("cvd") or cache.get("cvd_state", "?")
                        execution = cache.get("execution")
                        if isinstance(execution, dict):
                            execution = f"多:{execution.get('long','?')}|空:{execution.get('short','?')}"
                        else:
                            execution = execution or "?"
                        risk = cache.get("risk", "?")
                else:
                    # 格式B: tv_signal_monitor 旧格式
                    grade = cache.get("grade", "C等待")
                    treatment = cache.get("treatment", "?")
                    background = cache.get("background", "?")
                    position = cache.get("position", "?")
                    cvd_state = cache.get("cvd_state", "?")
                    execution = cache.get("execution", "?")
                    risk = cache.get("risk", "?")
                # 将缓存变量转换为 _tv_pine 格式（格式B/C未内联构建时走此处）
                if not tv_dmi_data:
                    tv_dmi_data = {
                        "studies": [],
                        "tables": [{"name": "SVP+ICT+VWAP+EMA+CVD", "tables": [{"rows": [
                            f"等级 | {grade}",
                            f"处理 | {treatment}",
                            f"背景 | {background}",
                            f"位置 | {position}",
                            f"量能 | 量能普通",
                            f"CVD | {cvd_state}",
                            f"执行 | {execution}",
                            f"风控 | {risk}",
                        ]}]}]
                    }
                engine_data["_tv_pine"] = tv_dmi_data
                tv_grade = cache.get("grade") if "grade" in cache else (cache.get("tv_data", {}).get("grade") if "tv_data" in cache else "?")
                print(f"  ✅ TV DMI(缓存): grade={tv_grade}")
        else:
            studies = tv_raw.get("studies", [])
            tables = tv_raw.get("tables", [])
            engine_data["_tv_pine"] = {"studies": studies, "tables": tables}
            tv_dmi_data = {"studies": studies, "tables": tables}
            print(f"  ✅ TV DMI(直连): {len(studies)} studies · {len(tables)} tables")
    except Exception as e:
        print(f"  ⚠ TV DMI跳过: {e}")
    
    # v2.0: Protections 状态注入
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from risk_constitution import apply_protections, load_protections
        from datetime import datetime as _dt
        current_bar = int(_dt.now().timestamp() // 300)
        prot = load_protections()
        prot_check = apply_protections(symbol, current_bar, prot)
        meta["protections_active"] = True
        meta["protections_passed"] = prot_check["passed"]
        meta["protections_status"] = "通过" if prot_check["passed"] else "拦截: " + "; ".join(prot_check["violations"])
        if not prot_check["passed"]:
            print(f"  ⚠️ Protections拦截: {meta['protections_status']}")
        else:
            print(f"  🛡️ Protections通过")
    except Exception as e:
        meta["protections_active"] = False
        meta["protections_status"] = f"未启用({e})"
    
    # ═══ Step 5: 双卡渲染 ═══
    # Card A: 完整分析卡（始终输出）
    full_card = render_card_locked(
        symbol, merged, results, meta, engine_data,
        grok=grok, search_sent=search_sent, community=community,
        regime_name=regime_name, force_full=True,
    )
    full_card = sanitize_card_format(full_card)
    rule_errors = validate_card_rules(full_card, meta)
    if rule_errors:
        print("  ⚠ 模板审计发现问题: " + "；".join(rule_errors))
    append_trade_plan(meta, full_card)
    update_monitor_metadata(symbol, meta)

    # Card B: 极简决策卡（仅当价格锚定关键位时）
    card = render_card_locked(
        symbol, merged, results, meta, engine_data,
        grok=grok, search_sent=search_sent, community=community,
        regime_name=regime_name, force_full=False,
    )
    card = sanitize_card_format(card)

    # Save both
    sym_name = symbol.replace('/', '_')
    full_path = DATA / f"auto_card_{sym_name}_full.md"
    compact_path = DATA / f"auto_card_{sym_name}.md"
    full_path.write_text(full_card, encoding="utf-8")
    compact_path.write_text(card, encoding="utf-8")
    
    is_compact = len(card.strip().split('\n')) <= 10
    print(f"  ✅ 已写入 {compact_path} ({'极简' if is_compact else '完整'})")
    print(f"  ✅ 已写入 {full_path} (完整)")
    
    # Show compact card (shorter) first, then note full card available
    print(f"\n{card}")
    if is_compact:
        line_count = len(full_card.strip().split('\n'))
        print(f"\n📋 完整分析卡 ({line_count}行) 已保存至 {full_path.name}")
    
    # ═══ Step 6: 推送 ═══
    if push:
        print("⑥ 推送...")
        try:
            import subprocess
            subprocess.run([
                sys.executable, "-m", "hermes_cli.main", "send",
                "-t", "telegram:-1003733144325:416",
                "-q", card[:3000]
            ], timeout=15, capture_output=True)
            print("  ✅ Telegram已推送")
        except Exception as e:
            print(f"  ⚠️ Push: {e}")
    
    return card


# ── v2.0 新增辅助函数 ──

def _cvd_display(cvd_dir: str) -> str:
    """CVD 清理显示"""
    if not cvd_dir or cvd_dir in ("N/A", "?", "None", ""):
        return "CVD ?"
    return f"CVD {cvd_dir}"


def _sweep_state(k: dict, merged: dict) -> str:
    """扫荡状态"""
    if not k:
        return "待扫"
    desc = k.get("description", "")
    if "扫荡" in desc or "sweep" in desc.lower():
        return "已扫"
    # Check merged for sweep signals
    perfect = merged.get("perfect_signals", {})
    if perfect.get("sweep"):
        return "已扫"
    return "待扫"


def _displacement(k: dict) -> str:
    """强位移检测"""
    if not k:
        return "弱"
    chg = abs(float(k.get("change_pct", 0) or 0))
    if chg > 0.005:
        return "强"
    if chg > 0.002:
        return "中"
    return "弱"


def _naked_poc(k: dict) -> str:
    """裸 POC 检测"""
    if not k:
        return "?"
    poc = k.get("poc")
    price = k.get("close") or k.get("price")
    if poc and price and abs(float(poc) - float(price)) < float(poc) * 0.001:
        return "有"
    return "无"


def _asset_game_line(symbol: str, engine_data: dict) -> str:
    """资产专属博弈文本"""
    cls = _asset_class(symbol)
    if cls == "crypto":
        cvd = engine_data.get("cvd", {})
        spot_vs_perp = "分化" if cvd.get("spot_perp_divergence") else "同向"
        # OI delta
        oi = engine_data.get("oi", {})
        oi_delta = ""
        if oi:
            trend = oi.get("trend", "")
            if trend == "up": oi_delta = " · OI→增(新多入场)"
            elif trend == "down": oi_delta = " · OI→减(多头离场)"
        return f"加密现货vs永续{spot_vs_perp} · Funding/OI/Taker综合{oi_delta}"
    elif cls == "gold":
        macro = engine_data.get("_macro", {})
        dxy = engine_data.get("dxy") or macro.get("dxy") or "?"
        kill = _kill_zone_active()
        kill_name = _kill_zone_name()
        return f"{kill_name} · DXY {_fmt_dxy(dxy)} · 扫荡后Displacement确认"
    else:
        return "按资产类规则判定"

def _effective_grade(base_grade: str, taker_data: dict, engine_data: dict) -> str:
    """数据等级降级：木桶原理——最弱一环决定"""
    if base_grade == "A":
        taker_q = taker_data.get("quality", "C") if isinstance(taker_data, dict) else "C"
        cvd_q = (engine_data.get("cvd", {}) or {}).get("quality", "C")
        if "C" in str(taker_q) or "C" in str(cvd_q):
            return "B"
    if base_grade == "B":
        taker_q = taker_data.get("quality", "C") if isinstance(taker_data, dict) else "C"
        cvd_q = (engine_data.get("cvd", {}) or {}).get("quality", "C")
        if "C" in str(taker_q) and "C" in str(cvd_q):
            return "C"
    return base_grade


def _kill_zone_active() -> bool:
    """当前是否在 Kill Zone 活跃时段"""
    from datetime import datetime as _dt
    h = _dt.now().hour
    # UTC+8 → 北京时间; Kill Zones are in NY time (UTC-4), but we store Beijing time
    # London: 15:00-18:00 Beijing (07:00-10:00 UTC)
    # NY AM: 20:00-23:00 Beijing (12:00-15:00 UTC)
    # NY PM: 01:00-04:00 Beijing (17:00-20:00 UTC previous day)
    # Asia: 08:00-12:00 Beijing (00:00-04:00 UTC)
    return (8 <= h < 12) or (15 <= h < 18) or (20 <= h < 23) or (1 <= h < 4)


def _kill_zone_name() -> str:
    """当前 Kill Zone 名称"""
    from datetime import datetime as _dt
    h = _dt.now().hour
    if 8 <= h < 12: return "Asia Kill Zone 活跃"
    if 15 <= h < 18: return "London Kill Zone 活跃"
    if 20 <= h < 23: return "NY AM Kill Zone 活跃"
    if 1 <= h < 4: return "NY PM Kill Zone 活跃"
    return "非Kill Zone · 低流动性"


def _clean_flow_line(symbol: str, engine_data: dict, funding_rate, taker_dir, taker_ratio) -> str:
    """②市场行：Taker/Funding/宏观，不重复CVD"""
    ac = _asset_class(symbol)
    macro = engine_data.get("_macro") or {}
    dxy = engine_data.get("dxy") or macro.get("dxy")
    us10y = engine_data.get("us10y") or macro.get("us10y")
    taker_clean = f"Taker {taker_dir}" if taker_dir not in ("N/A", None, "") else "Taker N/A"
    taker_r = f" `{taker_ratio}`" if taker_ratio and taker_ratio not in ("N/A", None) else ""
    if ac == "crypto":
        return f"Funding `{funding_rate}` · {taker_clean}{taker_r} · OI {engine_data.get('oi',{}).get('oi','N/A')}"
    if ac == "gold":
        dxy_part = f"DXY `{_fmt_dxy(dxy)}`" if dxy else "DXY N/A"
        us_part = f"US10Y `{us10y:.2f}`" if us10y else ""
        return f"{dxy_part} {us_part} · CVD N/A(金十)".strip()
    dxy_part = f"DXY `{dxy:.2f}`" if dxy else ""
    return f"{dxy_part} · 利差/央行窗口".strip()


def _fmt_dxy(dxy) -> str:
    """DXY 安全格式化"""
    try:
        return f"{float(dxy):.2f}"
    except (TypeError, ValueError):
        return str(dxy) if dxy else "?"


def _near_level_tag(klines: dict, price) -> str:
    """价格是否锚定关键位"""
    if _near_key_level(klines, price):
        return "锚定位 ✓"
    return "未锚定"


def _weekend_tag() -> str:
    """周末检测"""
    from datetime import datetime as _dt
    wd = _dt.now().weekday()
    if wd >= 5:
        return "⚠周末 · "
    return ""


def _session_tag() -> str:
    """当前 Kill Zone 标签"""
    if _kill_zone_active():
        return f"{_kill_zone_name()}"
    return "非Kill Zone"


def _price_label(symbol: str, engine_data: dict) -> tuple[str, str]:
    """返回(价格标签, 来源) — 区分期货/现货"""
    prices = engine_data.get("prices", {})
    source = prices.get("source", "")
    ac = _asset_class(symbol)
    if ac == "crypto":
        label = "期货 " if prices.get("futures") else "现货 "
        return label, source or "Binance Perp"
    if ac == "gold":
        return "现货 ", source or "gold-api"
    if ac == "forex":
        return "现货 ", source or "Alpha Vantage"
    if ac == "stock":
        return "", source or "Alpha Vantage"  
    return "", source or "多源"


# ═══════════════════ 日内止损止盈（ATR夹层+结构锚定）═══════════════════
def _calc_stop_target_atr(
    price: float, direction: str, klines: dict,
    symbol: str = "BTCUSDT", atr_mult: float = 2.0
) -> dict:
    """计算日内止损止盈。返回 {stop, target, rr, stop_reason, target_reason, atr}。
    
    direction: "short" 或 "long"
    atr_mult: ATR 倍数（默认 2.0x，日内夹层 1.5-2.5）
    """
    p = float(price or 0)
    if p <= 0:
        return {"stop": p, "target": p, "rr": 1, "stop_reason": "?", "target_reason": "?", "atr": 0}
    
    ac = _asset_class(symbol)
    MIN_MOVE = p * 0.003  # 0.3% 以内视为噪音
    
    # ATR
    atr_15m = 0
    for tf in ("15m", "5m"):
        k = klines.get(tf, {})
        atr_15m = float(k.get("atr", 0) or 0)
        if atr_15m > 0:
            break
    if atr_15m <= 0:
        atr_15m = p * 0.002  # 0.2% fallback
    
    atr_stop_dist = atr_15m * atr_mult
    atr_stop_dist = max(atr_stop_dist, MIN_MOVE)  # 最少 0.3%
    
    # 收集结构位
    above_levels = []  # (level, name, tf)
    below_levels = []
    
    for tf_name in ("15m", "1h", "4h"):
        k = klines.get(tf_name, {})
        for key, label in [("vah", "VAH"), ("vwap", "VWAP"), ("high", "高"),
                           ("poc", "POC"), ("ema21", "EMA21"), ("ema55", "EMA55")]:
            v = k.get(key)
            if v:
                try:
                    fv = float(v)
                    if fv > p + MIN_MOVE:
                        above_levels.append((fv, label, tf_name))
                    elif fv < p - MIN_MOVE:
                        below_levels.append((fv, label, tf_name))
                except (TypeError, ValueError):
                    pass
    
    above_levels.sort()  # nearest first
    below_levels.sort(reverse=True)  # nearest first
    
    if direction == "short":
        # 止损在最近阻力上方
        stop_structural = above_levels[0][0] if above_levels else p + atr_stop_dist
        stop = max(p + atr_stop_dist, stop_structural)
        stop_reason = f"{above_levels[0][1]}({above_levels[0][2]})上方" if above_levels else "ATR×2"
        
        # 止盈在最近支撑
        target = below_levels[0][0] if below_levels else p - atr_stop_dist * 2
        target_reason = f"{below_levels[0][1]}({below_levels[0][2]})" if below_levels else "ATR×4"
    else:
        # 止损在最近支撑下方
        stop_structural = below_levels[0][0] if below_levels else p - atr_stop_dist
        stop = min(p - atr_stop_dist, stop_structural)
        stop_reason = f"{below_levels[0][1]}({below_levels[0][2]})下方" if below_levels else "ATR×2"
        
        # 止盈在最近阻力
        target = above_levels[0][0] if above_levels else p + atr_stop_dist * 2
        target_reason = f"{above_levels[0][1]}({above_levels[0][2]})" if above_levels else "ATR×4"
    
    rr = abs(target - p) / abs(stop - p) if abs(stop - p) > 0 else 1
    return {
        "stop": stop, "target": target, "rr": rr,
        "stop_reason": stop_reason, "target_reason": target_reason,
        "atr": atr_15m,
    }


# ═══════════════════ 极简决策卡 ═══════════════════
def _compact_card(symbol: str, price, status: str, direction: str, model_id: str,
                  klines: dict, k4h: dict, k5m: dict, k15m: dict,
                  merged: dict, cvd_dir: str, cvd_quality: str,
                  taker_dir: str, taker_ratio, funding_rate,
                  engine_data: dict, risk_amt: float, risk_pct_limit,
                  prot_status: str, data_grade: str, fg: dict,
                  leverage_text: str, qty_unit: str, search_sent: str) -> str:
    """价格锚定关键位时的极简决策卡。8行替代60行全卡。"""
    p = float(price or 0)
    if p <= 0:
        return ""
    nearest_level, nearest_name, nearest_dist = _find_nearest_key_level(klines, p)
    if not nearest_level:
        return ""
    nl_fmt = _fmt_price(nearest_level).strip("`")
    hi = _fmt_price(k15m.get("high") or k4h.get("high"))
    lo = _fmt_price(k15m.get("low") or k4h.get("low"))
    taker_label = f"Taker {taker_dir}" if taker_dir not in ("N/A", None, "") else "Taker N/A"
    taker_r = f" {taker_ratio}" if taker_ratio and str(taker_ratio) not in ("N/A", "") else ""
    cvd_str = f"CVD {cvd_dir}" if cvd_dir not in ("N/A", "?", None, "") else "CVD ?"
    ac = _asset_class(symbol)
    bias = "空头偏" if cvd_dir == "卖" else "多头偏" if cvd_dir == "买" else "观望"
    from datetime import datetime as _dt
    wd_tag = "⚠周末 " if _dt.now().weekday() >= 5 else ""
    dist_pct = abs(p - nearest_level) / p * 100
    near_str = f"← 价踩在这 · {dist_pct:.1f}%" if dist_pct < 0.5 else f"← 距{abs(p - nearest_level):.0f}点"
    bearish = (cvd_dir == "卖" or taker_dir == "sell")
    
    # 使用共享 ATR 止损止盈计算
    st_a = _calc_stop_target_atr(p, "short" if bearish else "long", klines, symbol)
    st_b = _calc_stop_target_atr(p, "long" if bearish else "short", klines, symbol)
    stop_a, tp_a, rr_a = st_a["stop"], st_a["target"], st_a["rr"]
    stop_b, tp_b, rr_b = st_b["stop"], st_b["target"], st_b["rr"]
    
    rr_a_note = "" if rr_a >= 2.0 else " ⚠R:R不足"
    rr_b_note = "" if rr_b >= 2.0 else " ⚠R:R不足"
    
    plan_a = f"→ 破{nl_fmt}：空 止损{_fmt_price(stop_a)} 止盈{_fmt_price(tp_a)} R:R 1:{rr_a:.1f}{rr_a_note}" if bearish else f"→ 守{nl_fmt}：多 止损{_fmt_price(stop_a)} 止盈{_fmt_price(tp_a)} R:R 1:{rr_a:.1f}{rr_a_note}"
    plan_b = f"→ 守{nl_fmt}：多 止损{_fmt_price(stop_b)} 止盈{_fmt_price(tp_b)} R:R 1:{rr_b:.1f}{rr_b_note}" if bearish else f"→ 破{nl_fmt}：空 止损{_fmt_price(stop_b)} 止盈{_fmt_price(tp_b)} R:R 1:{rr_b:.1f}{rr_b_note}"
    scale_line = "→ 到了+1.5R先出一半 · 第4根15m无利润减半"
    
    # 社区共识标签
    fg_val = fg.get("value", "?") if isinstance(fg, dict) else "?"
    fg_cls = fg.get("value_classification", "") if isinstance(fg, dict) else ""
    fg_tag = f"F&G {fg_val}{fg_cls}" if fg_val != "?" else ""
    comm_tag = f"社区{fg_tag}" if fg_tag else ""
    
    prot_tag = "🛡" if prot_status == "通过" else f"⚠{prot_status}"
    
    # 低周期触发状态
    sweep_state = _sweep_state(k5m, merged) or "待扫"
    k15m_desc = _kl_desc("15m", k15m.get("close", [0]) if isinstance(k15m.get("close"), list) else [k15m.get("close", 0)], 
                          k15m.get("high", [0]) if isinstance(k15m.get("high"), list) else [k15m.get("high", 0)],
                          k15m.get("low", [0]) if isinstance(k15m.get("low"), list) else [k15m.get("low", 0)],
                          k15m.get("volume", [0]) if isinstance(k15m.get("volume"), list) else [k15m.get("volume", 0)])
    k15m_brief = k15m.get("description", str(k15m_desc)[:30]) if k15m else "?"
    trigger_line = f"5m {sweep_state} · 15m {k15m_brief} — 低周期触发"
    
    # 4h继承
    k4h_bias_compact = _kl_bias(k4h) or "?"
    header_4h = f"4h{k4h_bias_compact}"
    
    # TV DMI 决策表注入
    tv_active = engine_data.get("_tv_override", {}).get("tv_active", False)
    tv_grade = engine_data.get("_tv_override", {}).get("tv_grade", "")
    grade_line = ""
    if tv_active and tv_grade:
        if tv_grade == "X":
            grade_line = f"⚠TV: X — {engine_data.get('_tv_override', {}).get('tv_treatment', '结构冲突')} · 不进"
        elif tv_grade.startswith("A"):
            grade_line = f"🔥TV: {tv_grade} — {engine_data.get('_tv_override', {}).get('tv_treatment', '优先')}"
        else:
            grade_line = f"TV: {tv_grade} — {engine_data.get('_tv_override', {}).get('tv_treatment', '等')}"

    # VWAP/EMA 极简行（从 engine_data 提取）
    vwap_ema_compact = engine_data.get("_vwap_ema", {})
    vwap_line = ""
    if vwap_ema_compact.get("available"):
        v = vwap_ema_compact.get("vwap", {})
        ec = vwap_ema_compact.get("ema_cloud", {})
        if v.get("vwap"):
            vwap_line = f"VWAP `{v['vwap']}` {v.get('price_vs_vwap','?')}·{ec.get('fast_cloud','?')}·{ec.get('trend_strength','?')[:8]}"

    lines = [
        f"◷ {datetime.now(TZ).strftime('%m-%d %H:%M')} · {_display_symbol(symbol)} · {model_id} · {header_4h} · {bias}{' ' + grade_line if grade_line else ''}",
        f"③ {_fmt_price(price)} · 高 {hi} · 低 {lo}",
        f"{nearest_name} {nl_fmt} {near_str}",
        f"{cvd_str} · {taker_label}{taker_r} · Funding {funding_rate}",
        trigger_line,
    ]
    if vwap_line:
        lines.append(vwap_line)
    lines.extend([
        plan_a,
        plan_b,
        scale_line,
        f"风控：{wd_tag}{risk_amt:.2f}U上限 · {leverage_text} · {prot_tag} · {comm_tag}",
        f"—— 决策：你来选方向——",
    ])
    return "\n".join(lines) + "\n"


def _find_nearest_key_level(klines: dict, price: float) -> tuple:
    """找到价格最接近的关键位"""
    p = float(price or 0)
    if p <= 0:
        return None, None, None
    candidates = []
    for tf in ("15m", "1h", "4h"):
        k = klines.get(tf, {})
        for key, name in [("vah", "VAH"), ("val", "VAL"), ("poc", "POC"), ("vwap", "VWAP"),
                          ("high", "高"), ("low", "低")]:
            v = k.get(key)
            if v:
                try:
                    dist = abs(float(v) - p) / p * 100
                    candidates.append((float(v), name, dist))
                except (TypeError, ValueError):
                    pass
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda x: x[2])
    return candidates[0]


def _parse_cli_symbol(argv=None) -> str:
    """Return the first real trading symbol, ignoring pytest/hermes CLI flags."""
    argv = list(sys.argv[1:] if argv is None else argv)
    for arg in argv:
        if not arg or arg.startswith("-"):
            continue
        symbol = arg.upper().strip()
        if symbol in {"BTC", "BTCUSDT", "XAU", "XAUUSD"} or symbol.endswith(("USDT", "USD")):
            return "BTCUSDT" if symbol == "BTC" else "XAUUSD" if symbol == "XAU" else symbol
    return "BTCUSDT"


def _vwap_ema_display(vwap_ema: dict) -> str:
    """VWAP/EMA 单行展示（注入环境段⑧）。"""
    if not vwap_ema or not vwap_ema.get("available"):
        return "数据待刷新"
    vwap = vwap_ema.get("vwap", {})
    ema_cloud = vwap_ema.get("ema_cloud", {})
    parts = []
    if vwap.get("vwap"):
        parts.append(f"VWAP `{vwap['vwap']}` · 价在{'上' if vwap.get('price_vs_vwap') == '上' else '下'}·{vwap.get('in_band', '?')}")
    fast = ema_cloud.get("fast_cloud", "?")
    slow = ema_cloud.get("slow_cloud", "?")
    parts.append(f"EMA 快{fast}·慢{slow} — {ema_cloud.get('trend_strength', '?')}")
    return " · ".join(parts) if parts else "数据不足"


def _vwap_structure_line(vwap_ema: dict) -> str:
    """VWAP结构线（注入结构段·替代或增强⑤价值区）。"""
    if not vwap_ema or not vwap_ema.get("available"):
        return ""
    vwap = vwap_ema.get("vwap", {})
    if not vwap.get("vwap"):
        return ""
    return (
        f"VWAP `{vwap['vwap']}` "
        f"+1σ `{vwap.get('upper_1', '?')}` "
        f"-1σ `{vwap.get('lower_1', '?')}` "
        f"+2σ `{vwap.get('upper_2', '?')}` "
        f"-2σ `{vwap.get('lower_2', '?')}`"
    )


if __name__ == "__main__":
    sym = _parse_cli_symbol()
    do_push = "--push" in sys.argv
    auto_card(sym, push=do_push)
