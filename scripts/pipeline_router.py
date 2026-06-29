#!/usr/bin/env python3
"""Pipeline Router v1.0 — 按资产类别自动选流程步骤
用于 auto_card.py / analysis pipeline 中自动跳过不适用的数据源。

用法:
    from pipeline_router import route_pipeline
    steps = route_pipeline("BTCUSDT")   # → ['tv', 'binance', 'cg', 'cvd', ...]
    steps = route_pipeline("XAUUSD")    # → ['tv', 'macro', 'jin10', 'cot', ...]
    steps = route_pipeline("EURUSD")    # → ['tv', 'macro', 'jin10', 'cot', ...]
"""


def _asset_class(symbol: str) -> str:
    su = symbol.upper()
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
    if su.isalpha() and len(su) <= 5:
        return "stock"
    return "other"


# ===== 每个步骤的定义 =====
STEPS = {
    # 步骤ID: {label, description, 适用资产集合, executor}
    "tv":       {"label": "TV技术面",    "desc": "TradingView SVP+Volume",              "assets": {"crypto", "gold", "forex", "stock", "option"}},
    "binance":  {"label": "Binance衍生品","desc": "OI/费率/Taker/LS/多空比",           "assets": {"crypto"}},
    "cg_pro":   {"label": "CoinGecko Pro","desc": "板块/流动性/市值排名",                "assets": {"crypto"}},
    "macro":    {"label": "宏观背景",     "desc": "SPX/VIX/DXY/US10Y",                   "assets": {"gold", "forex", "stock", "crypto"}},
    "jin10":    {"label": "金十日历",     "desc": "经济数据/利率决议/快讯",               "assets": {"crypto", "gold", "forex", "stock"}},
    "poly":     {"label": "Polymarket",  "desc": "Fed/衰退/加密事件概率",               "assets": {"crypto"}},
    "etf_flow": {"label": "ETF Flow",    "desc": "BTC ETF 日净流入/流出",               "assets": {"crypto"}},
    "dune":     {"label": "Dune链上",    "desc": "BTC流/CEX净流/稳定币",                "assets": {"crypto"}},
    "cot":      {"label": "COT持仓",     "desc": "投机/商业持仓方向",                    "assets": {"gold", "forex", "stock"}},
    "deribit":  {"label": "Deribit期权", "desc": "OI/C/P比/MaxPain",                    "assets": {"crypto"}},
    "x_sent":   {"label": "X情绪",       "desc": "社交媒体实时情绪",                     "assets": {"crypto", "gold", "forex", "stock"}},
    "fg":       {"label": "恐惧贪婪",     "desc": "加密恐惧贪婪指数",                    "assets": {"crypto"}},
    "cvd":      {"label": "CVD订单流",   "desc": "量价背离/吸收/FVG",                   "assets": {"crypto", "gold"}},
    "depth":    {"label": "深度数据",     "desc": "挂单墙/清算池",                       "assets": {"crypto"}},
    "card":     {"label": "输出分析卡",   "desc": "结构化分析卡输出",                    "assets": {"crypto", "gold", "forex", "stock", "option"}},
    "gold_macro":{"label":"黄金宏观",     "desc": "DXY/TIP/GLD/GDX/白银比",              "assets": {"gold"}},
    "fmp":      {"label": "FMP基本面",   "desc": "PE/市值/财报/板块",                    "assets": {"stock"}},
    "options_chain":{"label":"期权链",    "desc": "OI/IV/Greeks/到期日",                 "assets": {"option", "stock"}},
    "forex_rate":{"label": "外汇利率",    "desc": "利差/央行窗口/点差",                   "assets": {"forex"}},
}


def route_pipeline(symbol: str, mode: str = "full") -> list[str]:
    """返回应执行的步骤ID列表。

    mode:
      'full' — 完整分析（15+步骤）
      'quick' — 快速更新（5步核心）
      'monitor' — 监控模式（仅关键数据）
    """
    ac = _asset_class(symbol)

    if mode == "quick":
        quick_map = {
            "crypto": ["tv", "binance", "macro", "card"],
            "gold":   ["tv", "macro", "card"],
            "forex":  ["tv", "macro", "card"],
            "stock":  ["tv", "macro", "card"],
            "option": ["tv", "card"],
            "other":  ["tv", "macro", "card"],
        }
        return [s for s in quick_map.get(ac, ["tv", "card"]) if s in STEPS]

    if mode == "monitor":
        mon_map = {
            "crypto": ["tv", "binance", "macro", "card"],
            "gold":   ["tv", "macro", "card"],
            "forex":  ["tv", "macro", "card"],
            "stock":  ["tv", "macro", "fmp", "card"],
            "option": ["tv", "card"],
        }
        return [s for s in mon_map.get(ac, ["tv", "card"]) if s in STEPS]

    # full mode: 所有适用于该资产类别的步骤
    ordered = [
        "tv", "binance", "cg_pro", "macro", "jin10",
        "poly", "etf_flow", "dune", "cot", "deribit",
        "x_sent", "fg", "cvd", "depth",
        "gold_macro", "forex_rate", "fmp", "options_chain",
        "card",
    ]
    return [s for s in ordered if s in STEPS and ac in STEPS[s]["assets"]]


def pipeline_summary(symbol: str) -> str:
    """可读的流程摘要"""
    ac = _asset_class(symbol)
    steps = route_pipeline(symbol, "full")
    lines = [f"{symbol} [{ac}] 完整流程 ({len(steps)}步):"]
    for s in steps:
        info = STEPS[s]
        lines.append(f"  {s:15s} → {info['label']}: {info['desc']}")
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
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["BTCUSDT", "XAUUSD", "EURUSD", "AAPL"]
    for sym in symbols:
        print(pipeline_summary(sym))
        print()
        sc = step_counts(sym)
        print(f"  执行{sc['included']}步 · 跳过{sc['skipped']}步\n")
        print("---")
