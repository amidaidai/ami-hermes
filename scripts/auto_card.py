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

import sys, json, time, re, subprocess, os
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")

# TV 结构复用窗口（分钟）——读取侧唯一常量。
# 语义：「卡内 TV 结构最多滞后一根 5m K 线」。XAU 注入判定与前置决策
# 必须引用同一个值，否则会出现「前置说新鲜跳过、读取说过期拒绝」的
# 自相矛盾卡（2026-09-13 已记录过同源事故，2026-09-14 复现时间维度版本）。
TV_LIVE_READ_MAX_AGE_MIN = 5.0
# 前置决策必须比读取窗口更严：出卡本身要花 20~160s，若前置按同一 5 分钟
# 判「新鲜」，卡跑完时缓存已跨过阈值 → 主指标被丢弃、门2 亮红。
# 留 3 分钟余量 = 覆盖最慢出卡路径，同时不改变用户批准的 5 分钟注入契约。
TV_LIVE_PRE_SYNC_MARGIN_MIN = 3.0
TV_LIVE_PRE_SYNC_MAX_AGE_MIN = TV_LIVE_READ_MAX_AGE_MIN - TV_LIVE_PRE_SYNC_MARGIN_MIN
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_json import append_text_line, atomic_write_json, atomic_write_text

# v7.5: 中文本地化
from zh_locale import T, CARD_LABELS, KILL_ZONE_ZH, DIR_ZH, STRATEGY_ZH, SYMBOL_ZH, asset_name
# v7.5: TV截图
try:
    from tv_screenshot import capture_analysis_setup as _tv_screenshot
except Exception:
    _tv_screenshot = lambda s, d=None, **kwargs: None
# v7.5: 话题路由
try:
    from topic_router import route_send as _route_send, get_target as _get_target
except Exception:
    _route_send = lambda s, m, sc=None: None
    _get_target = lambda s: None

# v13 双指标接口契约（唯一定义源：scripts/tv_indicator_contract.py）
# 指标侧改行名/字段名时只改那一处，本文件不再自写字符串，避免三处漂移。
try:
    import tv_indicator_contract as TVC
except Exception:  # pragma: no cover - 契约缺失时退化为空壳，不阻断出卡
    class _TVCStub:
        CONTRACT_VERSION = "missing"
        MAIN_ROW_LABELS: list = []
        SUB_ROW_LABELS: list = []
        RISK_ROW_VARIANTS = ["风控", "风控·观察", "风控·未授权", "禁做·不出价"]
        # 空壳是**降级态**，不是正常态：DW 字段与行动格行会全部读不到。
        # 卡面必须把它说出来（见 _source_summary 的「契约缺失」），不许静默出空卡。
        DEGRADED = True
        CONTRACT_CURRENT = 0
        SUPPORTED_CONTRACT_VERSIONS: tuple = ()
        DW_MAIN: list = []
        DW_SUB: list = []
        DW_ALIASES_MAIN: dict = {}
        DW_ALIASES_SUB: dict = {}
        LEGACY_DW_ALIASES_MAIN: dict = {}
        LEGACY_DW_ALIASES_SUB: dict = {}
        FEED_MODE: dict = {}
        SVP_AUTHORIZATION_LABEL = "风控"
        SVP_OBSERVATION_LABEL = "风控·观察"
        SVP_UNAUTHORIZED_LABEL = "风控·未授权"
        SVP_FORBIDDEN_VALUE = "禁做·不出价"
        SVP_FORBIDDEN_LABELS: tuple = (SVP_FORBIDDEN_VALUE,)

        @staticmethod
        def risk_row_label(rows):
            return ""

        @staticmethod
        def decode_basic_bus(pack, contract=None):
            return None

        @staticmethod
        def decode_feed_mode(code):
            return {"mode": None, "text": "缺失", "usable": False,
                    "aggregated": False, "fallback": False, "single": False,
                    "abnormal": False}

        @staticmethod
        def feed_mode_tail(code):
            return ""

        @staticmethod
        def decode_oi_presence(pack, contract=None):
            return {"present": False, "pct": None, "text": "OI未接"}

        @staticmethod
        def decode_trigger_pack(pack):
            return None

        @staticmethod
        def ordered_main_rows(rows):
            return []

        @staticmethod
        def ordered_sub_rows(rows):
            return []

        @staticmethod
        def risk_row_value(rows):
            return ""

        @staticmethod
        def parse_risk_row(text):
            return {"entry": None, "stop": None, "target": None,
                    "stop_atr": None, "rr": None, "label": ""}

        @staticmethod
        def format_no_trade(code, sep="+"):
            return ""

        @staticmethod
        def decode_haldro_state(code):
            return "缺失"

        @staticmethod
        def decode_entry_valid(code):
            return "缺失"

        @staticmethod
        def rr_gate(rr):
            return "R:R缺失"

    TVC = _TVCStub()

# v13 裁决矩阵（解除条件 / R:R 档位 / 主副九宫格）
try:
    import decision_matrix as DM
except Exception:  # pragma: no cover
    class _DMStub:
        @staticmethod
        def release_plan(_c): return []

        @staticmethod
        def format_release(_c, sep='；'): return ''

        @staticmethod
        def synthesis_verdict(**_k): return {}

        @staticmethod
        def rr_tier(_r): return {'tier': '缺失', 'a_ok': False, 'bc_ok': False, 'text': 'R:R缺失', 'value': None}

    DM = _DMStub()


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


# ═══════════════════ 风控层 v7.3 ═══════════════════
INITIAL_BALANCE = 100.0  # 棠溪本金
MAX_RISK_USD_CAP = INITIAL_BALANCE * 0.01  # 1%硬上限（防余额膨胀）

def _consecutive_losses() -> tuple[int, bool]:
    """读取 trade_events.jsonl 统计最近连续亏损笔数。
    返回 (consecutive_loss_count, paused)。
    """
    events_file = DATA / "trade_events.jsonl"
    if not events_file.exists():
        return 0, False
    try:
        with open(events_file, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if not lines:
            return 0, False
        count = 0
        for line in reversed(lines):
            try:
                ev = json.loads(line)
                pnl = float(ev.get("pnl_usd") or 0)
                if pnl < 0:
                    count += 1
                else:
                    break  # Won trade breaks the streak
            except Exception:
                continue
        return count, (count >= 5)  # ≥5 = auto-pause
    except Exception:
        return 0, False


def _risk_account_connected(engine_data: dict) -> bool:
    """卡面风控额度是否基于**真实账户余额**。

    历史缺陷：没有真实余额时 `_adaptive_risk` 用 `or 100.0` 兜底算出一个数，
    卡面照样写「风控1.00U」——看起来像真实额度，实际是凭空默认值。用户按它下单
    会误判单笔风险。现在显式区分：没接账户就在卡面写「未接账户」，不报假数。
    """
    if not isinstance(engine_data, dict):
        return False
    for key in ("account_balance", "balance"):
        try:
            if float(engine_data.get(key) or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    tmpl = engine_data.get("template")
    if isinstance(tmpl, dict):
        try:
            if float(tmpl.get("account_balance") or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
    return False


def _adaptive_risk(engine_data: dict) -> float:
    """按 ATR 波动率自适应单笔风险金额 v7.3。
    
    三层守卫：
      ① 连亏≥3笔 → 风险减半 · 连亏≥5笔 → 暂停(risk=0)
      ② 余额膨胀守卫 → max_risk_usd ≤ INITIAL_BALANCE × 1%
      ③ 单笔硬上限 10U（棠溪铁律）
    """
    try:
        from risk_constitution import adaptive_risk_usd
        balance = float(engine_data.get("account_balance") or 0)
        if balance <= 0:
            tmpl = engine_data.get("template") if isinstance(engine_data.get("template"), dict) else {}
            balance = float(engine_data.get("balance") or tmpl.get("account_balance") or 100.0)

        # —— 守卫①: 连亏追踪 ——
        consec, paused = _consecutive_losses()
        if paused:
            return 0.0
        shrink = 0.5 if consec >= 3 else 1.0  # ≥3笔 → 半仓
        
        # —— ATR自适应 ——
        atr_pct = engine_data.get("atr_pct")
        if atr_pct is None:
            spot = engine_data.get("binance_spot", {})
            hi, lo, px = spot.get("24h_high"), spot.get("24h_low"), (engine_data.get("prices", {}) or {}).get("primary")
            if hi and lo and px:
                atr_pct = (float(hi) - float(lo)) / float(px) / 3.0
        r = adaptive_risk_usd(account_balance=balance, atr_pct=float(atr_pct or 0))
        raw_risk = r["risk_usd"] * shrink
        
        # —— 守卫②: 余额膨胀硬上限 ——
        raw_risk = min(raw_risk, MAX_RISK_USD_CAP)
        
        # —— 守卫③: 10U铁律 ——
        return min(raw_risk, 10.0)
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
    """从 TradingView study values 提取关键数据。

    2026年7月2日双指标协议：主指标已恢复 MCP Data Window 导出
    (MCP Side/Grade/Score/Entry/Stop/Target/CVD/Quality)，副指标也导出
    OI/CVD/Volume/Coverage/Composite。这里统一保留这些字段，供表格缺失
    或 TV MCP 只返回 data_window 时兜底；行动格文字仍是进出场首选。
    """
    result = {}
    if not tv_studies:
        return result
    for s in tv_studies:
        name = s.get("name", "")
        vals = s.get("values", {})
        if "CVD" in name or "SVP" in name or "VWAP" in name or "Volume" in name or "Aggregated" in name:
            for k, v in vals.items():
                try:
                    val_raw = str(v)
                    mult = 1
                    raw_upper = val_raw.upper()
                    if "B" in raw_upper:
                        mult = 1000000000
                    elif "M" in raw_upper:
                        mult = 1000000
                    elif "K" in raw_upper:
                        mult = 1000
                    val_str = (val_raw.replace("\u2212", "-").replace(",", "")
                               .replace("\u202f", "").replace("%", "")
                               .replace("K", "").replace("k", "")
                               .replace("M", "").replace("m", "")
                               .replace("B", "").replace("b", "").strip())
                    # Also handle unicode minus sign
                    val_str = val_str.replace("\u2212", "-")
                    result[k] = float(val_str) * mult
                except (ValueError, TypeError):
                    result[k] = str(v)
    return result


def _tv_cache_indicators_to_studies(cache: dict | None) -> list[dict]:
    """把 tv_data_bridge 的 snake_case indicators 缓存转回 study_values 形态。

    tv_data_bridge.py 落盘的是 indicators={mcp_side_code:..., composite:...}，
    而正式消费链 _parse_tv_study_values() 只认 TV MCP 原始字段名。
    这里做一次反向映射，避免新鲜缓存也丢失 MCP Data Window / Composite。
    """
    if not isinstance(cache, dict):
        return []
    indicators = cache.get("indicators") or {}
    if not isinstance(indicators, dict):
        return []

    # snake_case → TV DW 标题一律取自接口契约：canonical 优先，LEGACY 只补
    # 历史缓存里才存在的旧名。本文件不再自写第三份清单（漂移根因）。
    main_map = {**TVC.LEGACY_DW_ALIASES_MAIN, **TVC.DW_ALIASES_MAIN}
    sub_map = {**TVC.LEGACY_DW_ALIASES_SUB, **TVC.DW_ALIASES_SUB}
    main_vals = {tv_key: indicators[src] for src, tv_key in main_map.items() if src in indicators}
    sub_vals = {tv_key: indicators[src] for src, tv_key in sub_map.items() if src in indicators}
    studies = []
    if main_vals:
        studies.append({"name": "SVP+ICT+VWAP+CVD", "values": main_vals})
    if sub_vals:
        studies.append({"name": "Volume Aggregated Spot & Futures", "values": sub_vals})
    return studies


def _tv_cache_decision_tables(cache: dict, grade: str = "C等待", treatment: str = "?") -> list[dict]:
    """把 tv_dmi_cache.json 的 decision_table 拆成主/副两个行动格表。"""
    dt = cache.get("decision_table") if isinstance(cache, dict) else None
    if not isinstance(dt, dict):
        return []
    tables = []
    synth = []
    if grade:
        synth.append(f"等级 | {grade}")
    if treatment:
        synth.append(f"处理 | {treatment}")
    # v13：行名/顺序一律取自接口契约（scripts/tv_indicator_contract.py），本文件不再自写字符串。
    # 旧 10 行里只有 结论/方向/磁吸↑/磁吸↓ 还在 v13 面板上，其余已并入「风控」行或删除；
    # 漏掉 位置/路径/CVD/OI/协同/结构/前位/现位 会静默丢决策信息。
    _synth = set(getattr(TVC, "SYNTH_ROWS", ("等级", "处理")))
    main_keys = [k for k in list(TVC.MAIN_ROW_LABELS) + list(getattr(TVC, "LEGACY_MAIN_ROWS", []))
                 if k not in _synth]
    for _variant in TVC.RISK_ROW_VARIANTS:
        if _variant not in main_keys:
            main_keys.append(_variant)
    _seen_main: set = set()
    _main_body: list = []
    for _k in main_keys:
        if _k in dt and _k not in _seen_main:
            _seen_main.add(_k)
            _main_body.append(f"{_k} | {dt[_k]}")
    main_rows = synth + _main_body
    if main_rows:
        tables.append({"name": "SVP+ICT+VWAP+CVD", "tables": [{"rows": main_rows}]})
    sub_keys = list(TVC.SUB_ROW_LABELS) + list(getattr(TVC, "LEGACY_SUB_ROWS", []))
    sub_rows = [f"{k} | {dt[k]}" for k in sub_keys if k in dt]
    if sub_rows and any(r.startswith("信号 |") for r in sub_rows):
        tables.append({"name": "Volume Aggregated", "tables": [{"rows": sub_rows}]})
    return tables


def _tv_symbol_cache_path(symbol: str) -> Path:
    raw = str(symbol or "").upper().split(":")[-1]
    if raw.endswith(".P"):
        raw = raw[:-2]
    key = "".join(ch for ch in raw if ch.isalnum())
    if key.endswith("PERP"):
        key = key[:-4]
    return DATA / f"tv_live_{key}.json"


def _tv_live_levels(cache: dict) -> tuple[float, float, float]:
    """读取tv_live顶层结构位；顶层为空时回退Data Window indicators。"""
    indicators = cache.get("indicators") if isinstance(cache, dict) else {}
    if not isinstance(indicators, dict):
        indicators = {}
    def level(name: str) -> float:
        raw = cache.get(name)
        if raw in (None, ""):
            raw = indicators.get(f"{name}_price")
        return _decision_float(raw)
    return level("poc"), level("vah"), level("val")


def _inject_tv_live_pine(engine_data: dict, cache: dict) -> bool:
    """把已通过symbol/fresh门禁的tv_live缓存提升为本轮唯一TV指标输入。"""
    if not isinstance(engine_data, dict) or not isinstance(cache, dict):
        return False
    studies = cache.get("studies", []) or _tv_cache_indicators_to_studies(cache)
    grade = cache.get("grade") or "C等待"
    treatment = cache.get("treatment") or cache.get("action") or "?"
    tables = _tv_cache_decision_tables(cache, grade=str(grade), treatment=str(treatment))
    if not tables and isinstance(cache.get("table_raw"), list):
        rows = [f"等级 | {grade}", f"处理 | {treatment}", *cache["table_raw"]]
        tables = [{"name": "SVP+ICT+VWAP+CVD", "tables": [{"rows": rows}]}]
        if isinstance(cache.get("sub_table_raw"), list):
            tables.append({"name": "Volume Aggregated", "tables": [{"rows": cache["sub_table_raw"]}]})
    if not studies and not tables:
        return False
    from copy import deepcopy
    engine_data["_tv_pine"] = {"studies": studies, "tables": tables}
    if isinstance(cache.get("chart_evidence"), dict):
        engine_data["_chart_evidence"] = deepcopy(cache["chart_evidence"])
        price_context = cache["chart_evidence"].get("price_context")
        if isinstance(price_context, dict):
            engine_data["_chart_price_context"] = deepcopy(price_context)
    # 防止同一轮前段读取的cron缓存继续覆盖刚验证的tv_live数据。
    from source_health import payload_timestamp
    indicators = cache.get("indicators") or {}
    engine_data["_tv_pine"]["_evidence"] = deepcopy({
        k: v for k, v in indicators.items()
        if k.startswith("mcp_evidence_") or k in (
            "mcp_location_valid", "mcp_trigger_confirmed", "mcp_bar_closed")
    }) if isinstance(indicators, dict) else {}
    captured = payload_timestamp(cache)
    engine_data["_tv_pine"]["_evidence_context"] = {
        "symbol": cache.get("symbol"),
        "timeframe": cache.get("timeframe", cache.get("resolution")),
        "captured_at": captured.timestamp() if captured else None,
    }
    engine_data.pop("_tv_main", None)
    engine_data.pop("_tv_sub", None)
    return True


def _parse_tv_sub_table(tv_tables: list | None) -> dict:
    """从TV表格解析副指标(Volume Aggregated)行动格数据。
    副指标行动格包含：信号/结论/高周/持仓/流向/量能/占比/爆仓/操作。
    支持两种分隔符：' | ' 和 '：'。"""
    if not tv_tables:
        return {}
    rows = {}
    raw_rows = None
    if isinstance(tv_tables, list) and tv_tables:
        for t in tv_tables:
            if not isinstance(t, dict):
                continue
            name = t.get("name", "")
            # 副指标识别：名称含 Volume/Aggregated/ACT 或第二个表
            inner = t.get("tables")
            if isinstance(inner, list) and inner:
                for inner_t in inner:
                    if isinstance(inner_t, dict):
                        r = inner_t.get("rows", [])
                        if r and any("信号" in str(x) for x in r[:3]):
                            raw_rows = r
                            break
                if raw_rows:
                    break
            # 回退：直接取 rows
            raw_rows = t.get("rows", [])
            if raw_rows:
                break
    if not raw_rows:
        return {}
    for row_text in raw_rows:
        row_str = str(row_text)
        # 尝试 pip 分隔
        if " | " in row_str:
            parts = row_str.split(" | ", 1)
        elif "｜" in row_str:
            parts = row_str.split("｜", 1)
        elif "：" in row_str:
            parts = row_str.split("：", 1)
        else:
            continue
        if len(parts) == 2:
            key, val = parts[0].strip(), parts[1].strip()
            # 标准化键名
            key_map = {"信号": "signal", "结论": "conclusion", "风险": "risk", "高周": "htf",
                       "持仓": "oi", "流向": "cvd_flow", "覆盖": "coverage", "量能": "volume",
                       "占比": "share", "爆仓": "liquidation", "操作": "operation"}
            mapped_key = key_map.get(key, key)
            rows[mapped_key] = val
    return rows



def _dual_indicator_verdict(symbol: str, meta: dict, engine_data: dict,
                            cvd_dir: str = "", cvd_quality: str = "") -> dict:
    """生成 SVP 主驾驶 + HALDRO 副驾驶的统一裁决。"""
    su = str(symbol or "").upper()
    is_crypto = su.endswith("USDT") or "BTC" in su or "ETH" in su or "SOL" in su
    tv_main = engine_data.get("_tv_main") if isinstance(engine_data, dict) else {}
    tv_sub = engine_data.get("_tv_sub") if isinstance(engine_data, dict) else {}
    if not isinstance(tv_main, dict):
        tv_main = {}
    if not isinstance(tv_sub, dict):
        tv_sub = {}
    # TradingView 主/副指标字段可能同处一个 study values 字典。
    # 旧解析会把 HALDRO 的 Composite / Confirm / OI 同时挂在 _tv_main 的 sub_* 字段；
    # 这里把这些字段也映射成 _tf_row 能识别的短字段，避免多周期表显示“副指标待刷新”。
    if not tv_sub and any(k.startswith("sub_") for k in tv_main):
        tv_sub = {
            "composite": tv_main.get("sub_composite"),
            "confirm_score": tv_main.get("sub_confirm_score"),
            "oi": tv_main.get("sub_oi_total"),
            "cvd_flow": tv_main.get("sub_estimated_cvd_value"),
            "coverage": tv_main.get("sub_coverage_exchanges"),
            "volume": tv_main.get("sub_volume_ratio"),
            "lsr": tv_main.get("sub_lsr"),
            "oi_change_pct": tv_main.get("sub_oi_change_pct_normalized"),
            "valid_code": tv_main.get("sub_haldro_valid_code"),
            "risk_code": tv_main.get("sub_haldro_risk_code"),
            "risk": tv_main.get("sub_haldro_risk_code") or tv_main.get("sub_cvd_quality_code"),
        }

    status = str(meta.get("status") or tv_main.get("grade") or "C等待")
    direction = str(meta.get("direction") or "")
    svp_dir = tv_main.get("direction_text") or direction or status
    svp_state = tv_main.get("grade") or status
    svp_flow = tv_main.get("cvd_state") or tv_main.get("mcp_cvd_value") or cvd_dir or "待判"
    dual = {
        "asset_is_crypto": is_crypto,
        "svp_state": svp_state,
        "svp_direction": svp_dir,
        "svp_position": tv_main.get("position") or tv_main.get("background") or "关键位待判",
        "svp_flow": svp_flow,
        "svp_quality": tv_main.get("mcp_quality_code") or meta.get("data_grade") or "待判",
        "svp_execution": " / ".join(str(x) for x in [tv_main.get("entry"), tv_main.get("stop"), tv_main.get("target")] if x) or "等待触发",
        "haldro_direction": "HALDRO不适用" if not is_crypto else "待刷新",
        "haldro_position": "—" if not is_crypto else "现货/合约待判",
        "haldro_flow": "—" if not is_crypto else "CVD/OI待判",
        "haldro_quality": "—" if not is_crypto else "覆盖率待判",
        "haldro_confirm": "—" if not is_crypto else "Confirm待判",
        "direction_verdict": "非加密不套HALDRO" if not is_crypto else "等待副指标",
        "structure_verdict": "按SVP+对应市场数据" if not is_crypto else "等关键位确认",
        "flow_verdict": "对应市场订单流降权参考" if not is_crypto else "CVD不配不追",
        "quality_verdict": "不因HALDRO缺失降级" if not is_crypto else "覆盖不足降级",
        "state": status,
        "conflict": False,
        "hard_conflict": False,
        "aligned": False,
        "valid_code": 0,
        "risk_code": 0,
        "usable": bool(tv_main) or not is_crypto,
    }

    if not is_crypto:
        engine_data["_dual_indicator_verdict"] = dual
        return dual

    composite = tv_main.get("sub_composite") or tv_sub.get("composite") or tv_sub.get("signal")
    confirm = tv_main.get("sub_confirm_score") or tv_sub.get("confirm_score") or tv_sub.get("operation")
    oi = tv_main.get("sub_oi_total") or tv_sub.get("oi")
    sub_cvd = tv_main.get("sub_estimated_cvd_value") or tv_sub.get("cvd_flow") or cvd_dir
    coverage = tv_main.get("sub_coverage_exchanges") or tv_sub.get("coverage")
    volume_ratio = tv_main.get("sub_volume_ratio") or tv_sub.get("volume")
    lsr = tv_main.get("sub_lsr") or tv_sub.get("lsr")
    # TradingView may not expose Binance's LSR metric suffix. Fall back to
    # the already collected Binance global account ratio, without pretending
    # it came from the AggVol Pine feed.
    lsr_source = "tradingview"
    if lsr in (None, ""):
        ls_fallback = engine_data.get("long_short") or {}
        if isinstance(ls_fallback, dict) and ls_fallback.get("long") is not None and ls_fallback.get("short") is not None:
            try:
                lsr = float(ls_fallback["long"]) / max(float(ls_fallback["short"]), 1e-9)
                lsr_source = "binance_global_account_ratio"
            except (TypeError, ValueError, ZeroDivisionError):
                lsr = None
                lsr_source = "unavailable"

    oi_change_pct = tv_main.get("sub_oi_change_pct_normalized") or tv_sub.get("oi_change_pct")
    risk_raw = tv_main.get("sub_haldro_risk_code")
    if risk_raw is None:
        risk_raw = tv_sub.get("risk_code")
    risk_code = 0
    try:
        risk_code = int(float(str(risk_raw).replace("−", "-")))
    except (TypeError, ValueError):
        pass
    risk_defs = ((1, "低覆盖"), (2, "单所主导"), (4, "上级冲突"),
                 (8, "OI背离"), (16, "CVD背离"), (32, "非加密"), (64, "LSR拥挤"))
    risk_labels = [label for bit, label in risk_defs if risk_code & bit]
    risk_text = "、".join(risk_labels) if risk_labels else "无硬风险"
    quality = tv_main.get("sub_cvd_quality_code") or tv_sub.get("risk") or coverage
    valid_raw = tv_main.get("sub_haldro_valid_code")
    if valid_raw is None:
        valid_raw = tv_sub.get("valid_code")
    valid_code = 1 if valid_raw is None and any(v not in (None, "") for v in (composite, confirm, coverage)) else 0
    try:
        if valid_raw is not None:
            valid_code = int(float(str(valid_raw).replace("−", "-")))
    except (TypeError, ValueError):
        pass

    # 20260911：接入 Coverage Feed Mode 四态（指标侧 F17）。
    # 只在非聚合态追加标注，正常态保持卡面紧凑；
    # 单源(3) 与 异常(4) 必须分开 —— 旧码把 Single 也报成「异常」，语义相反。
    feed = TVC.decode_feed_mode(
        tv_main.get("sub_coverage_feed_mode")
        if tv_main.get("sub_coverage_feed_mode") is not None
        else tv_sub.get("coverage_feed_mode")
    )
    feed_tail = TVC.feed_mode_tail(feed.get("mode"))

    comp_text = str(composite) if composite not in (None, "") else "待刷新"
    comp_num = None
    try:
        comp_num = float(composite)
    except (TypeError, ValueError):
        pass

    if comp_num is not None:
        haldro_dir = "偏多" if comp_num > 0 else "偏空" if comp_num < 0 else "中性"
    elif any(x in comp_text for x in ("多", "买", "long", "LONG", "+")):
        haldro_dir = "偏多"
    elif any(x in comp_text for x in ("空", "卖", "short", "SHORT", "-")):
        haldro_dir = "偏空"
    else:
        haldro_dir = "中性/待判"

    lsr_text = "待判"
    try:
        lsr_num = float(str(lsr))
        lsr_text = f"LSR {lsr_num:.2f}" + ("·多头拥挤" if lsr_num > 1.3 else "·空头拥挤" if lsr_num < 0.8 else "·均衡")
    except (TypeError, ValueError):
        if lsr not in (None, ""):
            lsr_text = str(lsr)

    svp_long = "多" in status or direction == "long" or "多" in str(svp_dir)
    svp_short = "空" in status or direction == "short" or "空" in str(svp_dir)
    sub_long = "偏多" in haldro_dir
    sub_short = "偏空" in haldro_dir
    raw_conflict = (svp_long and sub_short) or (svp_short and sub_long)
    aligned = (svp_long and sub_long) or (svp_short and sub_short)
    conflict = raw_conflict if valid_code >= 1 else False
    # 2026-09-13 审计修复：副指标 S3（CVD/OI 背离）必须与 decision_loop 的
    # haldro_state_conflict 硬阻断同源 —— 旧实现只看方向字符串，S3 会让
    # 门7「双指标共振」带着 usable=True 显示 GREEN，与硬闸门自相矛盾。
    haldro_s3 = False
    _s3_raw = tv_main.get("sub_haldro_state_pack")
    if _s3_raw not in (None, ""):
        try:
            haldro_s3 = int(float(str(_s3_raw).replace("−", "-"))) == 3
        except (TypeError, ValueError):
            haldro_s3 = False
    hard_conflict = (raw_conflict and valid_code >= 2) or haldro_s3
    crowding_risk = bool(risk_code & 64)
    flow_risk = bool(risk_code & (4 | 8 | 16))
    executable_grade = status.startswith(("A", "B", "C反"))
    downgraded_state = "X禁做观察" if hard_conflict and executable_grade else (
        "B等待（单源冲突）" if conflict and valid_code == 1 else
        "B等待（副单源·仅参考）" if valid_code <= 0 and executable_grade and feed.get("single") else
        "B等待（副指标无效）" if valid_code <= 0 and executable_grade else
        "B等待（副指标风险）" if status.startswith("A") and (crowding_risk or flow_risk) else status
    )

    # 2026-09-13：v13 独立字段接入（用户批准的消费矩阵修复，三处数据流）。
    # ① Basic Bus 解包：dual["oi_present"] 是 decision_loop 中 oi_agreement_low /
    #    oi_dispersion_high 判定的必要前置——此前无人写入该键（死逻辑根因）。
    # ② CVD 锚值 + 背景码（Bus 个位：1滚动买/2滚动卖/3仅前锚）→ ③表订单流行。
    # ③ OI 离散度 / 单所主导 / 扩张广度 → 质量行显示 + decision_loop 降权输入。
    _bus_info = None
    _bus_raw = tv_main.get("sub_basic_packed_bus")
    if _bus_raw not in (None, ""):
        try:
            _bus_info = TVC.decode_basic_bus(_bus_raw)
        except Exception:
            _bus_info = None
    if isinstance(_bus_info, dict) and _bus_info.get("valid"):
        dual["oi_present"] = bool(_bus_info.get("oi_present"))
    _cvd_bg_text = ""
    if isinstance(_bus_info, dict) and _bus_info.get("valid"):
        _cvd_bg_text = {1: "滚动买", 2: "滚动卖", 3: "仅前锚"}.get(_bus_info.get("cvdBg") or 0, "")
    _anchor_txt = ""
    _anchor_raw = tv_main.get("sub_cvd_anchor_value")
    if _anchor_raw not in (None, ""):
        try:
            _anchor_txt = f"锚{float(_anchor_raw):.2f}"
            if _cvd_bg_text:
                _anchor_txt += f"·{_cvd_bg_text}"
        except (TypeError, ValueError):
            _anchor_txt = ""
    if _anchor_txt:
        dual["cvd_anchor_text"] = _anchor_txt
    _disp_val = None
    _d_raw = tv_main.get("sub_oi_dispersion_ratio")
    if _d_raw not in (None, ""):
        try:
            _disp_val = float(str(_d_raw).replace("−", "-"))
        except (TypeError, ValueError):
            _disp_val = None
    if _disp_val is not None:
        dual["oi_dispersion_ratio"] = _disp_val
    _dom_val = None
    _dm_raw = tv_main.get("sub_exchange_dominance_pct")
    if _dm_raw not in (None, ""):
        try:
            _dom_val = int(float(str(_dm_raw).replace("−", "-")))
        except (TypeError, ValueError):
            _dom_val = None
    if _dom_val:
        dual["exchange_dominance_pct"] = _dom_val
    _breadth_val = None
    _b_raw = tv_main.get("sub_oi_breadth")
    if _b_raw not in (None, ""):
        try:
            _breadth_val = int(float(str(_b_raw).replace("−", "-")))
        except (TypeError, ValueError):
            _breadth_val = None
    if _breadth_val:
        dual["oi_breadth"] = _breadth_val
    _oi_metrics_txt = ""
    if _disp_val is not None:
        _oi_metrics_txt += f" · 离散{_disp_val:.2f}"
    if _dom_val:
        _oi_metrics_txt += f" · 主导{_dom_val}%" + ("⚠" if _dom_val >= 70 else "")
    if _breadth_val:
        _oi_metrics_txt += f" · 广度{_breadth_val:+d}"

    dual.update({
        "haldro_direction": f"{haldro_dir} · Composite {comp_text}",
        "haldro_position": f"OI {oi or '待判'} · 归一变化 {oi_change_pct if oi_change_pct not in (None, '') else '待判'}% · {lsr_text}",
        "lsr": lsr,
        "lsr_source": lsr_source,
        "haldro_flow": f"CVD {sub_cvd or '待判'} · 量能 {volume_ratio or '待判'}",
        "haldro_quality": f"覆盖 {coverage or '待判'} · 质量 {quality or '待判'}{_oi_metrics_txt} · 风险 {risk_text}" + feed_tail,
        "haldro_confirm": f"Confirm {confirm or '待判'}",
        "direction_verdict": "副单源，不参与协同" if valid_code <= 0 and feed.get("single") else "副指标无效，不参与裁决" if valid_code <= 0 else "主副强冲突" if (raw_conflict and valid_code >= 2) else "副S3冲突·CVD/OI背离" if haldro_s3 else "单源冲突，仅等待" if conflict else "同向但拥挤降级" if aligned and crowding_risk else "主副同向" if aligned else "副指标不足",
        "structure_verdict": "结构顺向" if aligned else "结构需确认",
        "flow_verdict": "订单流冲突，不追" if conflict else f"订单流风险：{risk_text}" if flow_risk or crowding_risk else "订单流支持" if aligned else "等CVD/OI确认",
        "quality_verdict": f"副指标降级：{risk_text}" if risk_labels else "质量已读",
        "state": downgraded_state,
        "conflict": conflict,
        "hard_conflict": hard_conflict,
        "s3_conflict": haldro_s3,
        "aligned": aligned and valid_code >= 1,
        "valid_code": valid_code,
        "risk_code": risk_code,
        "usable": valid_code >= 1 and bool(tv_sub or composite is not None or confirm is not None),
    })
    _register_source_record(
        engine_data,
        "haldro",
        dual,
        status="live" if dual.get("usable") else "unavailable",
        captured_at=datetime.now(TZ) if dual.get("usable") else None,
        symbol=symbol,
    )

    engine_data["_dual_indicator_verdict"] = dual
    return dual


def _project_final_verdict(main: dict, final: dict) -> dict:
    """把唯一FinalVerdict投影到现有渲染字段，禁止原始A级订单绕过闸门。"""
    projected = dict(main or {})
    projected["_final_verdict"] = dict(final or {})
    projected["grade"] = final.get("grade") or projected.get("grade") or "C等待"
    side = final.get("side")
    projected["direction_text"] = "偏多" if side == "long" else "偏空" if side == "short" else "观望"
    projected["treatment"] = final.get("reason") or projected.get("treatment") or ""
    if final.get("executable"):
        projected["entry"] = final.get("entry")
        projected["stop"] = final.get("stop")
        projected["target"] = final.get("target")
    else:
        projected.pop("entry", None)
        projected.pop("stop", None)
        projected.pop("target", None)
        projected["execution"] = "不执行·" + str(final.get("state") or "WAIT")
    return projected


def _decision_float(value, default: float = 0.0) -> float:
    """把TV/卡片数值安全转成float；等待文案、破折号和空值一律降级为默认值。"""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace(",", "").replace("−", "-").replace("%", "")
    if not text or text in {"—", "--", "N/A", "None", "null", "待确认", "等触发"}:
        return default
    multiplier = 1.0
    suffix = text[-1:].upper()
    if suffix in {"K", "M", "B"}:
        multiplier = {"K": 1e3, "M": 1e6, "B": 1e9}[suffix]
        text = text[:-1].strip()
    try:
        return float(text) * multiplier
    except (TypeError, ValueError):
        return default


def _tv_vwap_ema_fallback(symbol: str) -> dict:
    """Build the VWAP/EMA engine contract from fresh TV MCP Data Window fields."""
    path = _tv_symbol_cache_path(symbol)
    if not path.exists():
        return {}
    try:
        cache = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not _tv_cache_status(cache, symbol, max_age_minutes=30).get("usable"):
        return {}
    indicators = cache.get("indicators") if isinstance(cache.get("indicators"), dict) else {}
    vwap = _decision_float(indicators.get("s_vwap"))
    ema9 = _decision_float(indicators.get("ema_9"))
    ema55 = _decision_float(indicators.get("ema_55"))
    price = _decision_float(cache.get("last_price"))
    if not price:
        snapshot_path = DATA / f"source_snapshot_{str(symbol).upper()}.json"
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
            prices = snapshot.get("prices") if isinstance(snapshot.get("prices"), dict) else {}
            price = _decision_float(prices.get("primary"))
        except (OSError, json.JSONDecodeError):
            price = 0.0
    if not (vwap and ema9 and ema55):
        return {}
    return {
        "source": "TV MCP Data Window",
        "ema": {"9": ema9, "55": ema55},
        "vwap": {"value": vwap, "price_above": bool(price and price > vwap)},
        "cvd": _decision_float(indicators.get("mcp_cvd_value") or indicators.get("cumulative_delta")),
    }


def _apply_matrix_guard(final: dict, tv_main: dict) -> dict:
    """副指标只可否决/降权 —— 裁决落定后的最后一次保守化。

    铁律：副指标永远不能把非 A 变成 A；它在主 A 上只能「否决」或「降权」。
    宁可把可执行降成人工候选，也不放行一个副指标反对的单子。
    这是 fail-closed 方向的单向调整，任何情况下都不升级。
    """
    if not isinstance(final, dict):
        return final
    out = dict(final)
    syn = (tv_main or {}).get("synthesis")
    if not isinstance(syn, dict) or not syn.get("verdict"):
        return out
    verdict = str(syn.get("verdict"))
    # 始终把矩阵结论挂上，供卡片解释「为什么」
    out["matrix_verdict"] = verdict
    out["matrix_reason"] = str(syn.get("reason") or "")
    out["matrix_sub_role"] = str(syn.get("sub_role") or "")
    is_go_a = str(out.get("state") or "").upper() == "GO-A" and out.get("executable") is True
    if not is_go_a:
        return out            # 本就不是可执行，只做标注，不动它
    if verdict == "不执行·副冲突":
        out.update({
            "state": "NO-GO", "executable": False,
            "entry": None, "stop": None, "target": None,
            "grade": "C等待",
            "reason": f"副指标否决：{syn.get('reason', '')}",
            "matrix_downgraded": "hard_block",
        })
    elif verdict == "A降级候选":
        g = str(out.get("grade") or "")
        out.update({
            "state": "WAIT", "executable": False,
            "entry": None, "stop": None, "target": None,
            # 降为 B 档 = 人工观察候选：卡片会给触发条件与候选价，不给执行指令
            "grade": "B多" if g.startswith("A多") else "B空" if g.startswith("A空") else "C等待",
            "reason": f"副指标降权：{syn.get('reason', '')}",
            "matrix_downgraded": "degrade",
        })
    return out


def _resolve_card_final_verdict(symbol: str, meta: dict, engine_data: dict,
                                tv_main: dict, dual: dict, st_primary: dict,
                                model_id: str) -> dict:
    """用真实闭柱特征、HALDRO和风控宪法生成卡片唯一裁决。"""
    cached = engine_data.get("_final_verdict")
    if engine_data.get("_final_verdict_locked") is True and isinstance(cached, dict):
        return dict(cached)
    from decision_loop import resolve_final_verdict
    from decision_regime import classify_decision_regime
    from feature_builder import build_regime_features, ohlcv_from_binance_klines
    from risk_constitution_v2 import evaluate_risk

    fk = engine_data.get("futures_klines") or {}
    ohlcv = None
    if isinstance(fk, dict) and fk.get("closes"):
        ohlcv = fk
    elif isinstance(fk, dict):
        for key in ("15m", "5m", "1h"):
            candidate = fk.get(key)
            if isinstance(candidate, dict) and candidate.get("closes"):
                ohlcv = candidate
                break
        if ohlcv is None:
            candidates = [v for v in fk.values() if isinstance(v, dict) and v.get("closes")]
            if candidates:
                ohlcv = max(candidates, key=lambda value: len(value.get("closes") or []))
    if ohlcv is None:
        raw_multi = engine_data.get("_raw_klines_multi") or {}
        if isinstance(raw_multi, dict):
            for key in ("15m", "5m", "1h", "4h"):
                raw_rows = raw_multi.get(key)
                if isinstance(raw_rows, list) and len(raw_rows) >= 51:
                    parsed = ohlcv_from_binance_klines(raw_rows, drop_open_bar=True)
                    if len(parsed.get("closes") or []) >= 50:
                        ohlcv = parsed
                        engine_data["_decision_ohlcv_source"] = f"binance:{key}:closed"
                        break

    regime = None
    features = build_regime_features(ohlcv, tv_main) if isinstance(ohlcv, dict) else None
    if features:
        regime = classify_decision_regime(
            adx=float(features["adx"] or 0),
            atr_ratio=float(features["atr_ratio"] or 1),
            ema_spread_atr=float(features["ema_spread_atr"] or 0),
            vwap_crosses_20=int(features["vwap_crosses_20"] or 0),
            va_stay_ratio_20=float(features["va_stay_ratio_20"] or 0),
            displacement_atr=float(features["displacement_atr"] or 0),
            rvol=float(features["rvol"] or 0),
            adr_remaining_ratio=features.get("adr_remaining_ratio"),
            vwap_distance_atr=features.get("vwap_distance_atr"),
        )
        engine_data["_decision_features"] = features
        engine_data["_decision_regime"] = {
            "code": regime.code, "name": regime.name,
            "allowed_models": list(regime.allowed_models),
            "blocked_models": list(regime.blocked_models),
            "position_multiplier": regime.position_multiplier,
            "exhausted": regime.exhausted, "reason": regime.reason,
        }

    candidate = dict(tv_main or {})
    numeric_entry = _decision_float(candidate.get("entry"))
    if numeric_entry <= 0:
        numeric_entry = _decision_float(engine_data.get("prices", {}).get("primary") or meta.get("entry_price"))
    numeric_stop = _decision_float(candidate.get("stop"))
    if numeric_stop <= 0:
        numeric_stop = _decision_float(st_primary.get("stop"))
    numeric_target = _decision_float(candidate.get("target"))
    if numeric_target <= 0:
        numeric_target = _decision_float(st_primary.get("target"))
    numeric_rr = _decision_float(candidate.get("rr"))
    if numeric_rr <= 0:
        numeric_rr = _decision_float(st_primary.get("rr") or meta.get("rr_a") or meta.get("rr1"))
    candidate.update({
        "grade": meta.get("status") or candidate.get("grade") or "C等待",
        "direction": meta.get("direction") or candidate.get("direction_text") or "",
        "model_id": model_id,
        "entry": numeric_entry or None,
        "stop": numeric_stop or None,
        "target": numeric_target or None,
        "rr": numeric_rr,
        "data_grade": meta.get("data_grade") or candidate.get("data_grade") or engine_data.get("quality", "C"),
    })

    # Carry the data-boundary freshness decision into FinalVerdict.  A cache
    # can contain a perfectly parseable action grid while still being stale;
    # parseability is not proof of live TV confirmation.
    tv_status = engine_data.get("_tv_live_status") or engine_data.get("_tv_cache_status")
    if isinstance(tv_status, dict) and "usable" in tv_status:
        candidate["tv_live_verified"] = tv_status.get("usable") is True
    elif "_tv_direct_verified" in engine_data:
        candidate["tv_live_verified"] = engine_data.get("_tv_direct_verified") is True
    snapshot_status = engine_data.get("_snapshot_status")
    if isinstance(snapshot_status, dict) and snapshot_status.get("age_hours") is not None:
        candidate["snapshot_age_sec"] = max(0.0, float(snapshot_status.get("age_hours") or 0.0) * 3600.0)
    if engine_data.get("_tv_five_tf_required"):
        five_tf_status = engine_data.get("_tv_five_tf_status") or {}
        candidate["tv_five_tf_required"] = True
        candidate["tv_five_tf_verified"] = bool(
            isinstance(five_tf_status, dict) and five_tf_status.get("usable") is True
        )
    cross_validation = engine_data.get("_cross_validation")
    if isinstance(cross_validation, dict):
        candidate["cross_validation"] = cross_validation
        candidate["cross_source_hard_blockers"] = list(cross_validation.get("hard_blockers") or [])
        candidate["cross_source_warnings"] = list(cross_validation.get("warnings") or [])

    route_candidates = engine_data.get("_candidate_plans")
    if regime is not None and isinstance(route_candidates, list) and route_candidates:
        from model_router import select_primary_model
        route = select_primary_model(route_candidates, regime)
        if route:
            for key in ("model_id", "entry", "stop", "target", "rr", "quality"):
                if route.get(key) not in (None, ""):
                    candidate[key] = route[key]
            model_id = str(candidate.get("model_id") or model_id)
            engine_data["_model_route"] = route

    _bind_main_evidence(symbol, candidate)
    engine_data["_evidence_status"] = {
        "usable": all(candidate.get(k) is True for k in ("location_valid", "trigger_confirmed", "bar_closed")),
        "errors": list(candidate["evidence_errors"]),
        "reason": "SVP证据已验证" if not candidate["evidence_errors"] else "SVP执行证据缺失/无效：" + ",".join(candidate["evidence_errors"]),
    }
    entry = _decision_float(candidate.get("entry"))
    atr = _decision_float(st_primary.get("atr") or (features or {}).get("atr"))
    risk = evaluate_risk({
        "symbol": symbol,
        "account_balance": _decision_float(engine_data.get("account_balance") or engine_data.get("balance"), 100.0),
        "entry_price": entry,
        "stop_price": _decision_float(candidate.get("stop")),
        "target_price": _decision_float(candidate.get("target")),
        "atr": atr,
        "atr_pct": atr / entry if entry > 0 else 0,
        "regime_multiplier": regime.position_multiplier if regime else 1.5,
        "current_drawdown_pct": _decision_float(engine_data.get("_current_drawdown_pct")),
        "has_major_news": bool(engine_data.get("_banned_live")),
        "volatility_24h_pct": _decision_float(engine_data.get("_volatility_24h_pct")),
        "current_bar": int(_decision_float(engine_data.get("_current_bar"))),
        "total_exposure_pct": _decision_float(engine_data.get("_total_exposure_pct")),
        "corr_high": bool(engine_data.get("_corr_high")),
    })
    engine_data["_risk_v2"] = risk
    from copy import deepcopy
    from dataclasses import asdict
    engine_data["_decision_snapshot"] = deepcopy({
        "schema_version": 20260905, "symbol": symbol, "main": candidate,
        "dual": dual, "regime": asdict(regime) if regime else None,
        "risk": risk, "advanced": engine_data.get("_advanced"),
        "chart_evidence": engine_data.get("_chart_evidence") or
            (engine_data.get("_tv_cache") or {}).get("chart_evidence"),
    })
    chart_evidence = engine_data.get("_chart_evidence")
    if chart_evidence is None and isinstance(engine_data.get("_tv_cache"), dict):
        chart_evidence = engine_data["_tv_cache"].get("chart_evidence")
    final = resolve_final_verdict(
        symbol,
        candidate,
        dual,
        regime=regime,
        risk=risk,
        advanced=engine_data.get("_advanced"),
        chart_evidence=chart_evidence,
    ).to_dict()
    engine_data["_final_verdict"] = final
    engine_data["_final_verdict_locked"] = True
    if engine_data.get("_shadow_enabled"):
        from shadow_calibration import append_shadow_signal, order_model_for_plan
        interval_ms = 900_000 if str(symbol).upper().endswith("USDT") else 300_000
        ts_ms = int(engine_data.get("_snapshot_ts") or time.time() * 1000)
        signal_id = f"{symbol}:{model_id}:{ts_ms // interval_ms}"
        watch_entry = final.get("watch_entry") or candidate.get("entry")
        shadow_entry = _decision_float(watch_entry)
        shadow_stop = _decision_float(candidate.get("stop"))
        shadow_target = _decision_float(candidate.get("target"))
        if shadow_entry > 0 and shadow_stop > 0 and shadow_target > 0:
            frozen = engine_data["_decision_snapshot"]
            main_snapshot = deepcopy(frozen["main"])
            dual_snapshot = deepcopy(frozen["dual"])
            regime_snapshot = deepcopy(frozen["regime"])
            risk_snapshot = deepcopy(frozen["risk"])
            append_shadow_signal(
                engine_data.get("_shadow_path") or DATA / "shadow" / "decision_signals.jsonl",
                {
                    "signal_id": signal_id, "symbol": symbol,
                    "schema_version": frozen["schema_version"],
                    "final_verdict": deepcopy(final),
                    "timeframe": "15m" if str(symbol).upper().endswith("USDT") else "5m",
                    "ts": ts_ms, "side": final.get("watch_side") or candidate.get("direction"),
                    "entry": shadow_entry, "stop": shadow_stop,
                    "target": shadow_target, "model_id": final.get("model_id"),
                    # 2026-09-13：按计划语义写入执行订单模型（闭校准环）。
                    "order_model": order_model_for_plan(final.get("model_id") or main_snapshot.get("model_id")),
                    "regime_code": regime.code if regime else "unknown", "grade": candidate.get("grade"),
                    "fvg_quality": candidate.get("mcp_fvg_quality_score"),
                    "ob_quality": candidate.get("mcp_ob_quality_score"),
                    "haldro_valid_code": dual.get("valid_code"),
                    "haldro_risk_code": dual.get("risk_code"),
                    "final_state": final.get("state"), "blockers": final.get("blockers"),
                    "main": main_snapshot, "dual": dual_snapshot,
                    "regime": regime_snapshot, "risk": risk_snapshot,
                    "advanced": dict(engine_data.get("_advanced") or {}),
                    "features": features,
                },
            )
    return final


def _unknown_tv_text(value) -> bool:
    s = str(value or "").strip()
    return s in ("", "?", "—", "--", "None", "nan")


# 8/31 事故教训硬编码：行动格结论/处理行含这些语义 → 整卡 C级等待，禁止改写为 A/B。
# 注意区分：B等待（方向明确·等触发）≠ C等待（观望/未收线/方向不明）。
# 词表只覆盖 C 语义，不含"等待"本身；⚠ 必须带后续词（如 ⚠未收线），避免误伤
# B等待处理行的 ⚠ 前缀（如 "⚠ 等5m反抽VWAP确认"）。
_C_WAIT_SEMANTICS = ("观望", "未收线", "等解除", "等收线", "⚠冲突", "⚠未收线", "等待方向", "待确认方向", "C等待")


def _conclusion_forces_c_wait(conc: object) -> bool:
    """结论/处理行含 C级等待语义 → True。用于等级兜底前拦截 MCP 数字升A/B。"""
    if not conc:
        return False
    c = str(conc)
    return any(w in c for w in _C_WAIT_SEMANTICS)


def _grade_from_mcp_values(tv_vals: dict | None) -> str:
    """用 MCP Data Window 的 Side/Grade Code 兜底恢复 SVP 等级。"""
    if not isinstance(tv_vals, dict):
        return ""
    if "MCP Side Code" not in tv_vals or "MCP Grade Code" not in tv_vals:
        return ""
    try:
        side = int(float(str(tv_vals.get("MCP Side Code", 0)).replace("−", "-")))
        grade_code = int(float(str(tv_vals.get("MCP Grade Code", 0)).replace("−", "-")))
        if side == 9 or grade_code < 0:
            return "X"
        if side == 1:
            return "A多" if grade_code == 3 else "B多" if grade_code == 2 else "C反多" if grade_code == 1 else "C等待"
        if side == -1:
            return "A空" if grade_code == 3 else "B空" if grade_code == 2 else "C反空" if grade_code == 1 else "C等待"
        return "C等待"
    except (TypeError, ValueError):
        return ""


def _tv_main_from_dmi(pine: dict, price: float = 0, symbol: str = "") -> dict:
    """Production action-grid parser with main-only source evidence attached."""
    from copy import deepcopy
    from tv_data_bridge import _read_evidence
    main = _build_tv_main_data(_parse_tv_dmi_table(pine.get("tables")),
                               _parse_tv_study_values(pine.get("studies")), price,
                               symbol=symbol or str(pine.get("symbol") or ""))
    evidence = _read_evidence(pine) or pine.get("_evidence") or {}
    main.update(deepcopy(evidence))
    main["_evidence_context"] = deepcopy(pine.get("_evidence_context") or {})
    return main


def _bind_main_evidence(symbol: str, candidate: dict) -> None:
    """Validate source contract; grade/geometry never supplies evidence flags."""
    from source_health import parse_timestamp
    context = candidate.get("_evidence_context") or {}
    problems = []
    if candidate.get("mcp_evidence_version") != 20260905:
        problems.append("version")
    side = str(candidate.get("direction") or "").lower()
    direction = 1 if side in ("long", "多", "偏多") else -1 if side in ("short", "空", "偏空") else 0
    if not direction or candidate.get("mcp_evidence_direction") != direction:
        problems.append("direction")
    source_symbol = candidate.get("mcp_evidence_symbol")
    requested_symbol = str(symbol).upper()
    # Explicit exchange/product tokens must match exactly. Legacy bare aliases
    # retain their existing product-agnostic lookup, without rewriting the input.
    source_matches_request = isinstance(source_symbol, str) and (
        source_symbol.upper() == requested_symbol if ":" in requested_symbol
        else source_symbol.upper().split(":")[-1] == requested_symbol
        or (not requested_symbol.endswith(".P") and
            source_symbol.upper().split(":")[-1].removesuffix(".P") == requested_symbol)
    )
    if (not isinstance(source_symbol, str) or source_symbol != context.get("symbol")
            or not source_matches_request):
        problems.append("symbol")
    tf = str(candidate.get("mcp_evidence_timeframe") or "")
    context_tf = str(context.get("timeframe") or "")
    aliases = {"5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D", "1D": "D"}
    if not tf or tf != aliases.get(context_tf, context_tf):
        problems.append("timeframe")
    seconds = int(tf) * 60 if tf.isdigit() else {"D": 86400, "1D": 86400}.get(tf, 0)
    if not candidate.get("mcp_evidence_study_id"):
        problems.append("study_id")
    bar = parse_timestamp(candidate.get("mcp_evidence_bar_time"))
    close = parse_timestamp(candidate.get("mcp_evidence_close_time"))
    captured = parse_timestamp(context.get("captured_at"))
    now = time.time()
    if (not bar or not close or not captured or not seconds
            or (close - bar).total_seconds() != seconds
            or not 0 <= captured.timestamp() - close.timestamp() <= seconds
            or not 0 <= now - captured.timestamp() <= 900):
        problems.append("source_time")
    candidate["evidence_errors"] = problems
    for target, source in (("location_valid", "mcp_location_valid"),
                           ("trigger_confirmed", "mcp_trigger_confirmed"),
                           ("bar_closed", "mcp_bar_closed")):
        candidate[target] = not problems and candidate.get(source) is True
    if captured:
        candidate["snapshot_age_sec"] = max(0.0, now - captured.timestamp())


def _is_crypto_symbol(symbol: str) -> bool:
    """该品种是否加密（决定副指标是否有否决权）。

    未知/空 → True（保守：宁可让副指标参与降权，也不放行一个没被确认的单子）。
    """
    s = str(symbol or "").strip().upper()
    if not s:
        return True
    try:
        return _asset_class(s) == "crypto"
    except Exception:
        return True


def _build_tv_main_data(dmi_rows: dict, tv_vals: dict, price: float = 0,
                        symbol: str = "") -> dict:
    """从TV DMI表+study values构建主指标完整数据字典，供render_tv_card使用。

    symbol 用于判定 is_crypto：副指标（AggVol）的否决/降权只对加密有意义，
    套到 XAU/外汇/股票上违反多市场边界合同。未知品种按加密处理（更保守）。
    """
    main = {}
    dmi_rows = dmi_rows or {}
    tv_vals = tv_vals or {}

    if dmi_rows:
        # v2 行动格：grade 从"等级"行取，无则从"结论"行前缀提取（A多/A空/B多/B空/C反多/C反空）。
        # 注意：缓存偶发 grade='?'，这不是有效等级，必须允许 MCP Data Window 兜底。
        grade_raw = dmi_rows.get("等级", "")
        if _unknown_tv_text(grade_raw):
            conc = dmi_rows.get("结论", "")
            grade_raw = ""
            for prefix in ("A多", "A空", "B多", "B空", "C反多", "C反空", "C等待", "X"):
                if str(conc).startswith(prefix):
                    grade_raw = prefix
                    break
        main["grade"] = grade_raw or ""
        treatment = dmi_rows.get("处理")
        if _unknown_tv_text(treatment):
            treatment = dmi_rows.get("结论", "")
        main["treatment"] = treatment or ""
        main["background"] = dmi_rows.get("背景", "")
        main["position"] = dmi_rows.get("位置", "")
        main["cvd_state"] = dmi_rows.get("CVD", "")
        main["volume_state"] = dmi_rows.get("量能", "")
        main["execution"] = dmi_rows.get("执行", "")
        # v13：「风控」行标签是动态的（风控/风控·观察/风控·未授权/禁做·不出价），
        # 用 risk_row_value 取，避免只认字面「风控」而在观察态漏读。
        main["risk"] = TVC.risk_row_value(dmi_rows)
        main["risk_label"] = TVC.risk_row_label(dmi_rows)
        # v13 新增行：这几行是决策主信息，旧版根本没有对应字段。
        for _src, _dst in [("路径", "path"), ("协同", "sync"), ("结构", "structure"),
                           ("OI", "oi_state"), ("前位", "prev_level"), ("现位", "now_level")]:
            if dmi_rows.get(_src):
                main[_dst] = dmi_rows[_src]
        # 定版把 入场/止损/目标 折进「风控」行给人看；执行三件套只认后面的 MCP DW 导出。
        # 「风控·观察」的解析价只进 candidate_*，不能当 Entry。
        _risk = TVC.parse_risk_row(main["risk"])
        if main["risk_label"] == TVC.SVP_OBSERVATION_LABEL:
            for key in ("entry", "stop", "target", "rr"):
                main["candidate_" + key] = _risk.get(key)
            main["candidate_source"] = "SVP风控·观察"
        if _risk.get("stop_atr") is not None:
            main["stop_atr"] = _risk["stop_atr"]
        if _risk.get("rr") is not None:
            main["rr_ratio"] = _risk["rr"]
        # 现行行：方向/磁吸/结论。进场/止损/目标/核对只兼容历史缓存，不得覆盖风控解析。
        for src_key, dst_key in [
            ("方向", "direction_text"), ("磁吸↑", "magnet_up"),
            ("磁吸↓", "magnet_down"), ("结论", "conclusion"),
        ]:
            if dmi_rows.get(src_key):
                main[dst_key] = dmi_rows[src_key]
        for src_key, dst_key in [
            ("进场", "entry"), ("止损", "stop"), ("目标", "target"), ("核对", "check"),
        ]:
            if dmi_rows.get(src_key) and not main.get(dst_key):
                main[dst_key] = dmi_rows[src_key]

    if tv_vals:
        # 短名映射：卡片与下游一直用这些稳定键名，保留。
        # 旧实现里还混着一批**已废止的 DW 名**（MCP CVD Value / MCP EMA Length * /
        # MCP Risk Pack / MCP Bull·Bear FVG CE / OI Total / Estimated CVD Value /
        # 旧 MCP StructPack 长名 / 旧 CVD Method Code 短名…）——它们恒空，
        # 只会掩盖真正的接口漂移。删掉；DW 字段一律以 tv_indicator_contract 为准，
        # 漂移由 scripts/tv_indicator_alignment_check.py 拦截。
        for tv_key, dict_key in [
            ("S VWAP", "vwap"), ("VAH Price", "vah"), ("VAL Price", "val"),
            ("POC Price", "poc"), ("CVD Value", "cvd_value"),
            ("EMA 9", "ema9"), ("EMA 21", "ema21"), ("EMA 34", "ema34"), ("EMA 55", "ema55"),
        ]:
            if tv_key in tv_vals:
                main[dict_key] = tv_vals[tv_key]
        # Consume the canonical names, not a second drifting whitelist.
        for key, title in TVC.DW_ALIASES_MAIN.items():
            if title in tv_vals:
                main[key] = tv_vals[title]
        for key, title in TVC.DW_ALIASES_SUB.items():
            if title in tv_vals:
                main["sub_" + key] = tv_vals[title]
        # 已废止但历史缓存/老读数仍可能带的旧名：只从契约的 LEGACY 表取，
        # canonical 优先（setdefault 不覆盖上面已写入的正式字段）。
        for key, title in TVC.LEGACY_DW_ALIASES_MAIN.items():
            if title in tv_vals:
                main.setdefault(key, tv_vals[title])
        for key, title in TVC.LEGACY_DW_ALIASES_SUB.items():
            if title in tv_vals:
                main.setdefault("sub_" + key, tv_vals[title])
        if _unknown_tv_text(main.get("grade")):
            # P0-2 (2026-08-31): 结论行含 C级等待语义（观望/未收线/等解除等）
            # → 强制 C等待，禁止 MCP 数字兜底把"未收线/观望"改写为 A/B（8/31事故根因）。
            if _conclusion_forces_c_wait(main.get("conclusion") or main.get("treatment")):
                main["grade"] = "C等待"
            else:
                mcp_grade = _grade_from_mcp_values(tv_vals)
                if mcp_grade:
                    main["grade"] = mcp_grade
    # New four-state panel prices are NOT execution exports. Never mix a
    # rounded table price with a partial DW tuple or a historical legacy row.
    if main.get("risk_label"):
        for key in ("entry", "stop", "target"):
            main.pop(key, None)
        main["price_source"] = "none"
        if main["risk_label"] == "风控":
            prices = [_decision_float(main.get("mcp_" + key + "_price"))
                      for key in ("entry", "stop", "target")]
            if all(__import__("math").isfinite(v) and v > 0 for v in prices):
                main.update(dict(zip(("entry", "stop", "target"), prices)))
                main["price_source"] = "SVP执行导出"
            else:
                main["price_contract_error"] = "SVP执行三件套缺失"
        else:
            for key in ("mcp_entry_price", "mcp_stop_price", "mcp_target_price"):
                main.pop(key, None)
    # ── v13 解码层：把机器可读的闸门码翻成人能读的原因链 ──
    # 这三行是「为什么现在不能做」的唯一权威答案，面板文字是摘要，这里给全量。
    main["no_trade_reasons"] = TVC.format_no_trade(main.get("mcp_no_trade_reason_code"))
    main["entry_valid_text"] = TVC.decode_entry_valid(main.get("mcp_entry_valid_code"))
    main["rr_gate_text"] = TVC.rr_gate(main.get("mcp_rr_ratio") or main.get("rr_ratio"))
    main["haldro_state_text"] = TVC.decode_haldro_state(main.get("sub_haldro_state_pack"))
    # 解除条件清单：回答「现在是 A 禁，那我在等什么」。位序 + 可验证动作。
    main["release_plan"] = DM.release_plan(main.get("mcp_no_trade_reason_code"))
    main["release_text"] = DM.format_release(main.get("mcp_no_trade_reason_code"))
    main["rr_tier"] = DM.rr_tier(main.get("mcp_rr_ratio") or main.get("rr_ratio"))
    # 主副合成裁决（九宫格）。grade 此时已定，可安全求值。
    main["_is_crypto"] = _is_crypto_symbol(symbol)
    main["synthesis"] = DM.synthesis_verdict(
        main_grade=main.get("grade"),
        haldro_state=main.get("sub_haldro_state_pack"),
        haldro_valid=main.get("sub_haldro_valid_code"),
        rr=main.get("mcp_rr_ratio") or main.get("rr_ratio"),
        is_crypto=main["_is_crypto"],
    )
    if _unknown_tv_text(main.get("grade")):
        main["grade"] = "C等待"
    return main


def _apply_tv_dmi_override(meta: dict, engine_data: dict, symbol: str,
                           dmi_rows: dict, tv_vals: dict) -> dict:
    """用 TV DMI 数据覆盖引擎的 bias/grade/status。返回变更标记。"""
    if not dmi_rows:
        return {"tv_active": False}
    grade = dmi_rows.get("等级", "")
    if _unknown_tv_text(grade):
        conc = dmi_rows.get("结论", "")
        grade = ""
        for prefix in ("A多", "A空", "B多", "B空", "C反多", "C反空", "C等待", "X"):
            if str(conc).startswith(prefix):
                grade = prefix
                break
        # P0-2 (2026-08-31): 前缀提取失败且结论含 C级等待语义 → 强制 C等待，
        # 禁止走 MCP 数值兜底把"观望/未收线/等解除"改写为 A/B（8/31事故根因）。
        if not grade and _conclusion_forces_c_wait(conc):
            grade = "C等待"
    if _unknown_tv_text(grade):
        grade = _grade_from_mcp_values(tv_vals) or "C等待"
    # P0-2 第二道闸门：等级行给了 A/B，但结论/处理行含硬 C等待语义 → 整卡降 C。
    # （8/31 事故：1h结论=观望·等解除 仍被硬给 A级做空）
    if grade.startswith(("A", "B")):
        wait_conc = dmi_rows.get("结论", "") or dmi_rows.get("处理", "")
        if _conclusion_forces_c_wait(wait_conc):
            grade = "C等待"
    treatment = dmi_rows.get("处理", "?")
    if _unknown_tv_text(treatment):
        treatment = dmi_rows.get("结论", "?")
    changes = {"tv_active": True, "tv_grade": grade, "tv_treatment": treatment,
               "tv_background": dmi_rows.get("背景", "?"), "tv_position": dmi_rows.get("位置", "?"),
               "tv_volume": dmi_rows.get("量能", "?"), "tv_cvd_state": dmi_rows.get("CVD", "?"),
               "tv_execution": dmi_rows.get("执行", "?"), "tv_risk": dmi_rows.get("风控", "?")}

    # Grade -> status mapping (TV authority overrides engine)
    # 2026-08-31 加固：统一去掉"做"字变体（A做多/A做空），兼容 Pine 格式漂移
    g_norm = grade.replace("做", "")
    if g_norm.startswith("A多"):
        meta["status"] = "A做多"
        meta["direction"] = "long"
        meta["priority_plan"] = "A"
    elif g_norm.startswith("A空"):
        meta["status"] = "A做空"
        meta["direction"] = "short"
        meta["priority_plan"] = "A"
    elif g_norm.startswith("B多"):
        meta["status"] = "B等待"
        meta["direction"] = "long"
        meta["priority_plan"] = "B"
    elif g_norm.startswith("B空"):
        meta["status"] = "B等待"
        meta["direction"] = "short"
        meta["priority_plan"] = "B"
    elif g_norm.startswith("B") or g_norm == "B等待":
        # B等待 无显式方向时从结论/方向行推断
        _hint = dmi_rows.get("结论", "") + dmi_rows.get("方向", "")
        meta["status"] = "B等待"
        meta["direction"] = "short" if "空" in _hint else "long" if "多" in _hint else "wait"
        meta["priority_plan"] = "B"
    elif g_norm.startswith("C反"):
        # C反多/C反空 is a directional observation, not an executable order.
        # The direction may live in the background row while the conclusion
        # only says "回踩"; include all authoritative text before falling back
        # to neutral.
        _hint = " ".join(
            str(dmi_rows.get(key, ""))
            for key in ("等级", "结论", "方向", "背景", "处理")
        )
        meta["status"] = "C反转"
        meta["direction"] = "short" if "空" in _hint else "long" if "多" in _hint else "wait"
        meta["priority_plan"] = "C"
    elif g_norm.startswith("X"):
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
    levels = _approved_monitor_levels(symbol)

    # ── 衍生数据推算 ──
    funding_rate = funding.get("rate_pct") or "N/A"
    oi_latest = oi_data.get("oi") or oi_data.get("value") or "N/A"
    oi_trend = _oi_trend(oi_data)
    taker_dir = taker_data.get("direction") or "N/A"
    taker_ratio = taker_data.get("ratio") or "N/A"
    # 2026-09-13：非加密 XAU 回退黄金合约 CVD（独立键 gold_contract_cvd；来源已标注）
    _gold_cvd_data = engine_data.get("gold_contract_cvd") if isinstance(engine_data.get("gold_contract_cvd"), dict) else {}
    cvd_dir = cvd_data.get("direction") or _gold_cvd_data.get("direction") or "N/A"
    cvd_quality_raw = cvd_data.get("quality") or _gold_cvd_data.get("quality") or "C"
    cvd_quality = cvd_quality_raw.replace("级", "") if isinstance(cvd_quality_raw, str) else str(cvd_quality_raw)
    # 数据等级降级：木桶原理——最弱一环决定
    data_grade = _effective_grade(data_grade, taker_data, engine_data)
    meta["data_grade"] = data_grade
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
        # 如果有 TV Pine table 数据，解析它（v9: 同时解析主/副双指标）
        tv_pine = engine_data.get("_tv_pine", {})
        if tv_pine:
            tables = tv_pine.get("tables")
            tv_dmi_rows = _parse_tv_dmi_table(tables)
            if tv_dmi_rows:
                tv_vals = _parse_tv_study_values(tv_pine.get("studies"))
                tv_override = _apply_tv_dmi_override(meta, engine_data, symbol, tv_dmi_rows, tv_vals)
                engine_data["_tv_override"] = tv_override  # 存储供 compact card 使用
                # 同步更新局部变量（TV DMI 可能覆盖了 status/direction）
                status = meta.get("status", status)
                direction = meta.get("direction", direction)
            # 用 TV 真实 CVD 覆盖 Binance Taker 代理
                if tv_vals.get("CVD Value") is not None:
                    cvd_data = _tv_cvd_override(cvd_data, tv_vals)
            # 解析副指标(Volume)行动格
            tv_sub_rows = _parse_tv_sub_table(tables)
            if tv_sub_rows:
                engine_data["_tv_sub"] = tv_sub_rows
            # 构建主指标完整数据
            engine_data["_tv_main"] = _tv_main_from_dmi(
                tv_pine, price, symbol=str(engine_data.get("symbol") or symbol or ""))
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
    # 2026-09-13：优先复用主流程回写的引擎结果（Step1 后处理失败兜底更全：
    # 原始K线→期货K线→TV MCP）。本地重算仅在无可复用结果时进行——修复
    # 「引擎已打印快线/慢线但卡面 VWAP/EMA 行空白」（XAU 场景无本地K线可用）。
    vwap_ema = {}
    _ve_reused = False
    _ve_existing = engine_data.get("_vwap_ema")
    if isinstance(_ve_existing, dict) and (_ve_existing.get("vwap") or _ve_existing.get("ema")):
        vwap_ema = _ve_existing
        _ve_reused = True
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
        if not _vwap_klines:
            # P1b: 从 _raw_klines_multi 原始 Binance OHLCV 重组（klines[tf] 无 bars 键时）
            _raw_multi = engine_data.get("_raw_klines_multi") or {}
            _raw_15m = _raw_multi.get("15m") or []
            if isinstance(_raw_15m, list) and _raw_15m:
                _vwap_klines = [
                    {"open": float(c[1]), "high": float(c[2]),
                     "low": float(c[3]), "close": float(c[4]), "volume": float(c[5])}
                    for c in _raw_15m if isinstance(c, (list, tuple)) and len(c) >= 6
                ]
        if not _vwap_klines:
            # P1b: Binance futures_klines 兜底（TV 实时 K线未注入时）
            _fk = engine_data.get("futures_klines") or {}
            _fk_src = None
            if isinstance(_fk, dict):
                _fk_src = max(_fk.values(),
                              key=lambda v: len(v.get("closes", []))
                              if isinstance(v, dict) else 0, default={})
            elif isinstance(_fk, list):
                _fk_src = _fk
            if isinstance(_fk_src, dict) and _fk_src.get("closes"):
                # 重组为 [{"open","high","low","close","volume"}, ...]
                _o = _fk_src.get("opens") or _fk_src.get("open") or []
                _h = _fk_src.get("highs") or _fk_src.get("high") or []
                _l = _fk_src.get("lows") or _fk_src.get("low") or []
                _c = _fk_src.get("closes") or _fk_src.get("close") or []
                _v = _fk_src.get("volumes") or _fk_src.get("volume") or []
                _n = min(len(_o), len(_h), len(_l), len(_c), len(_v) or len(_c))
                if _n > 0:
                    _vwap_klines = [
                        {"open": _o[i], "high": _h[i], "low": _l[i],
                         "close": _c[i], "volume": _v[i] if i < len(_v) else 0}
                        for i in range(_n)
                    ]
        if _vwap_klines and not _ve_reused:
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
    fg_v = fg.get("value") if (fg and fg.get("value") not in (None, "")) else "—"
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
    risk_backed = _risk_account_connected(engine_data)
    leverage_text = _leverage_text(symbol)
    prot_status = meta.get("protections_status", "未检测")
    bearish = (cvd_dir == "卖" or direction == "short")
    st_a = _calc_stop_target_atr(price, "short" if bearish else "long", klines, symbol)
    st_b = _calc_stop_target_atr(price, "long" if bearish else "short", klines, symbol)
    rr_a, rr_b = st_a["rr"], st_b["rr"]
    meta["rr_a"] = round(float(rr_a or 0), 3)
    meta["rr_b"] = round(float(rr_b or 0), 3)
    meta["rr1"] = meta["rr_a"]
    meta["rr2"] = meta["rr_b"]
    if not meta.get("invalid_price"):
        meta["invalid_price"] = st_a.get("stop")
    rr_a_note = "" if rr_a >= 2.0 else " ⚠R:R不足"
    rr_b_note = "" if rr_b >= 2.0 else " ⚠R:R不足"

    # ── v7.1 手机适配 组装（每行≤38字符）──
    display_symbol = _display_symbol(symbol)
    _r = _fmt_price
    # Strip backticks from _fmt_price output for mobile (we add our own)
    def _p(v):
        s = _r(v)
        return s.replace('`','') if s.startswith('`') else s
    card_lines = [
        f"◷ {now.strftime('%m-%d %H:%M')} · {display_symbol} · {data_grade}",
        "",
        f"① {status} · {model_id} · {n5}/13 · 置信{eng_conf}/5",
        f"   {one_reason}",
        "",
        f"② 现价 `{_p(price)}`",
        f"   高 `{_p(high)}` 低 `{_p(low)}` 日{float(chg or 0):+.2f}%",
        f"   {tf_lines}",
        "",
    ]

    # v8.0: 叙事模板渲染
    from render_v96 import render_v96_card
    monitor_levels = _approved_monitor_levels(symbol)
    all_levels_list = monitor_levels.get("levels", [])
    
    # v8.0 需要的上下文变量
    kill_zone = _kill_zone_name()
    sweep_state = _sweep_state(k5m, merged) or "待扫"
    displacement = "待判"
    
    # 关键位回退：从K线数据补充
    if not all_levels_list:
        for tf in ("4h", "1h", "15m"):
            k = klines.get(tf, {})
            # 2026-09-13：名字必须带空格分隔的周期前缀（"5m 高"）。
            # _LEVEL_TF_RE 的 \b 对「5m高」（中文紧邻）不匹配 → XAU（无 keylevels
            # 配置、走本回退）卡面只显示无周期的「阻/支」，等待条件无法具名。
            for side, name, key in [("resistance", f"{tf} VAH", "vah"), ("support", f"{tf} VAL", "val"),
                                      ("resistance", f"{tf} 高", "high"), ("support", f"{tf} 低", "low")]:
                v = k.get(key)
                if v:
                    try:
                        fv = float(v)
                        if fv > 0:
                            all_levels_list.append({"side": side, "display_name": name, "level": fv, "name": name})
                    except (TypeError, ValueError):
                        pass

    # 2026-09-13：DO Price（日开盘）接入（消费矩阵建议 6——展示性字段接入）。
    # 指标 DW「DO Price」自 v13 起导出但系统未消费；作为日内定价参考并入
    # 「VWAP/EMA」环境行（与结构位解耦——DO 不是结构位，不参与位表排序竞争）。
    try:
        _do_src = engine_data.get("_tv_main") or {}
        _do_price_v = float(str(_do_src.get("do_price")).replace("−", "-"))
    except (TypeError, ValueError):
        _do_price_v = 0.0

    dual_indicator = _dual_indicator_verdict(symbol, meta, engine_data, cvd_dir, cvd_quality)
    try:
        from cross_validation import build_source_matrix, evaluate_cross_validation
        source_matrix = build_source_matrix(
            symbol, engine_data, dual_indicator, pipeline_steps=engine_data.get("_pipeline_steps") or ()
        )
        # 2026-09-13：风险快照陈旧/缺失/损坏必须在来源矩阵可见，不让它冒充实时。
        # 只上报为 risk_context（告警级），不新增 FinalVerdict 硬拦截。
        try:
            from risk_constitution import load_risk_state, risk_state_status
            _risk_status = risk_state_status(load_risk_state())
            engine_data["_risk_state_status"] = _risk_status
            _state_map = {"fresh": "live", "stale": "stale_cache",
                          "missing": "unavailable", "invalid": "unavailable"}
            source_matrix.append({
                "id": "risk_state", "label": "风险快照", "requested": True,
                "role": "risk_context",
                "status": _state_map.get(str(_risk_status.get("status")), "unavailable"),
                "evidence": f"{_risk_status.get('source_date') or '无来源日期'}·{_risk_status.get('status')}",
                "impact": str(_risk_status.get("reason") or "")[:32],
                "entered_final_verdict": False,
            })
        except Exception:
            pass
        engine_data["_cross_validation_matrix"] = source_matrix
        engine_data["_cross_validation"] = evaluate_cross_validation(source_matrix)
    except Exception as _cve:
        engine_data["_cross_validation_matrix"] = []
        engine_data["_cross_validation"] = {
            "state": "blocked",
            "hard_blockers": ["cross_validation"],
            "warnings": [],
            "rows": [],
            "reason": f"来源矩阵不可用:{type(_cve).__name__}",
        }
    decision_main = dict(engine_data.get("_tv_main") or {})
    decision_main.setdefault("entry", price)
    decision_main.setdefault("stop", st_a.get("stop"))
    decision_main.setdefault("target", st_a.get("target"))
    # Production route candidates must come from the current run.  Previously
    # only tests supplied _candidate_plans, so model_router silently had no
    # effect in live cards.  Confidence remains display metadata; routing uses
    # explicit structural quality/strategy fields plus R:R.
    if not isinstance(engine_data.get("_candidate_plans"), list):
        route_aliases = {
            "VWAP反抽": "vwap_pullback",
            "VAH回收": "value_rotation",
            "VAL回收": "value_rotation",
            "POC拒绝": "poc_rejection",
            "扫流动性回收": "liquidity_sweep",
            "突破接受": "breakout_acceptance",
        }
        plans = []
        for result in results or []:
            source_name = str(result.get("name") or "")
            canonical = route_aliases.get(source_name)
            if not canonical:
                continue
            quality_key = "mcp_fvg_quality_score" if canonical == "fvg_pullback" else "mcp_ob_quality_score" if canonical == "ob_pullback" else "quality"
            quality = _decision_float(decision_main.get(quality_key) or result.get("quality") or result.get("setup_quality"))
            plans.append({
                "model_id": canonical,
                "entry": _decision_float(result.get("entry")) or _decision_float(decision_main.get("entry")),
                "stop": _decision_float(result.get("stop")) or _decision_float(decision_main.get("stop")),
                "target": _decision_float(result.get("target")) or _decision_float(decision_main.get("target")),
                "rr": _decision_float(result.get("rr") or result.get("rr_ratio")) or _decision_float(decision_main.get("rr")),
                "quality": quality,
                "signal_confidence": _decision_float(result.get("confidence")),
            })
        if plans:
            engine_data["_candidate_plans"] = plans
            engine_data["_candidate_plans_source"] = "current_run_results"
    engine_data.setdefault("_shadow_enabled", True)
    final_verdict = _resolve_card_final_verdict(
        symbol, meta, engine_data, decision_main, dual_indicator, st_a, model_id
    )
    # v13：副指标只可否决/降权 —— 落定后做最后一次保守化（只降不升）
    if isinstance(final_verdict, dict):
        guarded = _apply_matrix_guard(final_verdict, engine_data.get("_tv_main") or decision_main)
        if guarded.get("matrix_downgraded"):
            print(f"  🛡 裁决矩阵保守化：{final_verdict.get('state')} → {guarded.get('state')}"
                  f"（{guarded.get('matrix_verdict')}）")
        final_verdict = guarded
        engine_data["_final_verdict"] = guarded
    projected_main = _project_final_verdict(decision_main, final_verdict)
    projected_main["_decision_regime"] = engine_data.get("_decision_regime") or {}
    engine_data["_tv_main_final"] = projected_main
    # 渲染只消费FinalVerdict状态，禁止旧A/B/C/X等级与GO-B执行权互相打架。
    status = final_verdict.get("state") or final_verdict.get("grade") or status
    direction = final_verdict.get("side") or direction
    bearish = direction == "short"
    # 2026-09-13：XAU 黄金合约 CVD（Binance XAUUSDT）显式标记 → 渲染层保留显示
    if engine_data.get("_gold_contract_cvd"):
        dual_indicator["gold_contract_cvd"] = True
    dual_indicator["final_state"] = final_verdict.get("state")
    dual_indicator["state"] = final_verdict.get("grade") or dual_indicator.get("state")
    if dual_indicator.get("asset_is_crypto") and dual_indicator.get("usable"):
        sub_line = dual_indicator.get("haldro_flow") or dual_indicator.get("haldro_direction")
        comp_line = dual_indicator.get("haldro_direction")
        for tf in ("D", "4h", "1h", "15m", "5m"):
            k = klines.get(tf)
            if isinstance(k, dict):
                k.setdefault("sub_indicator", sub_line)
                k.setdefault("sub_composite", comp_line)

    # 2026-09-13：卡面时段标注（亚洲/伦敦/纽约/盘外；空值不显示）
    try:
        from session_strategy import get_session as _get_session
        _sess = engine_data.get("_session") if isinstance(engine_data.get("_session"), dict) else {}
        _sess_name = str(_sess.get("name") or _get_session().get("name") or "")
    except Exception:
        _sess_name = ""
    if _sess_name == "低波动":
        _sess_name = "盘外"
    full = render_v96_card(
        symbol=symbol, status=status, direction=direction, price=price,
        high=high, low=low, chg=chg, tf_lines=tf_lines,
        cvd_dir=cvd_dir, cvd_quality=cvd_quality,
        taker_dir=taker_dir, taker_ratio=taker_ratio,
        funding_rate=funding_rate, kill_zone=kill_zone,
        vwap_ema=vwap_ema, fg_v=fg_v,
        do_price=_do_price_v,
        levels=all_levels_list,
        bearish=bearish, st_a=st_a, st_b=st_b,
        rr_a=rr_a, rr_b=rr_b, rr_a_note=rr_a_note, rr_b_note=rr_b_note,
        risk_amt=risk_amt, risk_backed=risk_backed, leverage_text=leverage_text,
        inv_line=inv_line, prot_status=prot_status,
        data_grade=data_grade, sweep_state=sweep_state,
        displacement=displacement, one_reason=one_reason,
        model_id=model_id, n5=n5, eng_conf=eng_conf,
        klines=klines,
        tv_dmi=projected_main or tv_dmi_rows or {},
        dual_indicator=dual_indicator,
        final_verdict=final_verdict,
        source_matrix=engine_data.get("_cross_validation_matrix") or [],
        session_name=_sess_name,
    )
    
    # v9: TV双指标直出卡（优先：主+副指标数据齐全时使用）
    tv_main = engine_data.get("_tv_main", {})
    tv_main = _project_final_verdict(tv_main, final_verdict)
    if isinstance(engine_data.get("_chart_evidence"), dict):
        tv_main["chart_evidence"] = engine_data["_chart_evidence"]
        price_context = engine_data["_chart_evidence"].get("price_context")
        if isinstance(price_context, dict):
            tv_main.setdefault("high", price_context.get("day_high"))
            tv_main.setdefault("low", price_context.get("day_low"))
    tv_main["_decision_regime"] = engine_data.get("_decision_regime") or {}
    tv_sub = engine_data.get("_tv_sub", {})
    # AggVol is crypto-only. Non-crypto cards must not leak its estimated CVD,
    # OI or exchange coverage into a gold/FX/equity decision.
    if not force_full and _asset_class(symbol) == "crypto" and tv_main and tv_sub:
        try:
            import sys as _tv_sys
            _tv_sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            from render_tv_card import render_tv_card as _render_tv
            # v9.9: 快速卡也必须带五周期和双指标裁决，不能只消费单周期TV表。
            if isinstance(tv_main, dict):
                tv_main = dict(tv_main)
                tv_main.setdefault("_klines", klines)
                tv_main.setdefault("_dual", dual_indicator)
                tv_main["_source_matrix"] = engine_data.get("_cross_validation_matrix") or []
            tv_card = _render_tv(tv_main, tv_sub, symbol, price or 0, mode="push")
            if tv_card:
                return tv_card
        except Exception:
            pass

    # v9.6: 标准出卡统一使用表格驾驶舱；旧极简卡仅保留为告警专用，不再覆盖手动分析卡。
    if not force_full:
        return full

    return full


# ── v6.9 helper functions ──

def _asset_class(symbol: str) -> str:
    """Use the router's canonical asset taxonomy everywhere in the pipeline."""
    from pipeline_router import _asset_class as classify_asset
    return classify_asset(symbol)


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
    if ac == "futures":
        return f"{su} · CME"
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
        return "杠杆按账户风控·OANDA仅数据源"
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
        return f"CVD{cvd_dir or '待确认'}与Taker顺向·现货vs永续不分裂·突破接受须无背离"
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
    except (TypeError, ValueError, AttributeError): return ""

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
    except (TypeError, ValueError, KeyError):
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


def _register_source_record(
    engine_data: dict,
    source_id: str,
    value,
    *,
    status: str | None = None,
    captured_at=None,
    error=None,
    symbol: str | None = None,
    max_age_hours: float = 6.0,
) -> dict:
    """Register an optional source without changing legacy consumer fields."""
    from source_contract import get_source_contract, source_record
    from source_health import inspect_payload, payload_timestamp

    records = engine_data.setdefault("_source_records", {})
    if not isinstance(records, dict):
        records = {}
        engine_data["_source_records"] = records
    existing = get_source_contract(value)
    effective_status = status
    effective_capture = captured_at
    if existing is None and effective_status is None:
        if isinstance(value, dict) and payload_timestamp(value) is not None:
            health = inspect_payload(value, max_age_hours=max_age_hours, expected_symbol=symbol)
            effective_status = health.get("status") or "unavailable"
        else:
            has_payload = value not in (None, "", False, {}, [])
            effective_status = "live" if has_payload else "not_run"
            if has_payload:
                effective_capture = datetime.now(TZ)
    record = source_record(
        source_id,
        value,
        status=effective_status,
        captured_at=effective_capture,
        error=error,
        symbol=symbol,
    )
    records[source_id] = record
    return record


def _source_record_status(engine_data: dict, source_id: str, fallback=None) -> str:
    """Read a normalized source status, falling back to legacy payloads."""
    from source_contract import source_status

    records = engine_data.get("_source_records")
    if isinstance(records, dict) and source_id in records:
        return source_status(records[source_id])
    return source_status(fallback, default="not_run")


def _source_record_usable(engine_data: dict, source_id: str, fallback=None) -> bool:
    return _source_record_status(engine_data, source_id, fallback) in {"live", "cache", "inherited"}

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
    except (TypeError, ValueError, KeyError):
            pass

    # Confluence score (community multi-asset: Sweep + CVD + Kill + Displacement + SMT)
    conf = 0
    if "已扫" in sweep: conf += 3
    if "背离" in cvd_div or "吸收" in cvd_div: conf += 2
    if "Kill Zone" in kill_zone and is_xau: conf += 2
    if "主要交易时段" in kill_zone and not is_btc: conf += 1   # forex/stock boost
    if displacement == "强": conf += 1
    # P2修复：XAU 占位推算时降级（非TV现场读数，可信度降一级）
    if is_xau and engine_data.get("_xau_placeholder"):
        conf = max(0, conf - 2)
        kill_zone = f"{kill_zone} · ⚠️XAU占位推算"

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
    except (TypeError, ValueError, KeyError):
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
        return f"{k.get('resistance') or k.get('high') or '待确认'}"
    return f"{k.get('support') or k.get('low') or '待确认'}"

def _atr_15m(klines: dict) -> float:
    k15 = klines.get("15m") or {}
    return float(k15.get("atr") or 242)

def _chase_ok(dist: float, atr: float) -> str:
    if atr <= 0: return "—"
    return "不追空" if dist < 2 * atr else "可追"

def _trigger_5m(k: dict, merged: dict, model_id: str) -> str:
    return f"{model_id}形态未确认 — 需15m收线确认"

def _noise_5m(k: dict) -> str:
    vol = k.get("volume") or 0
    return "低量弱反弹 — 可能是空头回补而非真正买盘" if float(vol or 0) < 200 else "正常"

def _tf_verdict(tf: str, k: dict, merged: dict) -> str:
    """按时间框架返回动态判语（v7.5: 基于实际数据而非硬编码）。"""
    if not k or not isinstance(k, dict):
        return "数据不足"
    close = k.get("close") or k.get("price")
    high = k.get("high")
    low = k.get("low")
    ema21 = k.get("ema21")
    if not close:
        return "待刷新"
    parts = []
    if ema21 and close > ema21:
        parts.append(f"{tf}价上EMA21·偏多")
    elif ema21:
        parts.append(f"{tf}价下EMA21·偏空")
    bias_val = k.get("bias") or k.get("trend", "")
    if bias_val:
        parts.append(str(bias_val)[:6])
    return "·".join(parts) if parts else f"{tf}方向待判"

def _exec_line(klines: dict, merged: dict, status: str) -> str:
    k4h = klines.get("4h") or {}
    val = k4h.get("val") or k4h.get("value_val")
    return f"{val:,.0f}" if val else "待确认"

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


def _load_binance_keys() -> tuple[str, str]:
    """Load Binance API keys with environment-first, repo-relative fallback."""
    api_key = os.environ.get("BINANCE_API_KEY", "").strip()
    secret_key = os.environ.get("BINANCE_SECRET_KEY", "").strip()
    if api_key and secret_key:
        return api_key, secret_key
    try:
        secrets_path = ROOT / "hermes" / "secrets" / "binance.json"
        data = json.loads(secrets_path.read_text(encoding="utf-8"))
        return (
            api_key or str(data.get("api_key", "")).strip(),
            secret_key or str(data.get("secret_key", "")).strip(),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError):
        return api_key, secret_key


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


def _merge_collected_klines(engine_data: dict, incoming: dict, *, preserve_existing: bool = False) -> None:
    """合并外部K线；XAU的Binance回退不得覆盖TV MCP现场结构。"""
    existing = engine_data.get("klines")
    if not isinstance(existing, dict):
        existing = {}
        engine_data["klines"] = existing
    for tf, payload in (incoming or {}).items():
        if preserve_existing and tf in existing:
            continue
        existing[tf] = payload


def _load_tv_five_tf_snapshot(symbol: str, *, mode: str = "quick", context: dict | None = None) -> dict:
    """Load a validated TV five-timeframe snapshot for this analysis run.

    Direct cache data is limited to 30 minutes.  Standard/inherit may use the last
    symbol-matched full snapshot stored in the lightweight context for up to
    four hours, and that source remains labelled as inherited rather than
    pretending to be live.
    """
    from tv_five_tf_contract import (
        load_five_tf_snapshot,
        normalize_engine_klines,
        validate_five_tf_payload,
    )

    direct = load_five_tf_snapshot(symbol, data_dir=DATA, max_age_minutes=30.0)
    if direct.get("usable"):
        direct["scope"] = "direct_cache"
        direct["engine_klines"] = normalize_engine_klines(direct)
        return direct

    if mode in {"inherit", "standard"} and isinstance(context, dict) and isinstance(context.get("timeframes"), dict):
        inherited_payload = {
            "symbol": context.get("symbol") or symbol,
            "updated_at": context.get("updated_at"),
            "timeframes": context.get("timeframes"),
            "source": "inherited_context",
        }
        inherited = validate_five_tf_payload(
            inherited_payload,
            symbol,
            max_age_minutes=240.0,
        )
        if inherited.get("usable"):
            inherited["scope"] = "inherited_context"
            inherited["engine_klines"] = normalize_engine_klines(inherited)
            return inherited

    direct["scope"] = "unavailable"
    direct["engine_klines"] = {}
    return direct


ANALYSIS_OWNER_ENV = "TANGXI_ANALYSIS_OWNER"
ANALYSIS_LEASE_MINUTES = 15.0


def _analysis_owner_env() -> dict:
    """给「分析自己的」子采集带上所有者标记。

    外部后台（btc_tv_refresh / xau_tv_sync / cron）不会置这个变量，照旧让路；
    只有分析管线自己发起的采集会放行（2026-09-14 修租约自锁）。
    """
    env = os.environ.copy()
    env[ANALYSIS_OWNER_ENV] = "1"
    return env


def _begin_analysis_lease_if_idle(symbol: str, minutes: float = ANALYSIS_LEASE_MINUTES) -> bool:
    """分析管线自持租约：让外部后台续航让路，同时给自己的采集放行。

    已有人在分析（交互式租约在生效）时不覆盖、不接管，返回 False —— 谁声明谁 end，
    避免把别人的租约提前释放。返回 True 表示租约为本进程声明，收尾必须 end。
    """
    try:
        from tv_data_bridge import analysis_lease_status, begin_analysis_lease
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠ 分析租约不可用: {exc}")
        return False
    try:
        status = analysis_lease_status()
        if status.get("active"):
            print(f"  ℹ️ 已有分析租约生效（剩 {status.get('remaining_seconds')}s）→ 沿用，不覆盖")
            return False
        begin_analysis_lease(minutes, note="auto_card 分析管线", symbol=str(symbol or ""))
        print(f"  ✅ 分析租约已声明 {minutes:.0f} 分钟（后台续航让路；自有采集放行）")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠ 分析租约声明失败: {exc}")
        return False


def _end_analysis_lease_quiet() -> None:
    try:
        from tv_data_bridge import end_analysis_lease
        end_analysis_lease()
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠ 分析租约释放失败: {exc}")


def _refresh_btc_tv_five_tf_snapshot(symbol: str) -> bool:
    """Refresh the active BTC TV collector once when a full run lacks evidence."""
    raw = str(symbol or "").upper().split(":")[-1].replace(".P", "")
    if raw != "BTCUSDT":
        return False
    collector = ROOT / "scripts" / "keylevels_collect.py"
    if not collector.exists():
        return False
    try:
        result = subprocess.run(
            [sys.executable, str(collector)],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=420,
            env=_analysis_owner_env(),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "collector failed").strip()
            print(f"  ⚠ BTC TV五周期刷新失败: {detail[:180]}")
            return False
        from tv_five_tf_contract import load_five_tf_snapshot
        snapshot = load_five_tf_snapshot(symbol, data_dir=DATA, max_age_minutes=30.0)
        if not snapshot.get("usable"):
            print(f"  ⚠ BTC TV五周期刷新未落盘为可用证据: {snapshot.get('reason','校验失败')}")
            return False
        print(f"  ✅ BTC TV五周期现场采集完成·落盘覆盖{snapshot.get('coverage', 0)}/5")
        return True
    except subprocess.TimeoutExpired:
        print("  ⚠ BTC TV五周期现场采集超时420s")
    except OSError as exc:
        print(f"  ⚠ BTC TV五周期现场采集无法启动: {exc}")
    return False


def _merge_tv_five_tf_into_engine(engine_data: dict, snapshot: dict) -> None:
    """Merge validated TV structure into per-TF engine rows without losing OHLCV."""
    if not isinstance(engine_data, dict) or not isinstance(snapshot, dict) or not snapshot.get("usable"):
        return
    incoming = snapshot.get("engine_klines") or {}
    if not isinstance(incoming, dict):
        return
    if snapshot.get("scope") == "inherited_context":
        # Only the background may be inherited.  The two execution layers must
        # retain this run's collector data, never a four-hour-old close/bias.
        incoming = {tf: row for tf, row in incoming.items() if tf in {"D", "4h", "1h"}}
    existing = engine_data.setdefault("klines", {})
    if not isinstance(existing, dict):
        existing = {}
        engine_data["klines"] = existing
    for tf, tv_row in incoming.items():
        if not isinstance(tv_row, dict):
            continue
        merged = dict(existing.get(tf) or {})
        # TV owns the value-area/action-grid fields.  Preserve Binance OHLCV
        # when the collector only returned a close/price for that timeframe.
        for key, value in tv_row.items():
            if value in (None, "", "—", "--"):
                continue
            if key in {"open", "close", "price", "high", "low", "change_pct"} and not tv_row.get("tv_ohlcv_complete"):
                continue
            merged[key] = value
        existing[tf] = merged
    engine_data["_tv_five_tf_klines"] = incoming


def _apply_tv_live_structure(
    engine_data: dict,
    klines: dict,
    *,
    poc,
    vah,
    val,
    direction: str,
) -> bool:
    """Apply a single-period TV structure only when no valid five-TF snapshot exists."""
    from render_v96 import _num as _tv_num  # FX 价格精度：与卡片渲染同规则（2026-09-13）
    if engine_data.get("_tv_five_tf_klines"):
        return False
    if not isinstance(klines, dict) or not poc or not vah or not val:
        return False
    for tf in ["D", "4h", "1h", "15m", "5m"]:
        if tf == "D":
            klines[tf] = {
                "close": poc, "high": vah, "low": val,
                "open": poc, "change_pct": 0,
                "poc": poc, "vah": vah, "val": val,
                "direction": direction,
                "description": f"TV现场 POC {_tv_num(poc)} | VAH {_tv_num(vah)} VAL {_tv_num(val)} | {direction}",
            }
        elif tf in klines and isinstance(klines[tf], dict):
            row = klines[tf]
            row["poc"] = poc
            row["vah"] = vah
            row["val"] = val
            if "待" in str(row.get("description", "")):
                row["description"] = f"TV注入 POC{_tv_num(poc)} VAH{_tv_num(vah)} VAL{_tv_num(val)}"
    return True


def _inject_orion_derivatives_fallback(engine_data: dict, symbol: str) -> None:
    """Fill missing derivatives fields from Orion's Binance feed at quality B."""
    try:
        from binance_public import orion_derivatives_snapshot
        snap = orion_derivatives_snapshot(symbol)
    except Exception:
        return
    if not snap.get("ok"):
        return
    source = str(snap.get("source") or "Orion/Binance Futures")
    if not engine_data.get("funding"):
        raw_rate = float(snap.get("funding") or 0)
        rate_pct = raw_rate * 100
        engine_data["funding"] = {
            "rate_pct": f"{rate_pct:.4f}%", "rate": rate_pct,
            "quality": "B", "source": source,
        }
    if not engine_data.get("oi"):
        oi_val = float(snap.get("open_interest") or 0)
        engine_data["oi"] = {
            "oi": f"{oi_val:,.0f}", "value": oi_val,
            "trend": "up" if float(snap.get("oi_change_1h_pct") or 0) > 0.1 else "down" if float(snap.get("oi_change_1h_pct") or 0) < -0.1 else "flat",
            "change_1h_pct": float(snap.get("oi_change_1h_pct") or 0),
            "quality": "B", "source": source,
        }


def _per_tf_cvd(closes: list, highs: list, lows: list, volumes: list) -> dict:
    """逐周期CVD近似（v9.7）。

    用该周期的真实 OHLCV 合成累积买卖压力，使多周期定位表的 CVD 列五层各自独立，
    不再共用一个主执行周期值。这是时序近似值，精度低于 TV tick级CVD，故带
    ``approx`` 标注，供渲染器显示、供裁决作弱确认（与全局 HALDRO CVD 双轨并行）。
    返回: {"value": float, "direction": "买"/"卖"/"?}
    """
    if not closes:
        return {"value": 0.0, "direction": "?"}
    total = 0.0
    n = len(closes)
    for i in range(n):
        c = closes[i]
        o = (closes[i - 1] if i > 0 else c)
        # 每根K的"实体方向"：实体为正=买方占优，实体为负=卖方占优
        body = c - o
        vol = volumes[i] if i < len(volumes) else 0.0
        # 权重：实体幅度 + 成交量；越放大成交量，方向信号越强
        total += body * (1.0 + (0.5 * (float(vol) / 1000.0)))
    direction = "买" if total > 0 else "卖" if total < 0 else "?"
    return {"value": round(total, 2), "direction": direction}


def _collect_binance_data(engine_data: dict, symbol: str) -> None:
    """Fetch Binance futures data with HMAC signing for authenticated endpoints."""
    import requests, time as _time, hmac, hashlib, urllib.parse
    from concurrent.futures import ThreadPoolExecutor, as_completed
    su = symbol.upper()
    is_xau = ("XAU" in su or "GOLD" in su)
    # 金属只拉 public K线供 VWAP/EMA 引擎（不覆盖 gold-api 价格）
    if not is_xau:
        ac = _asset_class(symbol) if callable(_asset_class) else (lambda s: "crypto" if s.endswith("USDT") else "other")(symbol)
        if ac not in ("crypto",):
            return
    base = "https://fapi.binance.com"
    sym = "XAUUSDT" if is_xau else (symbol if symbol.endswith("USDT") else f"{symbol}USDT")
    api_key, secret = _load_binance_keys()
    
    # ── K-lines (public, no sign needed) ──
    # v4.4: 拉长 15m/1h 回溯以支撑 FVG/OB 检测（lookback 50/100）
    # v9.7: XAUUSDT 在 Binance 可能不存在/慢，限制 timeout 避免管线卡住
    klines = {}
    _raw_klines_multi = {}
    from binance_public import fetch_spot, fetch_futures
    # XAUUSDT 在 Binance 现货不存在，只能走 U 本位期货 public K线
    # 加密执行数据也必须走 U 本位期货；此前非 XAU 分支误用现货 klines，
    # 会把 futures symbol、OI 和 spot K 线混在同一套结构引擎里。
    _kl_fetcher = fetch_futures
    _kl_path = "/fapi/v1/klines"
    _xau_tf_limit = [("15m", 100), ("1h", 100)] if is_xau else [("5m", 30), ("15m", 100), ("1h", 100), ("4h", 50), ("1d", 30)]
    _xau_timeout = 4 if is_xau else 6
    # Each timeframe is an independent read. Fetch concurrently with a small
    # bound; shared TradingView state is not involved here.
    _kline_payloads = {}
    with ThreadPoolExecutor(max_workers=min(5, len(_xau_tf_limit))) as pool:
        futures = {
            pool.submit(
                _kl_fetcher, _kl_path,
                {"symbol": sym, "interval": tf, "limit": limit},
                timeout=_xau_timeout,
            ): tf
            for tf, limit in _xau_tf_limit
        }
        for future in as_completed(futures):
            tf = futures[future]
            try:
                _kline_payloads[tf] = future.result()
            except Exception as exc:
                _kline_payloads[tf] = None
                engine_data.setdefault("_source_errors", {})[f"binance_klines_{tf}"] = type(exc).__name__
    for tf, limit in _xau_tf_limit:
        _ok = False
        try:
            data = _kline_payloads.get(tf)
            if isinstance(data, list) and data:
                _raw_klines_multi[tf] = data  # 原始已收/未收OHLCV；体制层会剔除末根未收K
                k_key = "D" if tf == "1d" else tf  # 币安日线键 -> 渲染层 D（2026-08-31 补D层缺失）
                closes = [float(c[4]) for c in data]
                highs = [float(c[2]) for c in data]
                lows = [float(c[3]) for c in data]
                volumes = [float(c[5]) for c in data]
                chg_pct = (closes[-1] - closes[0]) / closes[0] if closes[0] else 0
                avg_vol = sum(volumes) / len(volumes) if volumes else 0
                rng = max(highs) - min(lows)
                poc = sum(closes) / len(closes) if closes else closes[-1]
                direction = "偏多" if chg_pct > 0.3 else "偏空" if chg_pct < -0.3 else "震荡"
                klines[k_key] = {
                    "close": closes[-1], "high": max(highs), "low": min(lows),
                    "open": float(data[0][1]), "volume": sum(volumes),
                    "atr": (sum(h - l for h, l in zip(highs, lows)) / len(highs)) if highs else 0,
                    "change_pct": round(chg_pct, 4),
                    "avg_volume": avg_vol, "range": rng,
                    "poc": round(poc, 2), "vah": round(max(highs), 2), "val": round(min(lows), 2),
                    "direction": direction,
                    "description": _kl_desc(tf, closes, highs, lows, volumes),
                    # v9.7: 逐层CVD近似——用该周期真实OHLCV合成累积买卖压力，
                    # 使多周期定位表的CVD列不再五层共用一个主执行周期值。
                    "cvd": _per_tf_cvd(closes, highs, lows, volumes),
                }
                _ok = True
        except Exception:
            pass
        if not _ok:
            # 回退源全失败：留空该 tf，不阻断其他周期
            pass
    _merge_collected_klines(engine_data, klines, preserve_existing=is_xau)
    engine_data["_raw_klines_multi"] = _raw_klines_multi  # v4.4: 原始 OHLCV 供高级订单流分析
    from binance_public import fapi_available
    fapi_ok = fapi_available(timeout=2)
    if not api_key or not fapi_ok:
        # Futures主域不可用时，统一使用Orion的Binance期货快照；不再串行等待
        # funding/OI/LSR/taker四个超时。缺失的LSR/taker保持缺失，由HALDRO裁决。
        _inject_orion_derivatives_fallback(engine_data, sym)
        try:
            from cvd_aggtrades import get_cvd_aggtrades
            cvd = get_cvd_aggtrades(sym)
            engine_data["cvd"] = {"direction": cvd.get("direction", "N/A"), "quality": cvd.get("quality", "B")}
        except Exception:
            pass
        engine_data["_fapi_available"] = bool(fapi_ok)
        return

    # ── HMAC-signed endpoints ──
    # These four read-only endpoints are independent. A bounded pool removes
    # serial TLS/network latency without weakening source coverage.
    endpoint_specs = {
        "funding": ("/fapi/v1/fundingRate", {"symbol": sym, "limit": 1}),
        "oi": ("/fapi/v1/openInterest", {"symbol": sym}),
        "taker": ("/futures/data/takerlongshortRatio", {"symbol": sym, "period": "5m", "limit": 1}),
        "long_short": ("/futures/data/globalLongShortAccountRatio", {"symbol": sym, "period": "5m", "limit": 1}),
    }

    def _read_endpoint(path, unsigned_params):
        params = _signed_binance_params(unsigned_params, secret, base)
        response = requests.get(
            f"{base}{path}", params=params,
            headers=_binance_headers(api_key), timeout=5,
        )
        response.raise_for_status()
        return response.json()

    endpoint_data = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_read_endpoint, path, params): name
            for name, (path, params) in endpoint_specs.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                endpoint_data[name] = future.result()
            except Exception as exc:
                engine_data.setdefault("_source_errors", {})[f"binance_{name}"] = type(exc).__name__

    try:
        data = endpoint_data.get("funding")
        if isinstance(data, list) and data:
            rate = float(data[0]["fundingRate"]) * 100
            engine_data["funding"] = {"rate_pct": f"{rate:.4f}%", "rate": rate, "quality": "A"}
    except Exception:
        pass
    
    # Open Interest
    try:
        data = endpoint_data.get("oi") or {}
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
        data = endpoint_data.get("taker")
        if isinstance(data, list) and data:
            bs = float(data[0].get("buySellRatio", 1))
            engine_data["taker"] = {"ratio": f"{bs:.2f}", "direction": "buy" if bs >= 1 else "sell", "quality": "A", "raw": bs}
    except Exception:
        pass
    
    # Global long/short ratio
    try:
        data = endpoint_data.get("long_short")
        if isinstance(data, list) and data:
            engine_data["long_short"] = {"long": float(data[0].get("longAccount", 0.5)), "short": float(data[0].get("shortAccount", 0.5))}
    except Exception:
        pass
    
    _inject_orion_derivatives_fallback(engine_data, sym)
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


def _parse_bjt_dt(value) -> datetime | None:
    """Parse Beijing/ISO timestamps used by cache files."""
    if not value:
        return None
    try:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    except Exception:
        return None


def _norm_symbol_for_cache(symbol: str) -> str:
    s = str(symbol or "").upper()
    s = s.replace("BINANCE:", "").replace("OANDA:", "").replace("TVC:", "")
    s = s.replace(".P", "")
    return s


def _tv_cache_status(cache: dict, symbol: str, max_age_minutes: int = 10) -> dict:
    """Validate TV cache before it can influence a formal card."""
    now = datetime.now(TZ)
    ts = _parse_bjt_dt(cache.get("timestamp") or cache.get("time") or cache.get("updated"))
    age_min = None
    if ts:
        age_min = max(0.0, (now - ts).total_seconds() / 60.0)
    cache_symbol = cache.get("symbol") or cache.get("ticker") or cache.get("tv_symbol") or ""
    want = _norm_symbol_for_cache(symbol)
    got = _norm_symbol_for_cache(cache_symbol)
    # A cache without an identity is not safe to consume: the old permissive
    # branch allowed a generic/empty-symbol snapshot to cross-contaminate BTC
    # and XAU after a chart switch.
    # Identity is a hard contract, not a fuzzy prefix match. BTC/BTCUSDT and
    # XAU/XAUUSD must never satisfy one another after a chart switch.
    symbol_ok = bool(got) and got == want
    fresh = age_min is not None and age_min <= max_age_minutes

    # v9.6 第二道防线：价位合理性校验，拦截 XAU/BTC 缓存交叉污染
    # BTC POC/VAH/VAL 应 >10000；XAU 应 <10000。价位落在错品种区间即判污染。
    _poc_raw = cache.get("poc")
    poc = None
    try:
        poc = float(str(_poc_raw).replace(",", "").replace(" ", "")) if _poc_raw is not None else None
    except (ValueError, TypeError):
        poc = None
    price_ok = True
    price_reason = ""
    if poc:
        if want.startswith("BTC") and poc < 10000:
            price_ok = False
            price_reason = f"价位污染 POC={poc} 疑似XAU数据"
        elif want.startswith("XAU") and poc > 10000:
            price_ok = False
            price_reason = f"价位污染 POC={poc} 疑似BTC数据"

    identity_contract_ok = cache.get("identity_valid", True) is True
    action_contract_ok = cache.get("action_table_complete", True) is True
    usable = bool(symbol_ok and fresh and price_ok and identity_contract_ok and action_contract_ok)
    reason = "实时/新鲜" if usable else ""
    if not symbol_ok:
        reason = f"品种不匹配 {cache_symbol or '?'}"
    elif not identity_contract_ok:
        reason = "TV身份契约无效"
    elif not action_contract_ok:
        reason = "TV行动格核心字段不完整"
    elif age_min is None:
        reason = "无时间戳"
    elif not fresh:
        reason = f"缓存过期 {age_min:.0f}分钟"
    elif not price_ok:
        reason = price_reason
    return {
        "usable": usable,
        "source": "cache",
        "symbol": cache_symbol,
        "timestamp": ts.isoformat() if ts else "",
        "age_minutes": age_min,
        "reason": reason,
    }


def _source_snapshot_status(symbol: str, max_age_hours: float = 1.0) -> dict:
    """Return freshness metadata for the per-symbol source snapshot.

    GO/NO-GO previously used a hard-coded 24h default because auto_card never
    stamped ``engine_data['_snapshot_age_h']``. That made the freshness gate a
    warning-only decoration instead of a real accuracy control. This helper is
    deliberately file-based so it works after either source_snapshot() refreshes
    data or a cron/daemon refreshed it out of band.
    """
    # Formal freshness is per-asset only. The shared compatibility snapshot is
    # diagnostic and must never satisfy a GO/NO-GO input.
    candidates = [DATA / f"source_snapshot_{symbol}.json"]
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return {"usable": False, "age_hours": 24.0, "reason": "source_snapshot缺失", "path": ""}
    now = datetime.now(TZ)
    loaded = []
    expected_symbol = _norm_symbol_for_cache(symbol)
    for path in existing:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        payload_symbol = _norm_symbol_for_cache(str(payload.get("symbol") or payload.get("ticker") or ""))
        if not payload_symbol or payload_symbol != expected_symbol:
            continue
        root_dt = _parse_bjt_dt(payload.get("time") or payload.get("updated_at") or payload.get("updated"))
        loaded.append((path, payload, root_dt))
    if not loaded:
        return {"usable": False, "age_hours": 24.0, "reason": "source_snapshot缺少匹配品种", "path": ""}
    stamped = [item for item in loaded if item[2] is not None]
    if not stamped:
        return {"usable": False, "age_hours": 24.0, "reason": "source_snapshot无根时间戳", "path": str(loaded[0][0])}
    newest, payload, root_dt = max(stamped, key=lambda item: item[2].timestamp())
    age_h = max(0.0, (now - root_dt).total_seconds() / 3600.0)
    child_status = {}
    child_issues = []
    # Nested macro snapshots used to retain a July timestamp while the outer
    # XAU file was rewritten in September.  Validate the child timestamp too.
    macro = payload.get("macro_context")
    if isinstance(macro, dict) and macro:
        macro_dt = _parse_bjt_dt(macro.get("time") or macro.get("updated_at") or macro.get("updated"))
        if macro_dt is None:
            child_status["macro_context"] = {"usable": False, "reason": "无时间戳"}
            child_issues.append("macro_context无时间戳")
        else:
            macro_age_h = max(0.0, (now - macro_dt).total_seconds() / 3600.0)
            child_ok = macro_age_h <= max_age_hours
            child_status["macro_context"] = {"usable": child_ok, "age_hours": macro_age_h}
            if not child_ok:
                child_issues.append(f"macro_context过期{macro_age_h:.1f}h")
    usable = age_h <= max_age_hours and not child_issues
    if not usable:
        reason = "; ".join(child_issues) if child_issues else f"source_snapshot过期{age_h:.1f}h"
    else:
        reason = f"{age_h:.2f}h新鲜"
    return {
        "usable": usable,
        "age_hours": age_h,
        "reason": reason,
        "path": str(newest),
        "child_status": child_status,
    }


def _refresh_and_mark_snapshot(symbol: str, engine_data: dict) -> None:
    """Refresh source snapshot when possible and mark freshness for gates/cards."""
    prior = _source_snapshot_status(symbol)
    if prior.get("usable"):
        try:
            cached = json.loads(Path(prior["path"]).read_text(encoding="utf-8"))
            if isinstance(cached, dict):
                engine_data["source_snapshot"] = cached
                if cached.get("quality"):
                    engine_data.setdefault("grades", {})["source_snapshot"] = cached.get("quality")
        except (OSError, TypeError, json.JSONDecodeError):
            pass
        engine_data["_snapshot_status"] = prior
        engine_data["_snapshot_age_h"] = float(prior.get("age_hours") or 0.0)
        return
    try:
        import sys as _snap_sys
        sp = str(ROOT / "scripts")
        if sp not in _snap_sys.path:
            _snap_sys.path.insert(0, sp)
        from trading_system import source_snapshot
        snap = source_snapshot(symbol)
        if isinstance(snap, dict) and snap:
            engine_data["source_snapshot"] = snap
            if snap.get("quality"):
                engine_data.setdefault("grades", {})["source_snapshot"] = snap.get("quality")
    except Exception as exc:
        engine_data["_snapshot_refresh_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    status = _source_snapshot_status(symbol)
    engine_data["_snapshot_status"] = status
    engine_data["_snapshot_age_h"] = float(status.get("age_hours") or 24.0)
    if not status.get("usable") and engine_data.get("quality") in ("A", "A-", "B"):
        # Do not silently keep A/B if the underlying source snapshot is stale.
        engine_data["quality"] = "B" if status.get("age_hours", 24) <= 4 else "C"


def _load_xau_tv_contract(max_age_minutes: float | None = None) -> dict:
    """Validate the current XAU five-layer/action pair before any live resync."""
    try:
        from xau_tv_sync import validate_xau_outputs

        state = json.loads((ROOT / "data" / "xau_tv_state.json").read_text(encoding="utf-8"))
        live = json.loads((ROOT / "data" / "tv_live_XAUUSD.json").read_text(encoding="utf-8"))
        kwargs = {} if max_age_minutes is None else {"live_max_age_minutes": float(max_age_minutes)}
        return validate_xau_outputs(state, live, require_batch_id=True, **kwargs)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return {"usable": False, "reason": f"XAU双缓存读取失败:{type(exc).__name__}"}


def _pipeline_tv_step_status(engine_data: dict) -> dict:
    """Audit the routed TV step without treating Binance K-lines as TV evidence."""
    # 2026-09-13 口径统一：live_status=TV注入最终结论，cache_status 仅输入管道之一。
    live = engine_data.get("_tv_live_status") or engine_data.get("_tv_cache_status") or {}
    live = live if isinstance(live, dict) else {}
    override = engine_data.get("_tv_override") or {}
    override = override if isinstance(override, dict) else {}
    five = engine_data.get("_tv_five_tf_status") or {}
    five = five if isinstance(five, dict) else {}
    main_usable = bool(override.get("tv_active") or live.get("usable"))
    five_required = bool(engine_data.get("_tv_five_tf_required"))
    five_usable = bool(five.get("usable"))
    return {
        "usable": main_usable and (five_usable if five_required else True),
        "main_usable": main_usable,
        "five_required": five_required,
        "five_usable": five_usable,
        "five_reason": five.get("reason") or "未提供",
        "five_coverage": five.get("coverage", 0),
    }


def _freshness_line(engine_data: dict) -> str:
    """Human-readable freshness line for the cockpit card."""
    # 2026-09-13 口径统一：与门2/步骤审计一致，live_status 优先。
    tvs = engine_data.get("_tv_live_status") or engine_data.get("_tv_cache_status") or {}
    if tvs:
        age = tvs.get("age_minutes")
        if tvs.get("usable"):
            tv_part = f"TV缓存{age:.0f}分钟前" if age is not None else "TV缓存新鲜"
        else:
            tv_part = f"TV未采用({tvs.get('reason','未知')})"
    elif engine_data.get("_tv_override", {}).get("tv_active"):
        tv_part = "TV实时/直连"
    else:
        tv_part = "TV未接入"
    snap = engine_data.get("_snapshot_status") or {}
    snap_part = f"快照{snap.get('reason')}" if snap else "快照未检测"
    src = (engine_data.get("prices") or {}).get("source") or "多源"
    now_cn = datetime.now(TZ)
    time_cn = f"{now_cn.year}年{now_cn.month}月{now_cn.day}日{now_cn.hour:02d}：{now_cn.minute:02d}"
    return f"数据新鲜度：{tv_part} · {snap_part} · 价格源{src} · {time_cn}"


def append_trade_plan(meta: dict, card: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    row = dict(meta)
    # v9.6: 预测评级 A/B/C/D — 基于置信度+R:R+数据质量
    conf = float(row.get("engine_confidence", 0) or 0)
    rr_a = float(row.get("rr_a", 0) or 0)
    data_g = str(row.get("data_grade", "C"))
    gate = row.get("gate_verdict", "")
    status = str(row.get("status", ""))
    if "禁做" in str(status) or "禁" in str(gate):
        predicted_grade = "D"
    elif conf >= 0.6 and rr_a >= 2.0 and data_g in ("A", "A-"):
        predicted_grade = "A"
    elif conf >= 0.3 and rr_a >= 1.5:
        predicted_grade = "B"
    elif conf > 0:
        predicted_grade = "C"
    else:
        predicted_grade = "C"
    row["predicted_grade"] = predicted_grade
    row["card_excerpt"] = card[:500]
    append_text_line(
        DATA / "trade_plans.jsonl",
        json.dumps(row, ensure_ascii=False, separators=(",", ":")),
    )

def update_monitor_metadata(symbol: str, meta: dict) -> None:
    # monitor_levels.json 是历史兼容缓存，不再作为批准监测位真相源。
    # 分析结果只写 setup 审计文件，避免 auto_card 覆盖 keylevels_config 的人工批准位。
    path = DATA / f"analysis_setup_{symbol.replace('/', '_')}.json"
    try:
        data = {
            "symbol": symbol,
            "updated": datetime.now(TZ).isoformat(),
            "latest_setup": {k: meta.get(k) for k in ("setup_id", "model_id", "entry_tag", "exit_tag", "direction", "status", "priority_plan", "data_grade", "level_confidence", "engine_confidence", "confidence_5", "expires_at", "monitor_write")},
        }
        atomic_write_json(path, data)
    except Exception as e:
        print(f"  ⚠ monitor metadata skipped: {e}")


def _approved_monitor_levels(symbol: str) -> dict:
    """读取唯一批准监测配置；历史 monitor_levels 只保留兼容，不参与分析。"""
    try:
        config = json.loads((DATA / "keylevels_config.json").read_text(encoding="utf-8"))
        return (config.get("symbols", {}) or {}).get(symbol, {})
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _safe_import(module, func):
    try:
        mod = __import__(module, fromlist=[func])
        return getattr(mod, func)
    except Exception as e:
        print(f"  ⚠️ {module}.{func}: {e}")
        return None


def _advanced_orderflow(symbol: str, engine_data: dict, merged: dict, meta: dict) -> dict:
    """v4.4: 接通5个闲置分析模块 — 吸收/FVG/OB/相关性/Meta门控 + 多周期共振闸门。

    社区2026共识落地：单信号不够，多工具共振(≥4/6)才入场；相邻周期冲突=不交易。
    全部 try/except 隔离，任一模块失败不影响主卡。返回:
        {section: str(卡片段), gate: dict(放行/否决), factors: dict}
    """
    import sys as _sys
    _sp = str(ROOT / "scripts")
    if _sp not in _sys.path:
        _sys.path.insert(0, _sp)

    out = {"section": "", "gate": {}, "factors": {}}
    lines = ["", "## 高级订单流确认 (v4.4)"]

    raw = engine_data.get("_raw_klines_multi", {}) or {}
    klines = engine_data.get("klines", {}) or {}
    price = (engine_data.get("prices", {}) or {}).get("primary", 0) or 0
    cvd = engine_data.get("cvd", {}) or {}
    cvd_dir = cvd.get("direction", "?")
    cvd_qual = cvd.get("quality", "C")
    bias = merged.get("bias", "?")
    direction = "long" if "多" in str(bias) else "short" if "空" in str(bias) else "neutral"
    is_crypto = symbol.upper().endswith("USDT")

    # ── ① 订单流吸收（社区#1：真支撑要看吸收）──
    try:
        from orderflow_absorption import detect_absorption
        k15 = klines.get("15m", {}) or {}
        chg5 = (klines.get("5m", {}) or {}).get("change_pct", 0) or 0
        avg_v = k15.get("avg_volume", 0) or 1
        cur_v = k15.get("volume", 0) or 0
        vol_ratio = (cur_v / avg_v) if avg_v else 1.0
        atr = k15.get("atr", 0) or 0
        # 距最近关键位 ATR 倍数：用 VAH/VAL/POC 最近者
        tv = engine_data.get("tv", {}) or {}
        levels = [tv.get(k, 0) for k in ("vah", "val", "poc")] + [k15.get("poc", 0)]
        levels = [l for l in levels if l]
        prox = min((abs(price - l) / atr for l in levels), default=1.0) if atr else 1.0
        ab = detect_absorption(symbol, price, cvd_dir, cvd_qual, chg5, vol_ratio, prox)
        out["factors"]["absorption"] = ab
        if ab.get("absorption_detected"):
            lines.append(f"- 吸收：{ab['pattern']}·{ab['direction_bias']}·StopRun{ab['stop_run_risk']} (置信{ab['confidence']}%)")
        else:
            lines.append(f"- 吸收：订单流正常·无异常")
    except Exception as e:
        lines.append(f"- 吸收：跳过({str(e)[:40]})")

    # ── ② FVG + Order Block（ICT 进场位）──
    # 棠溪规则：FVG是4h/D中线结构；15m/5m只作执行回测参考，不能拿来判结构。
    try:
        from fvg_detector import detect_fvg, update_fvg_status, best_fvg
        from order_block import detect_obs, nearest_ob
        k_struct_raw = raw.get("4h") or raw.get("1d") or raw.get("1D") or []
        k_exec_raw = raw.get("15m", [])
        if k_struct_raw and price:
            side = "bullish" if direction == "long" else "bearish" if direction == "short" else None
            fvg_direction = "long" if direction == "long" else "short" if direction == "short" else None
            fvgs = update_fvg_status(detect_fvg(k_struct_raw, 120, timeframe="4h"), price, k_struct_raw)
            bf = best_fvg(fvgs, direction=fvg_direction, structural_only=True)
            obs = detect_obs(k_exec_raw or k_struct_raw, 100)
            nob = nearest_ob(obs, price, side)
            out["factors"]["fvg"] = bf
            out["factors"]["ob"] = nob
            fvg_txt = f"4h {bf['type']} {bf['bottom']}–{bf['top']} CE{bf.get('ce', bf.get('midpoint'))} ({bf.get('status','?')})" if bf else "无活跃4h/D中线FVG"
            ob_txt = f"{nob['type']} @{nob['price']} 强度{nob['strength']}/5" if nob else "无OB"
            lines.append(f"- ICT进场：中线FVG {fvg_txt} | OB {ob_txt}")
        else:
            lines.append("- ICT进场：4h/D原始K线不足，不能用15m FVG替代中线结构")
    except Exception as e:
        lines.append(f"- ICT进场：跳过({str(e)[:40]})")

    # ── ③ 跨市场相关性风险乘数（仅在 BTC/XAU 同时分析时有意义）──
    try:
        from correlation_matrix import compute_correlation
        corr = compute_correlation()
        if corr.get("status") == "ok":
            out["factors"]["correlation"] = corr
            lines.append(f"- 跨市场：BTC×XAU相关{corr.get('correlation_full','?')}·{corr.get('regime','?')}·{corr.get('advice','')[:30]}")
    except Exception as e:
        pass  # 相关性是可选增强，静默

    # ── ④ 多周期共振计数 + 相邻周期冲突硬门（社区核心）──
    try:
        def _tf_dir(tf):
            d = (klines.get(tf, {}) or {}).get("direction", "")
            if "多" in d or "涨" in d:
                return 1
            if "空" in d or "跌" in d:
                return -1
            return 0
        d4, d1, d15 = _tf_dir("4h"), _tf_dir("1h"), _tf_dir("15m")
        # 相邻周期冲突：4h vs 1h 明确反向 = 不交易
        conflict = (d4 * d1 == -1) or (d1 * d15 == -1)
        # 共振计数（0-6）
        factors_hit = 0
        f_detail = []
        # 1. HTF方向一致(4h+1h同向)
        if d4 != 0 and d4 == d1:
            factors_hit += 1; f_detail.append("HTF同向✓")
        # 2. 价在关键位(吸收检测到 prox<0.5)
        ab = out["factors"].get("absorption", {})
        if ab.get("absorption_detected"):
            factors_hit += 1; f_detail.append("关键位吸收✓")
        # 3. CVD配合方向
        if (cvd_dir in ("买", "buy") and direction == "long") or (cvd_dir in ("卖", "sell") and direction == "short"):
            factors_hit += 1; f_detail.append("CVD配合✓")
        # 4. 结构(FVG/OB存在且同向)
        if out["factors"].get("fvg") or out["factors"].get("ob"):
            factors_hit += 1; f_detail.append("ICT结构✓")
        # 5. VWAP位置有利
        tv = engine_data.get("tv", {}) or {}
        vwap = tv.get("vwap", 0)
        if vwap and price:
            if (direction == "long" and price >= vwap) or (direction == "short" and price <= vwap):
                factors_hit += 1; f_detail.append("VWAP位置✓")
        # 6. 量能确认
        if (klines.get("15m", {}) or {}).get("volume", 0) > (klines.get("15m", {}) or {}).get("avg_volume", 0):
            factors_hit += 1; f_detail.append("量能✓")
        out["factors"]["confluence_count"] = factors_hit
        out["factors"]["tf_conflict"] = conflict
        if conflict:
            lines.append(f"- **周期冲突：4h/1h/15m方向矛盾 → 观望不交易**")
        else:
            pos = "满仓" if factors_hit >= 5 else "半仓" if factors_hit == 4 else "轻仓/观望" if factors_hit == 3 else "不交易"
            lines.append(f"- 多周期共振：{factors_hit}/6 ({'·'.join(f_detail) or '无'}) → {pos}")
    except Exception as e:
        lines.append(f"- 多周期共振：跳过({str(e)[:40]})")
        conflict = False
        factors_hit = 0

    # ── ⑤ 多空比反向票（散户拥挤）──
    try:
        ls = engine_data.get("long_short", {}) or {}
        ls_long = ls.get("long")
        if ls_long is not None:
            ratio = float(ls_long) / max(1e-9, (1 - float(ls_long))) if float(ls_long) < 1 else float(ls_long)
            # long account fraction → ratio
            if float(ls_long) <= 1:
                ratio = float(ls_long) / max(0.01, 1 - float(ls_long))
            contra = ""
            if ratio > 2.5:
                contra = "散户极度拥挤多→反向警惕顶"
            elif ratio < 0.5:
                contra = "散户极度拥挤空→反向警惕底"
            if contra:
                lines.append(f"- 多空比反指：{ratio:.2f} {contra}")
                out["factors"]["ls_contra"] = contra
    except Exception:
        pass

    # ── ⑥ Meta-Labeling 执行门控（共振闸门，最终放行/否决）──
    try:
        from meta_labeler import check_meta_label
        score = int(round((merged.get("global_confidence", 0.5) or 0.5) * 10))
        sess = (engine_data.get("_session", {}) or {}).get("key", "off")
        signal = {
            "model_score": score,
            "data_quality": engine_data.get("quality", "C"),
            "cvd_direction": cvd_dir,
            "cvd_quality": cvd_qual,
            "session": sess,
            "direction": direction,
            "loss_streak": 0,
            "rr_ratio": meta.get("rr1", 0) or 0,
        }
        gate = check_meta_label(signal)
        if not isinstance(gate, dict) or not isinstance(gate.get("execute"), bool):
            gate = {"execute": False, "confidence": 0.0, "reason": "Meta-Labeling返回格式无效·默认拒绝"}
        # 周期冲突 → 强制否决
        if out["factors"].get("tf_conflict"):
            gate = {"execute": False, "confidence": gate.get("confidence", 0), "reason": "周期冲突·否决"}
        # 共振<4 → 否决
        elif out["factors"].get("confluence_count", 0) < 4:
            gate = {"execute": False, "confidence": gate.get("confidence", 0),
                    "reason": f"共振{out['factors'].get('confluence_count',0)}/6<4·否决"}
        out["gate"] = gate
        verdict = "✓放行" if gate.get("execute") else "✗否决"
        lines.append(f"- **执行门控：{verdict}·{gate.get('reason','?')}·置信{gate.get('confidence',0):.0%}**")
    except Exception as e:
        reason = f"高级门控不可用·{type(e).__name__}:{str(e)[:60]}·默认拒绝"
        out["gate"] = {"execute": False, "confidence": 0.0, "reason": reason, "error": str(e)[:120]}
        lines.append(f"- **执行门控：✗否决·{reason}**")

    # ── ⑦ 孤儿模块集成（订单流吸收+FVG+OB+CVD共振+相关性乘数）──
    try:
        from orphan_integration import run_orphan_checks
        klines_raw = engine_data.get("futures_klines", [])
        klines_for_orphan = klines_raw if isinstance(klines_raw, list) and len(klines_raw) > 10 else None
        orphan_results = run_orphan_checks(
            symbol=symbol,
            price=price or 0,
            direction=direction,
            klines=klines_for_orphan
        )
        out["orphan"] = orphan_results

        # 吸收检测
        absorp = orphan_results.get("absorption", {})
        if absorp.get("detected"):
            lines.append(f"- **订单流吸收：第{absorp.get('zone')}区·{absorp.get('signal','?')}·来源{absorp.get('_source','?')}**")

        # FVG缺口
        fvg = orphan_results.get("fvg", {})
        if fvg.get("count", 0) > 0:
            best = fvg.get("best", {})
            if best.get("high") and best.get("low"):
                lines.append(f"- **FVG缺口：{best.get('direction','?')}向·{best.get('low')}-{best.get('high')}·来源{best.get('_source','?')}**")

        # OB订单块
        ob = orphan_results.get("ob", {})
        if ob.get("nearest_price"):
            lines.append(f"- **Order Block：{ob.get('nearest_side','?')}向·价{ob.get('nearest_price')}·来源{ob.get('_source','?')}**")

        # CVD共振
        cvd_conf = orphan_results.get("cvd_confluence", {})
        if cvd_conf.get("verdict"):
            lines.append(f"- **CVD共振：{cvd_conf.get('verdict','?')}·严重度{cvd_conf.get('severity','?')}·来源{cvd_conf.get('_source','?')}**")

        # 相关性乘数
        corr_mult = orphan_results.get("corr_multiplier", 1.0)
        if corr_mult != 1.0:
            adj = "减小" if corr_mult < 1.0 else "增大"
            lines.append(f"- **相关性乘数：{corr_mult:.2f}（组合风险{adj}·来源{orphan_results.get('_meta',{}).get('_source','?')}）**")

        lines.append(f"- 孤儿信号已写入 data/orphan_signals_{symbol}.json")
    except Exception as e:
        lines.append(f"- 孤儿模块集成：跳过({str(e)[:60]})")

    # ── ⑧ 评分引擎 v1.0（14分机器评分）──
    try:
        from scoring_engine import score_setup
        _taker_data = engine_data.get("taker", {}) or {}
        _taker_r = _taker_data.get("ratio")
        _fear_greed_val = None
        try:
            _fear_greed_val = int(engine_data.get("fear_greed", {}).get("value", 0) or 0)
        except Exception:
            pass
        score_result = score_setup(
            symbol=symbol,
            smc_result=merged.get("smc"),
            tv_levels=engine_data.get("tv_levels"),
            cvd_value=float(engine_data.get("cvd", {}).get("value", 0) or 0),
            cvd_slope=float(engine_data.get("cvd", {}).get("slope", 0) or 0),
            taker_ratio=float(_taker_r) if _taker_r not in (None, "N/A", "") else None,
            fear_greed=_fear_greed_val,
        )
        total_score = score_result.get("total", 0)
        grade = score_result.get("grade", "?")
        recommendation = score_result.get("recommendation", "")
        lines.append(f"- **评分引擎：{total_score:.1f}/14 {grade}（{recommendation}）**")
    except Exception as e:
        lines.append(f"- 评分引擎：跳过({str(e)[:60]})")

    out["section"] = "\n".join(lines)
    return out


def auto_card(symbol: str, push: bool = False, mode: str = "full") -> str:
    """一键出卡。

    mode 支持 full/quick/standard/inherit。standard 是对话层“标准”档，
    inherit 作为旧调用方兼容名；二者都只刷新执行层并尽量读取高周期上下文。
    """
    if mode not in {"full", "quick", "standard", "inherit"}:
        raise ValueError(f"unsupported analysis mode: {mode}")
    print(f"\n{'='*60}")
    print(f"  棠溪 · 一键分析卡 · {symbol} · {mode}")
    print(f"  {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    asset_class = _asset_class(symbol)
    asset = "crypto" if asset_class == "crypto" else "metal" if asset_class == "gold" else asset_class
    
    # standard/inherit 尝试读取上下文；上下文缺失不偷偷升级 full，
    # 标准档仍按相邻周期结论执行，缺口在卡片完成度中显式显示。
    context = None
    effective_mode = mode
    try:
        from pipeline_router import load_analysis_context
        if mode in {"inherit", "standard"}:
            context = load_analysis_context(symbol)
            if context is None:
                print("  ⚠ 标准档上下文缺失/过期 → 保留标准档，邻近周期现场补读")
            else:
                print(f"  ✅ 继承高周期上下文: {context.get('updated_at', '?')}")
    except Exception as exc:
        if mode in {"inherit", "standard"}:
            print(f"  ⚠ 标准档上下文读取失败 → 保留标准档: {str(exc)[:100]}")

    # 管线路由：确定应该执行的步骤
    pipeline_steps = []
    try:
        from pipeline_router import route_pipeline
        pipeline_steps = route_pipeline(symbol, effective_mode)
        print(f"📋 管线路由：{len(pipeline_steps)}步 → {' → '.join(pipeline_steps)}")
    except ValueError:
        # Invalid contracts are not an unavailable provider: never execute a fallback.
        raise
    except Exception as e:
        print(f"⚠️ 管线路由不可用({e})·使用默认步骤")
        pipeline_steps = ["tv","binance","card"] if effective_mode != "full" else ["tv","macro","x_sent","card"]
        if effective_mode == "full" and asset_class == "crypto":
            try:
                from pipeline_router import crypto_full_pipeline
                pipeline_steps = crypto_full_pipeline()
            except Exception:
                # Keep the fallback fail-closed and aligned with the public
                # fifteen-stage contract even if the helper import fails.
                pipeline_steps = [
                    "tv", "binance", "cg_pro", "macro", "x_sent", "cron_read",
                    "cvd", "depth", "corr", "engine", "regime", "dual",
                    "advanced", "risk", "card",
                ]
    completed_steps = set()

    # TV MCP是分析前提：先切目标品种+主周期并刷新Data Window，再进入任何指标/体制引擎。
    xau_contract = {}
    try:
        from pipeline_router import timeframe_info
        tf_main = str(timeframe_info(symbol).get("main") or "15m")
        tf_code = {"5m": "5", "15m": "15", "1h": "60", "4h": "240", "D": "D"}.get(tf_main, "15")
        if _asset_class(symbol) == "gold":
            xau_env = os.environ.copy()
            xau_env["XAU_TV_NO_PUSH"] = "1"
            # 前置决策用「读取窗口 − 出卡余量」判新鲜，确保出卡期间不会跨过
            # 读取阈值（避免同一张卡「前置跳过 / 读取拒绝」自相矛盾）。
            xau_contract = _load_xau_tv_contract(max_age_minutes=TV_LIVE_PRE_SYNC_MAX_AGE_MIN)
            engine_tv_ready = bool(xau_contract.get("usable"))
            if engine_tv_ready:
                print("  ♻ XAU五层/5m行动格缓存新鲜，跳过重复切图")
            else:
                try:
                    xau_sync = subprocess.run(
                        [sys.executable, str(ROOT / "scripts" / "xau_tv_sync.py")],
                        cwd=str(ROOT), capture_output=True, text=True, env=xau_env,
                        encoding="utf-8", errors="replace", timeout=300,
                    )
                    if xau_sync.returncode != 0:
                        print(f"  ⚠ XAU五层前置同步失败: {(xau_sync.stderr or xau_sync.stdout)[:160]}")
                    else:
                        xau_contract = _load_xau_tv_contract()
                        engine_tv_ready = bool(xau_contract.get("usable"))
                        if not engine_tv_ready:
                            print(f"  ⚠ XAU五层/主周期成对校验失败: {xau_contract.get('reason','校验失败')}")
                except subprocess.TimeoutExpired:
                    print(f"  ⚠ XAU五层前置同步超时300s，降级继续")
            # XAU 已由 xau_tv_sync 完成TV同步，跳过 tv_live_dump 避免双倍等待
            tf_main = str(timeframe_info(symbol).get("main") or "5m")
            print(f"  {'✅' if engine_tv_ready else '⚠'} TV分析前置刷新: {symbol} {tf_main} (XAU专用路径)")
        else:
            _tv_dump = ROOT / "scripts" / "tv_live_dump.py"
            if _tv_dump.exists():
                tv_refresh = subprocess.run(
                    [sys.executable, str(_tv_dump),
                     "--symbol", symbol, "--timeframe", tf_code, "--verbose"],
                    cwd=str(ROOT), capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=45,
                )
                engine_tv_ready = tv_refresh.returncode == 0
                print(f"  {'✅' if engine_tv_ready else '⚠'} TV分析前置刷新: {symbol} {tf_main}")
                if not engine_tv_ready:
                    print(f"  ⚠ TV前置详情: {(tv_refresh.stderr or tv_refresh.stdout)[:160]}")
            else:
                # 2026-08-31 P0: tv_live_dump.py 已迁入归档区
                # （2026-09-12 起归档目录统一为 scripts/_disabled/），
                # 前置刷新改由实时缓存（tv_live_<SYM>.json / tv_dmi_cache.json）兜底，不再强制子进程。
                engine_tv_ready = False
                print(f"  ⚠ tv_live_dump.py 缺失（已归档8/29）→ 跳过前置刷新，依赖TV实时缓存/现场MCP")
    except Exception as exc:
        engine_tv_ready = False
        print(f"  ⚠ TV分析前置刷新异常: {str(exc)[:120]}")
    
    # ═══ Step 1: 数据采集 ═══
    print("① 数据采集...")
    
    engine_data = {"symbol": symbol, "quality": "B", "asset_class": asset_class,
                   "analysis_mode": effective_mode,
                   "_pipeline_steps": list(pipeline_steps),
                   "context_inherited": bool(context),
                   "inherited_context": context or {},
                   "_tv_preflight_ok": bool(engine_tv_ready),
                   "_xau_tv_contract": xau_contract if asset_class == "gold" else {},
                   "_source_records": {}}
    # Full crypto/gold cards must consume an actual symbol-scoped TV snapshot
    # for all five timeframes.  Quick/Inherit may use a fresh direct cache or
    # inherited context for background rows without turning that into a live
    # execution authorization.
    tv_five_tf = _load_tv_five_tf_snapshot(symbol, mode=effective_mode, context=context)
    if effective_mode == "full" and asset_class in {"crypto", "gold"} and not tv_five_tf.get("usable"):
        _refresh_btc_tv_five_tf_snapshot(symbol)
        tv_five_tf = _load_tv_five_tf_snapshot(symbol, mode=effective_mode, context=context)
    engine_data["_tv_five_tf_status"] = {
        key: tv_five_tf.get(key)
        for key in ("usable", "identity_valid", "fresh", "timestamp", "timeframes", "missing",
                    "coverage", "reason", "source", "source_path", "scope")
    }
    engine_data["_tv_five_tf_required"] = effective_mode == "full" and asset_class in {"crypto", "gold"}
    if tv_five_tf.get("usable"):
        _merge_tv_five_tf_into_engine(engine_data, tv_five_tf)
        print(f"  ✅ TV五周期契约: {tv_five_tf.get('scope','direct_cache')} · 覆盖{tv_five_tf.get('coverage')}/5")
    else:
        print(f"  ⚠ TV五周期契约: {tv_five_tf.get('reason','不可用')} · 覆盖{tv_five_tf.get('coverage',0)}/5")
    _refresh_and_mark_snapshot(symbol, engine_data)
    _snap_status = engine_data.get("_snapshot_status") or {}
    if not isinstance(_snap_status, dict):
        _snap_status = {}
    print(f"  📌 SourceSnapshot: {_snap_status.get('reason','未检测')}")
    
    if asset == "crypto":
        # 期货价格优先（TV/Binance Perp），CMC现货作 backup
        futures_price = None
        try:
            from binance_public import fetch_futures, orion_derivatives_snapshot
            sym = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
            # BTC 的执行价格必须优先来自 U 本位期货；Orion 只作后备，
            # 不能让 CMC 现货价格悄悄成为合约主价格。
            ticker = fetch_futures("/fapi/v1/ticker/price", {"symbol": sym}, timeout=6)
            futures_price = float(ticker.get("price") or 0) if isinstance(ticker, dict) else None
            if not futures_price:
                snap = orion_derivatives_snapshot(sym)
                futures_price = float(snap.get("mark_price") or 0) if snap.get("ok") else None
        except Exception:
            futures_price = None
        
        try:
            from multi_source_collector import cmc_quote, cmc_global, cmc_fear_greed
            if effective_mode == "full":
                cmc = cmc_quote(symbol[:3])
            else:
                cached_snapshot = engine_data.get("source_snapshot") or {}
                cached_prices = (cached_snapshot.get("prices") or {}).get("sources") or []
                cached_spot = next((
                    _decision_float(row.get("price")) for row in cached_prices
                    if isinstance(row, dict) and row.get("source") in {"Binance现货", "CoinGecko"}
                    and _decision_float(row.get("price")) > 0
                ), 0.0)
                # 2026-09-13：市占未知就不写 0.0 —— 旧实现硬编码 0.0，卡面把「没采到」
                # 打印成「市占0.0%」，读者会当成真实读数。
                cmc = {"price": cached_spot, "_source_status": "cache"}
            _register_source_record(engine_data, "cmc", cmc, symbol=symbol)
            spot_price = cmc.get("price", 0)
            # 优先 Binance U 本位期货价，CMC 仅保留为现货交叉验证/备用
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
            # P1b: 填充 Binance K线（VWAP/EMA/FVG 引擎依赖）
            try:
                _collect_binance_data(engine_data, symbol)
                engine_data["_binance_data_collected"] = True
            except Exception:
                pass
            basis = f" 期现差{(futures_price/spot_price-1)*100:+.3f}%" if futures_price and spot_price else ""
            _dom = _decision_float(cmc.get("dominance"))
            _dom_txt = f"{_dom:.1f}%" if _dom > 0 else "—（未采到）"
            print(f"  ✅ 期货: ${primary_price:,.0f} (Binance Perp) | CMC现货: ${spot_price:,.0f}{basis} | 市占{_dom_txt}")
            
            # CMC global
            glob = cmc_global() if "macro" in pipeline_steps else {}
            _register_source_record(engine_data, "cmc_global", glob, symbol=symbol)
            engine_data["cmc_global"] = glob
            
            # F&G
            fg = cmc_fear_greed() if "macro" in pipeline_steps else {}
            _register_source_record(engine_data, "fear_greed", fg, symbol=symbol, status="not_run" if "macro" not in pipeline_steps else None)
            engine_data["fear_greed"] = fg
            # 2026-09-13：没采到就直说，「✅ ? (?)」会被当成采到了。
            if fg.get("value") in (None, "", "?"):
                # 2026-09-13：区分「档位设计跳过」与「真采集失败」——把两者写成同一句
                # 「来源未路由或失败」会让正常降级看起来像故障，违反显式降级契约。
                if "macro" not in pipeline_steps:
                    print(f"  ⏭️ 恐慌贪婪: 当前档位跳过（需 macro 步）")
                else:
                    _fg_status = fg.get("_source_status") or "unavailable"
                    print(f"  ⚠️ 恐慌贪婪: 采集失败（状态{_fg_status}），需查源")
            else:
                print(f"  ✅ 恐慌贪婪: {fg.get('value')} ({fg.get('classification') or '—'})")
            
            # CoinGecko top coins → 板块轮动检测（仅full）
            try:
                from multi_source_collector import cg_top_coins, cg_trending
                top = cg_top_coins(10) if "cg_pro" in pipeline_steps else {}
                _register_source_record(engine_data, "cg_top", top, symbol=symbol, status="not_run" if "cg_pro" not in pipeline_steps else None)
                engine_data["cg_top"] = top
                cg_status = top.get("_source_status", "not_run") if isinstance(top, dict) else "unavailable"
                # 2026-09-13：not_run/失败时不再打印「BTC +0.0% vs Alt +0.0%」
                # —— 那是 .get(...,0) 的默认值伪装成读数。
                _btc_chg = top.get("btc_change_24h") if isinstance(top, dict) else None
                _alt_chg = top.get("avg_alt_change_24h") if isinstance(top, dict) else None
                # not_run = 档位设计跳过，不是故障；别用 ⚠️ 让正常降级看起来像坏了
                _icon = "✅" if cg_status in ("live", "cache") else (
                    "⏭️" if cg_status == "not_run" else "⚠️")
                if _btc_chg is None and _alt_chg is None:
                    if cg_status == "not_run":
                        print(f"  {_icon} CoinGecko Top10: 当前档位跳过（需 cg_pro 步）")
                    else:
                        print(f"  {_icon} CoinGecko Top10: 状态{cg_status}·本轮未采到有效字段")
                else:
                    _btc_txt = f"{float(_btc_chg):+.1f}%" if _btc_chg is not None else "—"
                    _alt_txt = f"{float(_alt_chg):+.1f}%" if _alt_chg is not None else "—"
                    print(f"  {_icon} CoinGecko Top10: {top.get('rotation','?')} | 状态{cg_status} | BTC {_btc_txt} vs Alt {_alt_txt}")
            except Exception:
                pass
            try:
                trend = cg_trending() if "cg_pro" in pipeline_steps else {}
                _register_source_record(engine_data, "cg_trending", trend, symbol=symbol, status="not_run" if "cg_pro" not in pipeline_steps else None)
                engine_data["cg_trending"] = trend
                hot = ", ".join(c["symbol"] for c in trend.get("trending", [])[:3]) or "无"
                trend_status = trend.get("_source_status", "not_run") if isinstance(trend, dict) else "unavailable"
                # not_run = 档位设计跳过（同 CoinGecko Top10 的处理，别让正常降级像故障）
                if trend_status == "not_run":
                    print(f"  ⏭️ Trending: 当前档位跳过（需 cg_pro 步）")
                else:
                    _t_icon = "✅" if trend_status in ("live", "cache") else "⚠️"
                    print(f"  {_t_icon} Trending: {hot} | 状态{trend_status}")
            except Exception:
                pass
            
            # Macro overview (SPX/VIX/US10Y/DXY) — full模式才刷新
            try:
                from multi_source_collector import macro_overview
                macro = macro_overview() if "macro" in pipeline_steps else {}
                _register_source_record(engine_data, "macro_overview", macro, symbol=symbol, status="not_run" if "macro" not in pipeline_steps else None)
                engine_data["macro"] = macro
                # 采不到就直说：不再用默认值打印出一个看起来正常的「中性 | VIX 20」。
                _m_status = str(macro.get("_source_status") or ("not_run" if not macro else "unavailable"))
                if macro.get("vix_level") is None and not macro.get("spx"):
                    if _m_status == "not_run":
                        print(f"  ⏭️ 宏观: 当前档位跳过（需 macro 步）")
                    else:
                        print(f"  ⚠️ 宏观[{_m_status}]: 本轮未采到有效字段，需查源")
                else:
                    _vix = macro.get("vix_level")
                    _spx = (macro.get("spx") or {}).get("change_pct")
                    print(f"  📊 宏观[{_m_status}]: {macro.get('sentiment') or '未判定'} | "
                          f"VIX {_vix if _vix is not None else '—'} | "
                          f"SPX {f'{float(_spx):+.1f}%' if _spx is not None else '—'}")
            except Exception:
                pass
            
        except Exception as e:
            print(f"  ⚠️ CMC/Binance采集失败: {e}")
            engine_data["quality"] = "C"
            engine_data["grades"] = {"overall": "C"}
            engine_data["prices"] = {"primary": None, "source": "采集失败"}
    elif asset == "metal":
        try:
            import requests as _req
            from pathlib import Path as _P
            import sys as _s
            _scripts_dir = str(_P("D:/Hermes agent/scripts"))
            if _scripts_dir not in _s.path:
                _s.path.insert(0, _scripts_dir)
            from trading_system import price_consensus, gold_api_price
            import trading_system as _ts
            
            # ── 三源共识价格（OANDA + gold-api + 金十）──
            consensus = price_consensus(symbol)
            price = consensus.get("price")
            quality = consensus.get("quality", "B")
            confidence = consensus.get("confidence", 70)
            source_label = consensus.get("source", "多源")
            
            if price and price > 0:
                engine_data["prices"] = {"primary": price, "source": source_label}
                engine_data["binance_spot"] = {
                    "price": price, "24h_high": price * 1.005,
                    "24h_low": price * 0.995, "percent_change_24h": 0
                }
                engine_data["quality"] = quality
                engine_data["grades"] = {"overall": quality, "confidence": confidence}
                print(f"  ✅ XAU: ${price:,.0f} [{quality}] ({source_label})")
                
                # ── 金十 Quote 原始数据（用于获取24h高/低/今开）──
                jin10_raw = None
                for src in consensus.get("sources", []):
                    if src.get("source") == "金十Quote" and src.get("raw"):
                        jin10_raw = src["raw"]
                        break
                if jin10_raw:
                    try:
                        j_high = float(jin10_raw.get("high", 0))
                        j_low = float(jin10_raw.get("low", 0))
                        j_open = float(jin10_raw.get("open", 0))
                        if j_high > 0: engine_data["binance_spot"]["24h_high"] = j_high
                        if j_low > 0: engine_data["binance_spot"]["24h_low"] = j_low
                        if j_open > 0:
                            pct = round((price - j_open) / j_open * 100, 2)
                            engine_data["binance_spot"]["percent_change_24h"] = pct
                        print(f"  📊 金十24h: 高{j_high:.0f} 低{j_low:.0f} 开{j_open:.2f}")
                    except Exception:
                        pass
            else:
                engine_data["prices"] = {"primary": None, "source": "XAU多源采集失败"}
                engine_data["quality"] = "C"
                engine_data["grades"] = {"overall": "C"}
            
            # ── DXY from Yahoo ──
            try:# TANGXI-DISABLED-NON-BINANCE 2026-08-29: DXY from Yahoo disabled

                dxy_r = _req.get(
                    # TANGXI-DISABLED-NON-BINANCE 2026-08-29: "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=5d",
                    timeout=5, headers={"User-Agent": "Mozilla/5.0"}
                )
                if dxy_r.status_code == 200:
                    dxy_data = dxy_r.json()
                    dxy_price = dxy_data["chart"]["result"][0]["meta"]["regularMarketPrice"]
                    engine_data["dxy"] = dxy_price
                    print(f"  ✅ DXY: {dxy_price:.2f}")
            except Exception:
                engine_data["dxy"] = None
                engine_data["_dxy_error"] = "DXY实时源不可用"
            
            # ── FMP macro: SPX/VIX/US10Y + EURUSD（full模式才刷新）──
            try:
                from multi_source_collector import macro_overview, fmp_forex
                macro = macro_overview() if "macro" in pipeline_steps else {}
                _register_source_record(engine_data, "macro_overview", macro, symbol=symbol, status="not_run" if "macro" not in pipeline_steps else None)
                engine_data["macro"] = macro
                _m_status = str(macro.get("_source_status") or ("not_run" if not macro else "unavailable"))
                if macro.get("vix_level") is None and not macro.get("spx") and not macro.get("us10y"):
                    print(f"  📊 宏观[{_m_status}]: 本轮未采到有效字段")
                else:
                    _vix = macro.get("vix_level")
                    _u10 = (macro.get("us10y") or {}).get("price")
                    _spx = (macro.get("spx") or {}).get("change_pct")
                    print(f"  📊 宏观[{_m_status}]: {macro.get('sentiment') or '未判定'} | "
                          f"VIX {_vix if _vix is not None else '—'} | "
                          f"US10Y {_u10 if _u10 is not None else '—'}% | "
                          f"SPX {f'{float(_spx):+.1f}%' if _spx is not None else '—'}")
            except Exception:
                pass
            try:
                eur = fmp_forex("EURUSD")
                _register_source_record(engine_data, "eurusd", eur, symbol="EURUSD")
                engine_data["eurusd"] = eur
                if eur.get("price"):
                    print(f"  💱 EURUSD: {eur['price']:.4f} ({eur.get('change_pct',0):+.2f}%)")
            except Exception as _eur_exc:
                _register_source_record(engine_data, "eurusd", None, status="unavailable", error=_eur_exc, symbol="EURUSD")
                pass
            
            # ── K线：基于 gold-api/Jin10 真实数据构建（TV SVP v10 对 XAU 为已知限制）──
            klines_dict = engine_data.setdefault("klines", {})
            if price and price > 0:
                # P2修复：优先用 TV MCP 现场读取的真实 XAU 状态；无则占位推算并明确降级标注
                xau_tv_state_path = ROOT / "data" / "xau_tv_state.json"
                tv_xau = None
                if xau_tv_state_path.exists() and xau_contract.get("usable"):
                    try:
                        tv_xau = json.loads(xau_tv_state_path.read_text(encoding="utf-8"))
                    except Exception:
                        tv_xau = None
                if tv_xau:
                    xau_tv_note = "XAU TV MCP现场读取(OANDA:XAUUSD 5/15/1h/4h真实结构)"
                    engine_data["_xau_tv_limitation"] = xau_tv_note
                    # 用 TV 真实高低覆盖占位（v9.7: 加入1D日线背景，供"自上而下确认"；
                    # state用key"1D"，引擎层统一建为渲染器期望的"D"键）
                    for tf in ["1D", "4h", "1h", "15m", "5m"]:
                        tvd = (tv_xau.get("timeframes") or {}).get(tf) or {}
                        if tvd.get("high") and tvd.get("low"):
                            _cp = tvd.get("change_pct", 0)
                            _dir = "偏多" if _cp > 0.3 else "偏空" if _cp < -0.3 else "震荡"
                            _k = "D" if tf == "1D" else tf
                            klines_dict[_k] = {
                                "close": tvd.get("close", price),
                                "high": tvd["high"], "low": tvd["low"],
                                "open": tvd.get("open", price),
                                "change_pct": _cp,
                                "poc": tvd.get("poc", price),
                                "vah": tvd.get("vah", price), "val": tvd.get("val", price),
                                # v9.7: XAU TV现场真实方向（用 change_pct 合成，语义与BTC _kl_desc一致）
                                "direction": _dir,
                                "description": f"TV现场·XAU {tf} {_dir}·{_cp:+.1f}%",
                            }
                    print(f"  📊 XAU K线: TV MCP现场读取 {int(price)} · 五周期真实结构已覆盖引擎占位")
                else:
                    xau_tv_note = "⚠️XAU使用gold-api+金十占位推算(非TV现场)；OANDA:XAUUSD程序化读数需xau_tv_sync.py补真"
                    engine_data["_xau_tv_limitation"] = xau_tv_note
                    engine_data["_xau_placeholder"] = True  # 标记占位，供状态降级
                    # 从金十/Jin10取24h高低
                    j_high = engine_data.get("binance_spot", {}).get("24h_high", price * 1.005)
                    j_low = engine_data.get("binance_spot", {}).get("24h_low", price * 0.995)
                    daily_range = j_high - j_low if j_high > j_low else price * 0.01
                    # 推算Value Area
                    vah = min(price + daily_range * 0.35, j_high)
                    val = max(price - daily_range * 0.35, j_low)
                    poc = price
                    for tf in ["5m", "15m", "1h", "4h"]:
                        tf_scale = {"5m": 0.15, "15m": 0.25, "1h": 0.50, "4h": 1.0}.get(tf, 0.5)
                        tf_range = daily_range * tf_scale
                        klines_dict[tf] = {
                            "close": price, "high": price + tf_range * 0.6, "low": max(price - tf_range * 0.4, j_low),
                            "open": price - tf_range * 0.1, "change_pct": 0,
                            "poc": poc, "vah": vah, "val": val,
                            "direction": "占位推算",
                            "description": f"gold-api·金十 现货{int(price)} | 24h高{int(j_high)} 低{int(j_low)} | ⚠️非TV现场",
                        }
                    print(f"  📊 XAU K线: gold-api+金十 现货{int(price)} · 日内高{int(j_high)} 低{int(j_low)} · VAH{int(vah)} VAL{int(val)} · ⚠️占位")
                engine_data["_xau_klines_pending"] = False
            else:
                for tf in ["5m", "15m", "1h", "4h"]:
                    klines_dict[tf] = {
                        "close": 0, "high": 0, "low": 0, "open": 0, "change_pct": 0,
                        "poc": 0, "vah": 0, "val": 0,
                        "direction": "缺失",
                        "description": f"XAU {tf} 无价格数据",
                    }
                engine_data["_xau_klines_pending"] = True
            
        except Exception as e:
            print(f"  ⚠️ XAU: {e}")
            engine_data["quality"] = "C"
            engine_data["grades"] = {"overall": "C"}
    elif asset in {"stock", "forex", "futures"}:
        # 非加密市场统一走按资产路由的数据矩阵，禁止只保存Key却不进入驾驶舱。
        try:
            from multi_source_collector import gather_all
            routed = gather_all(asset, symbol)
            engine_data["_asset_sources"] = routed
            if isinstance(routed.get("_source_records"), dict):
                engine_data["_source_records"] = dict(routed["_source_records"])
            for key in ("macro", "fmp", "av", "td", "td_tech", "massive", "tushare"):
                if routed.get(key):
                    engine_data[key] = routed[key]
            price_candidates = []
            for key in ("tushare", "fmp", "av", "td", "massive"):
                value = routed.get(key)
                if isinstance(value, dict):
                    price_candidates.append((key, _decision_float(value.get("price") or value.get("close"))))
            source, price = next(((key, value) for key, value in price_candidates if value > 0), ("", 0.0))
            engine_data["prices"] = {"primary": price or None, "source": source or "数据待刷新"}
            engine_data["quality"] = "A-" if price > 0 and len([v for v in routed.values() if isinstance(v, dict) and v and "_error" not in v]) >= 3 else "B" if price > 0 else "C"
            engine_data["grades"] = {"overall": engine_data["quality"]}
            print(f"  {'✅' if price else '⚠'} {asset}: {price if price else '价格待刷新'} · 来源{source or '无'} · 已接{','.join(k for k in routed if k not in {'symbol','asset_class','time'})}")
        except Exception as e:
            engine_data["quality"] = "C"
            engine_data["grades"] = {"overall": "C"}
            engine_data["_asset_source_error"] = str(e)[:160]
            print(f"  ⚠️ {asset}多源采集失败: {e}")

    # Re-apply TV structure after the asset collectors have populated their
    # fallback rows.  The merge is field-aware: TV owns value-area/action-grid
    # fields, while Binance/gold sources retain real OHLCV when TV lacks it.
    _merge_tv_five_tf_into_engine(engine_data, tv_five_tf)
    
    # v2.1: 实时事件禁做（Jin10日历 + 宏观过滤）；只在路由包含macro时刷新。
    print("② 引擎运算...")
    _banned_live, _ban_reason = False, ""

    # Session 策略诊断
    try:
        from session_strategy import get_session, get_session_summary
        _session = get_session()
        engine_data["_session"] = _session
        print(f"  🕐 Session: {_session['name']} | Strategy: {_session['strategy']} | Bonus: {_session.get('confidence_bonus',0):+.2f}")
    except Exception:
        engine_data["_session"] = {"key": "default", "name": "未知", "strategy": "default"}
    
    # Jin10 实时事件禁做
    if "macro" in pipeline_steps:
        try:
            from event_ban_live import check_event_ban_live
            _banned_live, _ban_reason = check_event_ban_live(symbol)
            _register_source_record(
                engine_data,
                "event_ban_live",
                {"banned": _banned_live, "reason": _ban_reason},
                status="live",
                captured_at=datetime.now(TZ),
                symbol=symbol,
            )
            if _banned_live:
                print(f"  🚫 事件禁做: {_ban_reason}")
        except Exception as _event_exc:
            _register_source_record(
                engine_data,
                "event_ban_live",
                None,
                status="unavailable",
                error=_event_exc,
                symbol=symbol,
            )
            _banned_live = False
            _ban_reason = ""
    else:
        _register_source_record(engine_data, "event_ban_live", None, status="not_run", symbol=symbol)
        print("  ⏭️ 事件日历: 当前档位跳过")

    # 宏观过滤器
    if "macro" in pipeline_steps:
        try:
            from macro_filter import fetch_macro_snapshot, macro_filter_bias
            _macro = fetch_macro_snapshot()
            engine_data["_macro"] = _macro
            _register_source_record(engine_data, "macro", _macro, symbol=symbol)
            _macro_bias, _macro_strength, _macro_label = macro_filter_bias(_macro)
            print(f"  🌍 宏观: {_macro_label} (强度{_macro_strength})")
        except Exception as _macro_exc:
            _register_source_record(
                engine_data,
                "macro",
                None,
                status="unavailable",
                error=_macro_exc,
                symbol=symbol,
            )
            _macro_bias, _macro_strength, _macro_label = "neutral", 0.0, "宏观数据不可用"
            engine_data["_macro"] = {}
    else:
        inherited_macro = (context or {}).get("macro") if isinstance(context, dict) else None
        engine_data["_macro"] = inherited_macro if isinstance(inherited_macro, dict) else {}
        _register_source_record(
            engine_data,
            "macro",
            engine_data["_macro"],
            status="inherited" if isinstance(inherited_macro, dict) and inherited_macro else "not_run",
            symbol=symbol,
        )
        _macro_bias, _macro_strength, _macro_label = "neutral", 0.0, "当前档位未刷新宏观"
        print("  ⏭️ 宏观过滤: 当前档位跳过")
    
    # v2.0: 合并TV数据到引擎（读取 btc_tv_data.json 缓存，由 TV 数据桥每2分钟更新）
    try:
        _ticker = symbol.upper().replace("USDT", "").replace(".P", "")
        _tv_path = Path.home() / f"AppData/Local/hermes/data/{_ticker}_tv_data.json"
        _crypto_symbol = symbol.upper().endswith("USDT") or symbol.upper().endswith(".P")
        if not _tv_path.exists() and _crypto_symbol and _ticker == "BTC":
            _tv_path = Path.home() / "AppData/Local/hermes/data/btc_tv_data.json"
        elif not _tv_path.exists():
            _tv_path = None
        if _tv_path and _tv_path.exists():
            with open(_tv_path, "r", encoding="utf-8") as _tf:
                _tv_raw = json.load(_tf)
            engine_data["tv"] = {
                "vwap": float(_tv_raw.get("vwap") or 0),
                "vah": float(_tv_raw.get("vah") or 0),
                "val": float(_tv_raw.get("val") or 0),
                "poc": float(_tv_raw.get("poc") or 0),
                "band1_high": float(_tv_raw.get("band1_high") or 0),
                "band1_low": float(_tv_raw.get("band1_low") or 0),
                "band2_high": float(_tv_raw.get("band2_high") or 0),
                "band2_low": float(_tv_raw.get("band2_low") or 0),
                "w_vwap": float(_tv_raw.get("w_vwap") or 0),
                "m_vwap": float(_tv_raw.get("m_vwap") or 0),
                "ema9": float(_tv_raw.get("ema9") or 0),
                "ema21": float(_tv_raw.get("ema21") or 0),
                "ema34": float(_tv_raw.get("ema34") or 0),
                "ema55": float(_tv_raw.get("ema55") or 0),
                "cvd": float(_tv_raw.get("cvd") or 0),
                "cvd_slope": float(_tv_raw.get("cvd_slope") or 0),
                "dopen": float(_tv_raw.get("dopen") or 0),
            }
            print(f"  ✅ TV数据合并: VWAP {engine_data['tv']['vwap']:.1f} | VAH {engine_data['tv']['vah']:.1f} | VAL {engine_data['tv']['val']:.1f}")
            # v4.3: 行动格 v2 解码桥接 —— fetch_tv_data.cjs 现在直接写入
            # tv_grade/tv_conclusion/tv_entry/tv_stop/tv_target（行动格 v2 无 等级/处理 行，
            # 等级嵌在 结论 内）。把这些字段重组成下游 _parse_tv_dmi_table/_apply_tv_dmi_override
            # 期望的 等级|处理 行 + study values，旧消费链零改动即可吃到实时等级。
            _tv_grade = _tv_raw.get("tv_grade")
            if _tv_grade:
                _dmi_rows = [
                    f"等级 | {_tv_grade}",
                    f"处理 | {_tv_raw.get('tv_treatment') or _tv_raw.get('tv_conclusion') or '?'}",
                    f"背景 | {_tv_raw.get('tv_direction') or '?'}",
                    f"位置 | {_tv_raw.get('tv_entry') or '?'}",
                    f"执行 | 进:{_tv_raw.get('tv_entry') or '?'} 损:{_tv_raw.get('tv_stop') or '?'} 标:{_tv_raw.get('tv_target') or '?'}",
                ]
                _study_vals = []
                for _t, _k in [("S VWAP", "vwap"), ("VAH Price", "vah"), ("VAL Price", "val"),
                               ("POC Price", "poc"), ("EMA 9", "ema9"), ("EMA 21", "ema21"),
                               ("EMA 34", "ema34"), ("EMA 55", "ema55")]:
                    _v = _tv_raw.get(_k)
                    if _v:
                        _study_vals.append({"name": "SVP+ICT+VWAP+CVD", "values": {_t: _v}})
                engine_data["_tv_pine"] = {
                    "studies": _study_vals,
                    "tables": [{"name": "SVP+ICT+VWAP+CVD", "tables": [{"rows": _dmi_rows}]}],
                }
                print(f"  ✅ 行动格v2解码: 等级={_tv_grade} | 进场={_tv_raw.get('tv_entry') or '—'} | 止损={_tv_raw.get('tv_stop') or '—'} | 目标={_tv_raw.get('tv_target') or '—'}")
    except Exception as _tve:
        print(f"  ⚠️ TV数据加载: {_tve}")
    
    # ── VWAP/EMA/CVD 综合引擎（Step 1 数据后处理）──
    _vwap_ema_result = None
    try:
        from vwap_ema_cvd_engine import vwap_ema_cvd_summary
        # P1b: 优先用 _raw_klines_multi 原始 Binance OHLCV（futures_klines 未填充时）
        _klines_raw_for_ve = engine_data.get("futures_klines", []) or []
        if not _klines_raw_for_ve:
            _raw_multi_ve = engine_data.get("_raw_klines_multi") or {}
            _raw_15m_ve = _raw_multi_ve.get("15m") or []
            if isinstance(_raw_15m_ve, list) and _raw_15m_ve:
                _klines_raw_for_ve = [
                    {"open": float(c[1]), "high": float(c[2]), "low": float(c[3]),
                     "close": float(c[4]), "volume": float(c[5])}
                    for c in _raw_15m_ve
                    if isinstance(c, (list, tuple)) and len(c) >= 6
                ]
        if isinstance(_klines_raw_for_ve, dict):
            # 有时是 {tf: {closes:[], ...}} 字典格式，尝试取最大数据集
            _biggest = max(_klines_raw_for_ve.values(), key=lambda v: len(v.get("closes", [])) if isinstance(v, dict) else 0, default={})
            _klines_raw_for_ve = _biggest.get("closes", []) if isinstance(_biggest, dict) else []
        if _klines_raw_for_ve:
            _vwap_ema_result = vwap_ema_cvd_summary(symbol, _klines_raw_for_ve)
            _ema = _vwap_ema_result.get("ema", {}) or {}
            _cv = "买" if _vwap_ema_result.get("vwap", {}).get("price_above") else "卖"
            print(f"  ✅ VWAP/EMA引擎：快线{_ema.get('9','?')}·慢线{_ema.get('55','?')}·CVD方向{_cv}")
        else:
            _vwap_ema_result = _tv_vwap_ema_fallback(symbol)
            if _vwap_ema_result:
                _ema = _vwap_ema_result.get("ema", {}) or {}
                _cv = "买" if _vwap_ema_result.get("vwap", {}).get("price_above") else "卖"
                print(f"  ✅ VWAP/EMA引擎：快线{_ema.get('9','?')}·慢线{_ema.get('55','?')}·CVD方向{_cv}·TV MCP")
            else:
                print("  ⏭ VWAP/EMA引擎：无K线或TV Data Window数据，跳过")
        # 2026-09-13：回写引擎结果供 render_card_locked 复用（EMA 上卡接线）。
        # schema 兼容：summary 引擎与 TV MCP fallback 字段不同，非空即回写。
        if isinstance(_vwap_ema_result, dict) and (_vwap_ema_result.get("vwap") or _vwap_ema_result.get("ema")):
            engine_data["_vwap_ema"] = _vwap_ema_result
    except Exception as _vee:
        print(f"  ⚠️ VWAP/EMA引擎：{_vee}")
    
    merged = {}
    results = []

    # ═══ 黄金宏观桥接（仅XAU）═══
    try:
        if 'XAU' in symbol.upper() and "gold_macro" in pipeline_steps:
            from jin10_gold_bridge import gold_macro_context
            gold_macro = gold_macro_context()
            _register_source_record(
                engine_data,
                "gold_macro",
                gold_macro,
                status=None if gold_macro else "unavailable",
                error=None if gold_macro else "empty_payload",
                symbol=symbol,
            )
            if gold_macro:
                print("  ✅ 金十黄金宏观已注入")
                engine_data['gold_macro'] = gold_macro
    except Exception as _gme:
        _register_source_record(engine_data, "gold_macro", None, status="unavailable", error=_gme, symbol=symbol)
        print(f"  ⚠️ 金十黄金宏观桥接: {_gme}")

    try:
        from multi_model_engine import (
            run_all_models, merge_directions, check_event_ban, call_grok_validation, model_scope,
        )
        results = run_all_models(
            engine_data,
            symbol,
            model_names=model_scope(effective_mode),
            include_confirmations=effective_mode == "full",
        )
        
        # v2.1: 事件禁做 — 优先使用 Jin10 实时日历，兜底关键词检查
        if _banned_live:
            banned, ban_reason = True, _ban_reason
        else:
            banned, ban_reason = check_event_ban(engine_data, symbol)
        
        # 宏观过滤：risk_off 时额外扣分
        if _macro_bias == "short" and _macro_strength > 0.2:
            if not banned:
                ban_reason = f"宏观risk_off({_macro_label}) → 半仓"
            merged = merge_directions(results, event_ban=banned, event_ban_reason=ban_reason)
            # 宏观偏空时压制做多方向
            if merged.get("bias") == "偏多":
                merged["bias"] = "方向不明/震荡"
                merged["global_confidence"] = round(merged["global_confidence"] * 0.7, 3)
                merged["action"] = "⚠宏观risk_off→B等待"
        else:
            merged = merge_directions(results, event_ban=banned, event_ban_reason=ban_reason)
        print(f"  ✅ Bias: {merged['bias']} | Conf: {merged['global_confidence']:.3f} | n/5: {merged.get('confidence_5','?')}")
    except Exception as e:
        print(f"  ❌ Engine: {e}")

    # ═══ COT持仓摘要（仅XAU）═══
    try:
        if 'XAU' in symbol.upper() and "cron_read" in pipeline_steps:
            from cot_bridge import cot_summary_line
            cot = cot_summary_line()
            _register_source_record(
                engine_data,
                "cot",
                cot,
                status=None if cot else "unavailable",
                error=None if cot else "empty_payload",
                symbol=symbol,
            )
            if cot:
                print(f"  ✅ COT黄金持仓：{cot}")
                engine_data['cot_line'] = cot
    except Exception as _ce:
        _register_source_record(engine_data, "cot", None, status="unavailable", error=_ce, symbol=symbol)
        print(f"  ⚠️ COT黄金持仓桥接: {_ce}")

    # ═══ Step 3: Grok催化剂验证（quick/inherit跳过）═══
    print("③ Grok催化剂...")
    grok = {}
    try:
        grok = (call_grok_validation(symbol, merged, results,
                                     price=engine_data.get("prices", {}).get("primary", 0),
                                     data=engine_data)
                if effective_mode == "full" and "x_sent" in pipeline_steps
                else {"skipped": f"{effective_mode}模式"})
        if grok.get("skipped"):
            print(f"  ⏭️ Grok跳过: {grok['skipped']}")
        elif grok.get("error"):
            print(f"  ⚠️ Grok错误: {grok['error'][:60]}")
        elif grok.get("agree"):
            print("  ✅ Grok: 催化剂/盲点交叉验证通过（不改变执行置信）")
        else:
            engine_data["x_model_caution"] = {
                "direction": grok.get("grok_direction", ""),
                "confidence": grok.get("grok_confidence", 0),
                "divergence": grok.get("divergence", ""),
                "blindspot": grok.get("blindspot", ""),
            }
            print(f"  ⚠️ Grok分歧已记录，仅作风险提示 | 方向: {grok.get('grok_direction','?')} {grok.get('grok_confidence',0):.3f}")
    except Exception as e:
        print(f"  ⚠️ Grok: {e}")
    
    # ═══ Step 4: 市场热点搜索 ═══
    print("④ 市场热点...")
    search_sent = ""
    try:
        from sentiment_search import sentiment_line
        search_sent = sentiment_line(symbol) if "x_sent" in pipeline_steps else ""
        print(f"  ✅ {search_sent}")
    except Exception as e:
        print(f"  ⚠️ 搜索: {e}")
    
    # ═══ Step 5: 社区情绪 ═══
    print("⑤ 社区情绪...")
    community = ""
    if asset == "crypto":
        try:
            from coingecko_collector import community_dashboard
            if "cg_pro" in pipeline_steps:
                community = community_dashboard()
                _register_source_record(engine_data, "cg_community", community, symbol=symbol)
                print(f"  ✅ {community[:80]}...")
            else:
                _register_source_record(engine_data, "cg_community", None, status="not_run", symbol=symbol)
                print("  ℹ️ 社区: 当前档位跳过CoinGecko")
        except Exception as e:
            _register_source_record(engine_data, "cg_community", None, status="unavailable", error=e, symbol=symbol)
            print(f"  ⚠️ 社区: {e}")
    else:
        community = search_sent
        print("  ℹ️ 社区: 非加密跳过CoinGecko加密社区面板·使用本品种热点")

    # v2.1: Polymarket 预测市场情绪（当前桥接源只采 BTC/crypto，非加密禁用，避免跨资产误导）
    if asset == "crypto" and "macro" in pipeline_steps:
        try:
            import importlib, sys as _sys
            _sys.path.insert(0, str(ROOT / "scripts"))
            from polymarket_bridge import get_polymarket_line
            poly_line = get_polymarket_line()
            _register_source_record(engine_data, "polymarket", poly_line, symbol=symbol)
            print(f"  📊 {poly_line}")
            engine_data["poly_sentiment"] = poly_line
        except Exception as e:
            _register_source_record(engine_data, "polymarket", None, status="unavailable", error=e, symbol=symbol)
            engine_data["poly_sentiment"] = ""
            print(f"  ⚠️ Poly: {e}")
    else:
        _register_source_record(engine_data, "polymarket", None, status="not_run", symbol=symbol)
        engine_data["poly_sentiment"] = ""
        print("  ℹ️ Poly: 非加密跳过BTC/crypto预测市场桥")

    # ═══ 外汇利差（仅外汇品种）═══
    if "forex_rate" in pipeline_steps and any(p in symbol.upper() for p in ['EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'NZD', 'CAD']):
        try:
            from forex_rate import forex_card_line
            fx_line = forex_card_line(symbol)
            _register_source_record(
                engine_data,
                "forex_rate",
                fx_line,
                status=None if fx_line else "unavailable",
                error=None if fx_line else "empty_payload",
                symbol=symbol,
            )
            if fx_line:
                print(f"  ✅ {fx_line}")
                engine_data['forex_rate'] = fx_line
        except Exception as e:
            _register_source_record(engine_data, "forex_rate", None, status="unavailable", error=e, symbol=symbol)
            print(f"  ⚠️ 外汇利差: {e}")

    # ═══ 期权链（加密+股票）═══
    if "options_chain" in pipeline_steps and any(s in symbol.upper() for s in ['BTC', 'ETH', 'AAPL', 'TSLA', 'MSFT', 'AMZN', 'GOOGL', 'NVDA', 'META']):
        try:
            from options_chain import options_card_line
            opt_line = options_card_line(symbol)
            _register_source_record(
                engine_data,
                "options_chain",
                opt_line,
                status=None if opt_line else "unavailable",
                error=None if opt_line else "empty_payload",
                symbol=symbol,
            )
            if opt_line:
                print(f"  ✅ {opt_line}")
                engine_data['options_line'] = opt_line
        except Exception as e:
            _register_source_record(engine_data, "options_chain", None, status="unavailable", error=e, symbol=symbol)
            print(f"  ⚠️ 期权链: {e}")

    # ═══ X情绪上下文读取 ═══
    try:
        if "x_sent" in pipeline_steps and asset == "crypto":
            _x_path = ROOT / "data" / "x_sentiment_context.json"
            if _x_path.exists():
                import json as _xj
                _x_data = _xj.loads(_x_path.read_text(encoding="utf-8"))
                # 2026-09-13 审计：该文件的生产者早已消失（停在 2026-07-15），旧实现却仍用
                # ✅ 打印那时的恐贪 25 / 市占 56.3% —— 比「没有」更容易误导。现在按语义
                # 时间戳判新鲜度：陈旧就明确写「本轮不采用」，不再把旧值当当前值展示。
                try:
                    from source_health import payload_timestamp
                    _x_ts = payload_timestamp(_x_data)
                except Exception:
                    _x_ts = None
                _x_age_h = ((datetime.now(TZ) - _x_ts.astimezone(TZ)).total_seconds() / 3600
                            if _x_ts is not None else None)
                _x_fresh = _x_age_h is not None and _x_age_h <= 6.0
                _fg = _x_data.get("fear_greed") or {}
                _gm = _x_data.get("global_market") or {}
                engine_data["x_sentiment"] = _x_data
                if _x_fresh:
                    _btc_dom = _gm.get("btc_dominance")
                    _dom_txt = (f"{float(_btc_dom):.1f}%"
                                if isinstance(_btc_dom, (int, float)) and _btc_dom else "—")
                    _note = _x_data.get("x_note") or {}
                    _note_txt = (f" · X叙述(仅情绪·不改裁决): {str(_note.get('text'))[:60]}"
                                 if _note.get("text") else "")
                    _q_str = " | ".join((_x_data.get("suggested_x_queries") or [])[:2]) or "无"
                    print(f"  ✅ X情绪: BTC恐贪{_fg.get('value', '?')}({_fg.get('classification', '?')})"
                          f" · 市占{_dom_txt} · {_q_str}{_note_txt}")
                    _register_source_record(engine_data, "x_sentiment", _x_data, symbol=None,
                                            max_age_hours=6.0)
                else:
                    _age_txt = f"{_x_age_h:.1f}h前" if _x_age_h is not None else "无时间戳"
                    print(f"  ⚠️ X情绪: 上下文陈旧({_age_txt})·本轮不采用（旧值不展示）")
                    _register_source_record(engine_data, "x_sentiment", _x_data, symbol=None,
                                            status="stale_cache",
                                            error=f"context_stale:{_age_txt}")
            else:
                _register_source_record(engine_data, "x_sentiment", None, status="unavailable", error="cache_missing", symbol=None)
                print(f"  ⚠️ X情绪: 缓存文件不存在")
        elif "x_sent" in pipeline_steps:
            engine_data["x_sentiment"] = f"{symbol}: {search_sent} · 非加密不采用BTC情绪缓存"
            _register_source_record(engine_data, "x_sentiment", engine_data["x_sentiment"], status="live", captured_at=datetime.now(TZ), symbol=symbol)
            print(f"  ℹ️ X情绪: 非加密不采用BTC缓存·使用本品种热点/宏观替代")
        else:
            engine_data["x_sentiment"] = {"_source_status": "not_run", "reason": f"{effective_mode}模式未路由x_sent"}
            _register_source_record(engine_data, "x_sentiment", None, status="not_run", symbol=symbol)
            print("  ⏭️ X情绪: 当前档位跳过")
    except Exception as _xe:
        _register_source_record(engine_data, "x_sentiment", None, status="unavailable", error=_xe, symbol=symbol)
        print(f"  ⚠️ X情绪: {_xe}")

    # ═══ Step 6: 市场体制由闭柱OHLCV+TV结构在决策闭环内实时判定 ═══
    print("⑥ 市场体制...")
    regime_name = None
    print("  ✅ 实时体制：等待闭柱特征构建，禁止固定VIX/演示波动率")

    # ═══ Step 7: 锁定排版输出 ═══
    print("⑥.① Binance数据采集...")
    if _asset_class(symbol) == "crypto":
        if not engine_data.get("_binance_data_collected"):
            _collect_binance_data(engine_data, symbol)
            engine_data["_binance_data_collected"] = True
        else:
            print("  ℹ️ Binance数据已在Step 1采集，跳过重复请求")
        _cvd_value = engine_data.get("cvd")
        _register_source_record(
            engine_data,
            "cvd",
            _cvd_value,
            status="live" if _cvd_value else "unavailable",
            captured_at=datetime.now(TZ) if _cvd_value else None,
            symbol=symbol,
        )
        if engine_data.get("cvd", {}).get("direction"):
            print(f"  ✅ CVD {engine_data['cvd']['direction']} {engine_data['cvd'].get('quality','?')} | Taker {engine_data.get('taker',{}).get('direction','?')} | Funding {engine_data.get('funding',{}).get('rate_pct','?')}")
    else:
        print("  ℹ️ 非加密品种：跳过Binance合约Funding/Taker/CVD采集")
        # Do not let generic/stale engine fields bleed crypto-only flow into
        # non-crypto cards after the collector was intentionally skipped.
        cvd_dir = ""
        taker_dir = ""
        taker_ratio = ""
        funding_rate = ""
        for _crypto_key in ("cvd", "taker", "funding", "oi"):
            engine_data.pop(_crypto_key, None)
        # 2026-09-13（用户批准）：XAU 单独接 Binance 黄金合约逐笔 CVD 作辅助源。
        # 来源明标「Binance XAUUSDT 黄金合约」——不冒充 OANDA 现货；数据存独立键
        # （gold_contract_cvd，不进任何加密评分链），仅展示/审计可见；失败不阻断。
        if "XAU" in str(symbol).upper() and "cvd" in pipeline_steps:
            try:
                from cvd_aggtrades import get_cvd_aggtrades
                _gold_cvd = get_cvd_aggtrades("XAUUSDT")
                _g_dir = str(_gold_cvd.get("direction") or "")
                if _g_dir in ("买", "卖", "中性"):
                    engine_data["gold_contract_cvd"] = {
                        "direction": _g_dir,
                        "quality": _gold_cvd.get("quality", "A级"),
                        "cvd": _gold_cvd.get("cvd"),
                        "source": "binance_xauusdt_contract",
                    }
                    engine_data["_gold_contract_cvd"] = True
                    cvd_dir = _g_dir
                    _register_source_record(
                        engine_data, "cvd", engine_data["gold_contract_cvd"],
                        status="live", captured_at=datetime.now(TZ), symbol="XAUUSDT",
                    )
                    print(f"  ✅ 黄金合约CVD(Binance XAUUSDT·非OANDA): {_g_dir} {_gold_cvd.get('quality', '?')}")
                else:
                    _register_source_record(engine_data, "cvd", None, status="unavailable",
                                            error="empty_aggtrades", symbol="XAUUSDT")
                    print("  ⚠️ 黄金合约CVD: 本轮未采到")
            except Exception as _ge:
                _register_source_record(engine_data, "cvd", None, status="unavailable",
                                        error=_ge, symbol="XAUUSDT")
                print(f"  ⚠️ 黄金合约CVD: {_ge}")

    # ═══ 深度数据采集（仅加密品种）═══
    try:
        _sym = symbol.upper().replace(".P", "").split("-")[0].split(" ")[0]
        if not _sym.endswith("USDT"):
            print(f"  ℹ️ 深度: {_sym} 非加密品种·跳过")
            engine_data["depth"] = {"note": f"{_sym}非加密"}
        elif "depth" not in pipeline_steps:
            print(f"  ℹ️ 深度: {symbol} 当前档位跳过")
            engine_data["depth"] = {"note": "当前档位跳过"}
        else:
            from binance_public import fetch_spot
            _depth = fetch_spot("/api/v3/depth", {"symbol": _sym, "limit": 5}, timeout=10) or {}
            _bids = _depth.get("bids", [])
            _asks = _depth.get("asks", [])
            if _bids and _asks:
                _bp = float(_bids[0][0]); _bq = float(_bids[0][1])
                _ap = float(_asks[0][0]); _aq = float(_asks[0][1])
                _spread = _ap - _bp
                _spread_pct = _spread / _bp * 100
                print(f"  ✅ 深度: 买{_bp:,.1f}({_bq:.2f}) / 卖{_ap:,.1f}({_aq:.2f}) · 点差{_spread:.2f}({_spread_pct:.3f}%)")
                engine_data["depth"] = {"bid_price": _bp, "bid_qty": _bq, "ask_price": _ap, "ask_qty": _aq, "spread": _spread, "spread_pct": _spread_pct}
    except Exception as _de:
        print(f"  ⚠️ 深度: {_de}")
    _depth_value = engine_data.get("depth")
    _depth_requested = _asset_class(symbol) == "crypto" and "depth" in pipeline_steps
    _depth_ok = isinstance(_depth_value, dict) and _depth_value.get("bid_price") and _depth_value.get("ask_price")
    _register_source_record(
        engine_data,
        "depth",
        _depth_value,
        status="live" if _depth_ok else "unavailable" if _depth_requested else "not_run",
        captured_at=datetime.now(TZ) if _depth_ok else None,
        symbol=symbol,
    )

    print("⑦ 渲染锁定卡片...")
    meta = build_setup_metadata(symbol, merged, results, engine_data)

    # v4.4: 高级订单流确认（吸收/FVG/OB/相关性/共振门控）— 接通5个原闲置模块
    print("⑦.① 高级订单流确认...")
    adv = {"section": "", "gate": {}, "factors": {}}
    if effective_mode == "full":
        try:
            adv = _advanced_orderflow(symbol, engine_data, merged, meta)
            engine_data["_advanced"] = adv
            _g = adv.get("gate", {})
            _cc = adv.get("factors", {}).get("confluence_count", "?")
            print(f"  ✅ 共振{_cc}/6 | 门控{'放行' if _g.get('execute') else '否决'}·{_g.get('reason','?')}")
            # 门控否决 → 压制等级（不强制改方向，只提示）
            if not _g.get("execute") and _g.get("reason"):
                meta["gate_verdict"] = f"否决·{_g.get('reason')}"
            else:
                meta["gate_verdict"] = "放行"
            # 孤儿模块信号细化（吸收/相关性/元标记）
            try:
                _orp = adv.get("factors", {})
                _abs = _orp.get("absorption", {})
                _corr = _orp.get("corr_multiplier", 1.0)
                _abs_summary = _abs.get("summary", "正常") if isinstance(_abs, dict) else "正常"
                print(f"  ✅ 孤儿: corr={_corr} · {_abs_summary[:40]}")
            except Exception:
                pass
        except Exception as _ae:
            print(f"  ⚠ 高级订单流跳过: {_ae}")
    else:
        adv = {"section": "当前档位跳过高级订单流", "gate": {}, "factors": {}, "skipped": effective_mode}
        engine_data["_advanced"] = adv
        meta["gate_verdict"] = f"未运行·{effective_mode}模式"
        print(f"  ⏭️ 高级订单流: {effective_mode}模式不运行")

    _corr_value = (adv.get("factors") or {}).get("correlation") if isinstance(adv, dict) else None
    _corr_requested = effective_mode == "full" and "corr" in pipeline_steps
    _corr_ok = isinstance(_corr_value, dict) and _corr_value.get("status") == "ok"
    # 2026-09-13 审计修复：_corr_high 旧实现无生产赋值 → 门8 恒「相关≤0.7」。
    # 从真实相关性输出接线；不可解析时置 None（门8 不引用虚假相关结论）。
    try:
        _corr_r = float(str((_corr_value or {}).get("correlation_full")))
        engine_data["_corr_high"] = abs(_corr_r) >= 0.7 if _corr_ok else None
    except (TypeError, ValueError):
        engine_data["_corr_high"] = None
    _register_source_record(
        engine_data,
        "correlation",
        _corr_value,
        status="live" if _corr_ok else "unavailable" if _corr_requested else "not_run",
        captured_at=datetime.now(TZ) if _corr_ok else None,
        symbol=symbol,
    )

    # v6.9.14: TV DMI 决策表数据注入（从 TradingView MCP 读取）
    # v6.9.15b P0 fix: 优先读 engine_data._tv_pine（调用方注入）→
    #   回退读 data/tv_dmi_cache.json（cron agent 每5分钟更新）
    tv_dmi_data = {}
    try:
        tv_raw = engine_data.get("_tv_pine")
        # 2026-09-13：tv_dmi_cache.json 是 BTC cron 专属缓存。XAU 读它必然
        # 品种不匹配，只会制造误导性的失败状态（实测「品种不匹配 BINANCE:BTCUSDT.P」）；
        # XAU 的正路是下方 tv_live_XAUUSD/xau_tv_state 注入。
        if not tv_raw and _asset_class(symbol) != "gold":
            # 回退：读 cron agent 维护的本地缓存
            import json as _j
            cache_path = ROOT / "data" / "tv_dmi_cache.json"
            if cache_path.exists():
                cache = _j.loads(cache_path.read_text(encoding="utf-8"))
                cache_status = _tv_cache_status(cache, symbol)
                engine_data["_tv_cache_status"] = cache_status
                if not cache_status.get("usable"):
                    print(f"  ⚠ TV DMI缓存未采用: {cache_status.get('reason')}")
                    cache = None
                if cache is not None:
                    # 兼容两种缓存格式:
                    # 格式A(cron agent): {"tv_data": {"grade":..., "action":...}}
                    # 格式B(tv_signal_monitor): {"grade":..., "treatment":...}
                    grade = "C等待"
                    treatment = background = position = cvd_state = execution = risk = "?"
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
                        # v4.3: 行动格 v2 行标是 结论/方向/进场/止损/目标 而非 等级/处理。
                        # cache 顶层已有 grade + treatment；在 table_raw 前合成 等级|处理 行，
                        # 让 _parse_tv_dmi_table/_apply_tv_dmi_override 旧消费链无缝吃到等级。
                        _raw_rows = list(cache["table_raw"])
                        _synth = []
                        if grade:
                            _synth.append(f"等级 | {grade}")
                        if cache.get("treatment"):
                            _synth.append(f"处理 | {cache['treatment']}")
                        if _synth:
                            _raw_rows = _synth + _raw_rows
                        tables = [{"name": "SVP+ICT+VWAP+CVD", "tables": [{"rows": _raw_rows}]}]
                        # v9: 副指标数据（单独缓存或与 table_raw 并列）
                        if "sub_table_raw" in cache and isinstance(cache["sub_table_raw"], list):
                            tables.append({"name": "Volume Aggregated", "tables": [{"rows": cache["sub_table_raw"]}]})
                        tv_dmi_data = {
                            "studies": cache.get("studies", []) or _tv_cache_indicators_to_studies(cache),
                            "tables": tables,
                        }
                    else:
                        decision_tables = _tv_cache_decision_tables(cache, grade=grade, treatment=treatment)
                        if decision_tables:
                            tv_dmi_data = {
                                "studies": cache.get("studies", []) or _tv_cache_indicators_to_studies(cache),
                                "tables": decision_tables,
                            }
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
                    # 将缓存变量转换为 _tv_pine 格式（格式B/C未内联构建时走此处）
                    if not tv_dmi_data:
                        dmi_rows_data = [
                            f"等级 | {grade}",
                            f"处理 | {treatment}",
                            f"背景 | {background}",
                            f"位置 | {position}",
                            f"量能 | 量能普通",
                            f"CVD | {cvd_state}",
                            f"执行 | {execution}",
                            f"风控 | {risk}",
                        ]
                        tables = [{"name": "SVP+ICT+VWAP+CVD", "tables": [{"rows": dmi_rows_data}]}]
                        # v9: 副指标缓存注入
                        if "sub_table_raw" in cache and isinstance(cache["sub_table_raw"], list):
                            tables.append({"name": "Volume Aggregated", "tables": [{"rows": cache["sub_table_raw"]}]})
                        tv_dmi_data = {
                            "studies": cache.get("studies", []) or _tv_cache_indicators_to_studies(cache),
                            "tables": tables,
                        }
                    engine_data["_tv_pine"] = tv_dmi_data
                    tv_grade = cache.get("grade") if "grade" in cache else (cache.get("tv_data", {}).get("grade") if "tv_data" in cache else "?")
                    print(f"  ✅ TV DMI(缓存): grade={tv_grade}")
        elif tv_raw:
            # 2026-09-13：原 else 在 tv_raw=None（XAU 跳过 dmi 缓存且无前置注入）时
            # 会 None.get() 崩溃——改为 elif，无 tv_raw 时保持 tv_dmi_data 为空。
            studies = tv_raw.get("studies", [])
            tables = tv_raw.get("tables", [])
            # TV MCP 标准返回：tables 嵌套在 studies[].tables[] 内，顶层为空
            if not tables and studies:
                for _s in studies:
                    _inner = _s.get("tables", [])
                    if isinstance(_inner, list):
                        tables.extend(_inner)
            engine_data["_tv_pine"] = {"studies": studies, "tables": tables}
            tv_dmi_data = {"studies": studies, "tables": tables}
            print(f"  ✅ TV DMI(直连): {len(studies)} studies · {len(tables)} tables")
    except Exception as e:
        print(f"  ⚠ TV DMI跳过: {e}")
    
    # v9.6: TV实时数据注入 — 优先读tv_live.json(agent现场) → 回退tv_dmi_cache.json(cron)
    try:
        import json as _j2
        if engine_data.get("_xau_placeholder"):
            xau_tv_reason = str(engine_data.get("_xau_tv_limitation"))
            engine_data.setdefault("_tv_live_status", {})
            engine_data.setdefault("_tv_cache_status", {})
            if isinstance(engine_data.get("_tv_live_status"), dict):
                engine_data["_tv_live_status"]["usable"] = False
                engine_data["_tv_live_status"]["reason"] = xau_tv_reason
            if isinstance(engine_data.get("_tv_cache_status"), dict):
                engine_data["_tv_cache_status"]["usable"] = False
                engine_data["_tv_cache_status"]["reason"] = xau_tv_reason
            print(f"  ℹ TV实时注入跳过: {xau_tv_reason}")
        else:
            # 优先同品种独立缓存，避免BTC/XAU轮流写通用tv_live.json导致跨品种覆盖。
            symbol_live_path = _tv_symbol_cache_path(symbol)
            generic_live_path = ROOT / "data" / "tv_live.json"
            cache_path2 = ROOT / "data" / "tv_dmi_cache.json"
            _is_gold_asset = _asset_class(symbol) == "gold"
            # 2026-09-13：XAU 只读专属缓存——通用 tv_live.json / tv_dmi_cache.json 是
            # BTC 写入的，XAU 读它们只会产生「品种不匹配」噪声并污染门2原因串。
            live_paths = [symbol_live_path] if _is_gold_asset else [symbol_live_path, generic_live_path]
            # 2026-09-13 用户批准：复用窗口统一收紧到 5 分钟。
            # 语义 = 「卡内 TV 结构最多滞后一根 5m K 线」；超出窗口的出卡前自动现场刷新。
            # （历史值：XAU 13 / BTC 10——用户担忧「缓存太久不实时」，实测后统一收紧。）
            _live_max_age = TV_LIVE_READ_MAX_AGE_MIN
            c2 = None
            skipped_tv_caches = []
            live_indicator_injected = False
            # Data Window指标与结构位分开选源；当前柱POC为空也不能丢HALDRO/MCP。
            for live_path in live_paths:
                if not live_path.exists():
                    continue
                try:
                    live_candidate = _j2.loads(live_path.read_text(encoding="utf-8"))
                    live_status = _tv_cache_status(live_candidate, symbol, max_age_minutes=_live_max_age)
                    if live_candidate.get("fresh") and live_status.get("usable"):
                        live_indicator_injected = _inject_tv_live_pine(engine_data, live_candidate)
                        if live_indicator_injected:
                            engine_data["_tv_live_status"] = live_status
                            print(f"  📡 TV实时指标注入: {live_path.name} Data Window/行动格已采用")
                            break
                    else:
                        skipped_tv_caches.append(f"{live_path.name}: {live_status.get('reason')}")
                except Exception as exc:
                    skipped_tv_caches.append(f"{live_path.name}: {exc}")
            # 2026-09-13：XAU 结构读取同样只用专属缓存（通用缓存为 BTC 数据）。
            structure_paths = [symbol_live_path] if _is_gold_asset else list(dict.fromkeys([*live_paths, cache_path2]))
            for p in structure_paths:
                if p.exists():
                    try:
                        candidate = _j2.loads(p.read_text(encoding="utf-8"))
                        if candidate.get("fresh") and _tv_live_levels(candidate)[0] > 0:
                            cache_status2 = _tv_cache_status(candidate, symbol, max_age_minutes=_live_max_age)
                            if cache_status2.get("usable"):
                                c2 = candidate
                                engine_data["_tv_live_status"] = cache_status2
                                break
                            skipped_tv_caches.append(f"{p.name}: {cache_status2.get('reason')}")
                    except Exception as exc:
                        skipped_tv_caches.append(f"{p.name}: {exc}")
            if not c2 and not live_indicator_injected:
                reason = "; ".join(skipped_tv_caches) or "没有通过现场品种/新鲜度校验的TV缓存"
                engine_data["_tv_live_status"] = {"usable": False, "reason": reason}
                print(f"  ⚠ TV实时注入未采用: {reason}")
            if c2 and c2.get("fresh"):
                from render_v96 import _num as _tv_num  # FX 价格精度：与卡片渲染同规则（2026-09-13）
                if not live_indicator_injected:
                    _inject_tv_live_pine(engine_data, c2)
                klines = engine_data.setdefault("klines", {})
                if _asset_class(symbol) == "gold":
                    # XAU五层结构权威来自xau_tv_sync；防止中间引擎重建klines后只剩Data Window单周期。
                    try:
                        xau_state = json.loads((ROOT / "data" / "xau_tv_state.json").read_text(encoding="utf-8"))
                        for x_tf, x_data in (xau_state.get("timeframes") or {}).items():
                            if x_tf in {"4h", "1h", "15m", "5m"} and isinstance(x_data, dict):
                                klines.setdefault(x_tf, dict(x_data))
                    except (OSError, json.JSONDecodeError):
                        pass
                poc, vah, val = _tv_live_levels(c2)
                ag = c2.get("action_grid", {})
                direction = ag.get("方向", "待判")
                applied_single_tf = _apply_tv_live_structure(
                    engine_data, klines, poc=poc, vah=vah, val=val, direction=direction
                )
                if applied_single_tf and vah and val:
                    merged = engine_data.setdefault("merged", {})
                    merged["vah"] = vah; merged["val"] = val; merged["poc"] = poc
                if applied_single_tf:
                    print(f"  📡 TV实时注入: POC{_tv_num(poc)} VAH{_tv_num(vah)} VAL{_tv_num(val)} → {len(klines)}周期")
                else:
                    print("  📡 TV实时指标已注入；保留五周期逐层结构，未用单周期值覆盖")
    except Exception as _tve:
        print(f"  ⚠ TV注入跳过: {_tve}")
    
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
        # 2026-09-13 审计修复：快照陈旧必须可见降级（门5 黄灯），不得显示「全部通过」。
        try:
            _prot_file = ROOT / "data" / "protections_state.json"
            if _prot_file.exists():
                _prot_mtime = _prot_file.stat().st_mtime
                meta["protections_snapshot"] = _dt.fromtimestamp(_prot_mtime).strftime("%Y-%m-%d")
                meta["protections_snapshot_stale"] = (_dt.now().timestamp() - _prot_mtime) > 48 * 3600
            else:
                meta["protections_snapshot"] = "缺失"
                meta["protections_snapshot_stale"] = True
        except Exception:
            meta["protections_snapshot_stale"] = True
        if not prot_check["passed"]:
            print(f"  ⚠️ Protections拦截: {meta['protections_status']}")
        elif meta.get("protections_snapshot_stale"):
            print(f"  🛡️ Protections无拦截·快照{meta.get('protections_snapshot', '?')}陈旧")
        else:
            print(f"  🛡️ Protections通过")
    except Exception as e:
        meta["protections_active"] = False
        meta["protections_status"] = f"未启用({e})"
    
    # ═══ Step 5: 双卡渲染 ═══
    # 主周期图表截图（BTC→15m / XAU→5m），失败降级为纯文字卡
    # 用线程级超时保护：即使 _tv_screenshot 内部子进程卡住，最多等45s
    screenshot_path = None
    try:
        import threading
        _screenshot_result = [None]
        def _do_screenshot():
            try:
                _screenshot_result[0] = _tv_screenshot(symbol, reuse_verified=True)
            except Exception:
                _screenshot_result[0] = None
        _t = threading.Thread(target=_do_screenshot, daemon=True)
        _t.start()
        _t.join(timeout=45)
        if _t.is_alive():
            print("  ⚠️ 主周期截图超时45s，降级为纯文字卡")
        else:
            screenshot_path = _screenshot_result[0]
            if screenshot_path:
                print(f"  📸 主周期截图: {screenshot_path}")
            else:
                print("  ⚠️ 主周期截图返回空（TV MCP 可能不可用）")
    except Exception as _se:
        print(f"  ⚠️ 主周期截图异常: {_se}")
    
    # Full artifacts belong only to Full runs. Lightweight runs previously
    # rendered twice and overwrote the last complete artifact with partial data.
    publish_full_artifact = effective_mode == "full"
    full_card = ""
    if publish_full_artifact:
        full_card = render_card_locked(
            symbol, merged, results, meta, engine_data,
            grok=grok, search_sent=search_sent, community=community,
            regime_name=regime_name, force_full=True,
        )
        full_card = sanitize_card_format(full_card)
        try:
            _adv_section = (engine_data.get("_advanced", {}) or {}).get("section", "")
            if _adv_section:
                full_card = full_card.rstrip() + "\n" + _adv_section + "\n"
        except Exception:
            pass
        rule_errors = validate_card_rules(full_card, meta)
        if rule_errors:
            print("  ⚠ 模板审计发现问题: " + "；".join(rule_errors))
    card = ""
    if not publish_full_artifact:
        # The gate must consume the verdict produced by this render.  Running
        # the gate first made every lightweight analysis report a missing
        # FinalVerdict even though the card resolved one immediately after.
        card = sanitize_card_format(render_card_locked(
            symbol, merged, results, meta, engine_data,
            grok=grok, search_sent=search_sent, community=community,
            regime_name=regime_name, force_full=False,
        ))
    # v9.6: GO/NO-GO下单闸门 — 追加到完整卡尾部
    gate_verified = False
    try:
        import sys as _gate_sys
        _gate_sys.path.insert(0, str(ROOT / "scripts"))
        from go_nogo_gate import check_gate, gate_report_card
        # 2026-09-13 审计修复：门6「样本0」是恒0假值 —— 接线真实影子统计。
        # mature=成熟样本数；WFO 效率无生产计算源 → 显式 None（门6 显示「WFO未计算」）。
        try:
            from shadow_calibration import shadow_sample_stats
            _shadow_stats = shadow_sample_stats(ROOT / "data" / "shadow" / "decision_outcomes.jsonl")
            engine_data["_shadow_stats"] = _shadow_stats
            engine_data["_reviews_count"] = int(_shadow_stats.get("mature", 0))
            engine_data.setdefault("_wfo_efficiency", None)
        except Exception as _ss_e:
            print(f"  ⚠ 影子统计注入失败: {_ss_e}")
        gate_result = check_gate(symbol, engine_data, meta)
        engine_data["_gate_result"] = gate_result
        gate_section = gate_report_card(gate_result, symbol)
        if publish_full_artifact:
            full_card = full_card.rstrip() + "\n" + gate_section + "\n"
        gate_verified = True
        print(f"  🚦 GO/NO-GO: {gate_result['verdict']}")
    except Exception as _ge:
        # A gate exception is a hard safety failure. The card may still be
        # saved locally for diagnosis, but it must never be delivered as a
        # trading decision.
        gate_verified = False
        engine_data["_gate_result"] = {
            "verdict": "✗ NO-GO · 闸门异常",
            "go": False,
            "execution_authorized": False,
            "final_state": "NO-GO",
            "reason": f"GO/NO-GO异常: {type(_ge).__name__}",
        }
        print(f"  ⚠ GO/NO-GO跳过({_ge})；已阻止外部推送")
    if publish_full_artifact:
        card = sanitize_card_format(render_card_locked(
            symbol, merged, results, meta, engine_data,
            grok=grok, search_sent=search_sent, community=community,
            regime_name=regime_name, force_full=False,
        ))

    append_trade_plan(meta, full_card if publish_full_artifact else card)
    update_monitor_metadata(symbol, meta)
    # Only Full refreshes the inherited high-timeframe context. A partial run
    # must not replace the last complete context.
    if publish_full_artifact:
        try:
            from pipeline_router import save_analysis_context
            save_analysis_context(
                symbol,
                mode=effective_mode,
                price=engine_data.get("prices", {}).get("primary"),
                levels=meta.get("key_levels", []) if isinstance(meta, dict) else [],
                timeframes=engine_data.get("_tv_five_tf_klines") or {},
                tv_five_tf_status=engine_data.get("_tv_five_tf_status") or {},
                macro=engine_data.get("_macro") if isinstance(engine_data.get("_macro"), dict) else None,
                final_verdict=engine_data.get("_final_verdict") if isinstance(engine_data.get("_final_verdict"), dict) else None,
                primary_action=engine_data.get("_tv_main_final") if isinstance(engine_data.get("_tv_main_final"), dict) else None,
                source_matrix=engine_data.get("_cross_validation_matrix") if isinstance(engine_data.get("_cross_validation_matrix"), list) else None,
            )
        except Exception as _ctxe:
            print(f"  ⚠ 分析上下文保存失败: {_ctxe}")

    # Save both
    sym_name = symbol.replace('/', '_')
    full_path = DATA / f"auto_card_{sym_name}_full.md"
    compact_path = DATA / f"auto_card_{sym_name}.md"
    atomic_write_text(compact_path, card)
    if publish_full_artifact:
        atomic_write_text(full_path, full_card)
    
    is_compact = len(card.strip().split('\n')) <= 10
    print(f"  ✅ 已写入 {compact_path} ({'极简' if is_compact else '完整'})")
    if publish_full_artifact:
        print(f"  ✅ 已写入 {full_path} (完整)")
    
    # Show compact card (shorter) first, then note full card available
    print(f"\n{card}")
    if is_compact and publish_full_artifact:
        line_count = len(full_card.strip().split('\n'))
        print(f"\n📋 完整分析卡 ({line_count}行) 已保存至 {full_path.name}")
    
    # ═══ Step 6: 推送 ═══
    # External delivery requires a successfully evaluated gate. A gate
    # exception is fail-closed: keep the local diagnostic artifact, do not
    # publish it as a trading decision.
    # Only an evaluated, executable GO-A decision may leave the process as a
    # trading card. WAIT/NO-GO/B/C remain local diagnostic artifacts.
    _push_verdict = engine_data.get("_final_verdict")
    _push_authorized = (
        isinstance(_push_verdict, dict)
        and _push_verdict.get("state") == "GO-A"
        and _push_verdict.get("executable") is True
        and all(_push_verdict.get(k) not in (None, "") for k in ("entry", "stop", "target"))
    )
    _push_enabled = (
        os.environ.get("TANGXI_ENABLE_AUTOMATED_TG") == "1"
        and os.environ.get("TANGXI_AUTOMATED_TG_TARGET", "").strip().startswith("telegram:")
    )
    if push and gate_verified and _push_authorized and _push_enabled:
        print("⑥ 推送...")
        try:
            target = os.environ["TANGXI_AUTOMATED_TG_TARGET"].strip()
            # 卡片走 telegram_reliable RichMarkdown 真表格（纯文字）
            sys.path.insert(0, str(Path(__file__).parent))
            from telegram_reliable import send_telegram_reliable, send_telegram_photo
            ok, reason = send_telegram_reliable(
                target, card[:3500],
                parse_mode="RichMarkdown",
                timeout=20, retries=3, persist_on_fail=True,
            )
            if ok:
                print(f"  ✅ Telegram文字卡已推送 → {target} ({reason})")
            else:
                print(f"  ⚠️ Push文字卡: {reason}")
            # 主周期图表截图（若有）单独发图
            main_tf_label = ""
            try:
                from pipeline_router import timeframe_info
                main_tf_label = timeframe_info(symbol).get("main", "")
            except Exception:
                pass
            if screenshot_path and Path(screenshot_path).exists():
                pok, preason = send_telegram_photo(
                    target, screenshot_path,
                    caption=f"{symbol} 主周期图表（{main_tf_label}）",
                    timeout=20, retries=3,
                )
                print(f"  {'✅' if pok else '⚠️'} Telegram主周期截图 → {target} ({preason})")
            else:
                print("  ⚠️ 主周期截图缺失，仅发文字卡")
        except Exception as e:
            print(f"  ⚠️ Push: {e}")
    elif push:
        print("⏸ 未推送：FinalVerdict不是完整GO-A可执行裁决")

    # 管线完成度审计表
    if pipeline_steps:
        print(f"\n{'='*50}")
        print("📋 管线完成度审计")
        print(f"{'='*50}")
        # Mark known completed steps
        # 基于 engine_data 判断各步骤完成（比卡文本匹配更可靠）
        completed_steps.add("card")
        # Crypto Full has five decision stages in addition to the ten source
        # stages.  Mark them from produced objects, never from route names
        # alone, so a partial run remains visibly incomplete.
        if effective_mode == "full" and asset_class == "crypto":
            if results or merged:
                completed_steps.add("engine")
            if isinstance(engine_data.get("_decision_regime"), dict) and engine_data.get("_decision_regime"):
                completed_steps.add("regime")
            if isinstance(engine_data.get("_dual_indicator_verdict"), dict):
                completed_steps.add("dual")
            if isinstance(engine_data.get("_advanced"), dict) and not engine_data["_advanced"].get("error"):
                completed_steps.add("advanced")
            if isinstance(engine_data.get("_final_verdict"), dict) and engine_data.get("_risk_v2") is not None:
                completed_steps.add("risk")
        tv_step = _pipeline_tv_step_status(engine_data)
        tv_usable = bool(tv_step["usable"])
        if tv_usable:
            completed_steps.add("tv")
        if "macro" in pipeline_steps:
            macro_value = engine_data.get("macro") or engine_data.get("_macro")
            if isinstance(macro_value, dict) and macro_value:
                macro_status = macro_value.get("_source_status") or macro_value.get("source_status") or "cache"
                if macro_status in ("live", "cache", "inherited"):
                    completed_steps.add("macro")
        cron_fresh = []
        cron_paused = []
        cron_missing = []
        if "cron_read" in pipeline_steps:
            try:
                from pipeline_router import (cron_sources, cron_source_paused,
                                            cron_source_max_age, cron_source_file)
                from source_health import inspect_json_file
                for source_name in cron_sources(symbol):
                    source_path = ROOT / "data" / cron_source_file(source_name)
                    source_health = inspect_json_file(
                        source_path, max_age_hours=cron_source_max_age(source_name))
                    if source_health.get("fresh"):
                        cron_fresh.append(source_name)
                    elif cron_source_paused(source_name):
                        # 刻意不采 ≠ 采不到：分开记账，避免每轮卡都像报故障。
                        cron_paused.append(source_name)
                    else:
                        status = source_health.get("status") or "unavailable"
                        cron_missing.append(f"{source_name}({status})")
                # 只要有「刻意停用」的源，本步就不算完成 —— 不把设计性缺口
                # 记成完成度，避免卡面分数虚高（脚注里已如实列出是哪几个）。
                if cron_fresh and not cron_missing and not cron_paused:
                    completed_steps.add("cron_read")
            except Exception:
                cron_missing.append("cron_sources")
        price_fields = engine_data.get("prices")
        if not isinstance(price_fields, dict):
            price_fields = {}
        if engine_data.get("_binance_data_collected") and price_fields.get("primary"):
            completed_steps.add("binance")
        cg_top = engine_data.get("cg_top")
        if isinstance(cg_top, dict) and cg_top:
            cg_status = _source_record_status(engine_data, "cg_top", cg_top)
            if cg_status in ("live", "cache", "inherited"):
                completed_steps.add("cg_pro")
        if _source_record_usable(engine_data, "x_sentiment", engine_data.get("x_sentiment")):
            completed_steps.add("x_sent")
        if _source_record_usable(engine_data, "cvd", engine_data.get("cvd")):
            completed_steps.add("cvd")
        if _source_record_usable(engine_data, "depth", engine_data.get("depth")):
            completed_steps.add("depth")
        if _source_record_usable(engine_data, "correlation", _corr_value):
            completed_steps.add("corr")
        if _source_record_usable(engine_data, "gold_macro", engine_data.get("gold_macro")):
            completed_steps.add("gold_macro")
        if _source_record_usable(engine_data, "forex_rate", engine_data.get("forex_rate")):
            completed_steps.add("forex_rate")
        if _source_record_usable(engine_data, "fmp", engine_data.get("fmp")): completed_steps.add("fmp")
        if _source_record_usable(engine_data, "options_chain", engine_data.get("options_line")): completed_steps.add("options_chain")
        completed_steps.add("orphan")  # orphan integration always runs
        
        step_status = {}
        step_notes = {}
        for s in pipeline_steps:
            emoji = "✅" if s in completed_steps else "⚠️"
            step_status[s] = emoji
            if s == "tv":
                if tv_usable:
                    if tv_step["five_required"]:
                        step_notes[s] = "TV五层与主周期行动格均已采用"
                    else:
                        step_notes[s] = f"TV主周期行动格已采用；五周期背景={tv_step['five_reason']}"
                else:
                    step_notes[s] = (
                        f"TV主周期可用={tv_step['main_usable']}·"
                        f"五周期可用={tv_step['five_usable']}·覆盖{tv_step['five_coverage']}/5"
                    )
            elif s == "cron_read":
                if cron_paused:
                    step_notes[s] = (f"新鲜:{','.join(cron_fresh) or '无'}；"
                                     f"设计性停用:{','.join(cron_paused)}；"
                                     f"缺失/过期:{','.join(cron_missing) or '无'}")
                else:
                    step_notes[s] = f"新鲜:{','.join(cron_fresh) or '无'}；缺失/过期:{','.join(cron_missing) or '无'}"
            elif s in completed_steps:
                step_notes[s] = "已完成"
            else:
                step_notes[s] = "本轮未采到有效字段"
        audit_lines = [
            "### 管线完成度审计",
            "",
            "| 步骤 | 状态 | 备注 |",
            "|:---|:---:|:---|",
        ]
        for s in pipeline_steps:
            label = {"tv":"TV五层","binance":"Binance衍生品","cg_pro":"CoinGecko Pro",
                     "macro":"宏观背景","x_sent":"X情绪","cron_read":"Cron缓存",
                     "cvd":"CVD订单流","depth":"深度数据","corr":"相关性",
                     "engine":"核心模型引擎","regime":"市场体制","dual":"双指标确认",
                     "advanced":"高级订单流","risk":"FinalVerdict风控",
                     "gold_macro":"黄金宏观","forex_rate":"外汇利率","fmp":"FMP基本面",
                     "options_chain":"期权链","card":"出卡","orphan":"孤儿模块"}.get(s, s)
            audit_lines.append(f"| {label} | {step_status[s]} | {step_notes.get(s, '')} |")
        audit_lines.extend([
            "",
            f"管线路由：{len(pipeline_steps)}步 · 完成 {sum(1 for v in step_status.values() if v=='✅')}/{len(pipeline_steps)}",
        ])
        for line in audit_lines:
            print(line)
        try:
            if publish_full_artifact:
                atomic_write_text(full_path, full_card.rstrip() + "\n\n" + "\n".join(audit_lines) + "\n")
        except Exception as e:
            print(f"  ⚠️ 管线完成度写入full卡失败: {e}")

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
    if 8 <= h < 12: return "亚洲盘活跃"
    if 15 <= h < 18: return "伦敦盘活跃"
    if 20 <= h < 23: return "纽约上午盘活跃"
    if 1 <= h < 4: return "纽约下午盘活跃"
    return "非主盘·低流动性"


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
    return "非主盘"


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


# ═══════════════════ 日内止损止盈（对手方流动性池后方·v7.3升级）═══════════════════
# v7.3升级: 止损放在对手方流动性池后方（社区2026共识），不再锚定结构位本身
#   Short: 最近阻力 + 0.5×ATR缓冲 → 止损在猎杀区后方
#   Long:  最近支撑 - 0.5×ATR缓冲 → 止损在猎杀区后方
#   最少保底: p ± 2×ATR（极端行情兜底）
def _calc_stop_target_atr(
    price: float, direction: str, klines: dict,
    symbol: str = "BTCUSDT", atr_mult: float = 2.0
) -> dict:
    """计算日内止损止盈。返回 {stop, target, rr, stop_reason, target_reason, atr}。
    
    direction: "short" 或 "long"
    atr_mult: ATR 倍数（默认 2.0x，日内夹层 1.5-2.5）
    v7.3: 止损放在对手方流动性池后方，不锚定结构位本身
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
    atr_buffer = atr_15m * 0.5  # 对手方流动性池外缓冲
    
    # 收集结构位（对手方流动性池）
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
        # 止损在最近阻力后方（对手方流动性池+ATR缓冲）
        if above_levels:
            stop_structural = above_levels[0][0] + atr_buffer  # 阻力上方推0.5ATR
            stop = max(p + atr_stop_dist, stop_structural)
            stop_reason = f"{above_levels[0][1]}({above_levels[0][2]})+缓冲上方"
        else:
            stop = p + atr_stop_dist
            stop_reason = "ATR×2"
        
        # 止盈在最近支撑
        target = below_levels[0][0] if below_levels else p - atr_stop_dist * 2
        target_reason = f"{below_levels[0][1]}({below_levels[0][2]})" if below_levels else "ATR×4"
    else:
        # 止损在最近支撑后方（对手方流动性池-ATR缓冲）
        if below_levels:
            stop_structural = below_levels[0][0] - atr_buffer  # 支撑下方推0.5ATR
            stop = min(p - atr_stop_dist, stop_structural)
            stop_reason = f"{below_levels[0][1]}({below_levels[0][2]})-缓冲下方"
        else:
            stop = p - atr_stop_dist
            stop_reason = "ATR×2"
        
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
    # 高/低优先从K线取，如K线占位(XAU无期货数据)则回退到binance_spot 24h范围
    _raw_hi = k15m.get("high") or k4h.get("high")
    _raw_lo = k15m.get("low") or k4h.get("low")
    # 如果K线高=低=现价（占位数据），回退到 binance_spot 的24h范围
    if _raw_hi == _raw_lo and _raw_hi and abs(float(_raw_hi) - p) < max(p * 0.001, 5):
        spot = engine_data.get("binance_spot", {})
        if spot:
            _raw_hi = spot.get("24h_high", _raw_hi)
            _raw_lo = spot.get("24h_low", _raw_lo)
    hi = _fmt_price(_raw_hi).strip("`")
    lo = _fmt_price(_raw_lo).strip("`")
    taker_label = f"Taker {taker_dir}" if taker_dir not in ("N/A", None, "") else "Taker 无"
    taker_r = f" {taker_ratio}" if taker_ratio and str(taker_ratio) not in ("N/A", "") else ""
    cvd_str = f"CVD {cvd_dir}" if cvd_dir not in ("N/A", "?", None, "") else "CVD ?"
    ac = _asset_class(symbol)
    bias = "空头偏" if cvd_dir == "卖" else "多头偏" if cvd_dir == "买" else "观望"
    from datetime import datetime as _dt
    wd_tag = "⚠周末 " if _dt.now().weekday() >= 5 else ""
    dist_pct = abs(p - nearest_level) / p * 100
    near_str = f"← 价踩在这 · {dist_pct:.1f}%" if dist_pct < 0.5 else f"← 距{abs(p - nearest_level):.0f}点"
    bearish = (cvd_dir == "卖" or taker_dir in ("sell", "卖"))
    
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

    flow_line = f"{cvd_str} · {taker_label}{taker_r}"
    if ac == "crypto":
        flow_line += f" · Funding {funding_rate}"

    price_fmt = _fmt_price(price).strip("`")
    lines = [
        f"◷ {datetime.now(TZ).strftime('%m-%d %H:%M')} · {_display_symbol(symbol)} · {bias}{' ' + grade_line if grade_line else ''}",
        "",
        f"现价 `{price_fmt}` 高 `{hi}` 低 `{lo}`",
        f"{nearest_name} `{nl_fmt}` 距 {dist_pct:.1f}%",
        flow_line,
        trigger_line,
    ]
    if vwap_line:
        lines.append(vwap_line)
    lines.extend([
        plan_a,
        plan_b,
        scale_line,
        f"风控：{wd_tag}{risk_amt:.2f}U上限 · {leverage_text} · {prot_tag} · {comm_tag}",

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
        for key, name in [("vah", "价值上沿"), ("val", "价值下沿"), ("poc", "控制点"), ("vwap", "量价均值"),
                          ("high", "日高"), ("low", "日低")]:
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


_KNOWN_FLAGS = ("--push", "--full", "--quick", "--inherit", "--now", "--mode-auto", "--message")
_FLAG_TAKES_VALUE = ("--message",)


def _reject_unknown_flags(argv) -> str | None:
    """未知 CLI 参数必须显式报错，不能静默当成品种。

    历史事故形态：`auto_card.py --mode full` —— `--mode` 不被识别、被
    `_parse_cli_symbol` 跳过，而它的值 `full` 被当成「品种」，
    于是为伪品种 FULL 生成了一张看起来正常的卡（静默错输出）。
    """
    it = iter(range(len(argv)))
    for i in it:
        arg = argv[i]
        if not arg.startswith("-"):
            continue
        if arg in _KNOWN_FLAGS:
            if arg in _FLAG_TAKES_VALUE:
                next(it, None)
            continue
        extra = ""
        if arg in ("--mode", "-m"):
            extra = "（档位请用 --full / --inherit / --quick，或 --mode-auto --message \"<原话>\"）"
        return f"未知参数 {arg}{extra}"
    return None


def _parse_cli_symbol(argv=None) -> str:
    """Return the trading symbol from positional args or --message text."""
    argv = list(sys.argv[1:] if argv is None else argv)
    message = ""
    for idx, arg in enumerate(argv):
        if arg == "--message" and idx + 1 < len(argv):
            message = str(argv[idx + 1])
            break
    for arg in argv:
        if not arg or arg.startswith("-"):
            continue
        symbol = arg.upper().strip()
        if re.match(r"^[A-Z0-9][A-Z0-9._:-]{0,31}$", symbol):
            return "BTCUSDT" if symbol == "BTC" else "XAUUSD" if symbol == "XAU" else symbol
    # --mode-auto commonly receives the user's natural-language request via
    # --message, so do not silently fall back to BTC when it names another
    # supported asset (e.g. "看下XAUUSD").
    message_upper = message.upper()
    if "XAU" in message_upper or "GOLD" in message_upper:
        return "XAUUSD"
    if "BTC" in message_upper:
        return "BTCUSDT"
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
    _unknown = _reject_unknown_flags(sys.argv[1:])
    if _unknown:
        print(f"❌ {_unknown}", file=sys.stderr)
        print("用法：auto_card.py <SYMBOL> [--quick|--full|--inherit|--now] [--push]\n"
              "      auto_card.py --mode-auto --message \"<用户原话>\"", file=sys.stderr)
        raise SystemExit(2)
    sym = _parse_cli_symbol()
    # 未识别资产仍按通用管线出卡（设计允许），但必须显式提示，
    # 避免「伪品种卡」看起来与真品种卡一模一样。
    try:
        from pipeline_router import parse_asset_identity
        _ident = parse_asset_identity(sym) or {}
        if str(_ident.get("asset_class") or "").lower() in ("unknown", ""):
            print(f"⚠ 未识别资产『{sym}』——按通用管线处理，请确认这不是参数误传。")
    except Exception:
        pass
    do_push = "--push" in sys.argv
    # 日常默认快速；完整扫描必须显式 --full，避免裸跑误触发重管线。
    _mode = "quick"
    if "--full" in sys.argv:
        _mode = "full"
    elif "--inherit" in sys.argv or "--now" in sys.argv:
        _mode = "inherit"
    # 2026-08-31 --mode-auto：档位识别代码化——对话层必传用户原话，
    # 由 pipeline_router.resolve_analysis_mode 定档，模型不再自行判断档位。
    if "--mode-auto" in sys.argv:
        try:
            from pipeline_router import resolve_analysis_mode, context_is_fresh
            _msg = ""
            if "--message" in sys.argv:
                _idx = sys.argv.index("--message")
                if _idx + 1 < len(sys.argv):
                    _msg = sys.argv[_idx + 1]
            if not _msg:
                _msg = " ".join(a for a in sys.argv if not a.startswith("-"))
            _mode = resolve_analysis_mode(_msg, has_context=context_is_fresh(sym))
            print(f"🎛 --mode-auto: 消息={_msg[:40]!r} → 档位={_mode}")
        except Exception as _me:
            print(f"⚠ --mode-auto 解析失败({_me}) → 保留 {_mode}")
    _lease_owned = _begin_analysis_lease_if_idle(sym)
    try:
        auto_card(sym, push=do_push, mode=_mode)
    finally:
        if _lease_owned:
            _end_analysis_lease_quiet()
