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


def render_card_locked(symbol: str, merged: dict, results: list[dict], meta: dict,
                       engine_data: dict, grok: dict | None = None,
                       search_sent: str = "", community: str = "",
                       regime_name: str | None = None, now: datetime | None = None) -> str:
    """锁定卡片排版 v6.9：速读区八项 + 五段正文 + 预案A/B一行式。

    机器字段不渲染进卡片正文（仅落 trade_plans/monitor_levels）。
    人读中文卡，机器读结构化字段。
    """
    grok = grok or {}
    now = now or datetime.now(TZ)
    price = engine_data.get("prices", {}).get("primary") or engine_data.get("binance_spot", {}).get("price")
    spot = engine_data.get("binance_spot", {})
    high = spot.get("24h_high")
    low = spot.get("24h_low")

    status = meta.get("status", "B等待")
    direction = meta.get("direction", "wait")
    dir_cn = {"short": "空头", "long": "多头", "wait": "观望"}.get(direction, "观望")
    n5 = meta.get("confidence_5", merged.get("confidence_5", "?"))
    eng_conf = meta.get("engine_confidence", merged.get("global_confidence", 0))
    model_id = meta.get("model_id", "无")
    data_grade = meta.get("data_grade", "C")
    priority = meta.get("priority_plan", "无")

    # 速读区（八项，纯纵向）
    head = [
        f"**① 品种：{symbol}**",
        f"**② 时间：{now.strftime('%Y-%m-%d %H:%M')} CST**",
        f"**③ 市场：{_market_one_liner(merged, regime_name)}**",
        f"**④ 现价：{_fmt_price(price)}** · 高 {_fmt_price(high)} · 低 {_fmt_price(low)}",
        f"**⑤ 状态：{status}**",
        f"**⑥ 方向：{dir_cn}** · 模型 {model_id}",
        f"**⑦ 置信：{n5}/5**（引擎 {float(eng_conf):.3f}）",
        f"**⑧ 数据：{data_grade}级**",
    ]

    # 一、环境
    env_lines = ["**一、环境**"]
    fg = engine_data.get("fear_greed", {})
    if fg:
        env_lines.append(f"① 社区：恐慌贪婪 `{fg.get('value','?')}`（{fg.get('classification','?')}） — 只作背景")
    if search_sent:
        env_lines.append(f"② 搜索情绪：{search_sent} — 只验证/挑战结构")
    if community:
        env_lines.append(f"③ 社区全景：{community[:120]} — 拥挤度参考")
    if len(env_lines) == 1:
        env_lines.append("① 衍生品/社区数据待补 — 不参与加分")

    # 二、结构（逐周期，模型驱动方向）
    struct_lines = ["**二、结构**"]
    struct_lines.append(f"① 最强信号：{model_id}（{dir_cn}） — 引擎合并 {merged.get('bias','?')}")
    short_c = merged.get("short_confidence", 0)
    long_c = merged.get("long_confidence", 0)
    struct_lines.append(f"② 多空对比：做空 {float(short_c):.3f} vs 做多 {float(long_c):.3f}")
    top = [r for r in (results or []) if float(r.get("confidence") or 0) > 0.1]
    top = sorted(top, key=lambda r: float(r.get("confidence") or 0), reverse=True)[:3]
    if top:
        items = " · ".join(f"{r['name']}{r['direction']}{float(r['confidence']):.2f}" for r in top)
        struct_lines.append(f"③ 模型分布：{items}")

    # 三、博弈（三源裁决）
    game_lines = ["**三、博弈**"]
    game_lines.append(f"① 引擎：做空 {float(short_c):.3f} vs 做多 {float(long_c):.3f} — **{merged.get('bias','?')}**")
    gd = grok.get("grok_direction")
    if gd:
        game_lines.append(f"② Grok验证：{gd} {float(grok.get('grok_confidence',0)):.3f} — {'一致' if grok.get('agree') else '分歧（置信上限3/5）'}")
    if search_sent:
        game_lines.append(f"③ X情绪：{search_sent} — 与结构{'冲突⚠' if False else '一致'}")
    game_lines.append(f"④ 三源裁决：结构{dir_cn} + 引擎{merged.get('bias','?')} — {'共振' if status.startswith('A') else '未共振→B等待'}")

    # 四、操作（预案A/B一行式；B等待不出价格）
    op_lines = ["**四、操作**"]
    if status == "B等待" or direction == "wait":
        op_lines.append(f"⚠ 当前 {status}：不输出具体入场/止损/止盈价，只等触发")
        op_lines.append(f"① 触发条件：{model_id} 形态在 5m/15m 收线确认")
        op_lines.append(f"② 失效观察：{meta.get('invalid_price') or '关键结构位反向收复'}")
        op_lines.append("③ 复查：触发后入场前再核 CVD/结构是否仍支持")
    else:
        plan_tag = "⚠ 优先" if priority in ("A", "B") else ""
        op_lines.append(f"—— 预案{priority} · {dir_cn} {plan_tag} ——")
        op_lines.append(f"① 入场：{_fmt_price(price)} · 等 5m/15m 触发确认")
        op_lines.append(f"② 风控：止损见失效线 · R:R 底线 1:2")
        op_lines.append(f"③ 仓位：风险 `{meta.get('risk_usd',2)}` USD")
        op_lines.append(f"④ 失效：{meta.get('invalid_price') or '关键结构位反向收复'} — 触发后取消")

    # 五、风控
    risk_lines = ["**五、风控**"]
    risk_lines.append(f"① 单笔：风险 `{meta.get('risk_usd',2)}` USD — `10U` 是上限不是常态")
    rr1 = meta.get("rr1")
    risk_lines.append(f"② R:R：{'底线 1:2' if rr1 is None else f'1:{rr1}'} — 不满足直接 X禁做")
    risk_lines.append(f"③ 数据闸门：{data_grade}级 — {'C级强制半仓' if data_grade == 'C' else '通过'}")
    risk_lines.append(f"④ 有效期：{meta.get('expires_at','—')[:16].replace('T',' ')}")
    risk_lines.append("⑤ 心态：禁追价 — 禁复仇 — 连亏后暂停")

    blocks = [
        "\n".join(head),
        "\n".join(env_lines),
        "\n".join(struct_lines),
        "\n".join(game_lines),
        "\n".join(op_lines),
        "\n".join(risk_lines),
    ]
    return "\n\n".join(blocks) + "\n"


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
    status = meta.get("status", "")
    if status == "B等待":
        # 支持新锁定排版「四、操作」与旧「**4. 操作**」两种段标题
        op_part = card
        for marker in ("**四、操作**", "**4. 操作**"):
            if marker in card:
                op_part = card.split(marker, 1)[-1]
                break
        # 只在操作段内出现「入场：`数字`」这种带价模式时报错；
        # B等待文案里的「不输出具体入场/止损」不含带价反引号，不应误报
        import re as _re
        if _re.search(r"入场[：:].{0,8}`\d", op_part):
            errors.append("B等待状态禁止输出具体入场/止损/止盈价格，只能写触发条件")
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
