#!/usr/bin/env python3
"""多品种分析模板生成器 v1.0。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path("D:/Hermes agent")
OUT = ROOT / "data" / "symbol_templates.json"
MD_OUT = ROOT / "data" / "multi_symbol_templates.md"

FIXED_TERMS = "VWAP/POC/VAH/VAL/CVD/DO/OI/Funding/Basis/Taker/ATR/R:R/ETF"

TEMPLATES = {
    "BTC": {
        "symbol": "BTCUSDT",
        "name": "比特币",
        "market": "加密主流",
        "exchange": "Binance",
        "leverage": "100x",
        "risk_usd": 10,
        "default_risk_usd": 3,
        "timeframes": "5m · 15m · 1h · 4h",
        "swing_timeframes": "15m · 1h · 4h · 日",
        "price_sources": ["Binance现货", "Binance合约", "FinanceKit/CoinGecko", "TradingView"],
        "catalyst_sources": ["金十Flash", "web_search", "X/社区情绪", "ETF/宏观新闻"],
        "derivatives": ["Funding", "OI", "多空比", "Taker", "Basis", "清算区"],
        "models": ["VWAP反抽", "VAH/VAL回收", "POC拒绝", "扫流动性回收", "突破接受"],
        "monitor_levels": ["前高/前低", "日内VWAP", "1h VWAP", "清算密集区", "扫损位"],
        "notes": "社区情绪只调仓位，不覆盖结构；CVD低质量时必须降权。",
    },
    "ETH": {
        "symbol": "ETHUSDT",
        "name": "以太坊",
        "market": "加密主流",
        "exchange": "Binance",
        "leverage": "100x",
        "risk_usd": 10,
        "default_risk_usd": 3,
        "timeframes": "5m · 15m · 1h · 4h",
        "swing_timeframes": "15m · 1h · 4h · 日",
        "price_sources": ["Binance现货", "Binance合约", "FinanceKit/CoinGecko", "TradingView"],
        "catalyst_sources": ["金十Flash", "web_search", "X/社区情绪", "ETF/链上/生态新闻"],
        "derivatives": ["Funding", "OI", "多空比", "Taker", "Basis", "清算区"],
        "models": ["VWAP反抽", "VAH/VAL回收", "POC拒绝", "扫流动性回收", "突破接受"],
        "monitor_levels": ["BTC联动分歧位", "日内VWAP", "前高/前低", "清算密集区", "生态催化价位"],
        "notes": "必须同步看 BTC 强弱；ETH 单独走强才允许提高置信。",
    },
    "SOL": {
        "symbol": "SOLUSDT",
        "name": "Solana",
        "market": "加密高波动",
        "exchange": "Binance",
        "leverage": "20x",
        "risk_usd": 10,
        "default_risk_usd": 2,
        "timeframes": "5m · 15m · 1h · 4h",
        "swing_timeframes": "15m · 1h · 4h · 日",
        "price_sources": ["Binance现货", "Binance合约", "FinanceKit/CoinGecko", "TradingView"],
        "catalyst_sources": ["web_search", "X/社区情绪", "生态新闻", "BTC/ETH联动"],
        "derivatives": ["Funding", "OI", "多空比", "Taker", "Basis", "清算区"],
        "models": ["扫流动性回收", "突破接受", "POC拒绝", "VWAP反抽"],
        "monitor_levels": ["前高/前低", "快速插针位", "VWAP", "清算密集区"],
        "notes": "波动更快，默认轻仓；只做清晰触发，不追第一根放量。",
    },
    "BNB": {
        "symbol": "BNBUSDT",
        "name": "BNB",
        "market": "平台币",
        "exchange": "Binance",
        "leverage": "20x",
        "risk_usd": 10,
        "default_risk_usd": 2,
        "timeframes": "5m · 15m · 1h · 4h",
        "swing_timeframes": "15m · 1h · 4h · 日",
        "price_sources": ["Binance现货", "Binance合约", "FinanceKit/CoinGecko", "TradingView"],
        "catalyst_sources": ["Binance公告", "web_search", "监管新闻", "BTC联动"],
        "derivatives": ["Funding", "OI", "多空比", "Taker", "Basis"],
        "models": ["突破接受", "VWAP反抽", "VAH/VAL回收", "POC拒绝"],
        "monitor_levels": ["平台公告触发位", "前高/前低", "VWAP", "成交密集区"],
        "notes": "受 Binance 事件影响大，突发公告时先降仓。",
    },
    "XAU": {
        "symbol": "XAUUSD",
        "name": "黄金",
        "market": "贵金属",
        "exchange": "OANDA/TradingView",
        "leverage": "1000x",
        "risk_usd": 10,
        "default_risk_usd": 2,
        "timeframes": "5m · 15m · 1h · 4h",
        "swing_timeframes": "15m · 1h · 4h · 日",
        "price_sources": ["金十Quote", "TradingView", "FinanceKit/现货代理源"],
        "catalyst_sources": ["金十Flash", "财经日历", "美元指数", "美债收益率", "地缘风险"],
        "derivatives": ["不使用加密Funding/OI", "看美元/美债/实际利率", "事件波动"],
        "models": ["VWAP反抽", "VAH/VAL回收", "POC拒绝", "扫流动性回收", "突破接受"],
        "monitor_levels": ["亚盘高低", "伦敦高低", "纽约开盘位", "日内VWAP", "前高/前低"],
        "notes": "高杠杆默认轻仓；数据公布前后禁追价，优先等扫流动性回收。",
    },
    "USOIL": {
        "symbol": "USOIL",
        "name": "原油",
        "market": "能源商品",
        "exchange": "TradingView/金十",
        "leverage": "按账户规则",
        "risk_usd": 10,
        "default_risk_usd": 2,
        "timeframes": "5m · 15m · 1h · 4h",
        "swing_timeframes": "15m · 1h · 4h · 日",
        "price_sources": ["金十Quote", "TradingView", "FinanceKit/期货代理源"],
        "catalyst_sources": ["EIA/API库存", "OPEC新闻", "地缘风险", "美元"],
        "derivatives": ["库存/期限结构", "事件波动", "不使用加密Funding/OI"],
        "models": ["突破接受", "POC拒绝", "VWAP反抽", "扫流动性回收"],
        "monitor_levels": ["EIA前区间", "日内VWAP", "前高/前低", "新闻跳空位"],
        "notes": "库存和地缘事件权重高，事件窗口内无确认不做。",
    },
    "SPX": {
        "symbol": "SPX",
        "name": "标普500",
        "market": "美股指数",
        "exchange": "TradingView/FinanceKit",
        "leverage": "按账户规则",
        "risk_usd": 10,
        "default_risk_usd": 2,
        "timeframes": "5m · 15m · 1h · 4h",
        "swing_timeframes": "15m · 1h · 4h · 日",
        "price_sources": ["TradingView", "FinanceKit", "金十Quote如可用"],
        "catalyst_sources": ["美股财报", "CPI/FOMC", "VIX", "美债收益率", "美元"],
        "derivatives": ["VIX", "美债", "期权隐波", "市场宽度"],
        "models": ["突破接受", "VWAP反抽", "VAH/VAL回收", "POC拒绝"],
        "monitor_levels": ["美股开盘区间", "前高/前低", "VWAP", "VIX突变位"],
        "notes": "指数优先看宏观/财报/美债/VIX，不套用加密衍生指标。",
    },
}


def render_template(key: str, cfg: dict) -> str:
    lines = [
        f"# {cfg['name']} 分析模板",
        "",
        f"① 品种：{cfg['symbol']} · {cfg['market']} · 杠杆 {cfg['leverage']}",
        f"② 周期：日内 {cfg['timeframes']} · Swing {cfg['swing_timeframes']}",
        f"③ 风控：单笔上限 `{cfg['risk_usd']}U` · 默认风险 `{cfg['default_risk_usd']}U`",
        f"④ 术语：固定英文保留 {FIXED_TERMS}，其余尽量中文",
        "",
        "## 数据源",
        "- 价格：" + "；".join(cfg["price_sources"]),
        "- 催化：" + "；".join(cfg["catalyst_sources"]),
        "- 衍生/背景：" + "；".join(cfg["derivatives"]),
        "",
        "## 固定模型",
        "- " + "；".join(cfg["models"]),
        "",
        "## 监控位",
        "- " + "；".join(cfg["monitor_levels"]),
        "",
        "## 输出顺序",
        "① 状态 → ② 环境 → ③ 结构 → ④ 模型 → ⑤ 操作 → ⑥ 风控 → ⑦ 监控闭环",
        "",
        "## 特别规则",
        f"- {cfg['notes']}",
        "- C级数据最高只能 B等待；R:R 低于 1:2 直接 X禁做。",
        "- 社区情绪只调仓位，不覆盖结构。",
    ]
    return "\n".join(lines)


def write_outputs() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(TEMPLATES, ensure_ascii=False, indent=2), encoding="utf-8")
    parts = ["# 多品种分析模板索引", "", "以下模板由 scripts/multi_symbol_templates.py 生成。", ""]
    for key, cfg in TEMPLATES.items():
        parts.append(render_template(key, cfg))
        parts.append("\n---\n")
    MD_OUT.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["list", "render", "write"], nargs="?", default="list")
    ap.add_argument("symbol", nargs="?", default="")
    args = ap.parse_args()
    if args.action == "write":
        write_outputs()
        print(f"written {OUT} {MD_OUT}")
        return
    if args.action == "render":
        key = args.symbol.upper().replace("USDT", "")
        if key not in TEMPLATES:
            raise SystemExit(f"unknown symbol: {args.symbol}")
        print(render_template(key, TEMPLATES[key]))
        return
    print("\n".join(f"{k}: {v['symbol']} · {v['name']} · {v['market']}" for k, v in TEMPLATES.items()))


if __name__ == "__main__":
    main()
