#!/usr/bin/env python3
"""Pipeline Router v1.1 — 按资产类别自动选流程步骤 + 五层TF规则 + cron-read捷径
用于 auto_card.py / analysis pipeline 中自动跳过不适用的数据源。

v1.1 (2026-06-29): 五层TF统一(D/4h/1h/15m/5m)·cron_read捷径·步数精简·跨资产相关性

用法:
    from pipeline_router import route_pipeline, timeframe_info, pipeline_summary
    steps = route_pipeline("BTCUSDT")   # → ['tv', 'binance', 'cg_pro', 'macro', 'cron_read', 'cvd', 'depth', 'card']
    steps = route_pipeline("XAUUSD")    # → ['tv', 'macro', 'cron_read', 'cvd', 'card']
    steps = route_pipeline("EURUSD")    # → ['tv', 'macro', 'cron_read', 'card']
    tfinfo = timeframe_info("BTCUSDT")  # → {'layers': ['D','4h','1h','15m','5m'], 'main':'15m', 'screenshot':'15m'}
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _asset_class(symbol: str) -> str:
    su = symbol.upper()
    su_clean = su.split(":")[-1].replace("1!", "").replace("!", "")
    if "XAU" in su or "GOLD" in su or "XAG" in su:
        return "gold"
    if "CALL" in su or "PUT" in su or "OPTION" in su:
        return "option"
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
    if su in ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN"] or (su.isalpha() and len(su) <= 5):
        return "stock"
    return "other"


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
                "rationale": "跟底层品种"},
    "other":   {"layers": ["D", "4h", "1h", "15m", "5m"], "main": "15m", "screenshot": "15m",
                "rationale": "默认五层"},
}


def timeframe_info(symbol: str) -> dict:
    """返回推荐的时间框架信息。{layers, main, screenshot, rationale}"""
    ac = _asset_class(symbol)
    return TF_RULES.get(ac, TF_RULES["other"])


# ===== 每个步骤的定义 =====
STEPS = {
    # 步骤ID: {label, description, 适用资产集合, executor}
    "tv":       {"label": "TV技术面",    "desc": "TradingView SVP+Volume 五层(D/4h/1h/15m/5m)", "assets": {"crypto", "gold", "forex", "stock", "futures", "option"}},
    "binance":  {"label": "Binance衍生品","desc": "OI/费率/Taker/LS/多空比",           "assets": {"crypto"}},
    "cg_pro":   {"label": "CoinGecko Pro","desc": "板块/流动性/市值排名",                "assets": {"crypto"}},
    "macro":    {"label": "宏观背景",     "desc": "SPX/VIX/DXY/US10Y + 金十日历 + Poly + FG(加密)", "assets": {"gold", "forex", "stock", "crypto", "futures"}},
    "jin10":    {"label": "金十日历",     "desc": "经济数据/利率决议/快讯 [已并入macro]", "assets": set()},  # merged into macro
    "poly":     {"label": "Polymarket",  "desc": "Fed/衰退/加密事件概率 [已并入macro]",  "assets": set()},  # merged into macro
    "fg":       {"label": "恐惧贪婪",     "desc": "加密恐惧贪婪指数 [已并入macro]",      "assets": set()},  # merged into macro
    "cron_read":{"label": "读Cron输出",   "desc": "读取最近cron输出(不重跑):dune+deribit+x+qlib+liq+stablecoin+COT",
                                              "assets": {"crypto", "gold", "forex", "stock", "futures"}},
    "etf_flow": {"label": "ETF Flow",    "desc": "BTC ETF 日净流入/流出 [SoSoValue被封·Dune替代]", "assets": set()},  # dead
    "dune":     {"label": "Dune链上",    "desc": "BTC流/CEX净流/稳定币 [已并入cron_read]", "assets": set()},  # merged into cron_read
    "deribit":  {"label": "Deribit期权", "desc": "OI/C/P比/MaxPain [已并入cron_read]",   "assets": set()},  # merged into cron_read
    "x_sent":   {"label": "X情绪",       "desc": "x_search 实时X/Twitter情绪+恐贪+CGTrending", "assets": {"crypto", "gold", "forex", "stock", "futures"}},
    "cot":      {"label": "COT持仓",     "desc": "投机/商业持仓方向 [已并入cron_read]",   "assets": set()},  # merged into cron_read
    "cvd":      {"label": "CVD订单流",   "desc": "量价背离/吸收/FVG",                   "assets": {"crypto", "gold"}},
    "depth":    {"label": "深度数据",     "desc": "挂单墙/清算池",                       "assets": {"crypto"}},
    "corr":     {"label": "跨资产相关",   "desc": "BTC-SPX-XAU-DXY 相关性矩阵(FnanceKit)", "assets": {"crypto", "gold", "forex", "stock", "futures"}},
    "card":     {"label": "输出分析卡",   "desc": "结构化分析卡输出",                    "assets": {"crypto", "gold", "forex", "stock", "futures", "option"}},
    "gold_macro":{"label":"黄金宏观",     "desc": "DXY/TIP/GLD/GDX/白银比·央行黄金储备·金银比", "assets": {"gold"}},
    "fmp":      {"label": "FMP基本面",   "desc": "PE/市值/财报/板块",                    "assets": {"stock"}},
    "options_chain":{"label":"期权链",    "desc": "OI/IV/Greeks/到期日",                 "assets": {"option", "stock"}},
    "forex_rate":{"label":"外汇利率",     "desc": "利差/央行窗口/点差·Carry Trade基础",  "assets": {"forex"}},
}


# ===== cron_read 数据源映射（按资产类别） =====
CRON_SOURCES = {
    "crypto":  ["dune_cache", "deribit", "x_sentiment", "qlib", "liquidation", "stablecoin"],
    "gold":    ["cot", "xau_macro", "x_sentiment"],
    "forex":   ["cot", "x_sentiment"],
    "stock":   ["cot", "fmp", "x_sentiment"],
    "futures": ["cot", "x_sentiment"],
    "other":   ["cot", "x_sentiment"],
}


def cron_sources(symbol: str) -> list[str]:
    """返回该品种应读取的 cron 输出文件列表（不含 .json 后缀）"""
    ac = _asset_class(symbol)
    return CRON_SOURCES.get(ac, CRON_SOURCES["other"])


def route_pipeline(symbol: str, mode: str = "full") -> list[str]:
    """返回应执行的步骤ID列表。

    mode:
      'full' — 完整分析（8步加密 / 5-6步其他）
      'quick' — 快速更新（4步核心）
      'monitor' — 监控模式（仅关键数据）
    """
    ac = _asset_class(symbol)

    if mode == "quick":
        # 快速模式: TV五层 + 宏观 + card
        quick_map = {
            "crypto":  ["tv", "binance", "macro", "x_sent", "card"],
            "gold":    ["tv", "macro", "x_sent", "card"],
            "forex":   ["tv", "macro", "x_sent", "card"],
            "stock":   ["tv", "macro", "x_sent", "card"],
            "futures": ["tv", "macro", "x_sent", "card"],
            "option":  ["tv", "card"],
            "other":   ["tv", "macro", "x_sent", "card"],
        }
        return [s for s in quick_map.get(ac, ["tv", "card"]) if s in STEPS]

    if mode == "monitor":
        mon_map = {
            "crypto": ["tv", "binance", "macro", "card"],
            "gold":   ["tv", "macro", "card"],
            "forex":  ["tv", "macro", "card"],
            "stock":  ["tv", "macro", "fmp", "card"],
            "futures":["tv", "macro", "x_sent", "card"],
            "option": ["tv", "card"],
        }
        return [s for s in mon_map.get(ac, ["tv", "card"]) if s in STEPS]

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
        "gold_macro",  # ⑩ 黄金宏观（仅黄金：TIP/GLD/GDX/白银比）
        "forex_rate",  # ⑩ 外汇利率（仅外汇：利差/央行窗口）
        "fmp",         # ⑪ FMP基本面（仅股票）
        "options_chain",# ⑫ 期权链（期权/股票）
        "card",        # 🔚 出卡
    ]
    return [s for s in ordered if s in STEPS and ac in STEPS[s]["assets"]]


def pipeline_summary(symbol: str, mode: str = "full") -> str:
    """可读的流程摘要"""
    ac = _asset_class(symbol)
    tfinfo = timeframe_info(symbol)
    steps = route_pipeline(symbol, mode)
    lines = [f"{symbol} [{ac}] {mode}模式 ({len(steps)}步) 主周期={tfinfo['main']}:"]
    for s in steps:
        info = STEPS[s]
        lines.append(f"  {s:15s} → {info['label']}: {info['desc']}")
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
            print(f"  执行{sc['included']}步 · 跳过{sc['skipped']}步")
            print()
            print("---")
            print()
