#!/usr/bin/env python3
"""棠溪 · 期权链分析模块 v1.0

统一接口：
  options_summary(symbol) -> dict
  options_card_line(symbol) -> str

数据源：
  BTC/ETH → Deribit (scripts/deribit_options.py)
  AAPL/TSLA/MSFT/AMZN/GOOGL/NVDA/META → yfinance
  其他 → 跳过（不报错）
"""

import sys, json, subprocess, os
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path("D:/Hermes agent")
SCRIPTS = ROOT / "scripts"
TZ = timezone(timedelta(hours=8))

def _parse_deribit_line(line: str) -> dict:
    """解析 '期权: BTCOI$20621M C/P=1.74 偏多 MaxPain=60000' 格式"""
    line = line.strip()
    result = {"type": "crypto_deribit", "source": "Deribit", "timestamp": datetime.now(TZ).isoformat(timespec="seconds")}
    try:
        # 分品种解析
        for part in line.replace("|", " ").split():
            if "BTCOI" in part or "ETHOI" in part:
                result["total_oi"] = part.split("$")[-1] if "$" in part else "?"
            if "C/P=" in part:
                result["cp_ratio"] = part.split("=")[-1]
            if "偏多" in part or "偏空" in part:
                result["verdict"] = part
            if "MaxPain=" in part:
                result["max_pain"] = part.split("=")[-1]
        if not result.get("cp_ratio"):
            # 尝试重新解析
            for part in line.split():
                if "C/P" in part:
                    result["cp_ratio"] = part.split("=")[-1].rstrip("%")
                if "MaxPain" in part:
                    result["max_pain"] = part.split("=")[-1]
        return result
    except Exception:
        return result


def _fetch_deribit() -> dict:
    """执行 deribit_options.py 并解析输出"""
    # 尝试读缓存（跨进程缓存文件）
    cache_path = ROOT / "data" / "deribit.json"
    cache_fresh = {}
    try:
        if cache_path.exists():
            cache_mtime = cache_path.stat().st_mtime
            if (datetime.now().timestamp() - cache_mtime) < 600:  # 10min 内缓存
                with open(cache_path) as f:
                    raw = f.read()[:500]
                for line in raw.split("\n"):
                    if "期权:" in line or "BTCOI" in line or "ETHOI" in line:
                        cache_fresh = _parse_deribit_line(line)
                        cache_fresh["source"] = "Deribit(cache)"
                        break
    except Exception:
        pass
    # 实时获取（25s 超时）
    try:
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "deribit_options.py"), "--line"],
            capture_output=True, text=True, timeout=25, cwd=str(ROOT)
        )
        out = r.stdout.strip()
        if out:
            return _parse_deribit_line(out)
    except subprocess.TimeoutExpired:
        if cache_fresh:
            return cache_fresh
    except Exception:
        pass
    return cache_fresh


def _fetch_yfinance(symbol: str) -> dict:
    """用 yfinance 获取美股期权数据"""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        exps = t.options
        if not exps:
            return {}
        # 取最近到期日
        chain = t.option_chain(exps[0])
        calls, puts = chain.calls, chain.puts
        if calls.empty and puts.empty:
            return {}
        cp_ratio = len(calls) / max(len(puts), 1)
        # IV
        call_iv = calls["impliedVolatility"].mean() if not calls.empty and "impliedVolatility" in calls else 0
        put_iv = puts["impliedVolatility"].mean() if not puts.empty and "impliedVolatility" in puts else 0
        avg_iv = (call_iv + put_iv) / 2
        # OI
        total_oi = int(calls["openInterest"].sum() + puts["openInterest"].sum())
        # 判定
        if cp_ratio > 1.3:
            verdict = "偏多"
        elif cp_ratio > 1.0:
            verdict = "中性偏多"
        elif cp_ratio > 0.7:
            verdict = "中性偏空"
        else:
            verdict = "偏空"
        return {
            "type": "stock_options",
            "source": "yfinance",
            "symbol": symbol,
            "expiry": str(exps[0]),
            "cp_ratio": round(cp_ratio, 2),
            "iv_pct": round(avg_iv * 100, 1),
            "total_oi": total_oi,
            "verdict": verdict,
            "timestamp": datetime.now(TZ).isoformat(timespec="seconds"),
        }
    except Exception:
        return {}


# --- 公开接口 ---

def options_summary(symbol: str) -> dict:
    """统一期权摘要接口"""
    sym = symbol.upper().replace("USDT", "").replace("USD", "")

    # BTC/ETH → Deribit
    if sym in ("BTC", "ETH"):
        d = _fetch_deribit()
        if d:
            d["symbol"] = sym
            return d

    # 美股 → yfinance
    stock_symbols = ("AAPL", "TSLA", "MSFT", "AMZN", "GOOGL", "NVDA", "META",
                     "GOOG", "NFLX", "AMD", "INTC", "PYPL", "SPY", "QQQ")
    if any(s.startswith(sym) or sym.startswith(s) for s in stock_symbols):
        return _fetch_yfinance(sym)

    return {}


def options_card_line(symbol: str) -> str:
    """一行期权摘要"""
    data = options_summary(symbol)
    if not data:
        return ""

    sym = symbol.upper()
    ts = data.get("timestamp", "")[11:16] if data.get("timestamp") else ""

    if data.get("type") == "crypto_deribit":
        oi = data.get("total_oi", "?")
        cp = data.get("cp_ratio", "?")
        verdict = data.get("verdict", "?")
        mp = data.get("max_pain", "?")
        return f"{sym}期权：OI${oi}·C/P={cp}{verdict}·MaxPain={mp}·{ts}"
    elif data.get("type") == "stock_options":
        cp = data.get("cp_ratio", "?")
        iv = data.get("iv_pct", "?")
        oi = data.get("total_oi", 0)
        verdict = data.get("verdict", "?")
        # OI 缩写
        if oi > 1_000_000:
            oi_str = f"{oi/1_000_000:.1f}M"
        elif oi > 1_000:
            oi_str = f"{oi/1_000:.0f}K"
        else:
            oi_str = str(oi)
        return f"{sym}期权：C/P={cp}{verdict}·IV{iv}%·OI{oi_str}·{ts}"

    return ""


if __name__ == "__main__":
    for sym in ("BTC", "AAPL", "TSLA", "MSFT", "XAU"):
        line = options_card_line(sym)
        if line:
            print(f"✅ {line}")
        else:
            print(f"ℹ️ {sym}: 无期权数据")
