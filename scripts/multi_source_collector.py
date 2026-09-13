#!/usr/bin/env python3
"""
棠溪 · 多源数据采集器 v3.3
集成了所有免费+Key API的统一数据层

已接入:
  CoinMarketCap (Key)  → 加密排名/行情/全球指标
  Alpha Vantage (Key)  → 股票报价
  Twelve Data (Key)    → 技术指标 RSI/MACD
  CoinGecko (Free)     → 社区/市占率/汇率
  alternative.me (Free)→ 恐慌贪婪
  Binance MCP          → 加密衍生品
  金十 MCP             → 快讯/日历/XAU
"""

import json, time, os, re, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from source_contract import (
    SOURCE_CONTRACT_VERSION,
    attach_source_contract,
    get_source_contract,
    source_record,
)
from source_health import payload_timestamp
from atomic_json import atomic_update_json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
SECRETS = ROOT / "hermes" / "secrets"
DATA = ROOT / "data"
CACHE = DATA / "api_cache.json"
CACHE_TTL = 120  # 2分钟通用缓存
SOURCE_STATE = DATA / "source_circuit_state.json"
SOURCE_COOLDOWN_SECONDS = 900

# ═══════════════════ Keys ═══════════════════
def _read_secret(name: str) -> str:
    try:
        return (SECRETS / name).read_text(encoding="utf-8").strip()
    except Exception:
        return ""

CMC_KEY = _read_secret("coinmarketcap_api_key.txt")
AV_KEY = _read_secret("alphavantage_api_key.txt")
TD_KEY = _read_secret("twelvedata_api_key.txt")
TUSHARE_TOKEN = _read_secret("tushare_token.txt")
FMP_KEY = _read_secret("fmp_api_key.txt")
MASSIVE_KEY = _read_secret("massive_api_key.txt")
CG_KEY = os.environ.get("CG_API_KEY", "") or _read_secret("coingecko_api_key.txt")


def _fetch(url: str, headers: dict[str, str] | None = None, timeout: int = 10) -> Any:
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _cached(key: str, fetcher, ttl: int = CACHE_TTL, cache_when=None):
    """带缓存的抓取。

    `cache_when(payload) -> bool` 决定这次的 payload 值不值得入缓存。
    默认「非空即可」，但对「取到部分字段才叫成功」的源（如 macro），
    调用方应传入只认带显式时间戳的判定，否则全失败也会被缓存成 cache。
    """
    should_cache = cache_when or (lambda payload: bool(payload))
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    entry = cache.get(key, {})
    # 2026-09-13 实测缺陷：空结果也会被当成「成功抓取」写进缓存，随后 5 分钟内
    # 以 status="cache"（属于 LIVE_STATES）返回 —— 宏观整步就是被这样洗成「live」的，
    # 而管线审计同时写着「本轮未采到有效字段」。空 payload 既不该入缓存，也不该算 live。
    cached_data = entry.get("data") if isinstance(entry, dict) else None
    if cached_data and time.time() - entry.get("ts", 0) < ttl:
        return _source_status(
            cached_data,
            "cache",
            cached=True,
            source_id=key,
            captured_at=entry.get("captured_at"),
        )
    circuit = _read_source_state().get(key, {})
    if circuit.get("blocked_until", 0) > time.time():
        return _source_status(
            cached_data or {},
            "quota_cooldown",
            cached=bool(cached_data),
            error=RuntimeError("quota cooldown"),
            source_id=key,
            captured_at=entry.get("captured_at") if cached_data else None,
        )
    try:
        data = fetcher()
        fetched_at = time.time()
        captured_at = payload_timestamp(data) if isinstance(data, dict) else None

        def merge_cache(current: Any) -> dict[str, Any]:
            merged = current if isinstance(current, dict) else {}
            merged[key] = {
                "ts": fetched_at,
                "captured_at": captured_at.isoformat() if captured_at else None,
                "data": data,
            }
            return merged

        if should_cache(data):  # 空结果不入缓存：否则失败会被洗成「5 分钟内的 cache」
            atomic_update_json(CACHE, merge_cache, default={})
        return _source_status(
            data,
            "live" if captured_at is not None else "unavailable",
            source_id=key,
            captured_at=captured_at,
            error=None if captured_at is not None else "missing_timestamp",
        )
    except Exception as e:
        if _classify_source_error(e) == "quota_or_rate_limited":
            _write_source_state(key, time.time() + SOURCE_COOLDOWN_SECONDS)
        if cached_data:
            return _source_status(
                cached_data,
                "stale_cache",
                cached=True,
                error=e,
                source_id=key,
                captured_at=entry.get("captured_at"),
            )
        return _source_status(
            {},
            "unavailable",
            error=e,
            source_id=key,
        )


def _source_status(
    data: Any,
    status: str,
    *,
    cached: bool = False,
    error: Any = None,
    source_id: str = "unknown",
    captured_at: Any = None,
) -> dict[str, Any]:
    """Attach observable source state without making a failed source fatal."""
    return attach_source_contract(
        data,
        source_id,
        status=status,
        captured_at=captured_at,
        error=error,
        cached=cached,
    )


def _read_source_state() -> dict:
    try:
        return json.loads(SOURCE_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_source_state(key: str, blocked_until: float) -> None:
    try:
        def merge_state(current: Any) -> dict[str, Any]:
            state = current if isinstance(current, dict) else {}
            state[key] = {"blocked_until": blocked_until, "reason": "quota_or_rate_limited"}
            return state
        atomic_update_json(SOURCE_STATE, merge_state, default={})
    except Exception:
        pass


def _classify_source_error(error: Exception) -> str:
    text = str(error).lower()
    if any(token in text for token in ("429", "rate limit", "quota", "too many")):
        return "quota_or_rate_limited"
    if any(token in text for token in ("401", "403", "unauthorized", "forbidden", "api key")):
        return "credential_or_plan_blocked"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    return "request_failed"


# ═══════════════════ CoinMarketCap ═══════════════════
def cmc_quote(symbol: str = "BTC") -> dict:
    """CMC实时行情"""
    def fetch():
        d = _fetch(
            f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?symbol={symbol}",
            headers={"X-CMC_PRO_API_KEY": CMC_KEY},
        )
        coin = d["data"][symbol]
        q = coin["quote"]["USD"]
        return {
            "price": q["price"],
            "market_cap": q["market_cap"],
            "volume_24h": q["volume_24h"],
            "percent_change_24h": q["percent_change_24h"],
            "percent_change_7d": q.get("percent_change_7d", 0),
            "rank": coin["cmc_rank"],
            "dominance": q.get("market_cap_dominance", 0),
            "last_updated": coin["last_updated"],
        }
    return _cached(f"cmc_{symbol}", fetch, ttl=120)


def cmc_global() -> dict:
    """CMC全球加密指标"""
    def fetch():
        d = _fetch(
            "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest",
            headers={"X-CMC_PRO_API_KEY": CMC_KEY},
        )
        m = d["data"]
        q = m["quote"]["USD"]
        return {
            "total_mc": q["total_market_cap"],
            "total_vol": q["total_volume_24h"],
            "btc_dominance": m["btc_dominance"],
            "eth_dominance": m["eth_dominance"],
            "active_cryptos": m["active_cryptocurrencies"],
            "mc_change_24h": q.get("total_market_cap_yesterday_percentage_change", 0),
        }
    return _cached("cmc_global", fetch)


def cmc_fear_greed() -> dict:
    """CMC恐慌贪婪 (替代alternative.me)"""
    def fetch():
        d = _fetch(
            "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest",
            headers={"X-CMC_PRO_API_KEY": CMC_KEY},
        )
        fg = d["data"]
        return {
            "value": fg["value"],
            "classification": fg.get("value_classification", fg.get("classification", "")),
            "timestamp": fg.get("timestamp", fg.get("update_time", "")),
        }
    return _cached("cmc_fg", fetch, ttl=600)


# ═══════════════════ CoinGecko (Free · FinanceKit替代) ═══════════════════

CG_BASE = "https://api.coingecko.com/api/v3"


def cg_top_coins(n: int = 10) -> dict:
    """Top N 加密排名 + BTC/ETH 市占率变化 → 板块轮动检测"""
    def fetch():
        d = _fetch(f"{CG_BASE}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page={n}&page=1&sparkline=false&price_change_percentage=1h,24h,7d",
            headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None)
        coins = []
        btc_dom_shift = 0
        for c in d:
            coins.append({
                "symbol": c["symbol"].upper(),
                "name": c["name"],
                "price": c["current_price"],
                "mc_rank": c.get("market_cap_rank"),
                "change_1h": c.get("price_change_percentage_1h_in_currency", 0),
                "change_24h": c.get("price_change_percentage_24h", 0),
                "change_7d": c.get("price_change_percentage_7d_in_currency", 0),
                "mc": c.get("market_cap", 0),
            })
            if c["symbol"].upper() == "BTC":
                btc_dom_shift = c.get("price_change_percentage_24h", 0)
        # Sector rotation signal: if BTC << alt avg → alt season
        alt_changes = [c["change_24h"] for c in coins if c["symbol"] not in ("BTC", "ETH", "USDT", "USDC")]
        avg_alt = sum(alt_changes) / len(alt_changes) if alt_changes else 0
        btc_change = next((c["change_24h"] for c in coins if c["symbol"] == "BTC"), 0)
        rotation = "BTC主导" if btc_change > avg_alt + 1 else "山寨季" if avg_alt > btc_change + 3 else "同步"
        return {
            "top_coins": coins,
            "btc_change_24h": btc_change,
            "avg_alt_change_24h": round(avg_alt, 2),
            "rotation": rotation,
            "coin_count": len(coins),
        }
    return _cached("cg_top", fetch, ttl=300)


def cg_trending() -> dict:
    """CoinGecko trending → 山寨热点检测"""
    def fetch():
        d = _fetch(f"{CG_BASE}/search/trending",
            headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None)
        coins = d.get("coins", [])[:7]
        items = []
        for c in coins:
            item = c.get("item", {})
            items.append({
                "symbol": item.get("symbol", "").upper(),
                "name": item.get("name", ""),
                "mc_rank": item.get("market_cap_rank"),
                "score": item.get("score", 0),
            })
        return {"trending": items, "count": len(items)}
    return _cached("cg_trend", fetch, ttl=600)


# ═══════════════════ CoinGecko Pro 新增端点 ═══════════════════

def cg_coin_detail(coin_id: str = "bitcoin") -> dict:
    """CoinGecko Pro 币种详情 — 流动性评分/社区/开发者数据"""
    def fetch():
        d = _fetch(
            f"{CG_BASE}/coins/{coin_id}?localization=false&tickers=false&community_data=true&developer_data=true&market_data=true",
            headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None,
        )
        md = d.get("market_data", {})
        cd = d.get("community_data", {})
        dd = d.get("developer_data", {})
        return {
            "name": d.get("name", ""),
            "symbol": d.get("symbol", "").upper(),
            "liquidity_score": md.get("liquidity_score"),
            "market_cap_fdv_ratio": md.get("market_cap_fdv_ratio"),
            "total_value_locked": md.get("total_value_locked"),
            "community_score": cd.get("community_score"),
            "twitter_followers": cd.get("twitter_followers"),
            "reddit_subscribers": cd.get("reddit_subscribers"),
            "dev_score": dd.get("score"),
            "github_stars": dd.get("stars"),
            "github_commits_4w": dd.get("commit_count_4_weeks"),
            "sentiment_votes_up_pct": d.get("sentiment_votes_up_percentage"),
            "sentiment_votes_down_pct": d.get("sentiment_votes_down_percentage"),
            "coingecko_score": d.get("coingecko_score"),
            "coingecko_rank": d.get("coingecko_rank"),
        }
    return _cached(f"cg_detail_{coin_id}", fetch, ttl=600)


def cg_categories() -> dict:
    """CoinGecko 板块/分类涨幅 — 轮动检测"""
    def fetch():
        d = _fetch(
            f"{CG_BASE}/coins/categories",
            headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None,
        )
        cats = []
        for c in d[:20]:
            cats.append({
                "name": c.get("name"),
                "change_24h": c.get("market_cap_change_24h"),
                "mc": c.get("market_cap"),
                "vol_24h": c.get("volume_24h"),
                "top_coins": c.get("top_3_coins", []),
            })
        # Sort by 24h change to detect rotation
        cats.sort(key=lambda x: x.get("change_24h", 0) or 0, reverse=True)
        top_cat = cats[0]["name"] if cats else ""
        bottom_cat = cats[-1]["name"] if cats else ""
        return {
            "categories": cats,
            "top_performer": top_cat,
            "bottom_performer": bottom_cat,
            "rotation_signal": f"资金流向: {top_cat} / 流出: {bottom_cat}" if cats else "N/A",
        }
    return _cached("cg_categories", fetch, ttl=600)


def cg_exchange_volumes(coin_id: str = "bitcoin") -> dict:
    """CoinGecko Pro 交易所成交量明细 — BTC 流动性验证"""
    def fetch():
        d = _fetch(
            f"{CG_BASE}/coins/{coin_id}/tickers?order=volume_desc&depth=true",
            headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None,
        )
        tickers = d.get("tickers", [])
        # Aggregate by exchange
        ex_map = {}
        for t in tickers[:50]:
            ex_name = t.get("market", {}).get("name", "Unknown")
            vol = t.get("converted_volume", {}).get("usd", 0) or 0
            ts = t.get("trust_score", "")
            if ex_name not in ex_map:
                ex_map[ex_name] = {"volume_usd": 0, "trust": ts, "pairs": 0}
            ex_map[ex_name]["volume_usd"] += vol
            ex_map[ex_name]["pairs"] += 1
        # Top exchanges by volume
        top_ex = sorted(ex_map.items(), key=lambda x: x[1]["volume_usd"], reverse=True)[:10]
        total_vol = sum(v["volume_usd"] for _, v in top_ex)
        exchanges = [{"exchange": n, "vol_24h_usd": v["volume_usd"],
                       "vol_share_pct": round(v["volume_usd"]/total_vol*100, 1) if total_vol else 0,
                       "trust": v["trust"], "pairs": v["pairs"]} for n, v in top_ex]
        # Flag low-trust exchanges (>10% volume on red/orange trust)
        low_trust_vol = sum(e["vol_share_pct"] for e in exchanges
                            if e["trust"] in ("red", "orange"))
        return {
            "exchanges": exchanges,
            "total_vol_24h": total_vol,
            "low_trust_vol_pct": round(low_trust_vol, 1),
            "volume_health": "✅" if low_trust_vol < 15 else "⚠" if low_trust_vol < 30 else "🚩",
        }
    return _cached(f"cg_exvol_{coin_id}", fetch, ttl=600)


# ═══════════════════ 市场概览 (SPX/VIX · FMP) ═══════════════════

def _fmp_change_pct(quote: dict) -> Any:
    """FMP 涨跌幅字段名在迁移前后不一致，必须两个都认。

    /api/v3 返回 `changesPercentage`；现行 /stable 返回 `changePercentage`（无 s）。
    只读旧名的代码会静默拿到 0 —— 实测 ^VIX 真实 -11.21%、^GSPC +0.86% 全被写成 0.0%。
    """
    for key in ("changePercentage", "changesPercentage"):
        if quote.get(key) is not None:
            return quote[key]
    return 0


def macro_overview() -> dict:
    """SPX + VIX + US10Y + DXY + Gold — 宏观快照

    2026-09-13 实测：FMP 已下线 `/api/v3/quote/{sym}`（403 Forbidden），
    同仓库的 `fmp_quote` / `fmp_forex` 早已迁到 `/stable/quote?symbol=`，
    只有这里漏迁 —— 结果是宏观整步恒 unavailable（0 字段）。
    现在改用 stable 端点，并**逐符号**记录可用性：本套餐下 ^VIX / ^GSPC 可用，
    ^TNX / DX-Y.NYB / GC=F 返回 402 Payment Required，如实标注而不补默认值。
    """
    def fetch():
        result = {}
        unavailable = {}
        symbols = [("^GSPC", "spx"), ("^VIX", "vix"), ("^TNX", "us10y"),
                   ("DX-Y.NYB", "dxy"), ("GC=F", "gold_fut")]
        for sym, label in symbols:
            try:
                d = _fetch(
                    "https://financialmodelingprep.com/stable/quote"
                    f"?symbol={urllib.parse.quote(sym)}&apikey={FMP_KEY}"
                )
            except Exception as exc:  # 402/403/超时：单符号失败不拖垮整步
                unavailable[label] = type(exc).__name__
                continue
            if isinstance(d, list) and d:
                q = d[0]
                result[label] = {
                    "price": float(q.get("price", 0)),
                    "change_pct": _fmp_change_pct(q),
                    "change": float(q.get("change", 0)),
                }
            else:
                unavailable[label] = "empty"
        # 宏观情绪分类：只允许用**真实取到**的字段判定。
        # 历史缺陷（2026-09-13 实测）：VIX 取数失败时用默认 20、SPX 用默认 0，
        # 于是失败场景固定输出「中性 | VIX 20 | SPX +0.0%」——看起来像采到了。
        def _num(value):
            try:
                number = float(value)
            except (TypeError, ValueError):
                return None
            return number if number == number and abs(number) != float("inf") else None

        vix_val = _num((result.get("vix") or {}).get("price"))
        spx_chg = _num((result.get("spx") or {}).get("change_pct"))
        if vix_val is None and spx_chg is None:
            sentiment = None
        elif vix_val is not None and vix_val > 30:
            sentiment = "恐慌 (Risk-off)"
        elif vix_val is not None and vix_val > 22:
            sentiment = "谨慎 (Risk-off 偏)"
        elif spx_chg is not None and spx_chg < -1:
            sentiment = "避险 (Risk-off)"
        elif spx_chg is not None and vix_val is not None and spx_chg > 1 and vix_val < 18:
            sentiment = "乐观 (Risk-on)"
        else:
            sentiment = "中性"
        if sentiment is not None:
            result["sentiment"] = sentiment
        if vix_val is not None:
            result["vix_level"] = vix_val
        if unavailable:
            # 哪几个字段取不到必须可见（本套餐 ^TNX/DX-Y.NYB/GC=F 是 402）
            result["unavailable_fields"] = unavailable
        if any(k in result for k in ("spx", "vix", "us10y", "dxy", "gold_fut")):
            # 只在这一轮真的取到东西时才盖时间戳：否则 _cached 只能报 unavailable，
            # 不允许拿旧快照冒充实时；也绝不让「全失败」被缓存成 cache。
            result["timestamp"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
        return result
    # 只有带显式时间戳（= 真的取到至少一个字段）的结果才值得缓存。
    return _cached("macro", fetch, ttl=300,
                   cache_when=lambda payload: bool(payload.get("timestamp")))


# ═══════════════════ Alpha Vantage ═══════════════════
def av_quote(symbol: str = "AAPL") -> dict:
    """Alpha Vantage 股票报价"""
    def fetch():
        d = _fetch(
            f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={AV_KEY}"
        )
        q = d.get("Global Quote", {})
        return {
            "price": float(q.get("05. price", 0)),
            "change": float(q.get("09. change", 0)),
            "change_pct": q.get("10. change percent", "0%"),
            "volume": int(q.get("06. volume", 0)),
            "high": float(q.get("03. high", 0)),
            "low": float(q.get("04. low", 0)),
            "open": float(q.get("02. open", 0)),
        }
    return _cached(f"av_{symbol}", fetch, ttl=120)


# ═══════════════════ Twelve Data ═══════════════════
def td_technical(symbol: str = "AAPL") -> dict:
    """Twelve Data 技术指标 (RSI/MACD/BB)"""
    def fetch():
        result = {}
        # RSI
        try:
            d = _fetch(
                f"https://api.twelvedata.com/rsi?symbol={symbol}&interval=1h&apikey={TD_KEY}"
            )
            result["rsi"] = float(d["values"][0]["rsi"])
        except Exception:
            result["rsi"] = None
        # MACD
        try:
            d = _fetch(
                f"https://api.twelvedata.com/macd?symbol={symbol}&interval=1h&apikey={TD_KEY}"
            )
            v = d["values"][0]
            result["macd"] = float(v["macd"])
            result["macd_signal"] = float(v["macd_signal"])
            result["macd_hist"] = float(v["macd_hist"])
        except Exception:
            result["macd"] = None
        return result
    return _cached(f"td_{symbol}", fetch, ttl=300)


def td_quote(symbol: str = "AAPL") -> dict:
    """Twelve Data 实时报价"""
    def fetch():
        d = _fetch(
            f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={TD_KEY}"
        )
        return {
            "price": float(d.get("close", 0)),
            "open": float(d.get("open", 0)),
            "high": float(d.get("high", 0)),
            "low": float(d.get("low", 0)),
            "volume": int(d.get("volume", 0)),
            "change": float(d.get("change", 0)),
            "change_pct": d.get("percent_change", 0),
        }
    return _cached(f"tdq_{symbol}", fetch, ttl=60)


# ═══════════════════ 汇总输出 ═══════════════════

# ═══════════════════ Massive.com ═══════════════════

def massive_aggs(symbol: str = "AAPL", asset: str = "stock") -> dict:
    try:
        from massive import RESTClient
        client = RESTClient(api_key=MASSIVE_KEY)
        ticker = symbol if asset == "stock" else f"X:{symbol}USD"
        result = client.get_aggs(ticker=ticker, multiplier=1, timespan="day", 
                                  from_="2026-06-17", to="2026-06-18", limit=2)
        if isinstance(result, list) and len(result) > 0:
            r = result[-1]
            def _to_float(value: Any) -> float:
                return float(value or 0)
            return {
                "open": _to_float(getattr(r, "open", 0)), "high": _to_float(getattr(r, "high", 0)),
                "low": _to_float(getattr(r, "low", 0)), "close": _to_float(getattr(r, "close", 0)),
                "volume": _to_float(getattr(r, "volume", 0)), "vwap": _to_float(getattr(r, "vwap", 0)),
                "timestamp": r.timestamp,
            }
    except Exception as e:
        return {"_error": str(e)[:80]}
    return {}


def massive_futures_snapshot(ticker: str = "ES") -> dict:
    """期货快照 (免费层)"""
    try:
        from massive import RESTClient
        client = RESTClient(api_key=MASSIVE_KEY)
        result = list(client.get_futures_snapshot(ticker=ticker, limit=1))
        if result:
            return {"snapshot": str(result[0])[:200]}
    except Exception as e:
        return {"_error": str(e)[:80]}
    return {}


# ═══════════════════ FMP (Financial Modeling Prep) ═══════════════════
def fmp_quote(symbol: str = "AAPL") -> dict:
    """FMP 股票/ETF 实时行情"""
    def fetch():
        d = _fetch(
            f"https://financialmodelingprep.com/stable/quote?symbol={symbol}&apikey={FMP_KEY}"
        )
        if isinstance(d, list) and d:
            q = d[0]
            return {
                "price": float(q.get("price", 0)),
                "change": float(q.get("change", 0)),
                "change_pct": _fmp_change_pct(q),
                "volume": int(q.get("volume", 0)),
                "high": float(q.get("dayHigh", 0)),
                "low": float(q.get("dayLow", 0)),
                "open": float(q.get("open", 0)),
                "prev_close": float(q.get("previousClose", 0)),
                "market_cap": q.get("marketCap", 0),
                "pe": q.get("pe", None),
            }
        return {}
    return _cached(f"fmp_{symbol}", fetch, ttl=120)


def fmp_forex(pair: str = "EURUSD") -> dict:
    """FMP 外汇实时行情"""
    def fetch():
        d = _fetch(
            f"https://financialmodelingprep.com/stable/quote?symbol={pair}&apikey={FMP_KEY}"
        )
        if isinstance(d, list) and d:
            q = d[0]
            return {
                "price": float(q.get("price", 0)),
                "change": float(q.get("change", 0)),
                "change_pct": _fmp_change_pct(q),
                "high": float(q.get("dayHigh", 0)),
                "low": float(q.get("dayLow", 0)),
            }
        return {}
    return _cached(f"fmpfx_{pair}", fetch, ttl=60)

def tushare_daily(symbol: str = "600519.SH") -> dict:
    """TuShare A股最近交易日行情；非A股代码返回空，不污染美股路径。"""
    raw = str(symbol or "").upper().strip()
    if raw.isdigit() and len(raw) == 6:
        raw += ".SH" if raw.startswith(("5", "6", "9")) else ".SZ"
    if not TUSHARE_TOKEN or not re.match(r"^\d{6}\.(SH|SZ|BJ)$", raw):
        return {}

    def fetch():
        body = json.dumps({
            "api_name": "daily", "token": TUSHARE_TOKEN,
            "params": {"ts_code": raw},
            "fields": "ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount",
        }).encode("utf-8")
        req = urllib.request.Request("https://api.tushare.pro", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=12) as response:
            payload = json.loads(response.read())
        data = payload.get("data") or {}
        fields, items = data.get("fields") or [], data.get("items") or []
        if not items:
            return {}
        row = dict(zip(fields, items[0]))
        return {"symbol": raw, "date": row.get("trade_date"), "price": row.get("close"),
            "open": row.get("open"), "high": row.get("high"), "low": row.get("low"),
            "change_pct": row.get("pct_chg"), "volume": row.get("vol"),
            "amount": row.get("amount"), "source": "TuShare"}
    return _cached(f"tushare_{raw}", fetch, ttl=300)


def _collect_routed_source(
    records: dict[str, dict[str, Any]],
    key: str,
    fetcher,
    *,
    symbol: str,
) -> dict[str, Any]:
    """Run one optional source and always return a structured record."""
    observed_at = datetime.now(TZ)
    try:
        value = fetcher()
        existing = get_source_contract(value)
        if existing:
            decorated = value if isinstance(value, dict) else attach_source_contract(
                value,
                key,
                status=existing.get("status"),
                captured_at=existing.get("timestamp"),
                observed_at=observed_at,
                error=existing.get("error"),
                cached=bool(existing.get("cached")),
                symbol=symbol,
            )
        else:
            has_payload = value not in (None, "", False, {}, [])
            captured_at = payload_timestamp(value) if isinstance(value, dict) else None
            decorated = attach_source_contract(
                value,
                key,
                status=("live" if captured_at is not None else "unavailable") if has_payload else "not_run",
                captured_at=captured_at,
                observed_at=observed_at,
                error=None if not has_payload or captured_at is not None else "missing_timestamp",
                symbol=symbol,
            )
    except Exception as exc:
        decorated = attach_source_contract(
            {},
            key,
            status="unavailable",
            observed_at=observed_at,
            error=exc,
            symbol=symbol,
        )
        decorated["_error"] = decorated["_source_contract"].get("error")

    contract = source_record(key, decorated, symbol=symbol)
    records[key] = contract
    return decorated


def _has_source_payload(value: Any) -> bool:
    contract = get_source_contract(value)
    if contract is not None:
        return bool(contract.get("payload_present"))
    return value not in (None, "", False, {}, [])


def gather_all(asset_class: str = "crypto", symbol: str = "BTC") -> dict[str, Any]:
    """
    统一采集入口
    asset_class: crypto | stock | forex | metal

    Every routed provider is represented under ``_source_records`` with the
    versioned source contract.  Legacy flat provider keys remain available only
    when the provider returned a payload or an explicit failure.
    """
    result: dict[str, Any] = {
        "symbol": symbol,
        "asset_class": asset_class,
        "time": datetime.now(TZ).isoformat(),
        "_source_contract_version": SOURCE_CONTRACT_VERSION,
        "_source_records": {},
    }
    records = result["_source_records"]

    def collect(key: str, fetcher) -> None:
        value = _collect_routed_source(records, key, fetcher, symbol=symbol)
        contract = records[key]
        if _has_source_payload(value) or contract.get("error"):
            result[key] = value

    collectors: dict[str, Any] = {}
    if asset_class == "crypto":
        collectors = {
            "cmc": lambda: cmc_quote(symbol),
            "cmc_global": cmc_global,
            "fear_greed": cmc_fear_greed,
            "cg_top": lambda: cg_top_coins(10),
            "cg_trending": cg_trending,
            "cg_detail": lambda: cg_coin_detail("bitcoin" if symbol.upper() == "BTC" else symbol.lower()),
            "cg_categories": cg_categories,
            "macro": macro_overview,
        }
        pass
    elif asset_class == "stock":
        collectors = {
            "av": lambda: av_quote(symbol),
            "td": lambda: td_quote(symbol),
            "td_tech": lambda: td_technical(symbol),
            "fmp": lambda: fmp_quote(symbol),
            "massive": lambda: massive_aggs(symbol, "stock"),
            "tushare": lambda: tushare_daily(symbol),
            "macro": macro_overview,
        }
        pass
    elif asset_class == "forex":
        collectors = {
            "fmp": lambda: fmp_forex(symbol),
            "td": lambda: td_quote(symbol),
            "td_tech": lambda: td_technical(symbol),
            "macro": macro_overview,
        }
        pass
    elif asset_class == "futures":
        collectors = {
            "massive": lambda: massive_futures_snapshot(symbol),
            "macro": macro_overview,
        }
        pass

    if collectors:
        with ThreadPoolExecutor(max_workers=min(8, len(collectors))) as pool:
            futures = {
                pool.submit(collect, key, fetcher): key
                for key, fetcher in collectors.items()
            }
            for future in as_completed(futures):
                future.result()

    return result


# ═══════════════════ CLI ═══════════════════
if __name__ == "__main__":
    import sys
    a = sys.argv[1] if len(sys.argv) > 1 else "crypto"
    s = sys.argv[2] if len(sys.argv) > 2 else "BTC"
    
    if a == "cmc_global":
        print(json.dumps(cmc_global(), indent=2, ensure_ascii=False))
    elif a == "fg":
        print(json.dumps(cmc_fear_greed(), indent=2, ensure_ascii=False))
    else:
        data = gather_all(a, s)
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
