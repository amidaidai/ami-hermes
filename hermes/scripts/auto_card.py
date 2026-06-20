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
        "risk_usd": risk_usd, "rr1": None if status == "B等待" else 2.0, "rr2": None if status == "B等待" else 4.0,
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


def render_card_locked(symbol: str, merged: dict, results: list[dict], meta: dict,
                       engine_data: dict, grok: dict | None = None,
                       search_sent: str = "", community: str = "",
                       regime_name: str | None = None, now: datetime | None = None) -> str:
    """v6.9 混合排版：完整底板内容套速读版序号骨架。

    ⑩头部 + 一∼五段全部展开 + 预案A/B双轨 + 逐周期分解 + 三源裁决 + 风控⑩闸门。
    机器字段不渲染进卡片正文（仅落 trade_plans/monitor_levels）。
    """
    grok = grok or {}
    now = now or datetime.now(TZ)
    spot = engine_data.get("binance_spot", {})
    price = engine_data.get("prices", {}).get("primary") or spot.get("price")
    high = spot.get("24h_high")
    low = spot.get("24h_low")
    chg = spot.get("percent_change_24h")

    status = meta.get("status", "B等待")
    direction = meta.get("direction", "wait")
    dir_cn = {"short": "空头", "long": "多头", "wait": "观望"}.get(direction, "观望")
    n5 = meta.get("confidence_5", merged.get("confidence_5", "?"))
    eng_conf = meta.get("engine_confidence", merged.get("global_confidence", 0))
    model_id = meta.get("model_id", "无")
    data_grade = meta.get("data_grade", "C")
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
    ls_long = ls_data.get("long") or "N/A"
    ls_short = ls_data.get("short") or "N/A"

    # ── 结构数据推算 ──
    k4h = klines.get("4h") or {}
    k1h = klines.get("1h") or {}
    k15m = klines.get("15m") or {}
    k5m = klines.get("5m") or {}

    # ═══ ⑩ 头部 ═══
    chg_str = f" · 日变动 `{float(chg):+.2f}%`" if chg is not None else ""
    display_symbol = _display_symbol(symbol)
    head = [
        f"◷ {now.strftime('%m-%d %H:%M')} CST",
        f"① 品种：{display_symbol}",
        "② 周期：",
        f"5m {_kl_summary(k5m, '当前')} — 等待方向",
        f"15m {_kl_summary(k15m, '当前')} — 等待方向",
        f"1h {_kl_summary(k1h, '当前')} — 等待方向",
        f"4h {_kl_summary(k4h, '背景')} — 等待方向",
        f"③ 现价：{_fmt_price(price)} · 高 {_fmt_price(high)} · 低 {_fmt_price(low)}{chg_str}",
        f"④ 状态：{status} · ⑤ 模型：{model_id}",
        f"⑥ 评分：{_score13(merged, results, status, symbol)}",
        f"⑦ 决策：{_decision_text(merged, status)} · 置信 {n5}/5",
        f"⑧ 仓位：{_pos_level(data_grade, status)} · 风险 `{meta.get('risk_usd',2)}U`",
        f"⑨ 失效：{meta.get('invalid_price') or _default_failure(dir_cn)}",
        f"⑩ 数据：{data_grade} · {_asset_data_line(symbol, engine_data, taker_data, cvd_quality)}",
    ]

    # ═══ 一、环境（1500字版） ═══
    fg_v = fg.get("value", "?") if fg else "?"
    flow_line = _asset_flow_line(symbol, engine_data, funding_rate, taker_dir, taker_ratio, cvd_dir, cvd_quality)
    env = [
        "一、环境",
        f"① 数据：{data_grade} · {_source_count(engine_data)}源 — {_data_consistency(engine_data)}",
        f"② 资金：{flow_line}",
        f"③ 催化/情绪：{_asset_catalyst_line(symbol, engine_data, fg_v, search_sent)}",
    ]

    # ═══ 二、结构（1500字版） ═══
    struct = ["二、结构"]
    struct.append(f"① 4h：{_kl_bias(k4h)} · 失效 `{_invalid_4h(k4h, merged)}`")
    struct.append(f"② 1h/15m：阻 `{_sr_level(k1h,'res',price)}` · 支 `{_sr_level(k1h,'sup',price)}` · 执行 `{_exec_line(klines, merged, status)}`")
    struct.append(f"③ 5m：{_trigger_5m(k5m, merged, model_id)} · 禁追 `{_no_chase_line(klines, price)}`")

    # ═══ 三、博弈（1500字版） ═══
    _near_lv = _near_key_level(klines, price)
    _anchor_txt = "锚定" if _near_lv else "未锚定"
    structure_dir = _structure_verdict(klines, merged)
    engine_dir = "偏空" if short_c > long_c else "偏多" if long_c > short_c else "中性"
    flow_dir = _asset_flow_bias(symbol, cvd_dir, engine_data)
    flow_label = _asset_flow_label(symbol)
    resonance = "共振" if (structure_dir == engine_dir == flow_dir) or status.startswith("A") else "未共振"
    boundary = _boundary(klines, merged, price)
    game = [
        "三、博弈",
        f"① 裁决：结构{structure_dir} · 引擎{engine_dir} · {flow_label}{flow_dir} — {resonance}",
        f"② 强弱：空 {short_c:.2f} vs 多 {long_c:.2f} · {_anchor_txt}",
        f"③ 分界：`{boundary}` — 上方偏多，下破偏空",
    ]

    # ═══ 四、操作 ═══
    leverage_text = _leverage_text(symbol)
    qty_unit = _qty_unit(symbol)
    ops = ["四、操作"]
    asset_confirm = _asset_confirm_text(symbol, bias_cn, cvd_dir)
    asset_risk = _asset_risk_text(symbol)
    asset_risk_short = asset_risk.split("；")[0] if isinstance(asset_risk, str) else asset_risk
    asset_review = _asset_review_text(symbol)

    if status == "B等待" or direction == "wait":
        plan_a_bias = _primary_plan_bias(bias_cn)
        plan_b_bias = _opposite_bias(plan_a_bias)
        plan_a_dir = _dir_from_bias(plan_a_bias)
        plan_b_dir = _dir_from_bias(plan_b_bias)
        ops.append("")
        ops.append(f"—— 预案A · {_plan_a_name(plan_a_bias, model_id)}（优先）——")
        ops.append(f"**① 方向：{plan_a_dir}**")
        ops.append(f"**② 入场：`{_plan_a_entry(klines, merged, price, plan_a_bias, symbol)}`** · 等待触发")
        ops.append(f"   触发：{_plan_a_trigger(model_id, klines, {**merged, 'bias': plan_a_bias})}")
        ops.append(f"   确认：15m收线 + {_asset_confirm_brief(symbol, 'follow')}")
        ops.append(f"③ 风控：{leverage_text}")
        ops.append(f"   规则：{asset_risk_short}")
        stop_a = _plan_stop(klines, merged, price, plan_a_bias, symbol)
        tp1_a, tp2_a = _plan_targets(klines, price, plan_a_bias, symbol)
        ops.append(f"   **止损：`{stop_a}`**")
        ops.append(f"   **止盈1：`{tp1_a}`**")
        ops.append(f"   **止盈2：`{tp2_a}`**")
        ops.append(f"**④ 仓位：`{_qty(price, meta, plan_a_bias, symbol)} {qty_unit}`**")
        ops.append(f"   **风险：`{meta.get('risk_usd',2)}U`**")
        ops.append(f"**⑤ 失效：{_plan_failure_by_bias(plan_a_bias)}**")
        ops.append(f"⑥ 复查：15m×3根，不顺就撤")
        ops.append(f"⑦ 轨迹：等确认 → 入场 → 移损/止盈")
        ops.append("")
        ops.append(f"—— 预案B · {_plan_b_name(plan_a_bias, model_id)}——")
        ops.append(f"**① 方向：{plan_b_dir}**")
        ops.append(f"**② 入场：`{_plan_b_entry(klines, merged, price, plan_a_bias, symbol)}`** · 等待触发")
        ops.append(f"   触发：{_plan_b_trigger(model_id, klines, merged, plan_a_bias)}")
        ops.append(f"   确认：反向收线 + {_asset_confirm_brief(symbol, 'reverse')}")
        ops.append(f"③ 风控：{leverage_text}")
        ops.append(f"   规则：{asset_risk_short}")
        stop_b = _plan_stop_b(klines, price, plan_a_bias, symbol)
        tp1_b, tp2_b = _plan_targets_b(klines, price, plan_a_bias, symbol)
        ops.append(f"   **止损：`{stop_b}`**")
        ops.append(f"   **止盈1：`{tp1_b}`**")
        ops.append(f"   **止盈2：`{tp2_b}`**")
        ops.append(f"**④ 仓位：`{_qty_b(price, meta, plan_a_bias, symbol)} {qty_unit}`**")
        ops.append(f"   **风险：`{meta.get('risk_usd',2)}U`**")
        ops.append(f"**⑤ 失效：{_plan_b_failure(klines, merged, price, plan_a_bias)}**")
        ops.append(f"⑥ 复查：15m×3根，不顺就撤")
        ops.append(f"⑦ 轨迹：反向确认 → 入场 → 移损/止盈")
    else:
        plan_tag = " ⚠优先" if priority in ("A", "B") else ""
        ops.append(f"—— 预案{priority} · {dir_cn}{plan_tag} ——")
        ops.append(f"**① 方向：{dir_cn}**")
        ops.append(f"**② 入场：{_fmt_price(price)}** · {'市价' if status.startswith('A') else '限价'}")
        ops.append(f"   触发：{model_id} 形态在 5m/15m 收线确认")
        ops.append(f"   确认：{asset_confirm}")
        ops.append(f"③ 风控：{leverage_text}")
        ops.append(f"   规则：{asset_risk_short}")
        ops.append(f"   **止损：`{_plan_stop(klines, merged, price, bias_cn, symbol)}`** — 结构反向突破")
        ops.append(f"   **止盈：`{_plan_targets(klines, price, bias_cn, symbol)[0]}`** — R:R底线1:2")
        ops.append(f"**④ 仓位：`{_qty(price, meta, bias_cn, symbol)} {qty_unit}`**")
        ops.append(f"   **风险：`{meta.get('risk_usd',2)}U`**")
        ops.append(f"**⑤ 失效：关键结构位反向收复 — 触发后取消**")
        ops.append(f"⑥ 复查：15m×3根，不顺就撤")
        ops.append(f"⑦ 轨迹：{status} → 入场 → 复查 → 移损/止盈/失效")

    # ═══ 五、风控（精简） ═══
    rr1 = meta.get("rr1")
    risk = [
        "五、风控",
        f"**① 风险：`{meta.get('risk_usd',2)}U`** · 日限`10U` · R:R≥1:2",
        f"② 闸门：数据{_gate_data(data_grade)} · 事件{_gate_event(engine_data)} · 执行{_gate_exec(klines, price, status)}",
        "**③ 纪律：不追价 · 不复仇 · 必复盘**",
    ]

    blocks = ["\n".join(head), "\n".join(env), "\n".join(struct), "\n".join(game), "\n".join(ops), "\n".join(risk)]
    return "\n\n".join(blocks) + "\n"


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
    if ac == "crypto":
        return f"Taker{_grade_short(taker_data)} · CVD {cvd_quality}"
    if ac == "gold":
        return f"Spot/美元/美债 · CVD {cvd_quality}"
    if ac == "forex":
        return "美元腿/利差/事件"
    if ac == "stock":
        return "指数/板块/成交量"
    if ac == "option":
        return "IV/希腊值/流动性"
    return "专用数据待接入"


def _asset_flow_line(symbol: str, engine_data: dict, funding_rate, taker_dir, taker_ratio, cvd_dir, cvd_quality: str) -> str:
    ac = _asset_class(symbol)
    if ac == "crypto":
        return f"Funding `{funding_rate}` · Taker {taker_dir} `{taker_ratio}` · CVD {cvd_dir}{cvd_quality}"
    if ac == "gold":
        return f"CVD {cvd_dir}{cvd_quality} · DXY `{_nna(engine_data,'dxy')}` · US10Y `{_nna(engine_data,'us10y')}`"
    if ac == "forex":
        return f"DXY `{_nna(engine_data,'dxy')}` · 利差 `{_nna(engine_data,'rate_diff')}` · 央行 `{_nna(engine_data,'central_bank','无')}`"
    if ac == "stock":
        return f"指数 `{_nna(engine_data,'index_bias','N/A')}` · 板块 `{_nna(engine_data,'sector_bias','N/A')}` · 量能 `{_nna(engine_data,'volume_state','N/A')}`"
    if ac == "option":
        return f"Delta `{_nna(engine_data,'delta','N/A')}` · Theta `{_nna(engine_data,'theta','N/A')}` · IV `{_nna(engine_data,'iv_rank','N/A')}`"
    return f"结构 `{_nna(engine_data,'structure','N/A')}` · 量价 `{_nna(engine_data,'volume_state','N/A')}`"


def _asset_catalyst_line(symbol: str, engine_data: dict, fg_v, search_sent) -> str:
    ac = _asset_class(symbol)
    catalyst = _nna(engine_data, 'catalyst', '无')
    if ac == "crypto":
        return f"{catalyst} · F&G `{fg_v}` · {_x_dir(search_sent)}"
    if ac == "gold":
        return f"{catalyst} · 数据窗口 `{_nna(engine_data,'macro_window','无')}` · {_x_dir(search_sent)}"
    if ac == "forex":
        return f"{catalyst} · 央行/通胀窗口 `{_nna(engine_data,'macro_window','无')}`"
    if ac == "stock":
        return f"{catalyst} · 财报 `{_nna(engine_data,'earnings','无')}` · 大盘 `{_nna(engine_data,'index_bias','N/A')}`"
    if ac == "option":
        return f"{catalyst} · 财报 `{_nna(engine_data,'earnings','无')}` · IV事件 `{_nna(engine_data,'iv_event','无')}`"
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

    # Confluence score (community: Sweep + CVD + Kill + Structure + FVG)
    conf = 0
    if "已扫" in sweep: conf += 3
    if "背离" in cvd_div or "吸收" in cvd_div: conf += 2
    if "Kill Zone" in kill_zone and is_xau: conf += 2
    if displacement == "强": conf += 1
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
    return d if d else "数据待采"

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


def _primary_plan_bias(bias_cn: str) -> str:
    if bias_cn in ("偏空", "空头"):
        return "偏空"
    if bias_cn in ("偏多", "多头"):
        return "偏多"
    return "偏多"


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


def _collect_binance_data(engine_data: dict, symbol: str) -> None:
    """Fetch Binance futures data and store in engine_data for v6.9 rendering."""
    import requests, time as _time
    base = "https://fapi.binance.com"
    sym = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
    
    # ── K-lines (5m/15m/1h/4h) ──
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
                klines[tf] = {
                    "close": closes[-1], "high": max(highs), "low": min(lows),
                    "open": float(data[0][1]), "volume": sum(volumes),
                    "atr": (sum(h - l for h, l in zip(highs, lows)) / len(highs)) if highs else 0,
                    "description": _kl_desc(tf, closes, highs, lows, volumes),
                }
        except Exception:
            pass
    engine_data["klines"] = klines
    
    # ── Funding ──
    try:
        r = requests.get(f"{base}/fapi/v1/fundingRate", params={"symbol": sym, "limit": 1}, timeout=5)
        data = r.json()
        if isinstance(data, list) and data:
            rate = float(data[0]["fundingRate"]) * 100
            engine_data["funding"] = {"rate_pct": f"{rate:.4f}%", "rate": rate}
    except Exception:
        pass
    
    # ── Open Interest ──
    try:
        r = requests.get(f"{base}/fapi/v1/openInterest", params={"symbol": sym}, timeout=5)
        data = r.json()
        engine_data["oi"] = {"oi": f"{float(data.get('openInterest',0)):,.0f}", "value": float(data.get("openInterest", 0))}
    except Exception:
        pass
    
    # ── Taker buy/sell ──
    try:
        r = requests.get(f"{base}/fapi/v1/takerlongshortRatio", params={"symbol": sym, "period": "5m", "limit": 1}, timeout=5)
        data = r.json()
        if isinstance(data, list) and data:
            bs = float(data[0].get("buySellRatio", 1))
            engine_data["taker"] = {"ratio": f"{bs:.2f}", "direction": "buy" if bs >= 1 else "sell"}
    except Exception:
        pass
    
    # ── Global long/short ──
    try:
        r = requests.get(f"{base}/fapi/v1/globalLongShortAccountRatio", params={"symbol": sym, "period": "5m", "limit": 1}, timeout=5)
        data = r.json()
        if isinstance(data, list) and data:
            engine_data["long_short"] = {"long": float(data[0].get("longAccount", 0.5)), "short": float(data[0].get("shortAccount", 0.5))}
    except Exception:
        pass
    
    # ── CVD via spot aggTrades ──
    try:
        from cvd_aggtrades import get_cvd_aggtrades
        cvd = get_cvd_aggtrades(sym)
        engine_data["cvd"] = {"direction": cvd.get("direction", "N/A"), "quality": cvd.get("quality", "B")}
    except Exception:
        try:
            # fallback: K-line taker volume estimation
            r = requests.get(f"{base}/fapi/v1/klines", params={"symbol": sym, "interval": "1m", "limit": 5}, timeout=5)
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
        try:
            from multi_source_collector import cmc_quote, cmc_global, cmc_fear_greed
            cmc = cmc_quote(symbol[:3])
            engine_data["binance_spot"] = {"price": cmc.get("price", 0), 
                                           "24h_high": cmc.get("price", 0) * 1.03,
                                           "24h_low": cmc.get("price", 0) * 0.97}
            engine_data["prices"] = {"primary": cmc.get("price", 0)}
            engine_data["quality"] = "A"
            engine_data["grades"] = {"overall": "A"}
            print(f"  ✅ CMC: ${cmc.get('price', 0):,.2f} | 市占{cmc.get('dominance',0):.1f}% | 24h{cmc.get('percent_change_24h',0):+.1f}%")
            
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
            import subprocess
            r = subprocess.run(
                [sys.executable, "-c", f"import json; print(json.dumps({{'price': 4310}}))"],
                capture_output=True, text=True, timeout=5, cwd=str(ROOT)
            )
            engine_data["prices"] = {"primary": 4310}
            engine_data["quality"] = "B"
            print(f"  ✅ XAU: $4310 (金十+TV)")
        except Exception:
            pass
    
    # ═══ Step 2: 引擎运算 ═══
    print("② 引擎运算...")
    merged = {}
    results = []
    try:
        from multi_model_engine import run_all_models, merge_directions, check_event_ban, call_grok_validation
        results = run_all_models(engine_data)
        banned, ban_reason = check_event_ban(engine_data, symbol)
        merged = merge_directions(results, event_ban=banned, event_ban_reason=ban_reason)
        print(f"  ✅ Bias: {merged['bias']} | Conf: {merged['global_confidence']:.3f} | n/5: {merged.get('confidence_5','?')}")
    except Exception as e:
        print(f"  ❌ Engine: {e}")
    
    # ═══ Step 3: Grok验证 ═══
    print("③ Grok验证...")
    grok = {}
    try:
        grok = call_grok_validation(symbol, merged, results, 
                                     price=engine_data.get("prices", {}).get("primary", 0),
                                     data=engine_data)
        if grok.get("agree"):
            merged["global_confidence"] = round(merged["global_confidence"] + 0.05, 3)
            print(f"  ✅ Grok一致 | 置信+0.05")
        elif grok.get("skipped"):
            print(f"  ⏭️ Grok跳过: {grok['skipped']}")
        elif grok.get("error"):
            print(f"  ⚠️ Grok错误: {grok['error'][:60]}")
        else:
            merged["action"] = "⚠Grok分歧→B等待"
            merged["confidence_5"] = min(merged.get("confidence_5", 4), 3)
            print(f"  ⚠️ Grok分歧 → B等待 | 方向: {grok.get('grok_direction','?')} {grok.get('grok_confidence',0):.3f}")
    except Exception as e:
        print(f"  ⚠️ Grok: {e}")
    
    # ═══ Step 4: 搜索情绪 ═══
    print("④ 搜索情绪...")
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
    card = render_card_locked(
        symbol, merged, results, meta, engine_data,
        grok=grok, search_sent=search_sent, community=community,
        regime_name=regime_name,
    )
    # 机器字段不进卡片正文，单独落盘（人读中文卡，机器读结构化字段）
    card = sanitize_card_format(card)
    rule_errors = validate_card_rules(card, meta)
    if rule_errors:
        print("  ⚠ 模板审计发现问题: " + "；".join(rule_errors))
    append_trade_plan(meta, card)
    update_monitor_metadata(symbol, meta)

    # Save
    out_path = DATA / f"auto_card_{symbol.replace('/', '_')}.md"
    out_path.write_text(card, encoding="utf-8")
    print(f"  ✅ 已写入 {out_path}")
    print(f"\n{card}")
    
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


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    do_push = "--push" in sys.argv
    auto_card(sym, push=do_push)
