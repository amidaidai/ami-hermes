#!/usr/bin/env python3
"""
stock_quote.py - 股票报价获取脚本

用法:
    python stock_quote.py <股票代码> [<股票代码> ...]

示例:
    python stock_quote.py AAPL
    python stock_quote.py AAPL MSFT GOOGL
    python stock_quote.py SH510500 SZ000651

输出: Markdown 表格，包含价格、涨跌幅、成交量等

数据源优先级:
    1. Stock-API MCP (仅支持 A 股代码: SH/SH/HK 前缀)
    2. yfinance (支持全球股票，作为美股/港股回退方案)
"""

import sys
import json
import subprocess
import urllib.request
import urllib.parse


def is_a_share(code: str) -> bool:
    """判断是否为 A 股代码（SH/SH/HK 前缀）"""
    code_upper = code.upper().strip()
    return code_upper.startswith(("SH", "SZ", "HK", "BJ"))


def fetch_via_stock_api_mcp(code: str) -> dict | None:
    """
    通过 Stock-API MCP 获取报价（使用 npx 调用）
    仅对 A 股代码有效。
    """
    # 使用 Hermes MCP JSON-RPC 调用
    # 由于 MCP 通过 Hermes agent 代理，这里尝试直接 HTTP 调用
    # 但 Stock-API MCP 是 stdio 模式，需要通过 agent tool_call
    # 这里我们尝试用 inspect 端点或直接返回 None 让调用方回退

    # Stock-API MCP 是 stdio MCP，无法从 Python 直接调用
    # 返回 None，由 yfinance 处理
    return None


def fetch_via_yfinance(code: str) -> dict | None:
    """
    通过 yfinance 获取股票报价
    支持全球股票（美股、港股、A股等）
    """
    try:
        import yfinance as yf
    except ImportError:
        print("错误: yfinance 未安装。请运行: pip install yfinance", file=sys.stderr)
        sys.exit(1)

    try:
        ticker = yf.Ticker(code)
        info = ticker.info

        if not info or info.get("regularMarketPrice") is None:
            # 尝试用 history 获取最新数据
            hist = ticker.history(period="1d")
            if hist.empty:
                return None
            row = hist.iloc[-1]
            return {
                "code": code.upper(),
                "name": info.get("shortName") or info.get("longName") or code.upper(),
                "price": round(float(row["Close"]), 2),
                "change_pct": round(float((row["Close"] - row["Open"]) / row["Open"] * 100), 2) if row["Open"] > 0 else 0,
                "volume": int(row["Volume"]),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "prev_close": round(float(row["Open"]), 2),
                "source": "yfinance",
            }

        price = info.get("regularMarketPrice", 0)
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or price
        change_pct = round(float((price - prev_close) / prev_close * 100), 2) if prev_close > 0 else 0

        return {
            "code": code.upper(),
            "name": info.get("shortName") or info.get("longName") or code.upper(),
            "price": round(float(price), 2),
            "change_pct": change_pct,
            "volume": info.get("volume") or info.get("regularMarketVolume") or 0,
            "high": round(float(info.get("dayHigh") or info.get("regularMarketDayHigh") or price), 2),
            "low": round(float(info.get("dayLow") or info.get("regularMarketDayLow") or price), 2),
            "prev_close": round(float(prev_close), 2),
            "pe": info.get("trailingPE"),
            "market_cap": info.get("marketCap"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "source": "yfinance",
        }
    except Exception as e:
        print(f"警告: yfinance 获取 {code} 失败: {e}", file=sys.stderr)
        return None


def format_market_cap(value: float | None) -> str:
    """格式化市值"""
    if value is None:
        return "N/A"
    if value >= 1e12:
        return f"{value/1e12:.2f}T"
    if value >= 1e9:
        return f"{value/1e9:.2f}B"
    if value >= 1e6:
        return f"{value/1e6:.2f}M"
    return f"{value:,.0f}"


def format_volume(value: int | None) -> str:
    """格式化成交量"""
    if value is None or value == 0:
        return "N/A"
    if value >= 1e8:
        return f"{value/1e8:.2f}亿"
    if value >= 1e4:
        return f"{value/1e4:.2f}万"
    return f"{value:,}"


def render_markdown_table(quotes: list[dict]) -> str:
    """将报价数据渲染为 Markdown 表格"""
    if not quotes:
        return "未获取到任何股票数据。\n"

    # 表头
    headers = ["代码", "名称", "价格", "涨跌幅(%)", "成交量", "最高", "最低", "数据源"]
    has_pe = any("pe" in q for q in quotes)
    has_mcap = any("market_cap" in q for q in quotes)

    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for q in quotes:
        change = q.get("change_pct", 0)
        change_str = f"{change:+.2f}%" if change != 0 else "0.00%"
        # 涨跌标记
        if change > 0:
            change_str = f"🔴 {change_str}"  # A股红涨
        elif change < 0:
            change_str = f"🟢 {change_str}"

        row = [
            q.get("code", "N/A"),
            q.get("name", "N/A"),
            str(q.get("price", "N/A")),
            change_str,
            format_volume(q.get("volume")),
            str(q.get("high", "N/A")),
            str(q.get("low", "N/A")),
            q.get("source", "N/A"),
        ]
        lines.append("| " + " | ".join(row) + " |")

    # 如果有 PE/市值数据，追加详细信息
    if has_pe or has_mcap:
        lines.append("")
        lines.append("### 详细信息")
        lines.append("")
        extra_headers = ["代码", "名称"]
        if has_pe:
            extra_headers.append("P/E")
        if has_mcap:
            extra_headers.append("市值")
        extra_headers.append("52周区间")

        lines.append("| " + " | ".join(extra_headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(extra_headers)) + " |")

        for q in quotes:
            extra_row = [q.get("code", ""), q.get("name", "")]
            if has_pe:
                pe = q.get("pe")
                extra_row.append(f"{pe:.2f}" if pe else "N/A")
            if has_mcap:
                extra_row.append(format_market_cap(q.get("market_cap")))
            # 52周区间
            h52 = q.get("52w_high")
            l52 = q.get("52w_low")
            if h52 and l52:
                extra_row.append(f"{l52:.2f} - {h52:.2f}")
            else:
                extra_row.append("N/A")
            lines.append("| " + " | ".join(extra_row) + " |")

    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) < 2:
        print(f"用法: python {sys.argv[0]} <股票代码> [<股票代码> ...]", file=sys.stderr)
        print(f"示例: python {sys.argv[0]} AAPL", file=sys.stderr)
        print(f"      python {sys.argv[0]} AAPL MSFT GOOGL", file=sys.stderr)
        sys.exit(1)

    codes = [c.strip() for c in sys.argv[1:] if c.strip()]
    quotes = []

    for code in codes:
        print(f"正在获取 {code} 的报价...", file=sys.stderr)

        # A 股尝试 Stock-API MCP（通过 npx 调用）
        if is_a_share(code):
            result = fetch_via_stock_api_mcp(code)
            if result:
                quotes.append(result)
                continue

        # 回退到 yfinance
        result = fetch_via_yfinance(code)
        if result:
            quotes.append(result)
        else:
            print(f"错误: 无法获取 {code} 的数据", file=sys.stderr)

    # 输出 Markdown 表格
    print(render_markdown_table(quotes))


if __name__ == "__main__":
    main()
