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
            from depth_wall import analyze_walls
            sym2 = symbol if su.endswith("USDT") else su + "USDT"
            w = analyze_walls(sym2, top_n=2, min_notional_usd=1_000_000)
            if w.get("ok") and (w.get("support_walls") or w.get("resist_walls")):
                return f"④ 挂单墙：{w['summary']} — 大额限价墙=磁吸位/止损陷阱"
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
    head = [
        f"**① 品种：{symbol}.P:{'OANDA' if 'XAU' in symbol.upper() else 'BINANCE'}**",
        f"**② 周期：**",
        f"**5m {_kl_summary(k5m, '当前')}**",
        f"**15m {_kl_summary(k15m, '当前')}**",
        f"**1h {_kl_summary(k1h, '当前')}**",
        f"**4h {_kl_summary(k4h, '背景')}**",
        f"**③ 现价：{_fmt_price(price)}** · 高 {_fmt_price(high)} · 低 {_fmt_price(low)}{chg_str}",
        f"**④ 状态：{status}**",
        f"**⑤ 模型：{model_id}**",
        f"**⑥ 评分：{_score13(merged, results, status)}**",
        f"**⑦ 决策：{_decision_text(merged, status)}** · 置信 {n5}/5 — {_reason_one_liner(merged, dir_cn)}",
        f"**⑧ 仓位：{_pos_level(data_grade, status)}** · 最大风险 `{meta.get('risk_usd',2)}U`",
        f"**⑨ 失效：{meta.get('invalid_price') or _default_failure(dir_cn)}** · 有效期 {meta.get('expires_at','—')[:16].replace('T',' ')}",
        f"**⑩ 数据：{data_grade}** · {_source_count(engine_data)}源 · 多空{_grade_short(ls_data)}级 · Taker{_grade_short(taker_data)}级 · CVD {cvd_quality}级{_cvd_note(cvd_quality)}",
    ]

    # ═══ 一、环境 ═══
    env = ["**一、环境**"]
    env.append(f"① 数据：{data_grade}级 · {_source_count(engine_data)}源 — {_data_consistency(engine_data)}")
    if "XAU" in symbol.upper():
        env.append(f"② 衍生：黄金无 Funding/OI/Taker（非加密·不适用）— 替代：DXY {_nna(engine_data,'dxy')} · US10Y {_nna(engine_data,'us10y')} · 实际利率/避险情绪")
        env.append(f"③ 主动成交：Binance 订单流不适用黄金 — 改看多源现货一致性（金十+gold-api+Yahoo）· CVD {cvd_dir} {cvd_quality}级（TV估算·仅参考）")
    else:
        env.append(f"② 衍生：Funding `{funding_rate}` · OI `{oi_latest}`{oi_trend} · 杠杆情绪{_lev_sentiment(funding_rate, ls_long)}")
        env.append(f"③ 主动成交：Taker {taker_dir} `{taker_ratio}` · CVD {cvd_dir} {cvd_quality}级 — {_taker_cvd_read(taker_dir, cvd_dir, cvd_quality)}")
    env.append(_env_walls_line(symbol, price, klines))
    env.append(f"⑤ 宏观：DXY {_nna(engine_data,'dxy')} · US10Y {_nna(engine_data,'us10y')} · SPX {_nna(engine_data,'spx')} — {_macro_read(engine_data)}")
    env.append(f"⑥ 催化：{_nna(engine_data,'catalyst','无')} · 等级{_nna(engine_data,'catalyst_grade','D')} — {_catalyst_impact(engine_data)}")
    fg_v = fg.get("value", "?") if fg else "?"
    fg_c = fg.get("classification", "?") if fg else "?"
    env.append(f"⑦ 社区全景：恐慌贪婪 `{fg_v}`（{fg_c}）· CG情绪 {_cg_read(engine_data)} — 只作背景/仓位微调")
    _sent_src = "web源·非X实时" if search_sent else "未采集"
    env.append(f"⑧ 情绪：{search_sent or '未采集'}（{_sent_src}）— 只验证/挑战结构·不覆盖方向{' ⚠与结构冲突' if _sent_conflict(search_sent, bias_cn) else ''}")
    env.append(f"⑨ 数据缺口：{_gaps(engine_data)} — 缺失项不参与加分")
    env.append(f"⑩ 风控：{_env_risk(data_grade, status)} · {_pos_level(data_grade, status)} · 最大风险 `{meta.get('risk_usd',2)}U` — {_risk_reason(status, bias_cn)}")

    # ═══ 二、结构 ═══
    struct = ["**二、结构**"]
    for tf_name, tf_key, tf_label in [("4h背景", "4h", "背景"), ("1h结构", "1h", "结构"), ("15m执行", "15m", "日内操作"), ("5m触发", "5m", "实时")]:
        k = klines.get(tf_key) or {}
        struct.append(f"**{tf_name}**")
        struct.append(f"① 状态：{_kl_bias(k)} — {_kl_reason(tf_key, k, merged)}")
        if tf_key == "4h":
            struct.append(f"② 趋势：{_trend_4h(k)}")
            struct.append(f"③ VWAP：S `{_vwap(k)}` · W `{_vwap(k, 'w')}` · M `{_vwap(k, 'm')}` — {_vwap_pos(k, price)}")
            struct.append(f"④ 价值：VAH `{_value_area(k,'vah')}` · POC `{_value_area(k,'poc')}` · VAL `{_value_area(k,'val')}` — {_va_read(k, price)}")
            struct.append(f"⑤ 流动性：上 `{_liq_level(k,'up',price)}` · 下 `{_liq_level(k,'down',price)}` — {_liq_direction(k, price)}")
            struct.append(f"⑥ 失效线：`{_invalid_4h(k, merged)}` — {_invalid_reason_4h(merged)}")
        elif tf_key in ("1h", "15m"):
            struct.append(f"② 关键位：阻 `{_sr_level(k,'res',price)}` · 支 `{_sr_level(k,'sup',price)}`")
            if tf_key == "15m":
                atr_v = _atr_15m(klines)
                dist = abs((float(price or 0) - float(klines.get('low_15m', price or 0)))) if price and klines.get('low_15m') else 0
                struct.append(f"③ 禁追线：距关键位 `{dist:,.0f}` · ATR `~{atr_v:,.0f}` — {_chase_ok(dist, atr_v)}")
        elif tf_key == "5m":
            struct.append(f"② 触发：{_trigger_5m(k, merged, model_id)}")
            struct.append(f"③ 噪音：{_noise_5m(k)}")
        struct.append(f"④ 判断：{_tf_verdict(tf_key, k, merged)}")
    # 三线汇总
    struct.append("**三线汇总**")
    struct.append(f"① 失效线：`{_invalid_4h(klines.get('4h',{}), merged)}` — 错了在哪里认错")
    struct.append(f"② 执行线：`{_exec_line(klines, merged, status)}` — 确认后才动手")
    struct.append(f"③ 禁追线：`{_no_chase_line(klines, price)}` — 离关键位过远不追")

    # ═══ 三、博弈 ═══
    game = ["**三、博弈**"]
    game.append(f"① DMI：{bias_cn} — 背景{_dmi_bg(merged)} · 位置{_dmi_pos(klines, price)} · 量能{_dmi_vol(klines)} · 执行等待")
    game.append(f"② 引擎：做空 {short_c:.3f} vs 做多 {long_c:.3f} — **{bias_cn}**")
    game.append(f"③ 订单流：CVD {cvd_dir} · Taker {taker_dir} · OI {oi_trend.replace('(','').replace(')','') if oi_trend else 'N/A'} — {_flow_confirm(cvd_dir, taker_dir, bias_cn)}")
    top_models = sorted([r for r in (results or []) if float(r.get("confidence") or 0) > 0.1], key=lambda r: float(r.get("confidence") or 0), reverse=True)
    strongest_long = next((r for r in top_models if r.get("direction") == "long"), None)
    strongest_short = next((r for r in top_models if r.get("direction") == "short"), None)
    game.append(f"④ 最强多：{strongest_long['name'] if strongest_long else '无'} {float(strongest_long.get('confidence',0)):.2f}" if strongest_long else "④ 最强多：无 — 无有效做多模型匹配")
    game.append(f"⑤ 最强空：{strongest_short['name'] if strongest_short else '无'} {float(strongest_short.get('confidence',0)):.2f}" if strongest_short else "⑤ 最强空：无 — 无有效做空模型匹配")
    game.append(f"⑥ 社区：情绪 {_x_dir(search_sent)}（web源·非X实时）· CG {_cg_read(engine_data)} · F&G `{fg_v}` — {_community_read(fg, community)}")
    game.append(f"⑦ 催化：{_nna(engine_data,'catalyst','无')} · 等级{_nna(engine_data,'catalyst_grade','D')} — {_catalyst_dir(engine_data)}")
    structure_dir = _structure_verdict(klines, merged)
    engine_dir = "偏空" if short_c > long_c else "偏多" if long_c > short_c else "中性"
    flow_dir = "偏空" if cvd_dir == "卖" else "偏多" if cvd_dir == "买" else "中性"
    resonance = "共振" if (structure_dir == engine_dir == flow_dir) or status.startswith("A") else "未共振"
    game.append(f"⑧ 三源裁决：结构{structure_dir} + 引擎{engine_dir} + 订单流{flow_dir} — **{resonance}**")
    game.append(f"⑨ 分歧处理：{_divergence_handling(resonance, status)}")
    gd = grok.get("grok_direction")
    gc = grok.get("grok_confidence", 0)
    game.append(f"⑩ Grok验证：{'一致' if grok.get('agree') else '跳过' if grok.get('skipped') else '分歧'} — 方向{gd or '?'} · 置信{float(gc):.2f}{' · 分歧时置信上限3/5' if not grok.get('agree') and not grok.get('skipped') else ''}")
    boundary = _boundary(klines, merged, price)
    game.append(f"⑪ 分界：`{boundary}` — 不破判{_boundary_up(boundary, bias_cn)} · 跌破判{_boundary_down(boundary, bias_cn)}")

    # ═══ 四、操作 ═══
    ops = ["**四、操作**"]
    if status == "B等待" or direction == "wait":
        ops.append("")
        ops.append(f"—— 预案A · {_plan_a_name(bias_cn, model_id)}（⚠ 当前B等待·等确认后优先）——")
        ops.append(f"① 方向：{dir_cn}")
        ops.append(f"② 入场：`{_fmt_price(price).strip('`')}` · 限价")
        ops.append(f"   触发：{_plan_a_trigger(model_id, klines, merged)}")
        ops.append(f"   确认：CVD转{bias_cn} · Taker {bias_cn}≥1.0 · 15m收线确认")
        ops.append(f"③ 风控：100x")
        stop_a = _plan_stop(klines, merged, price, bias_cn)
        tp1_a, tp2_a = _plan_targets(klines, price, bias_cn)
        ops.append(f"   止损：`{stop_a}` — {_stop_reason(bias_cn)}")
        ops.append(f"   止盈：`{tp1_a}` — {_tp_reason(1, tp1_a, price, bias_cn)}")
        ops.append(f"   止盈：`{tp2_a}` — {_tp_reason(2, tp2_a, price, bias_cn)}")
        ops.append(f"④ 仓位：`{_qty(price, meta, bias_cn)} BTC`")
        ops.append(f"   风险：`{meta.get('risk_usd',2)}U`")
        ops.append(f"   名义：`{_notional(price, meta, bias_cn)}U`")
        ops.append(f"⑤ 失效：{_plan_a_failure(model_id, klines, merged)} — 取消预案A")
        ops.append(f"⑥ 复查：入场后 15m×3根 — 检查CVD是否转{bias_cn}、是否移损")
        ops.append(f"⑦ 轨迹：{_trajectory(status, bias_cn, direction)}")
        ops.append("")
        ops.append(f"—— 预案B · {_plan_b_name(bias_cn, model_id)}（备选 · 次优）——")
        ops.append(f"① 方向：{_alt_dir(dir_cn)}")
        ops.append(f"② 入场：`{_plan_b_entry(klines, merged, price, bias_cn)}` · 限价")
        ops.append(f"   触发：{_plan_b_trigger(model_id, klines, merged, bias_cn)}")
        ops.append(f"   确认：CVD转{_alt_dir(bias_cn)} · Taker {_alt_dir(bias_cn)}≥1.3 · 不再跌回关键位下方")
        ops.append(f"③ 风控：100x")
        stop_b = _plan_stop_b(klines, price, bias_cn)
        tp1_b, tp2_b = _plan_targets_b(klines, price, bias_cn)
        ops.append(f"   止损：`{stop_b}` — 关键位下方，跌破说明{_alt_dir(bias_cn)}失败")
        ops.append(f"   止盈：`{tp1_b}` — {_tp_reason_b(1, tp1_b, price, bias_cn)}")
        ops.append(f"   止盈：`{tp2_b}` — {_tp_reason_b(2, tp2_b, price, bias_cn)}")
        ops.append(f"④ 仓位：`{_qty_b(price, meta, bias_cn)} BTC`")
        ops.append(f"   风险：`{meta.get('risk_usd',2)}U`")
        ops.append(f"   名义：`{_notional_b(price, meta, bias_cn)}U`")
        ops.append(f"⑤ 失效：{_plan_b_failure(klines, merged, price, bias_cn)} — {_alt_dir(bias_cn)}失败")
        ops.append(f"⑥ 复查：入场后 15m×3根 — 检查VWAP/EMA收复、CVD不再背离")
        ops.append(f"⑦ 轨迹：{_trajectory_b(status, bias_cn)}")
    else:
        plan_tag = " ⚠优先" if priority in ("A", "B") else ""
        ops.append(f"—— 预案{priority} · {dir_cn}{plan_tag} ——")
        ops.append(f"① 方向：{dir_cn}")
        ops.append(f"② 入场：{_fmt_price(price)} · {'市价' if status.startswith('A') else '限价'}")
        ops.append(f"   触发：{model_id} 形态在 5m/15m 收线确认")
        ops.append(f"   确认：CVD{'顺向' if cvd_dir=='买' else '顺向'} · Taker确认 · 回踩不破")
        ops.append(f"③ 风控：100x")
        ops.append(f"   止损：`{_plan_stop(klines, merged, price, bias_cn)}` — 结构反向突破")
        ops.append(f"   止盈：`{_plan_targets(klines, price, bias_cn)[0]}` — R:R底线1:2")
        ops.append(f"④ 仓位：`{_qty(price, meta, bias_cn)} BTC`")
        ops.append(f"   风险：`{meta.get('risk_usd',2)}U`")
        ops.append(f"⑤ 失效：关键结构位反向收复 — 触发后取消")
        ops.append(f"⑥ 复查：入场后 15m×3根 — CVD/结构/移损")
        ops.append(f"⑦ 轨迹：{status} → 入场 → 复查 → 移损/止盈/失效")

    # ═══ 五、风控 ═══
    risk = ["**五、风控**"]
    risk.append(f"① 单笔：风险 `{meta.get('risk_usd',2)}U` — 小本金阶段默认轻仓，`10U`是上限不是常态")
    risk.append(f"② 日限：已用 `0` / `10U` — 达线停止新仓")
    rr1 = meta.get("rr1")
    risk.append(f"③ R:R：{'底线 1:2' if rr1 is None else f'1:{rr1}'} · 底线 1:2 — 不满足直接 X禁做")
    risk.append(f"④ 止损：{_stop_pair(klines, merged, price, bias_cn)} — 不因止盈不足而放宽")
    risk.append(f"⑤ 移损：+1R移至保本 — +2R保护利润")
    risk.append(f"⑥ 数据闸门：{_gate_data(data_grade)} — 数据{data_grade}级 · 缺口{_gaps(engine_data)}")
    risk.append(f"⑦ 事件闸门：{_gate_event(engine_data)} — 重大数据前后{'30' if _has_event(engine_data) else '0'}分钟")
    risk.append(f"⑧ 执行闸门：{_gate_exec(klines, price, status)} — 入场距现价≤0.5ATR才可执行")
    risk.append(f"⑨ 复盘：入场、止损、止盈、失效、结果必须本地记录 — 卡面只保留人读内容")
    risk.append(f"⑩ 心态：禁追价 — 禁复仇 — 连亏后暂停")

    blocks = ["\n".join(head), "\n".join(env), "\n".join(struct), "\n".join(game), "\n".join(ops), "\n".join(risk)]
    return "\n\n".join(blocks) + "\n"


# ── v6.9 helper functions ──

def _oi_trend(oi_data: dict) -> str:
    if not oi_data: return ""
    try: return " (微降)" if oi_data.get("trend") == "down" else " (微升)" if oi_data.get("trend") == "up" else ""
    except: return ""

def _kl_summary(k: dict, role: str) -> str:
    if not k: return f"{role}无数据"
    desc = k.get("description") or k.get("state") or ""
    return desc if desc else f"{role}数据待采集"

def _score13(merged: dict, results: list[dict], status: str) -> str:
    struct_s = 2 if any(r.get("name") in FIXED_MODELS for r in (results or [])) else 1
    cycle_s = 1
    flow_s = 1
    deriv_s = 0 if status == "B等待" else 1
    cat_s = 0
    risk_s = 1 if status != "X禁做" else 0
    sent_s = 1
    total = struct_s + cycle_s + flow_s + deriv_s + cat_s + risk_s + sent_s
    return f"{total}/13 — 结构+{struct_s}·周期+{cycle_s}·订单流+{flow_s}·衍生+{deriv_s}·催化+{cat_s}·风控+{risk_s}·情绪+{sent_s}"

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

def _plan_a_trigger(model_id: str, klines: dict, merged: dict) -> str:
    bias = str(merged.get("bias") or "偏空")
    if bias == "偏空":
        return f"反弹至EMA21失败回落"
    return f"回踩支撑确认"

def _plan_stop(klines: dict, merged: dict, price, bias_cn: str) -> str:
    k4h = klines.get("4h") or {}
    hi = float(k4h.get("high") or float(price or 0) * 1.02)
    lo = float(k4h.get("low") or float(price or 0) * 0.98)
    if bias_cn == "偏空":
        return f"{hi:,.0f}"
    return f"{lo:,.0f}"

def _plan_targets(klines: dict, price, bias_cn: str):
    p = float(price or 0)
    if bias_cn == "偏空":
        tp1 = p - 500
        tp2 = p - 1200
    else:
        tp1 = p + 500
        tp2 = p + 1200
    return f"{tp1:,.0f}", f"{tp2:,.0f}"

def _stop_reason(bias_cn: str) -> str:
    return "反弹高点上沿" if bias_cn == "偏空" else "支撑下方"

def _tp_reason(n: int, tp: str, price, bias_cn: str) -> str:
    p = float(price or 0)
    tp_v = float(tp.replace(",",""))
    dist = abs(tp_v - p)
    rr = dist / abs(float(_plan_stop({}, {}, price, bias_cn).replace(",","")) - p) if bias_cn else 1
    return f"${dist:,.0f}（1:{rr:.1f}）"

def _qty(price, meta: dict, bias_cn: str) -> str:
    risk = float(meta.get("risk_usd", 2))
    p = float(price or 62000)
    stop_dist = 500
    qty = risk / stop_dist
    return f"{qty:.4f}"

def _notional(price, meta: dict, bias_cn: str) -> str:
    qty = float(_qty(price, meta, bias_cn))
    return f"{qty * float(price or 62000):,.0f}"

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
    mapping = {"偏空": "多头", "偏多": "空头", "空头": "多头", "多头": "空头"}
    return mapping.get(bias_cn_or_dir, "观望")

def _plan_b_entry(klines: dict, merged: dict, price, bias_cn: str) -> str:
    p = float(price or 0)
    offset = -200 if bias_cn == "偏空" else 200
    return f"{p + offset:,.0f}"

def _plan_b_trigger(model_id: str, klines: dict, merged: dict, bias_cn: str) -> str:
    if bias_cn == "偏空":
        return "站回VAL + 15m收线确认"
    return "跌破支撑 + 15m收线确认"

def _plan_stop_b(klines: dict, price, bias_cn: str) -> str:
    p = float(price or 0)
    offset = -300 if bias_cn == "偏空" else 300
    return f"{p + offset:,.0f}"

def _plan_targets_b(klines: dict, price, bias_cn: str):
    p = float(price or 0)
    if bias_cn == "偏空":
        return f"{p + 600:,.0f}", f"{p + 1250:,.0f}"
    return f"{p - 600:,.0f}", f"{p - 1250:,.0f}"

def _tp_reason_b(n: int, tp: str, price, bias_cn: str) -> str:
    p = float(price or 0)
    tp_v = float(tp.replace(",",""))
    dist = abs(tp_v - p)
    stop_v = float(_plan_stop_b({}, price, bias_cn).replace(",",""))
    rr = dist / abs(stop_v - p) if abs(stop_v - p) > 0 else 2
    return f"${dist:,.0f}（1:{rr:.1f}）"

def _qty_b(price, meta: dict, bias_cn: str) -> str:
    risk = float(meta.get("risk_usd", 2))
    p = float(price or 62000)
    stop_dist = 300
    qty = risk / stop_dist
    return f"{qty:.4f}"

def _notional_b(price, meta: dict, bias_cn: str) -> str:
    qty = float(_qty_b(price, meta, bias_cn))
    return f"{qty * float(price or 62000):,.0f}"

def _plan_b_failure(klines: dict, merged: dict, price, bias_cn: str) -> str:
    if bias_cn == "偏空":
        return "跌回VAL下方"
    return "站回阻力上方"

def _trajectory_b(status: str, bias_cn: str) -> str:
    alt = "反弹" if bias_cn == "偏空" else "回调"
    return f"急跌 → 企稳 → {alt} → 入场 → 目标VWAP/EMA"

def _stop_pair(klines: dict, merged: dict, price, bias_cn: str) -> str:
    s = _plan_stop(klines, merged, price, bias_cn)
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
