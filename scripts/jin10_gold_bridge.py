#!/usr/bin/env python3
"""Jin10 Gold Bridge v1.0 — 封装 Jin10 MCP 调用，为 auto_card 提供黄金宏观上下文。

核心函数：
    fetch_gold_calendar()  → 本周黄金相关经济事件列表
    fetch_gold_news()      → 黄金相关快讯（"黄金", "XAU", "美元", "利率"）
    gold_macro_context()   → 综合：日历事件 + 快讯 + 报价 = 黄金宏观摘要

容错：Jin10 MCP 不可用时回退 web_search（标注「web源·非金十」）

注意：本模块设计为可被 auto_card 直接 import 调用。
      Jin10 MCP 调用复用 trading_system.jin10_quote 的 SSE 直连方式。
"""
from __future__ import annotations

import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 路径设置 ──
ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))

TZ = timezone(timedelta(hours=8))

# ── Jin10 MCP 配置 ──
JIN10_MCP_URL = "https://mcp.jin10.com/mcp"
TOKEN_PATH = ROOT / "hermes" / "secrets" / "jin10_token.txt"

# 黄金相关关键词
GOLD_KEYWORDS = ["黄金", "XAU", "美元", "利率", "美联储", "DXY", "US10Y", "通胀", "CPI", "非农", "FOMC"]

# ── 工具函数 ──


def _parse_sse_json(text: str) -> dict:
    """解析 Jin10 MCP SSE 响应"""
    payload = ""
    for line in text.splitlines():
        if line.startswith("data:"):
            payload += line[5:].lstrip()
    return json.loads(payload) if payload else {}


def _get_jin10_token() -> str | None:
    """读取 Jin10 MCP Token"""
    try:
        if TOKEN_PATH.exists():
            return TOKEN_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return None


def _jin10_mcp_call(tool_name: str, arguments: dict) -> dict:
    """直接调用 Jin10 MCP 工具（SSE 协议）

    返回解析后的 structuredContent 数据。
    失败返回 {"error": "..."}
    """
    token = _get_jin10_token()
    if not token:
        return {"error": "jin10_token.txt 不存在"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    try:
        import requests
    except ImportError:
        return {"error": "requests 未安装"}

    try:
        # 1. 初始化会话
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "tangxi-gold-bridge", "version": "1.0"},
            },
        }
        r = requests.post(JIN10_MCP_URL, headers=headers, json=init_payload, timeout=12)
        r.raise_for_status()
        session_id = r.headers.get("Mcp-Session-Id")
        if session_id:
            headers["Mcp-Session-Id"] = session_id

        # 2. 发送 initialized 通知
        requests.post(
            JIN10_MCP_URL,
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            timeout=8,
        )

        # 3. 调用工具
        call_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        r = requests.post(JIN10_MCP_URL, headers=headers, json=call_payload, timeout=15)
        r.raise_for_status()

        result = _parse_sse_json(r.content.decode("utf-8", "replace"))
        content = result.get("result", {}).get("structuredContent") or {}
        return content

    except Exception as e:
        return {"error": f"Jin10 MCP 调用失败: {e}"}


def _web_search_fallback(query: str) -> list[dict]:
    """回退：使用 web_search 搜索黄金信息

    注意：在纯 Python 脚本中无法直接调用 Hermes tool_call，
    这里使用 Brave Search API key 或返回空列表。
    """
    # 尝试读取 Brave API key
    brave_key_path = ROOT / "hermes" / "secrets" / "brave_api_key.txt"
    if not brave_key_path.exists():
        return []

    try:
        brave_key = brave_key_path.read_text(encoding="utf-8").strip()
        url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count=5"
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": brave_key,
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("web", {}).get("results", [])
            return [{"title": r.get("title", ""), "snippet": r.get("description", ""), "url": r.get("url", "")} for r in results[:5]]
    except Exception:
        return []


# ── 核心函数 ──


def fetch_gold_calendar() -> list[dict]:
    """获取本周黄金相关经济事件列表

    返回格式：
        [{"date": "2026-07-01", "time": "20:30", "country": "US", "event": "非农就业", "importance": "高", "forecast": "180k", "previous": "190k"}]
    """
    # 尝试 Jin10 MCP list_calendar（无参数，返回当前自然周）
    result = _jin10_mcp_call("list_calendar", {})

    if "error" not in result and result.get("data"):
        events = result["data"]
        if isinstance(events, list):
            # 过滤黄金/美元相关事件（star>=2 或 关键词匹配）
            gold_events = []
            gold_keywords = ["黄金", "XAU", "美联储", "FOMC", "利率决议", "CPI", "非农", "DXY", "美元", "通胀", "PCE", "GDP", "PMI", "失业", "零售销售", "消费者信心", "ISM", "ECB", "欧央行", "日央行", "BOJ", "加息", "降息"]
            for ev in events:
                title = str(ev.get("title", ""))
                star = int(ev.get("star", 0))
                # 保留 star>=2 的所有事件 + 黄金/美元直接相关
                is_gold_related = any(kw in title for kw in gold_keywords)
                if star >= 2 or is_gold_related:
                    pub_time = str(ev.get("pub_time", ""))
                    # 分离日期和时间
                    date_part = pub_time[:10] if len(pub_time) >= 10 else ""
                    time_part = pub_time[11:16] if len(pub_time) >= 16 else ""
                    # 影响方向
                    affect = ev.get("affect_txt", "")
                    affect_icon = "🔴" if "利高" in affect or "利空" in affect else "🟡" if affect else "⚪"
                    gold_events.append({
                        "date": date_part,
                        "time": time_part,
                        "event": title,
                        "importance": "高" if star >= 3 else "中" if star == 2 else "低",
                        "star": star,
                        "forecast": ev.get("consensus", ""),
                        "previous": ev.get("previous", ""),
                        "actual": ev.get("actual", ""),
                        "affect": affect,
                        "importance_icon": affect_icon,
                    })
            # 按 star 降序 + 时间升序
            gold_events.sort(key=lambda x: (-x.get("star", 0), x.get("date", "") + x.get("time", "")))
            return gold_events[:15]

    # 回退：web_search
    now = datetime.now(TZ)
    week_str = now.strftime("%Y-W%U")
    fallback_results = _web_search_fallback(f"gold macro calendar economic events {week_str}")
    if fallback_results:
        return [{"source": "web", "title": r.get("title", ""), "snippet": r.get("snippet", "")} for r in fallback_results]

    return []


def fetch_gold_news(keywords: list[str] | None = None) -> list[dict]:
    """搜索黄金相关快讯

    参数：
        keywords: 搜索关键词列表，默认 ["黄金", "XAU", "美元", "利率"]

    返回格式：
        [{"time": "20:30", "title": "...", "content": "...", "source": "金十"}]
    """
    if keywords is None:
        keywords = GOLD_KEYWORDS[:4]  # 默认前4个

    all_news = []
    seen_titles = set()

    for kw in keywords:
        result = _jin10_mcp_call("search_flash", {"keyword": kw})

        if "error" not in result:
            # search_flash 返回格式: {"data": {"items": [...]}}
            data = result.get("data", {})
            if isinstance(data, dict):
                items = data.get("items", [])
            elif isinstance(data, list):
                items = data
            else:
                items = []
            if isinstance(items, list):
                for item in items:
                    # search_flash 返回格式: {"content": "...", "time": "...", "url": "...", "title": "..."(可选)}
                    content = item.get("content", "")
                    title = str(item.get("title", "") or content)[:80]
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        time_str = str(item.get("time", ""))
                        # 简化时间格式：2026-06-30T16:00:42+08:00 → 16:00
                        if "T" in time_str:
                            time_str = time_str.split("T")[1][:5]
                        all_news.append({
                            "time": time_str,
                            "title": title,
                            "content": content[:200] if content != title else "",
                            "source": "金十",
                        })
        # 每个关键词之间不等待，快速收集

    # 如果 Jin10 完全不可用，回退 web_search
    if not all_news:
        fallback = _web_search_fallback("gold price today XAUUSD macro")
        for r in fallback:
            title = r.get("title", "")[:80]
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_news.append({
                    "time": "",
                    "title": title,
                    "content": r.get("snippet", "")[:200],
                    "source": "web源·非金十",
                })

    return all_news[:12]  # 最多12条


def fetch_gold_quote() -> dict:
    """获取黄金现货报价

    返回格式：
        {"price": 4310.50, "high": 4320, "low": 4295, "open": 4300, "change_pct": 0.24, "source": "金十"}
    """
    # 优先使用 trading_system 的 jin10_quote
    try:
        from trading_system import jin10_quote
        quote = jin10_quote("XAUUSD")
        if quote and quote.get("price"):
            raw = quote.get("raw", {})
            return {
                "price": quote["price"],
                "high": raw.get("high"),
                "low": raw.get("low"),
                "open": raw.get("open"),
                "change_pct": raw.get("change_pct"),
                "source": "金十Quote",
            }
    except Exception:
        pass

    # 回退：直接 MCP get_quote
    result = _jin10_mcp_call("get_quote", {"code": "XAUUSD"})
    if "error" not in result:
        data = result.get("data", result)
        price = data.get("close") or data.get("price")
        if price:
            return {
                "price": float(price),
                "high": data.get("high"),
                "low": data.get("low"),
                "open": data.get("open"),
                "change_pct": data.get("change_pct"),
                "source": "金十MCP",
            }

    # 最终回退：gold-api.com
    try:
        req = urllib.request.Request(
            "https://api.gold-api.com/price/XAU",
            headers={"User-Agent": "TangXi-GoldBridge/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            price = data.get("price")
            if price:
                return {"price": float(price), "source": "gold-api·非金十"}
    except Exception:
        pass

    return {"price": None, "source": "无数据"}


def gold_macro_context() -> str:
    """综合黄金宏观摘要：日历事件 + 快讯 + 报价

    输出格式：Markdown 列表
    容错：Jin10 MCP 不可用时回退 web_search 并标注「web源·非金十」
    """
    now = datetime.now(TZ)
    lines = []
    lines.append(f"## 🏆 黄金宏观摘要 · {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # ── 1. 报价 ──
    quote = fetch_gold_quote()
    price = quote.get("price")
    if price:
        change = quote.get("change_pct")
        try:
            change_f = float(change)
            change_str = f" ({change_f:+.2f}%)"
        except (TypeError, ValueError):
            change_str = ""
        try:
            high_val = float(quote.get("high", 0))
            high_str = f" | 高{high_val:.0f}" if high_val > 0 else ""
        except (TypeError, ValueError):
            high_str = ""
        try:
            low_val = float(quote.get("low", 0))
            low_str = f" | 低{low_val:.0f}" if low_val > 0 else ""
        except (TypeError, ValueError):
            low_str = ""
        lines.append(f"**XAUUSD: ${float(price):,.2f}{change_str}**{high_str}{low_str} · 来源: {quote.get('source', '?')}")
    else:
        lines.append("**XAUUSD: 暂无报价** · 所有数据源均不可用")
    lines.append("")

    # ── 2. 经济日历 ──
    lines.append("### 📅 本周关键事件")
    calendar = fetch_gold_calendar()
    if calendar:
        for ev in calendar[:10]:
            if ev.get("source") == "web":
                # web 回退格式
                lines.append(f"- 🌐 **[web源·非金十]** {ev.get('title', '')}")
            else:
                icon = ev.get("importance_icon", "⚪")
                forecast_str = f"预期{ev['forecast']}" if ev.get("forecast") else ""
                previous_str = f"前值{ev['previous']}" if ev.get("previous") else ""
                actual_str = f"**实际{ev['actual']}**" if ev.get("actual") else ""
                detail = " · ".join(filter(None, [forecast_str, previous_str, actual_str]))
                detail_str = f" | {detail}" if detail else ""
                affect_str = f" ({ev['affect']})" if ev.get("affect") else ""
                lines.append(
                    f"- {icon} **{ev.get('date', '')} {ev.get('time', '')}** "
                    f"{ev.get('event', '')}{affect_str}{detail_str}"
                )
    else:
        lines.append("- ⚠️ 日历数据不可用（Jin10 MCP 离线 + web_search 回退失败）")
    lines.append("")

    # ── 3. 快讯 ──
    lines.append("### ⚡ 黄金快讯")
    news = fetch_gold_news()
    if news:
        for item in news[:8]:
            source_tag = f" `[{item['source']}]`" if item.get("source") != "金十" else ""
            time_str = f"**{item['time']}** " if item.get("time") else ""
            lines.append(f"- {time_str}{item['title']}{source_tag}")
    else:
        lines.append("- ⚠️ 快讯数据不可用")
    lines.append("")

    return "\n".join(lines)


# ── CLI 入口 ──

if __name__ == "__main__":
    print(gold_macro_context())
