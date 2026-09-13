#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""XAU 五周期 OHLCV 取数 —— 不切图。

## 为什么需要它
XAU 现场同步原来为取五周期 OHLCV 要切 5 次周期（加品种与归还共 7 次），
而用户会看到 TV 图表自己在切品种和周期。核对源码后确认：
那 5 个周期的循环只读 `get_chart_state` + `get_ohlcv`，
**完全不读指标**（没有 study_values / pine_lines / pine_labels），
报告 `_build_xau_report` 也只用 OHLCV。
→ 这 5 次切换纯属浪费，OHLCV 可以走 API。

## 取数优先级
  1. **OANDA v20**（`XAU_USD`）—— 与用户图表 `OANDA:XAUUSD` **同源**，最准。
     密钥文件 `hermes/secrets/oanda_token.txt` 当前是占位符，填进真 token 即自动启用。
  2. **TwelveData**（`XAU/USD`）—— 现货，5min/15min/1h/4h/1day 全覆盖。
     实测与 TV 的已闭合 K 线差约 0.1%，边界对齐。
  3. 都失败 → 返回 None，由调用方回退到「逐周期切图」的老路径（fail-safe）。

## 口径
与原来一致：只消费**最后一根已闭合** K 线（`bars[-2]` 的等价物），
返回 {tf: {open, high, low, close, change_pct}}。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "hermes" / "secrets"

TIMEFRAMES = ["1D", "4h", "1h", "15m", "5m"]

OANDA_GRAN = {"1D": "D", "4h": "H4", "1h": "H1", "15m": "M15", "5m": "M5"}
TD_INTERVAL = {"1D": "1day", "4h": "4h", "1h": "1h", "15m": "15min", "5m": "5min"}
TD_SYMBOL = "XAU/USD"
OANDA_INSTRUMENT = "XAU_USD"

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Tangxi/1.0"}


def _read_secret(name: str) -> str:
    """读取密钥；跳过注释行与占位符。"""
    try:
        raw = (SECRETS / name).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "//")):
            continue
        up = line.upper()
        if up.startswith(("PLACEHOLDER", "TODO", "CHANGEME", "YOUR_")):
            return ""
        return line
    return ""


def _http_json(url: str, headers: dict | None = None, timeout: int = 20) -> dict | None:
    """取 JSON。429 单独识别出来（源级熔断要用）。"""
    try:
        req = urllib.request.Request(url, headers={**_UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            _trip_breaker("twelvedata", "HTTP 429 限流")
        return None
    except Exception:
        return None


# ── 源级熔断（与全系统的降级契约一致：429 触发约 15 分钟熔断）──
BREAKER_FILE = ROOT / "data" / ".xau_ohlcv_breaker.json"
BREAKER_COOLDOWN_MIN = 15.0


def _trip_breaker(source: str, reason: str) -> None:
    try:
        import json as _json
        from datetime import datetime, timezone
        BREAKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        state = {}
        if BREAKER_FILE.exists():
            try:
                state = _json.loads(BREAKER_FILE.read_text(encoding="utf-8"))
            except Exception:
                state = {}
        state[source] = {"until_ts": datetime.now(timezone.utc).timestamp()
                         + BREAKER_COOLDOWN_MIN * 60,
                         "reason": reason}
        BREAKER_FILE.write_text(_json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def breaker_open(source: str) -> bool:
    """该源是否处于熔断期。熔断期间跳过它、直接降级 —— 不拿旧值冒充实时。"""
    try:
        import json as _json
        from datetime import datetime, timezone
        state = _json.loads(BREAKER_FILE.read_text(encoding="utf-8"))
        rec = state.get(source) or {}
        return float(rec.get("until_ts") or 0) > datetime.now(timezone.utc).timestamp()
    except Exception:
        return False


def _bar(open_, high, low, close) -> dict | None:
    """统一口径并做几何自检：H≥max(O,C)、L≤min(O,C)、L≤H，价格量级像黄金。"""
    try:
        o, h, l, c = float(open_), float(high), float(low), float(close)
    except (TypeError, ValueError):
        return None
    if not (500 < l <= h < 20000):
        return None
    if not (l <= min(o, c) and max(o, c) <= h):
        return None
    return {"open": o, "high": h, "low": l, "close": c,
            "change_pct": (c - o) / o * 100 if o else 0.0}


def _oanda_candles(token: str, granularity: str, count: int = 3) -> list[dict]:
    """返回该周期的 K 线列表（新的在前），只含已闭合的。"""
    for host in ("api-fxpractice.oanda.com", "api-fxtrade.oanda.com"):
        url = (f"https://{host}/v3/instruments/{OANDA_INSTRUMENT}/candles"
               f"?granularity={granularity}&count={count}&price=M")
        data = _http_json(url, headers={"Authorization": f"Bearer {token}"})
        if not data or "candles" not in data:
            continue
        out = []
        for c in reversed(data["candles"]):          # 统一成“新的在前”
            if not c.get("complete"):
                continue
            mid = c.get("mid") or {}
            bar = _bar(mid.get("o"), mid.get("h"), mid.get("l"), mid.get("c"))
            if bar:
                out.append(bar)
        if out:
            return out
    return []


def _twelvedata_candles(key: str, interval: str, count: int = 3) -> list[dict]:
    """TD 的 values[0] 是【正在形成】的 K 线，必须跳过。

    实测（2026-09-11 03:42 UTC）：5min 的 values[0] = 03:40（覆盖 03:40-03:45，
    正在形成）；15min 的 values[0] = 03:30（正在形成）；1day 的 values[0] = 今天。
    而 TV 那条路取的是 `last_5_bars[-2]` = 最后一根【已闭合】。
    口径必须一致，否则卡片上的高/低会随盘口跳动，且与用户图上对不上。
    """
    url = (f"https://api.twelvedata.com/time_series?symbol={TD_SYMBOL}"
           f"&interval={interval}&outputsize={max(count, 2)}&apikey={key}&timezone=UTC")
    data = _http_json(url)
    if not data or data.get("status") == "error":
        return []
    from xau_ohlcv_evidence import evidence, timestamp
    meta = data.get("meta") or {}
    tf = next((tf for tf, value in TD_INTERVAL.items() if value == interval), None)
    if meta.get("symbol") != TD_SYMBOL or meta.get("interval") != interval or not tf:
        return []
    # The request explicitly sets timezone=UTC; reject conflicting metadata.
    if meta.get("exchange_timezone", "UTC") not in ("UTC", "Etc/UTC"):
        return []
    values = data.get("values") or []
    def utc_time(v):
        raw = str(v.get("datetime") or "")
        return timestamp(raw + "+00:00") if raw else None
    times = [utc_time(v) for v in values]
    if any(t is None for t in times) or any(a <= b for a, b in zip(times, times[1:])):
        return []
    out = []
    for i, v in enumerate(values[1:], 1):
        bar = _bar(v.get("open"), v.get("high"), v.get("low"), v.get("close"))
        proof = evidence("twelvedata", meta["symbol"], tf, times[i].isoformat(),
                         next_open=times[i-1].isoformat())
        if bar and proof:
            bar.update(evidence=proof, volume=v.get("volume"), volume_kind="unavailable" if v.get("volume") is None else "provider_volume")
            out.append(bar)
    return out


def _clean(d: dict) -> dict:
    """把内部字段去掉，只留对外口径。

    2026-09-13：OHLCV 之外补带来源证据（evidence/volume/volume_kind）。
    消费者的既有口径（open/high/low/close/change_pct）保持不变，只做增量——
    否则「这层 K 线到底来自哪个源、哪根已闭合柱」在落盘后无法复核。
    """
    keep = ("open", "high", "low", "close", "change_pct", "evidence", "volume", "volume_kind")
    return {k: d[k] for k in keep if k in d}


def fetch_all(count: int = 3) -> dict:
    """取五周期 OHLCV。返回 {"source": ..., "timeframes": {tf: {...}}}。

    两个源都失败时返回 {}，调用方必须回退到逐周期切图的老路径。
    熔断中的源直接跳过（不拿旧缓存冒充实时）。
    """
    oanda_token = _read_secret("oanda_token.txt")
    td_key = _read_secret("twelvedata_api_key.txt")

    for source, fn, key in (("oanda", _oanda_candles, oanda_token),
                            ("twelvedata", _twelvedata_candles, td_key)):
        if not key:
            continue
        if breaker_open(source):
            continue
        frames: dict[str, dict] = {}
        for tf in TIMEFRAMES:
            gran = OANDA_GRAN[tf] if source == "oanda" else TD_INTERVAL[tf]
            bars = fn(key, gran, count)
            if not bars:
                frames = {}
                break
            frames[tf] = bars[0]                     # 新的在前 → [0] 即最后一根已闭合
        if len(frames) == len(TIMEFRAMES) and all(bars_ok(v) for v in frames.values()):
            return {"source": source,
                    "timeframes": {tf: _clean(frames[tf]) for tf in TIMEFRAMES}}
    return {}


def bars_ok(bar: dict) -> bool:
    """几何自检（外部源也可能给出坏数据）。"""
    try:
        o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]
    except (KeyError, TypeError):
        return False
    return bool(500 < l <= h < 20000 and l <= min(o, c) and max(o, c) <= h)


def cross_check(api_frames: dict, tv_bar: dict, tolerance: float = 0.0035) -> tuple[bool, str]:
    """用 TV 5m 的已闭合 K 线校核 API 数据。

    TV 只在一趟 5m 里被读到（为了 SVP 行动格），顺手拿它做校核：
    对得上就用 API 的五周期（省掉 4 次切图），对不上就回退到逐周期切图并告警。
    阈值 0.35% —— 实测跨源差异在 0.1% 量级，留 3 倍余量。
    """
    api_5m = (api_frames or {}).get("5m")
    if not api_5m or not tv_bar:
        return False, "缺 TV 5m 或 API 5m"
    diffs = {}
    for field in ("high", "low", "close"):
        tv_v = tv_bar.get(field)
        api_v = api_5m.get(field)
        if not tv_v or not api_v:
            return False, f"缺 {field}"
        diffs[field] = abs(api_v - tv_v) / tv_v
    worst = max(diffs.values())
    detail = " ".join(f"{k}={v * 100:.3f}%" for k, v in diffs.items())
    if worst <= tolerance:
        return True, f"5m 校核通过（{detail}）"
    return False, f"5m 校核超出 {tolerance * 100:.2f}%（{detail}）"
