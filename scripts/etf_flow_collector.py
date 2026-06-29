#!/usr/bin/env python3
"""
棠溪 · SoSoValue ETF Flow 采集器 v1.0
免费 · 无需 API Key · 抓取 SoSoValue 公开页面

输出: BTC ETF 日净流入/流出 + 累计 + 各ETF明细
用于: 驾驶舱 Step 5c — ETF Flow 验证

API: https://m.sosovalue.com/assets/etf/us-btc-spot
     页面内嵌 __NEXT_DATA__ JSON，直接解析
"""

import json, re, time, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
CACHE_FILE = ROOT / "data" / "etf_flow_cache.json"
CACHE_TTL = 600  # 10分钟缓存（ETF数据每天更新一次）


def _fetch_page() -> str:
    """抓取 SoSoValue BTC ETF 页面 — curl 避开 Python urllib 的 Cloudflare 拦截"""
    import subprocess
    url = "https://m.sosovalue.com/assets/etf/us-btc-spot"
    cmd = [
        "curl", "-sL", "--connect-timeout", "20",
        "-H", f"User-Agent: {UA}",
        "-H", "Accept: text/html,application/xhtml+xml",
        "-H", "Accept-Language: en-US,en;q=0.9",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    if result.returncode != 0 or not result.stdout:
        raise Exception(f"curl failed: {result.stderr[:200]}")
    return result.stdout


def _extract_from_html(html: str) -> dict:
    """从HTML提取ETF数据 — 多种策略"""
    out = {}

    # 策略1: __NEXT_DATA__ JSON
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if match:
        try:
            nd = json.loads(match.group(1))
            props = nd.get("props", {}).get("pageProps", {})
            if isinstance(props, dict):
                out["daily_net_inflow_usd"] = props.get("dailyNetInflow")
                out["cumulative_net_inflow_usd"] = props.get("cumulativeNetInflow")
                out["total_net_assets_usd"] = props.get("totalNetAssets")
                out["btc_price"] = props.get("btcPrice")
        except (json.JSONDecodeError, KeyError):
            pass

    # 策略2: 正则匹配页面内嵌 JSON 中的 netInflow
    if not out.get("daily_net_inflow_usd"):
        # 找第一个 netInflow（通常是 ETF 汇总）
        m = re.search(r'"netInflow":\s*"([^"]+)"', html)
        if m:
            try:
                val = float(m.group(1))
                out["daily_net_inflow_usd"] = val
            except ValueError:
                pass

    # 策略3: 累计 netInflow — 找 cumNetInflow 或 "Cumulative Total Net Inflow" 附近的数值
    if not out.get("cumulative_net_inflow_usd"):
        m = re.search(r'"cumNetInflow":\s*"([^"]+)"', html)
        if m:
            try:
                out["cumulative_net_inflow_usd"] = float(m.group(1))
            except ValueError:
                pass
    # 备用：从可见文本提取 "Cumulative Total Net Inflow $51.61B"
    if not out.get("cumulative_net_inflow_usd"):
        m = re.search(r'Cumulative\s+Total\s+Net\s+Inflow[^$]*\$?([\d,]+(?:\.\d+)?)\s*([BMK])', html, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                unit = m.group(2).upper()
                if unit == "B":
                    val *= 1e9
                elif unit == "M":
                    val *= 1e6
                elif unit == "K":
                    val *= 1e3
                out["cumulative_net_inflow_usd"] = val
            except ValueError:
                pass

    # 策略4: BTC 价格
    if not out.get("btc_price"):
        m = re.search(r'"btcPrice":\s*"?([\d.]+)"?', html)
        if m:
            try:
                out["btc_price"] = float(m.group(1))
            except ValueError:
                pass

    # 提取页面可见的数值行 (fallback)
    if not out.get("daily_net_inflow_usd"):
        m = re.search(r'-\$([\d,]+(?:\.\d+)?)\s*[MBK]?', html)
        if m:
            try:
                out["daily_net_inflow_usd"] = -float(m.group(1).replace(",", ""))
            except ValueError:
                pass

    return out


def parse_etf_flow() -> dict:
    """解析 ETF 流量数据"""
    html = _fetch_page()
    extracted = _extract_from_html(html)

    result = {
        "source": "SoSoValue",
        "url": "https://m.sosovalue.com/assets/etf/us-btc-spot",
        "fetched_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "daily_net_inflow_usd": extracted.get("daily_net_inflow_usd"),
        "cumulative_net_inflow_usd": extracted.get("cumulative_net_inflow_usd"),
        "total_net_assets_usd": extracted.get("total_net_assets_usd"),
        "btc_price": extracted.get("btc_price"),
    }

    # 方向判断
    inflow = result.get("daily_net_inflow_usd")
    if inflow is not None:
        try:
            val = float(inflow)
            if val > 100_000_000:
                result["signal"] = "🟢 强流入"
                result["signal_level"] = "strong_inflow"
            elif val > 0:
                result["signal"] = "🟢 流入"
                result["signal_level"] = "inflow"
            elif val > -100_000_000:
                result["signal"] = "🟡 微流出"
                result["signal_level"] = "mild_outflow"
            else:
                result["signal"] = "🔴 强流出"
                result["signal_level"] = "strong_outflow"
        except (ValueError, TypeError):
            result["signal"] = "⚪ 未知"

    result["ok"] = result.get("daily_net_inflow_usd") is not None
    return result


def get_etf_flow(cached: bool = True) -> dict:
    """获取 ETF 流量（带缓存）"""
    if cached and CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if time.time() - cache.get("ts", 0) < CACHE_TTL:
                return cache.get("data", {})
        except Exception:
            pass

    try:
        data = parse_etf_flow()
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps({"ts": time.time(), "data": data}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return data
    except Exception as e:
        # 过期缓存兜底
        if CACHE_FILE.exists():
            try:
                cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                data = cache.get("data", {})
                data["_stale"] = True
                data["_error"] = str(e)[:100]
                return data
            except Exception:
                pass
        return {"ok": False, "_error": str(e)[:200], "source": "SoSoValue"}


def get_etf_summary_line() -> str:
    """生成 ETF Flow 摘要行（用于分析卡）"""
    data = get_etf_flow()
    if not data.get("ok"):
        return "ETF Flow: 数据不可用"

    inflow = data.get("daily_net_inflow_usd", 0)
    cum = data.get("cumulative_net_inflow_usd", 0)
    signal = data.get("signal", "")

    def fmt(val) -> str:
        if val is None:
            return "N/A"
        val = float(val)
        if abs(val) >= 1e9:
            return f"${val/1e9:+.2f}B"
        elif abs(val) >= 1e6:
            return f"${val/1e6:+.1f}M"
        else:
            return f"${val:+,.0f}"

    return f"ETF Flow: {fmt(inflow)} ({signal}) · 累计 {fmt(cum)}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--line":
        print(get_etf_summary_line())
    elif len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps(get_etf_flow(cached=False), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(get_etf_flow(), indent=2, ensure_ascii=False, default=str))
