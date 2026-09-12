#!/usr/bin/env python3
"""Pipeline Router v1.1 — 按资产类别自动选流程步骤 + 五层TF规则 + cron-read捷径
用于 auto_card.py / analysis pipeline 中自动跳过不适用的数据源。

v1.1 (2026-06-29): 五层TF统一(D/4h/1h/15m/5m)·cron_read捷径·步数精简·跨资产相关性

用法:
    from pipeline_router import route_pipeline, timeframe_info, pipeline_summary
    steps = route_pipeline("BTCUSDT")   # → 15步: 采集/验证/引擎/风控/出卡
    steps = route_pipeline("XAUUSD")    # → 8步: tv/macro/x_sent/cron_read/cvd/corr/gold_macro/card
    steps = route_pipeline("EURUSD")    # → 7步: tv/macro/x_sent/cron_read/corr/forex_rate/card
    tfinfo = timeframe_info("BTCUSDT")  # → {'layers': ['D','4h','1h','15m','5m'], 'main':'15m', 'screenshot':'15m'}
"""

import sys
import re
import hashlib
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone, timedelta
_stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(_stdout_reconfigure):
    _stdout_reconfigure(encoding="utf-8", errors="replace")
_stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if callable(_stderr_reconfigure):
    _stderr_reconfigure(encoding="utf-8", errors="replace")


def parse_asset_identity(symbol: str) -> dict:
    """Parse local routing identity; this does NOT verify a listed instrument.

    Raw input is never repaired. Normalization is separate, case-only, and
    tick size/listing/settlement metadata require a real provider lookup.
    """
    normalized = symbol.upper() if isinstance(symbol, str) else None
    exchange, ticker = None, normalized
    if normalized and normalized.count(":") == 1:
        exchange, ticker = normalized.split(":")
    ac = _legacy_asset_class(ticker or "")
    product_type, underlying = None, None
    option = _option_parts(ticker or "")
    continuous = re.fullmatch(r"([A-Z][A-Z0-9]*?)([1-9][0-9]*)!", ticker or "")
    perpetual = re.fullmatch(r"([A-Z0-9]+?)(USDT|USDC|USD)\.P", ticker or "")
    if option:
        # OSI/OPRA：期权分析跟随底层品种（用户规则「option 跟随底层」）。
        ac = "option"
        product_type = option["right"] + "_option"
        underlying = option["underlying"]
    elif continuous:
        ac = "futures"
        product_type, underlying = "continuous_future", continuous.group(1)
    elif perpetual:
        ac = "crypto"
        product_type, underlying = "perpetual", perpetual.group(1)
    underlying_class = _legacy_asset_class(underlying) if underlying else None
    return {"raw_symbol": symbol, "normalized_symbol": normalized,
            "exchange": exchange, "ticker": ticker, "asset_class": ac,
            "product_type": product_type, "underlying": underlying,
            "underlying_class": underlying_class,
            "supported": ac != "other", "exchange_verified": False,
            "tick_size": None}


def _asset_class(symbol: str) -> str:
    return parse_asset_identity(symbol)["asset_class"]


def _legacy_asset_class(symbol: str) -> str:
    su = symbol.upper()
    su_clean = su.split(":")[-1].replace("1!", "").replace("!", "")
    # 期权必须先于 BTC/ETH/USDT 加密识别，否则 Deribit 格式
    # BTC-29MAR24-60000-C / ETH-29MAR24-3000-P 会误走 crypto 10步管线。
    if "CALL" in su or "PUT" in su or "OPTION" in su or re.search(r"-[CP]$", su_clean):
        return "option"
    if _option_parts(su_clean):
        # OSI/OPRA 标准代码 AAPL240119C150 / SPX 240119C5000。
        return "option"
    if "XAU" in su or "GOLD" in su or "XAG" in su:
        return "gold"
    # Forex markers
    forex = ["EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"]
    if any(x in su for x in forex):
        if "USDT" not in su:
            return "forex"
    if su.endswith("USDT") or "BTC" in su or "ETH" in su or "SOL" in su:
        return "crypto"
    # Futures: CME/CBOT/COMEX/NYMEX standard codes
    futures_codes = {"ES", "CL", "NQ", "GC", "ZC", "ZS", "ZW", "NG", "SI", "HG", "PL", "PA",
                     "YM", "RTY", "MES", "MNQ", "M2K", "MGC", "QM", "ZB", "ZN", "ZF", "ZT",
                     "HE", "LE", "KC", "CT", "CC", "SB", "OJ", "RB", "HO"}
    if su_clean in futures_codes:
        return "futures"
    if su_clean in _INDEX_TICKERS or su in _INDEX_TICKERS:
        return "index"
    if su in ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN"] or (su.isalpha() and len(su) <= 5):
        return "stock"
    return "other"


# 指数/现金指数（用户图表里有 SPX；不属于 stock 也不属于 futures）。
_INDEX_TICKERS = {
    "SPX", "SPX500", "SPXUSD", "US500", "NDX", "NAS100", "US100", "US30", "DJI", "WS30",
    "DAX", "DE40", "UK100", "FTSE", "NIKKEI", "JP225", "VIX", "DXY", "USDOLLAR",
}


def _option_parts(ticker: str) -> dict | None:
    """识别期权代码，返回 {underlying, expiry, right, strike}；识别不了返回 None。

    支持两种写法：
      1) OSI/OPRA：`<ROOT><YYMMDD><C|P><STRIKE>`，含 OCC 空格补齐；
      2) Deribit：`<ROOT>-<DDMMMYY>-<STRIKE>-<C|P>`，如 BTC-29MAR24-60000-C。
    """
    compact = re.sub(r"\s+", "", ticker or "").upper()
    match = re.fullmatch(r"([A-Z]{1,6})(\d{6})([CP])(\d{1,8})", compact)
    if match:
        return {"underlying": match.group(1), "expiry": match.group(2),
                "right": "call" if match.group(3) == "C" else "put",
                "strike": match.group(4)}
    deribit = re.fullmatch(r"([A-Z0-9]{2,10})-([A-Z0-9]+)-([0-9.]+)-([CP])", compact)
    if deribit:
        return {"underlying": deribit.group(1), "expiry": deribit.group(2),
                "right": "call" if deribit.group(4) == "C" else "put",
                "strike": deribit.group(3)}
    return None


# ===== 五层时间框架规则（2026-06-29 用户确认） =====
TF_RULES = {
    # 资产类别: {layers, main, screenshot, rationale}
    "crypto":  {"layers": ["D", "4h", "1h", "15m", "5m"], "main": "15m", "screenshot": "15m",
                "rationale": "24×7·15m平衡噪音与信号"},
    "gold":    {"layers": ["D", "4h", "1h", "15m", "5m"], "main": "5m",  "screenshot": "5m",
                "rationale": "用户快进快出风格·5m主执行"},
    "forex":   {"layers": ["D", "4h", "1h", "15m", "5m"], "main": "15m", "screenshot": "15m",
                "rationale": "24×5流动性·15m与加密节奏一致"},
    "stock":   {"layers": ["D", "4h", "1h", "15m", "5m"], "main": "1h",  "screenshot": "1h",
                "rationale": "有跳空缺口·15m噪音大·1h更可靠"},
    "futures": {"layers": ["D", "4h", "1h", "15m", "5m"], "main": "15m", "screenshot": "15m",
                "rationale": "ES 23h流动性·15m与加密同步"},
    "option":  {"layers": ["D", "4h", "1h", "15m", "5m"], "main": "15m", "screenshot": "15m",
                "rationale": "跟底层品种：timeframe_info 会按底层类别覆盖"},
    "index":   {"layers": ["D", "4h", "1h", "15m", "5m"], "main": "15m", "screenshot": "15m",
                "rationale": "现金指数无夜盘·15m与期货同步"},
    "other":   {"layers": ["D", "4h", "1h", "15m", "5m"], "main": "15m", "screenshot": "15m",
                "rationale": "默认五层"},
}


def timeframe_info(symbol: str) -> dict:
    """返回推荐的时间框架信息。{layers, main, screenshot, rationale}

    期权跟随底层：AAPL 期权用 stock 的 1h，SPX 期权用 index 的 15m，
    加密期权用 crypto 的 15m。只跟随**已知**底层类别，未知时退回 option 自身默认。
    """
    identity = parse_asset_identity(symbol)
    ac = identity["asset_class"]
    if ac == "option":
        base = identity.get("underlying_class")
        if base in TF_RULES and base not in ("option", "other"):
            info = dict(TF_RULES[base])
            info["rationale"] = f"期权跟随底层 {identity.get('underlying')}（{base}）：" + info["rationale"]
            info["follows_underlying"] = base
            return info
    return TF_RULES.get(ac, TF_RULES["other"])


# ===== 每个步骤的定义 =====
STEPS = {
    # 步骤ID: {label, description, 适用资产集合, executor}
    "tv":       {"label": "TV技术面",    "desc": "TradingView SVP+Volume 五层(D/4h/1h/15m/5m)", "assets": {"crypto", "gold", "forex", "stock", "futures", "option", "index", "other"}},
    "binance":  {"label": "Binance衍生品","desc": "OI/费率/Taker/LS/多空比",           "assets": {"crypto"}},
    "cg_pro":   {"label": "CoinGecko Pro","desc": "板块/流动性/市值排名",                "assets": {"crypto"}},
    "macro":    {"label": "宏观背景",     "desc": "SPX/VIX/DXY/US10Y + 金十日历 + Poly + FG(加密)", "assets": {"gold", "forex", "stock", "crypto", "futures", "index", "other"}},
    "jin10":    {"label": "金十日历",     "desc": "经济数据/利率决议/快讯 [已并入macro]", "assets": set()},  # merged into macro
    "poly":     {"label": "Polymarket",  "desc": "Fed/衰退/加密事件概率 [已并入macro]",  "assets": set()},  # merged into macro
    "fg":       {"label": "恐惧贪婪",     "desc": "加密恐惧贪婪指数 [已并入macro]",      "assets": set()},  # merged into macro
    "cron_read":{"label": "读Cron输出",   "desc": "读取最近cron输出(不重跑):dune+deribit+x+qlib+liq+stablecoin+COT",
                                              "assets": {"crypto", "gold", "forex", "stock", "futures", "index", "other"}},
    "etf_flow": {"label": "ETF Flow",    "desc": "BTC ETF 日净流入/流出 [SoSoValue被封·Dune替代]", "assets": set()},  # dead
    "dune":     {"label": "Dune链上",    "desc": "BTC流/CEX净流/稳定币 [已并入cron_read]", "assets": set()},  # merged into cron_read
    "deribit":  {"label": "Deribit期权", "desc": "OI/C/P比/MaxPain [已并入cron_read]",   "assets": set()},  # merged into cron_read
    "x_sent":   {"label": "X情绪",       "desc": "x_search 实时X/Twitter情绪+恐贪+CGTrending", "assets": {"crypto", "gold", "forex", "stock", "futures", "index", "other"}},
    "cot":      {"label": "COT持仓",     "desc": "投机/商业持仓方向 [已并入cron_read]",   "assets": set()},  # merged into cron_read
    "cvd":      {"label": "CVD订单流",   "desc": "量价背离/吸收/FVG",                   "assets": {"crypto", "gold"}},
    "depth":    {"label": "深度数据",     "desc": "挂单墙/清算池",                       "assets": {"crypto"}},
    "corr":     {"label": "跨资产相关",   "desc": "BTC-SPX-XAU-DXY 相关性矩阵(FnanceKit)", "assets": {"crypto", "gold", "forex", "stock", "futures", "index", "other"}},
    # Crypto Full 的固定15步中，以下是实际执行器内部的决策阶段；
    # 它们不是空占位，auto_card 会在相应数据/裁决生成后写入完成度审计。
    "engine":   {"label": "核心模型引擎", "desc": "VWAP/EMA/CVD + 多模型候选",           "assets": {"crypto"}},
    "regime":   {"label": "市场体制",     "desc": "闭柱特征/体制分类/模型适配",             "assets": {"crypto"}},
    "dual":     {"label": "双指标确认",   "desc": "SVP主指标 + AggVol/HALDRO副指标",        "assets": {"crypto"}},
    "advanced": {"label": "高级订单流",   "desc": "吸收/FVG/OB/共振门控",                   "assets": {"crypto"}},
    "risk":     {"label": "FinalVerdict风控", "desc": "R:R/风险宪法/唯一执行裁决",            "assets": {"crypto"}},
    "card":     {"label": "输出分析卡",   "desc": "结构化分析卡输出",                    "assets": {"crypto", "gold", "forex", "stock", "futures", "option", "index", "other"}},
    "gold_macro":{"label":"黄金宏观",     "desc": "DXY/TIP/GLD/GDX/白银比·央行黄金储备·金银比", "assets": {"gold"}},
    "fmp":      {"label": "FMP基本面",   "desc": "PE/市值/财报/板块",                    "assets": {"stock"}},
    "options_chain":{"label":"期权链",    "desc": "OI/IV/Greeks/到期日",                 "assets": {"option", "stock"}},
    "forex_rate":{"label":"外汇利率",     "desc": "利差/央行窗口/点差·Carry Trade基础",  "assets": {"forex"}},
}


# ===== cron_read 数据源映射（按资产类别） =====
CRON_SOURCES = {
    # 这里只列真实落盘文件。仅推TG而没有本地JSON的采集器不得伪装成 cron_read 已消费。
    "crypto":  ["dune_cache", "deribit_options", "x_sentiment", "qlib_factors", "liquidation_pressure"],
    "gold":    ["cot_data", "xau_macro_context", "x_sentiment"],
    "forex":   ["cot_data", "x_sentiment"],
    "stock":   ["cot_data", "x_sentiment"],
    "futures": ["cot_data", "x_sentiment"],
    "other":   ["cot_data", "x_sentiment"],
}


ASSET_STEP_DESCRIPTIONS = {
    "macro": {
        "crypto": "SPX/VIX/DXY/US10Y + 金十日历 + Polymarket + 加密恐贪",
        "gold": "DXY/US10Y/TIP/SPX/VIX + 金十黄金日历/快讯",
        "forex": "DXY/利率/央行/经济日历 + 风险偏好",
        "stock": "SPX/NDX/VIX/US10Y + 公司/行业/财报事件",
        "futures": "DXY/利率/库存/经济日历 + 风险偏好",
    },
    "x_sent": {
        "crypto": "x_search实时加密情绪 + 恐贪 + CoinGecko热度",
        "gold": "x_search黄金/XAU实时情绪 + 金十/宏观交叉验证",
        "forex": "x_search本货币对实时情绪 + 央行/宏观交叉验证",
        "stock": "x_search公司/行业实时情绪 + 新闻催化剂",
        "futures": "x_search对应期货实时情绪 + 库存/宏观交叉验证",
    },
    "corr": {
        "crypto": "BTC-SPX-XAU-DXY滚动相关性",
        "gold": "XAU-DXY-SPX-US10Y滚动相关性",
        "forex": "本货币对-DXY-利差资产滚动相关性",
        "stock": "AAPL-SPX-NDX-VIX同类矩阵（代码按标的替换）",
        "futures": "本期货-SPX-DXY-相关商品滚动相关性",
    },
}

# Multi-asset collection and cross-validation contract. X is evidence only.
ASSET_PROFILES = {
    "crypto": {"primary_timeframe": "15m", "timeframes": ["D", "4h", "1h", "15m", "5m"], "cross_validation_sources": ["TradingView SVP", "AggVol", "Binance Futures", "CoinGecko", "macro", "Deribit"]},
    "gold": {"primary_timeframe": "5m", "timeframes": ["D", "4h", "1h", "15m", "5m"], "cross_validation_sources": ["TradingView SVP", "Jin10", "DXY", "US10Y", "GLD/GDX/TIP", "COT"]},
    "forex": {"primary_timeframe": "15m", "timeframes": ["D", "4h", "1h", "15m", "5m"], "cross_validation_sources": ["TradingView SVP", "Jin10", "DXY", "central-bank/rates", "correlated pairs"]},
    "stock": {"primary_timeframe": "1h", "timeframes": ["D", "4h", "1h", "15m", "5m"], "cross_validation_sources": ["TradingView SVP", "FinanceKit", "SEC/earnings", "sector rotation", "options chain"]},
    "futures": {"primary_timeframe": "15m", "timeframes": ["D", "4h", "1h", "15m", "5m"], "cross_validation_sources": ["TradingView SVP", "futures quote", "inventory/calendar", "DXY/rates", "related commodity"]},
    "option": {"primary_timeframe": "15m", "timeframes": ["D", "4h", "1h", "15m", "5m"], "cross_validation_sources": ["underlying TV", "options chain", "IV/Greeks", "OI/PCR", "event calendar"]},
}
for _profile in ASSET_PROFILES.values():
    _profile.update({"x_model_role": "sentiment_catalyst_only", "forbidden_overrides": ["final_verdict", "entry", "stop", "target"]})


def asset_analysis_profile(symbol: str) -> dict:
    asset_class = _asset_class(symbol)
    profile = dict(ASSET_PROFILES.get(asset_class, ASSET_PROFILES["futures"]))
    profile["asset_class"] = asset_class
    return profile


def x_model_can_override_final_verdict() -> bool:
    return False


# ═══════════════════════════════════════════════════════════════════════════
# 分析档位（唯一权威）— L1/L2/L3 与机器名只在这里对应一次
# ═══════════════════════════════════════════════════════════════════════════
# 20260911 收敛：此前档位词汇三套并存 —— 技能写 L1/L2/L3、router 写
# quick/inherit/standard/full/monitor、对话里又混用 Quick/Full；更糟的是关键词表
# 不一致（技能承诺「扫一下 / 状态」属标准档，router 不认 → 静默降成轻量档）。
# 从现在起：本表是唯一权威，技能 / 文档 / 卡面一律引用这里，不得另抄一份。
ANALYSIS_TIERS = {
    "L1": {
        "machine": "quick",
        "label": "轻量",
        "display_name": "轻量",
        "scope": "主周期行动格 + 现价 + 一张截图（加密再补衍生品方向票）",
        "refresh_scope": "execution_only",
    },
    "L2": {
        "machine": "standard",
        "label": "标准",
        "display_name": "标准",
        "scope": "轻量 + 相邻周期结论行 + 关键位/多源交叉（高周期继承）",
        "refresh_scope": "execution_plus_context",
    },
    "L3": {
        "machine": "full",
        "label": "完整",
        "display_name": "完整",
        "scope": "全管线：五周期全源 + 来源矩阵 + 管线审计",
        "refresh_scope": "all_sources",
    },
    "MON": {
        "machine": "monitor",
        "label": "监控",
        "display_name": "监控",
        "scope": "仅事件发现，不出方向卡、不出执行三件套",
        "refresh_scope": "event_only",
    },
}

# 顺序敏感：先匹配到的档位赢。裸品种名（无动词）不在这里，落默认 L1。
_TIER_KEYWORD_ROUTES = (
    ("L3", ("分析", "深度", "完整卡", "出完整卡", "全面", "全周期", "重新从高周期", "刷高周期")),
    ("L2", ("现在呢", "更新", "扫一下", "状态", "继续", "接着", "继承", "追踪")),
    ("L1", ("看下", "看一眼", "看一下", "扫一眼", "瞄一眼", "快速")),
)
TIER_ORDER = ("L1", "L2", "L3", "MON")
MODE_TO_TIER = {spec["machine"]: tier for tier, spec in ANALYSIS_TIERS.items()}
# 「分析」是硬开关：说出它就必须上完整档，不因刚出过卡而降级。
HARD_FULL_KEYWORDS = ("分析", "深度", "完整卡", "出完整卡")


def tier_for_mode(mode: str) -> str:
    """机器名 → 对话档位名（quick→L1 / standard→L2 / full→L3 / monitor→MON）。"""
    key = validate_analysis_mode(mode)
    return MODE_TO_TIER["standard" if key == "inherit" else key]


def tier_label(mode: str) -> str:
    """机器名 → 中文显示档位（轻量/标准/完整/监控）。"""
    return ANALYSIS_TIERS[tier_for_mode(mode)]["display_name"]


def tier_scope(mode: str) -> str:
    """机器名 → 该档实际跑什么（一句话）。"""
    return ANALYSIS_TIERS[tier_for_mode(mode)]["scope"]


def tier_table() -> list[dict]:
    """档位表（供文档/卡面渲染）。唯一权威，别处不要另抄一份。"""
    return [
        {
            "tier": tier,
            "machine": ANALYSIS_TIERS[tier]["machine"],
            "label": ANALYSIS_TIERS[tier]["label"],
            "display_name": ANALYSIS_TIERS[tier]["display_name"],
            "scope": ANALYSIS_TIERS[tier]["scope"],
            "triggers": [kw for t, kws in _TIER_KEYWORD_ROUTES if t == tier for kw in kws],
        }
        for tier in TIER_ORDER
    ]


def resolve_tier(request: str) -> str:
    """自然语言 → 对话档位（L1/L2/L3/MON）。

    默认 L1：无动词的裸品种名（「BTC」「XAU」）按轻量起步，用户追问再升级；
    绝不默认上全管线。含硬开关词（分析/深度/完整卡）一定落 L3。
    """
    text = str(request or "").strip().lower()
    for tier, keywords in _TIER_KEYWORD_ROUTES:
        if any(kw in text for kw in keywords):
            return tier
    return "L1"


MODE_SPECS = {
    "quick": {
        "refresh_scope": "execution_only",
        "requires_new_screenshot": True,
        "card": "snapshot",
        "required_output": ["price", "primary_indicator", "cross_validation", "trigger_or_blocker"],
    },
    "inherit": {
        "refresh_scope": "execution_plus_context",
        "requires_new_screenshot": True,
        "card": "delta",
        "required_output": ["what_changed", "inherited_context", "price", "cross_validation", "trigger_or_blocker"],
    },
    # 对话层称为“标准”；保留 inherit 作为内部兼容别名。
    "standard": {
        "refresh_scope": "execution_plus_context",
        "requires_new_screenshot": True,
        "card": "delta",
        "required_output": ["what_changed", "inherited_context", "price", "cross_validation", "trigger_or_blocker"],
    },
    "full": {
        "refresh_scope": "all_sources",
        "requires_new_screenshot": True,
        "card": "full",
        "required_output": ["five_timeframes", "key_levels", "source_matrix", "final_verdict", "pipeline_audit"],
    },
    "monitor": {
        "refresh_scope": "event_only",
        "requires_new_screenshot": False,
        "card": "none",
        "required_output": ["event_id", "event_type", "analysis_required"],
    },
}


# Public crypto Full contract: ten collection/output stages plus five
# decision stages. All fallbacks should use this tuple instead of copying a
# stale prose list.
CRYPTO_FULL_PIPELINE = (
    "tv", "binance", "cg_pro", "macro", "x_sent", "cron_read",
    "cvd", "depth", "corr", "engine", "regime", "dual",
    "advanced", "risk", "card",
)


def validate_analysis_mode(mode: str) -> str:
    """Normalize a known machine mode; reject explicit invalid input."""
    key = mode.strip().lower() if isinstance(mode, str) else None
    if key not in MODE_SPECS:
        raise ValueError(f"Unknown analysis mode {mode!r}; expected one of: {', '.join(MODE_SPECS)}")
    return key


def analysis_mode_spec(mode: str) -> dict:
    """Return the required refresh and output contract for an analysis tier.

    模式名大小写不敏感（对话层会写 Quick/Full），但**未知模式必须显式失败**：
    静默回落到 quick 会把「档位写错」伪装成一次正常的快速更新，
    等于让 Full 少跑十一步而卡面看不出来。未知档位统一抛出 ValueError。
    """
    key = validate_analysis_mode(mode)
    spec = deepcopy(MODE_SPECS[key])
    spec["mode"] = key
    return dict(spec)


def step_description(step: str, asset_class: str) -> str:
    return str(ASSET_STEP_DESCRIPTIONS.get(step, {}).get(asset_class) or STEPS[step]["desc"])


def cron_sources(symbol: str) -> list[str]:
    """返回该品种应读取的 cron 输出文件列表（不含 .json 后缀）"""
    ac = _asset_class(symbol)
    return CRON_SOURCES.get(ac, CRON_SOURCES["other"])


def route_pipeline(symbol: str, mode: str = "full") -> list[str]:
    """返回应执行的步骤ID列表。

    mode（大小写不敏感）:
      'full' — 完整分析（加密固定15步；其他资产按适用步骤路由）
      'quick' — 快速更新（3步核心）
      'inherit'/'standard' — 继承高周期，只刷新主执行/触发与加密衍生品
      'monitor' — 监控模式（仅事件）

    未知 mode 与 analysis_mode_spec 一致抛出 ValueError，不生成任何管线。
    省略 mode 仍默认 full；显式空值不等于省略。
    """
    mode = validate_analysis_mode(mode)
    identity = parse_asset_identity(symbol)
    ac = identity["asset_class"]
    # 期权跟随底层：用底层的步骤集，再补上期权链。底层未知时用 option 自身规则。
    follows = None
    if ac == "option":
        base = identity.get("underlying_class")
        if base in TF_RULES and base not in ("option", "other"):
            follows, ac = base, base

    if mode in ("quick", "inherit", "standard"):
        # 快速/继承不重拉宏观与X情绪；高周期上下文由调用方从最近一次完整卡继承。
        # TV步骤的具体周期由执行器决定：crypto=15m+5m，gold=5m+触发周期。
        quick_map = {
            "crypto":  ["tv", "binance", "card"],
            "gold":    ["tv", "card"],
            "forex":   ["tv", "card"],
            "stock":   ["tv", "card"],
            "futures": ["tv", "card"],
            "option":  ["tv", "card"],
            "index":   ["tv", "card"],
            "other":   ["tv", "card"],
        }
        steps = [s for s in quick_map.get(ac, ["tv", "card"]) if s in STEPS]
        return _add_option_chain(steps, identity)

    if mode == "monitor":
        mon_map = {
            # Monitor is an event-discovery mode. It must not render a
            # directional card or be mistaken for an analysis request.
            # 因此 monitor 也**不补期权链**：那是分析步骤，不是事件发现。
            "crypto": ["binance"],
        }
        return [s for s in mon_map.get(ac, []) if s in STEPS]

    if mode == "full" and ac == "crypto":
        return _add_option_chain(list(CRYPTO_FULL_PIPELINE), identity)

    # full mode: 所有适用于该资产类别的步骤
    ordered = [
        "tv",          # ① TV MCP 五层全周期 + 截图@主周期
        "binance",     # ② Binance 衍生品（仅加密）
        "cg_pro",      # ③ CoinGecko Pro（仅加密）
        "macro",       # ④ 宏观背景（含金十+Poly+FG）
        "x_sent",      # ⑤ X情绪（实时x_search·所有市场）
        "cron_read",   # ⑥ 读Cron输出（dune/deribit/cot/qlib/liq/stablecoin）
        "cvd",         # ⑦ CVD订单流（加密/黄金）
        "depth",       # ⑧ 深度数据（仅加密）
        "corr",        # ⑨ 跨资产相关性
        "engine",      # ⑩ 核心模型引擎
        "regime",      # ⑪ 市场体制
        "dual",        # ⑫ 双指标确认
        "advanced",    # ⑬ 高级订单流
        "risk",        # ⑭ 风控与FinalVerdict
        "gold_macro",  # ⑩ 黄金宏观（仅黄金：TIP/GLD/GDX/白银比）
        "forex_rate",  # ⑩ 外汇利率（仅外汇：利差/央行窗口）
        "fmp",         # ⑪ FMP基本面（仅股票）
        "options_chain",# ⑫ 期权链（期权/股票）
        "card",        # 🔚 出卡
    ]
    steps = [s for s in ordered if s in STEPS and ac in STEPS[s]["assets"]]
    assert steps, f"路由为空：asset_class={ac!r} symbol={symbol!r} 未命中任何步骤"
    return _add_option_chain(steps, identity)


def _add_option_chain(steps: list[str], identity: dict) -> list[str]:
    """期权标的始终补上期权链步骤（放在出卡之前）。

    期权分析跟随底层做方向，但 OI/IV/Greeks 只能从期权链来，少这一步
    等于给期权一个残缺的方向卡。
    """
    if not steps:
        # Monitor 等「仅事件」档位本来就无步骤：补期权链会把它变成一次分析。
        return steps
    if identity.get("asset_class") != "option" or "options_chain" not in STEPS:
        return steps
    if "options_chain" in steps:
        return steps
    out = list(steps)
    out.insert(-1 if out and out[-1] == "card" else len(out), "options_chain")
    return out


def crypto_full_pipeline() -> list[str]:
    """Return the canonical fifteen-stage crypto Full route.

    Keep this helper as the single fallback source for callers that cannot
    import/execute the normal router path.  It intentionally returns a copy
    so callers cannot mutate the contract for later analyses.
    """
    return list(CRYPTO_FULL_PIPELINE)


def resolve_analysis_mode(request: str, *, has_context: bool = False) -> str:
    """把自然语言请求映射到 quick/standard/full 三档（= L1/L2/L3）。

    档位判定**唯一走 `resolve_tier`**，避免关键词表两处漂移（这正是 20260911
    修掉的缺陷：技能承诺「扫一下/状态」= 标准档，而这张表不认 → 静默降档）。
    标准档在对话层固定对应「现在呢/继续/接着看/更新」等追踪请求，不因上下文是否
    存在而偷偷降为 quick；``has_context`` 只供调用方判断继承内容是否可用，不改变
    用户所选档位。
    """
    tier = resolve_tier(request)
    if tier not in ANALYSIS_TIERS:
        return "quick"
    machine = ANALYSIS_TIERS[tier]["machine"]
    return machine if machine in MODE_SPECS else "quick"


def context_file(symbol: str) -> Path:
    """返回最近一次分析上下文文件路径；只存摘要/时间，不存凭据。"""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(symbol).upper())
    return Path.home() / "AppData/Local/hermes/data" / f"analysis_context_{safe}.json"


def context_is_fresh(symbol: str, *, max_age_hours: float = 4.0) -> bool:
    """判断是否可以继承高周期背景。"""
    p = context_file(symbol)
    try:
        d = __import__("json").loads(p.read_text(encoding="utf-8"))
        ts = float(d.get("updated_epoch", 0))
        age = datetime.now(timezone.utc).timestamp() - ts
        return ts > 0 and -60.0 <= age <= max_age_hours * 3600
    except (OSError, ValueError, TypeError):
        return False


def load_analysis_context(symbol: str, *, max_age_hours: float = 4.0) -> dict | None:
    """读取新鲜上下文；过期或品种不匹配时返回 None。"""
    p = context_file(symbol)
    try:
        data = __import__("json").loads(p.read_text(encoding="utf-8"))
        if str(data.get("symbol", "")).upper() != str(symbol).upper():
            return None
        ts = float(data.get("updated_epoch", 0))
        age = datetime.now(timezone.utc).timestamp() - ts
        if ts <= 0 or age < -60.0 or age > max_age_hours * 3600:
            return None
        return data
    except (OSError, ValueError, TypeError):
        return None


def _compact_timeframes(timeframes: dict | None) -> dict:
    """Keep only the small, decision-relevant part of a TF snapshot."""
    if not isinstance(timeframes, dict):
        return {}
    allowed = {
        "open", "close", "high", "low", "price", "change_pct", "poc", "vah", "val",
        "vwap", "npoc", "direction", "description", "tv_source", "tv_timestamp",
        "tv_identity_valid", "tv_ohlcv_complete", "tv_action_grid",
    }
    compact = {}
    for tf, record in timeframes.items():
        if not isinstance(record, dict):
            continue
        compact[tf] = {key: record[key] for key in allowed if key in record}
    return compact


def save_analysis_context(
    symbol: str,
    *,
    mode: str,
    price=None,
    levels=None,
    timeframes: dict | None = None,
    tv_five_tf_status: dict | None = None,
    macro: dict | None = None,
    final_verdict: dict | None = None,
    primary_action: dict | None = None,
    source_matrix: list[dict] | None = None,
    keylevels_revision: str | None = None,
) -> Path:
    """保存可继承的轻量上下文，供“现在呢”避免重扫高周期。"""
    p = context_file(symbol)
    p.parent.mkdir(parents=True, exist_ok=True)
    compact_timeframes = _compact_timeframes(timeframes)
    now_utc = datetime.now(timezone.utc)
    payload = {
        "context_schema_version": 2,
        "symbol": symbol,
        "mode": mode,
        "updated_epoch": now_utc.timestamp(),
        "updated_at": now_utc.astimezone(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "price": price,
        "levels": levels or [],
    }
    if compact_timeframes:
        payload["timeframes"] = compact_timeframes
        payload["timeframes_complete"] = len(compact_timeframes) == 5
    if isinstance(tv_five_tf_status, dict):
        payload["tv_five_tf_verified"] = bool(tv_five_tf_status.get("usable"))
        payload["tv_five_tf_source"] = tv_five_tf_status.get("source")
    if isinstance(macro, dict) and macro:
        payload["macro"] = dict(macro)
    if isinstance(final_verdict, dict) and final_verdict:
        final_keys = (
            "state", "executable", "side", "grade", "model_id", "rr", "risk_usd",
            "blockers", "warnings", "reason", "watch_side", "watch_entry",
        )
        payload["final_verdict"] = {
            key: final_verdict.get(key)
            for key in final_keys
            if key in final_verdict
        }
    if isinstance(primary_action, dict) and primary_action:
        action_keys = (
            "state", "side", "grade", "model_id", "direction_text", "execution",
            "reason", "watch_entry", "rr",
        )
        payload["primary_action"] = {
            key: primary_action.get(key)
            for key in action_keys
            if key in primary_action
        }
    if isinstance(source_matrix, list):
        payload["source_matrix"] = [
            {
                key: row.get(key)
                for key in ("id", "status", "role", "entered_final_verdict", "evidence", "conflict", "timestamp", "source_error", "payload_present", "requested")
                if key in row
            }
            for row in source_matrix
            if isinstance(row, dict)
        ]
    if keylevels_revision is None:
        try:
            config_path = Path(__file__).resolve().parents[1] / "data" / "keylevels_config.json"
            keylevels_revision = hashlib.sha256(config_path.read_bytes()).hexdigest()[:16]
        except OSError:
            keylevels_revision = None
    if keylevels_revision:
        payload["keylevels_revision"] = keylevels_revision
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from atomic_json import atomic_write_json
    atomic_write_json(p, payload)
    return p


def pipeline_summary(symbol: str, mode: str = "full") -> str:
    """可读的流程摘要"""
    ac = _asset_class(symbol)
    tfinfo = timeframe_info(symbol)
    steps = route_pipeline(symbol, mode)
    lines = [f"{symbol} [{ac}] {mode}模式 ({len(steps)}步) 主周期={tfinfo['main']}:"]
    for s in steps:
        info = STEPS[s]
        lines.append(f"  {s:15s} → {info['label']}: {step_description(s, ac)}")
    # 附加 cron 源
    if "cron_read" in steps:
        cs = cron_sources(symbol)
        lines.append(f"\n  cron_read 将读取: {', '.join(f'data/{c}.json' for c in cs)}")
    return "\n".join(lines)


def step_counts(symbol: str) -> dict:
    """返回 {included: N, skipped: M, total: T}"""
    ac = _asset_class(symbol)
    ordered = list(STEPS.keys())
    included = [s for s in ordered if s in STEPS and ac in STEPS[s]["assets"]]
    skipped = [s for s in ordered if s not in included]
    return {"included": len(included), "skipped": len(skipped), "total": len(ordered),
            "included_steps": included, "skipped_steps": skipped}


# ===== CLI =====
if __name__ == "__main__":
    import sys
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["BTCUSDT", "XAUUSD", "EURUSD", "AAPL", "ES"]
    for sym in symbols:
        for mode in ["quick", "full"]:
            print(pipeline_summary(sym, mode))
            print()
            tfinfo = timeframe_info(sym)
            print(f"  五层TF: {'→'.join(tfinfo['layers'])} · 主周期={tfinfo['main']} · 截图={tfinfo['screenshot']}")
            sc = step_counts(sym)
            print(f"  当前模式执行{len(route_pipeline(sym, mode))}步 · 全量适用步骤{sc['included']}步")
            print()
            print("---")
            print()
