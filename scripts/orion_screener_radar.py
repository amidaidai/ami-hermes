#!/usr/bin/env python3
"""
Orion 全市场雷达 v2 — 多源交叉验证版
四层验证链：Orion Binance → Orion Hyperliquid → Binance API → CoinGecko

工作流：
  1. 拉 Orion Binance（604品种）→ 检测异动候选项
  2. 拉 Orion Hyperliquid（451品种）→ 跨交易所验证
  3. 对高分候选项调 Binance REST API → OI趋势/费率历史/Taker量/多空比
  4. CoinGecko Pro API → 市值排名+现货成交量验证
  5. 置信度评分 + 格式化输出

环境变量（Hermes 自动注入）：
  BINANCE_API_KEY, BINANCE_SECRET_KEY — Binance 签名请求
  CG_API_KEY — CoinGecko Pro API Key (x-cg-pro-api-key)
  ORION_EXCHANGE — binance / hl / both
"""

import json, os, sys, time, hmac, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── 配置 ───
BJT = timezone(timedelta(hours=8))
NOW = datetime.now(BJT)
API_BASE = "https://screener.orionterminal.com/api"
BINANCE_FAPI = "https://fapi.binance.com"
BINANCE_API = "https://api.binance.com"
UA = "Hermes/1.0 (+https://github.com/amidaidai/ami-hermes)"

# Binance credentials
BK = os.environ.get("BINANCE_API_KEY", "")
BS = os.environ.get("BINANCE_SECRET_KEY", "")
HAS_KEYS = bool(BK and BS)

# CoinGecko Demo API (CG- prefix key, uses api.coingecko.com)
CG_KEY = os.environ.get("CG_API_KEY", "") or "CG-tkuaqHxNbpTQ92HgpvEc4QXY"
HAS_CG = bool(CG_KEY)
CG_BASE = "https://api.coingecko.com/api/v3"  # Demo & Free both use api.coingecko.com

# Thresholds
MIN_OI_USD = float(os.environ.get("ORION_MIN_OI_USD", "500000"))
OI_SPIKE_PCT = float(os.environ.get("ORION_OI_SPIKE_PCT", "8"))
BIG_MOVER_PCT = float(os.environ.get("ORION_BIG_MOVER_PCT", "5"))
FUNDING_THRESHOLD = float(os.environ.get("ORION_FUNDING_THRESHOLD", "0.0008"))
VOL_SURGE_PCT = float(os.environ.get("ORION_VOL_SURGE_PCT", "200"))
MAX_CANDIDATES = 3   # Candidates to deep-verify (reduced from 5 for speed)
MAX_OUTPUT = 5       # Final output count
BINANCE_TIMEOUT = 8  # Per-call timeout for Binance REST (reduced from 15)
DEADLINE_SECONDS = 90  # Overall deadline guard (cron default is 120s)


# ─── Orion API ───
def fetch_orion(exchange=""):
    """Fetch tickers from Orion Screener API. Retries with/without proxy."""
    url = f"{API_BASE}/screener"
    if exchange: url += f"?exchange={exchange}"
    
    strategies = [
        # Strategy 1: Use system proxy (may fail in cron without proxy env)
        (None, "proxy"),
        # Strategy 2: Direct connection (may fail if network requires proxy)  
        (urllib.request.ProxyHandler({}), "direct"),
    ]
    
    for proxy_handler, strategy in strategies:
        try:
            if proxy_handler:
                opener = urllib.request.build_opener(proxy_handler)
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with opener.open(req, timeout=15) as r:
                tickers = json.loads(r.read()).get("tickers", [])
                if tickers:
                    return tickers
        except Exception as e:
            pass  # Try next strategy
    
    return []


# ─── Binance REST (public) ───
def _bfetch(path):
    try:
        req = urllib.request.Request(f"{BINANCE_API}{path}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=BINANCE_TIMEOUT) as r:
            return json.loads(r.read())
    except: return None

def _fapi_signed(path, params=""):
    """Binance Futures signed request."""
    if not HAS_KEYS: return {"_e": "no_keys"}
    ts = int(time.time() * 1000)
    p = f"{params}{'&' if params else ''}timestamp={ts}"
    sig = hmac.new(BS.encode(), p.encode(), hashlib.sha256).hexdigest()
    try:
        req = urllib.request.Request(
            f"{BINANCE_FAPI}{path}?{p}&signature={sig}",
            headers={"X-MBX-APIKEY": BK, "User-Agent": UA}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_e": str(e)[:120]}


def verify_binance(symbol):
    """Deep verify a symbol via Binance API (internal calls parallelized). Returns dict or None."""
    name = symbol.replace("USDT", "")
    result = {"name": name, "symbol": symbol}

    def _fetch_24h():
        d24 = _bfetch(f"/api/v3/ticker/24hr?symbol={symbol}")
        if d24 and "priceChangePercent" in d24:
            result["price_24h_pct"] = float(d24["priceChangePercent"])
            result["volume_24h"] = float(d24["quoteVolume"]) if "quoteVolume" in d24 else 0

    def _fetch_oi():
        oi_data = _bfetch(f"/fapi/v1/openInterest?symbol={symbol}")
        if oi_data and "openInterest" in oi_data:
            result["oi"] = float(oi_data["openInterest"])
            mk = _bfetch(f"/fapi/v1/premiumIndex?symbol={symbol}")
            if mk and "markPrice" in mk:
                mp = float(mk["markPrice"])
                result["oi_usd"] = result["oi"] * mp
                result["mark_price"] = mp
                result["funding_rate"] = float(mk.get("lastFundingRate", 0))

    def _fetch_oi_hist():
        oih = _fapi_signed(f"/futures/data/openInterestHist", f"symbol={symbol}&period=15m&limit=3")
        if isinstance(oih, list) and len(oih) >= 2:
            oi_vals = [float(x["sumOpenInterest"]) for x in oih[:3]]
            result["oi_trend"] = "↑" if oi_vals[-1] > oi_vals[0] * 1.02 else ("↓" if oi_vals[-1] < oi_vals[0] * 0.98 else "→")
            result["oi_trend_pct"] = (oi_vals[-1] / oi_vals[0] - 1) * 100

    def _fetch_funding():
        frh = _bfetch(f"/fapi/v1/fundingRate?symbol={symbol}&limit=3")
        if isinstance(frh, list) and frh:
            rates = [float(x["fundingRate"]) for x in frh[:3]]
            result["funding_rates"] = rates
            result["funding_avg"] = sum(rates) / len(rates)
            result["funding_dir"] = "neg" if all(r < 0 for r in rates) else ("pos" if all(r > 0 for r in rates) else "mixed")

    def _fetch_taker():
        tk = _fapi_signed(f"/futures/data/takerlongshortRatio", f"symbol={symbol}&period=5m&limit=1")
        if isinstance(tk, list) and tk:
            ratio = float(tk[-1].get("buySellRatio", 1))
            result["taker_ratio"] = ratio
            result["taker_dir"] = "买" if ratio > 1.05 else ("卖" if ratio < 0.95 else "中性")

    def _fetch_ls():
        ls = _fapi_signed(f"/futures/data/topLongShortAccountRatio", f"symbol={symbol}&period=5m&limit=1")
        if isinstance(ls, list) and ls:
            result["ls_ratio"] = float(ls[-1].get("longShortRatio", 1))
            result["ls_dir"] = "偏多" if result["ls_ratio"] > 1.5 else ("偏空" if result["ls_ratio"] < 0.67 else "均衡")

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda fn: fn(), [_fetch_24h, _fetch_oi, _fetch_oi_hist, _fetch_funding, _fetch_taker, _fetch_ls]))

    return result if len(result) > 2 else None


# ─── CoinGecko Pro API ───
def _cg_headers():
    return {"x-cg-pro-api-key": CG_KEY, "User-Agent": UA}


def _cg_get(path):
    """Call CoinGecko API. Returns parsed JSON or None."""
    try:
        req = urllib.request.Request(f"{CG_BASE}{path}", headers=_cg_headers())
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(1.5)
            return None  # Rate limited
        return None
    except: return None


def cg_search_symbol(symbol):
    """Search CoinGecko by symbol (e.g. 'BTC', 'MANTA'). Returns coin ID or None."""
    base = symbol.replace("USDT", "").replace("USDC", "").replace("BULL", "").replace("BEAR", "")
    if len(base) <= 1:
        return None  # Too short, likely misidentification
    base_lower = base.lower().strip()

    d = _cg_get(f"/search?query={base_lower}")
    if not d or "coins" not in d:
        return None

    # Try exact symbol match first (most reliable)
    for c in d["coins"][:10]:
        cs = (c.get("symbol") or "").lower().strip()
        if cs == base_lower:
            return c.get("id")

    # Try name contains symbol (handles 'Manta Network' → 'MANTA')
    for c in d["coins"][:10]:
        cn = (c.get("name") or "").lower()
        if base_lower in cn and len(cn) < 30:
            return c.get("id")

    # Fallback: first result if it has real market data
    top = d["coins"][0] if d["coins"] else None
    if top and top.get("market_cap_rank") and top["market_cap_rank"] <= 500:
        return top.get("id")

    return None


def verify_coingecko(symbol):
    """Verify a symbol via CoinGecko. Returns dict with market data or None."""
    if not HAS_CG:
        return None

    coin_id = cg_search_symbol(symbol)
    if not coin_id:
        return None

    d = _cg_get(f"/coins/{coin_id}?localization=false&tickers=false&community_data=false&developer_data=false&sparkline=false")
    if not d:
        return None

    result = {"coin_id": coin_id, "name": d.get("name", "")}

    md = d.get("market_data") or {}
    result["market_cap_rank"] = d.get("market_cap_rank")
    result["market_cap"] = (md.get("market_cap") or {}).get("usd")
    result["total_volume_24h"] = (md.get("total_volume") or {}).get("usd")
    result["price_usd"] = (md.get("current_price") or {}).get("usd")
    result["price_change_24h"] = md.get("price_change_percentage_24h")
    result["price_change_1h"] = md.get("price_change_percentage_1h_in_currency", {}).get("usd") if isinstance(md.get("price_change_percentage_1h_in_currency"), dict) else None
    result["ath"] = (md.get("ath") or {}).get("usd")
    result["ath_change_pct"] = md.get("ath_change_percentage", {}).get("usd") if isinstance(md.get("ath_change_percentage"), dict) else None

    return result


def cg_batch_verify(candidates):
    """Batch verify top candidates via CoinGecko (parallelized)."""
    if not HAS_CG:
        print("[CG] No API key — CoinGecko verify skipped", file=sys.stderr)
        return candidates

    top = candidates[:MAX_CANDIDATES]

    def _verify_one(idx_c):
        i, c = idx_c
        print(f"  [CG] {i+1}/{min(MAX_CANDIDATES, len(top))} {c['symbol']}...", file=sys.stderr)
        cg_data = verify_coingecko(c["symbol"])
        if cg_data:
            c["coingecko"] = cg_data
            return c, True
        else:
            print(f"  [CG] {c['symbol']} failed", file=sys.stderr)
            return c, False

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(_verify_one, list(enumerate(top))))

    verified = sum(1 for _, ok in results if ok)
    print(f"[CG] {verified} 个已完成 CoinGecko 验证", file=sys.stderr)
    return candidates


# ─── Anomaly Detection ───
def detect_anomalies(tickers, exchange_name):
    """Detect anomalies across all tickers. Returns list of candidate dicts."""
    candidates = []
    for t in tickers:
        sym = t["symbol"]
        oi_usd = t.get("openInterestUsd") or 0
        funding = t.get("fundingRate") or 0
        tf1h = t.get("tf1h") or {}

        if oi_usd < MIN_OI_USD:
            continue

        chg_1h = tf1h.get("changePercent")
        oi_chg = tf1h.get("oiChange")
        vol_chg = tf1h.get("volumeChange")
        vol_15m = (t.get("tf15m") or {}).get("volume") or 0

        signals = []
        score = 0

        # OI spike
        if oi_chg is not None and abs(oi_chg) >= OI_SPIKE_PCT:
            signals.append(("oi", oi_chg))
            score += 3

        # Big mover
        if chg_1h is not None and abs(chg_1h) >= BIG_MOVER_PCT:
            signals.append(("move", chg_1h))
            score += 2

        # Extreme funding
        if abs(funding) >= FUNDING_THRESHOLD:
            signals.append(("fund", funding))
            score += 2

        # Volume surge
        if vol_chg is not None and vol_chg >= VOL_SURGE_PCT:
            signals.append(("vol", vol_chg))
            score += 2

        # High volatility
        vol_15m_pct = (t.get("tf15m") or {}).get("volatility") or 0
        if vol_15m_pct >= 0.5:
            signals.append(("vlt", vol_15m_pct))
            score += 1

        if signals:
            candidates.append({
                "symbol": sym,
                "price": t.get("price"),
                "oi_usd": oi_usd,
                "signals": signals,
                "score": score,
                "exchange": exchange_name,
                "chg_1h": chg_1h,
                "oi_chg": oi_chg,
                "funding": funding,
                "vol_chg": vol_chg,
                "vol_15m_pct": vol_15m_pct,
                "vol_15m": vol_15m,
                "base": sym.replace("USDT", "").replace("USDC", ""),
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def cross_verify(candidates, hl_tickers):
    """Cross-reference Binance candidates with Hyperliquid data."""
    hl_map = {}
    for t in hl_tickers:
        hl_map[t["symbol"]] = t

    for c in candidates:
        base = c["base"]
        hl_sym = base  # HL uses bare symbol (e.g., 'BTC' not 'BTCUSDT')

        hl_t = hl_map.get(hl_sym)
        if hl_t:
            hl_tf1h = hl_t.get("tf1h") or {}
            hl_oi_chg = hl_tf1h.get("oiChange")
            hl_chg = hl_tf1h.get("changePercent")
            hl_funding = hl_t.get("fundingRate") or 0
            hl_oi = hl_t.get("openInterestUsd") or 0

            c["hl_confirmed"] = True
            c["hl_oi_chg"] = hl_oi_chg
            c["hl_chg"] = hl_chg
            c["hl_funding"] = hl_funding
            c["hl_oi"] = hl_oi

            # Agreement scoring
            c["hl_agree"] = 0
            if hl_oi_chg is not None and c["oi_chg"] is not None:
                if (hl_oi_chg > 0) == (c["oi_chg"] > 0):
                    c["hl_agree"] += 2  # OI direction agree
            if hl_chg is not None and c["chg_1h"] is not None:
                if (hl_chg > 0) == (c["chg_1h"] > 0):
                    c["hl_agree"] += 1  # Price direction agree
            if (hl_funding > 0) == (c["funding"] > 0):
                c["hl_agree"] += 1  # Funding sign agree
        else:
            c["hl_confirmed"] = False
            c["hl_agree"] = 0

    return candidates


def deep_verify(candidates):
    """Deep verify top candidates via Binance REST API (parallelized)."""
    if not HAS_KEYS:
        print("[Binance] No API keys — deep verify skipped", file=sys.stderr)
        return candidates

    top = candidates[:MAX_CANDIDATES]

    def _verify_one(idx_sym):
        i, c = idx_sym
        sym = c["symbol"]
        print(f"  [BN] {i+1}/{MAX_CANDIDATES} {sym}...", file=sys.stderr)
        bsv = verify_binance(sym)
        if bsv:
            c["binance"] = bsv
        return c

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(_verify_one, list(enumerate(top))))

    return candidates


def compute_confidence(c):
    """Compute final confidence score (1-10) for a candidate."""
    conf = 0
    base_score = min(c["score"], 5)

    # 1. Orion anomaly strength
    conf += base_score * 1.0

    # 2. HL cross-confirmation
    if c.get("hl_confirmed"):
        conf += 1.5
        conf += c.get("hl_agree", 0) * 0.5
    else:
        conf -= 0.5  # No HL data

    # 3. Binance deep verify
    bn = c.get("binance")
    if bn:
        conf += 1.0
        # OI trend agreement
        if "oi_trend" in bn:
            oi_up = bn["oi_trend"] == "↑"
            bn_oi_pos = (c.get("oi_chg") or 0) > 0
            if oi_up == bn_oi_pos:
                conf += 0.5

        # Funding direction sustained
        if bn.get("funding_dir") in ("neg", "pos"):
            neg_fund = c.get("funding", 0) < 0
            bn_neg = bn["funding_dir"] == "neg"
            if neg_fund == bn_neg:
                conf += 0.5

        # Taker direction
        if bn.get("taker_dir") == "买" and (c.get("chg_1h") or 0) > 0:
            conf += 0.5  # Price up + buy pressure = strong
        if bn.get("taker_dir") == "卖" and (c.get("chg_1h") or 0) < 0:
            conf += 0.5

    # 4. CoinGecko verification
    cg = c.get("coingecko")
    if cg:
        conf += 0.5  # Has CoinGecko data
        mcr = cg.get("market_cap_rank")
        if mcr and mcr <= 100:
            conf += 1.0  # Top 100 = liquid, trustworthy
        elif mcr and mcr <= 300:
            conf += 0.5  # Mid cap
        elif mcr and mcr > 500:
            conf -= 0.5  # Small cap, higher risk

        vol24 = cg.get("total_volume_24h")
        if vol24 and vol24 >= 10_000_000:
            conf += 0.5  # $10M+ daily volume = real liquidity

        # Price consistency: CoinGecko vs Orion
        cg_price = cg.get("price_usd")
        orion_price = c.get("price")
        if cg_price and orion_price and orion_price > 0:
            diff = abs(cg_price - orion_price) / orion_price
            if diff < 0.02:
                conf += 0.5  # Prices within 2% = data integrity

    c["confidence"] = round(min(conf, 10), 1)
    return c


# ─── Formatting ───
def fmt_price(p):
    if p is None: return "N/A"
    if p >= 1000: return f"${p:,.2f}"
    elif p >= 1: return f"${p:,.4f}"
    elif p >= 0.01: return f"${p:,.6f}"
    else: return f"${p:,.8f}"

def fmt_pct(v):
    return f"{v:+.2f}%" if v is not None else "N/A"

def fmt_funding(v):
    return f"{v*100:.4f}%" if v is not None else "N/A"

def fmt_volume(v):
    if v is None: return "N/A"
    if v >= 1e9: return f"${v/1e9:.2f}B"
    elif v >= 1e6: return f"${v/1e6:.2f}M"
    elif v >= 1e3: return f"${v/1e3:.2f}K"
    return f"${v:.0f}"

SIG_LABELS = {
    "oi": {"🟢": "OI涨", "🔴": "OI跌"},
    "move": {"🚀": "价涨", "💥": "价跌"},
    "fund": {"🔥": "负费", "💰": "正费"},
    "vol": {"📊": "量变"},
    "vlt": {"🌪️": "波变"},
}

def signal_emoji(sig_type, val):
    if sig_type == "oi": return "🟢OI涨" if val > 0 else "🔴OI跌"
    if sig_type == "move": return "🚀价涨" if val > 0 else "💥价跌"
    if sig_type == "fund": return "🔥负费" if val < 0 else "💰正费"
    if sig_type == "vol": return "📊量变"
    if sig_type == "vlt": return "🌪️波变"
    return "⚡"


def build_report(candidates, ts):
    """Build formatted report with multi-source verification. 纯Markdown表格格式."""
    lines = []

    if not candidates:
        lines.append(f"🛡️ Orion 全市场雷达 · {ts}")
        lines.append("")
        lines.append("✅ 无明显异动，市场平静。")
        return "\n".join(lines)

    # Sort by confidence
    candidates.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    top = candidates[:MAX_OUTPUT]

    lines.append(f"🛡️ Orion 全市场雷达 · {ts}")
    lines.append("")

    # ── Table 1: 验证链 ──
    hl_ok = any(c.get('hl_confirmed') for c in candidates)
    lines.append("**表1 · 验证链**")
    lines.append("| 层 | 源 | 状态 |")
    lines.append("|:--|:--|:--:|")
    lines.append(f"| ① | Orion Binance | ✅ {len(candidates)} 候选 |")
    lines.append(f"| ② | Hyperliquid | {'✅ 跨所确认' if hl_ok else '❌ 无对应品种'} |")
    bn_count = sum(1 for c in candidates if c.get("binance"))
    lines.append(f"| ③ | Binance REST | {'✅ ' + str(bn_count) + '深度验证' if HAS_KEYS else '⏳ 无 API Key'} |")
    cg_count = sum(1 for c in candidates if c.get("coingecko"))
    lines.append(f"| ④ | CoinGecko | {'✅ ' + str(cg_count) + '确认' if cg_count else ('❌ 0确认' if HAS_CG else '❌ 未配置')} |")
    lines.append("")

    # Summary
    high_conf = sum(1 for c in candidates if c.get("confidence", 0) >= 6)
    med_conf = sum(1 for c in candidates if 4 <= c.get("confidence", 0) < 6)
    low_conf = sum(1 for c in candidates if c.get("confidence", 0) < 4)
    lines.append(f"{len(candidates)} 检测 · 🟢高 {high_conf} · 🟡中 {med_conf} · ⚪低 {low_conf}")
    lines.append("")

    # ── Table 2: 候选详细数据 ──
    lines.append("**表2 · 候选数据**")
    lines.append("| # | 品种 | 现价 | 1h% | OI($) | OI% | 资金费率 | 多空比 | Taker | 置信度 |")
    lines.append("|:-:|:----|:---:|:---:|:-----:|:---:|:-------:|:-----:|:-----:|:-----:|")

    for i, c in enumerate(top[:8], 1):
        price_str = f"${c['price']}" if c['price'] < 1000 else f"${c['price']:,.0f}"
        chg_str = f"{c.get('chg_1h',0):+.2f}%"
        oi_str = fmt_volume(c.get('oi_usd',0))
        oi_chg_str = f"{c.get('oi_chg',0):+.2f}%"
        fund_str = fmt_funding(c.get('funding',0))
        
        bn = c.get("binance")
        if bn:
            ls_str = f"{bn.get('ls_ratio', '—'):.2f}x{bn.get('ls_dir','')}" if bn.get('ls_ratio') else "—"
            taker_str = f"{bn.get('taker_dir','')}{bn.get('taker_ratio','—')}" if bn.get('taker_ratio') else "—"
        else:
            ls_str = "—"
            taker_str = "—"
        
        conf_str = f"{c.get('confidence',0):.1f}"
        
        lines.append(f"| {i} | {c['symbol']} | {price_str} | {chg_str} | {oi_str} | {oi_chg_str} | {fund_str} | {ls_str} | {taker_str} | {conf_str} |")

    lines.append("")

    # ── Table 3: 判断 ──
    lines.append("**表3 · 判断**")
    lines.append("| 品种 | OI+价 | 费率 | Taker | 综合判断 |")
    lines.append("|:----|:-----|:----|:-----|:--------|")
    for c in top[:6]:
        oi_chg = c.get("oi_chg") or 0
        chg = c.get("chg_1h") or 0
        funding = c.get("funding") or 0
        bn = c.get("binance")
        
        # OI+price
        if oi_chg > 0 and chg > 0: oi_price = "📈 同涨真突破"
        elif oi_chg > 0 and chg < 0: oi_price = "⚠️ OI涨价跌出货"
        elif oi_chg < 0 and chg > 0: oi_price = "💨 空平反弹"
        elif oi_chg < 0 and chg < 0: oi_price = "📉 同跌趋势下行"
        else: oi_price = "➖ 中性"
        
        # Funding
        if funding < -0.001: fund_judge = "🔥 空头重仓"
        elif funding > 0.001: fund_judge = "💰 多头拥挤"
        else: fund_judge = "⚖ 中性"
        
        # Taker
        if bn:
            td = bn.get("taker_dir","")
            tv = bn.get("taker_ratio", 1)
            if td == "卖" and tv < 0.8: taker_judge = "⬇ 主动卖压"
            elif td == "买" and tv > 1.2: taker_judge = "⬆ 主动买盘"
            elif td == "卖": taker_judge = "🔻 卖方主导"
            elif td == "买": taker_judge = "🔺 买方主导"
            else: taker_judge = "➖ 无数据"
        else:
            taker_judge = "➖ 无数据"
        
        # Overall
        if oi_chg > 0 and chg > 0 and funding < -0.001:
            verdict = "⚠️ 真突破+空头重仓·轧空潜力"
        elif oi_chg > 0 and chg < 0 and funding < -0.001:
            verdict = "❌ OI涨+价跌+费负=诱多陷阱"
        elif oi_chg > 5 and chg < -3:
            verdict = "❌ 暴跌中OI暴增=接盘"
        elif oi_chg > 0 and chg > 0:
            verdict = "✅ 量价齐升·有机会"
        elif oi_chg < 0 and chg > 0:
            verdict = "⚠️ 空平反弹·短命"
        else:
            verdict = "➖ 观望"
        
        lines.append(f"| {c['symbol']} | {oi_price} | {fund_judge} | {taker_judge} | {verdict} |")

    return "\n".join(lines)


def assess_setup(c):
    """Generate actionable assessment for a candidate."""
    parts = []
    chg = c.get("chg_1h") or 0
    oi_chg = c.get("oi_chg") or 0
    funding = c.get("funding") or 0
    bn = c.get("binance")

    # OI + price relationship
    if oi_chg > 0 and chg > 0:
        parts.append("📈 OI价同步涨，真突破信号")
    elif oi_chg > 0 and chg < 0:
        parts.append("⚠️ OI涨但价跌，可能抄底接盘")
    elif oi_chg < 0 and chg > 0:
        parts.append("💨 OI跌价涨，空头平仓反弹")
    elif oi_chg < 0 and chg < 0:
        parts.append("📉 OI价同步跌，趋势性下跌")

    # Funding + price
    if funding < -0.001 and chg > 0:
        parts.append("🔥 空头重度拥挤+价涨，轧空潜力")
    elif funding < -0.001 and chg < 0:
        parts.append("⚠️ 空头拥挤但价跌，等企稳")
    elif funding > 0.001 and chg > 0:
        parts.append("💰 多头拥挤拉涨，小心回调")
    elif funding > 0.001 and chg < 0:
        parts.append("🔻 多头拥挤+价跌，趋势可能反转")

    # Taker confirmation
    if bn and bn.get("taker_dir") == "买" and chg > 0:
        parts.append("✅ 主动买方确认上涨")
    elif bn and bn.get("taker_dir") == "卖" and chg < 0:
        parts.append("✅ 主动卖方确认下跌")

    # Cross-exchange signal
    if c.get("hl_confirmed") and c.get("hl_agree", 0) >= 3:
        parts.append("🟢 跨交易所一致确认")

    return " | ".join(parts) if parts else None


# ─── Main ───
def main():
    ts = f"{NOW.year}年{NOW.month}月{NOW.day}日{NOW.hour:02d}：{NOW.minute:02d}"
    _start = time.time()
    stderr_log = []

    def log(m):
        stderr_log.append(m)
        print(m, file=sys.stderr)

    def elapsed():
        return time.time() - _start

    def time_left():
        return DEADLINE_SECONDS - elapsed()

    # ── Step 1+2: Fetch Orion Binance + Hyperliquid in parallel ──
    log("📡 第1+2层: 并行扫描 Orion Binance + Hyperliquid...")
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_bn = pool.submit(fetch_orion, "binance")
        fut_hl = pool.submit(fetch_orion, "hl")
        bn_tickers = fut_bn.result()
        hl_tickers = fut_hl.result()

    if not bn_tickers:
        print("[ERROR] Orion Binance data fetch failed - API returned empty")
        return 1
    log(f"  → Binance {len(bn_tickers)} 个品种 / Hyperliquid {len(hl_tickers) or 0} 个品种")

    bn_candidates = detect_anomalies(bn_tickers, "Binance")
    log(f"  → 异动候选项: {len(bn_candidates)}")

    if not bn_candidates:
        # 无异动=静默，只落空报告；避免“市场平静”状态报告刷屏。
        return 0

    # Cross-verify with Hyperliquid (already fetched)
    if hl_tickers:
        bn_candidates = cross_verify(bn_candidates, hl_tickers)
        hl_confirmed = sum(1 for c in bn_candidates if c.get("hl_confirmed"))
        log(f"  → HL 交叉验证: {hl_confirmed} 个有对应品种")

    # ── Step 3: Binance API deep verify ──
    if time_left() > 20 and HAS_KEYS:
        log(f"📡 第3层: Binance API 深度验证... (剩余 {time_left():.0f}s)")
        bn_candidates = deep_verify(bn_candidates)
        verified = sum(1 for c in bn_candidates if c.get("binance"))
        log(f"  → {verified} 个已完成深度验证")
    else:
        log("  → 跳过深度验证（时间不足或无 API Key）")

    # ── Step 4: CoinGecko 验证 ──
    if time_left() > 15:
        log(f"📡 第4层: CoinGecko 市场数据验证... (剩余 {time_left():.0f}s)")
        bn_candidates = cg_batch_verify(bn_candidates)
        cg_count = sum(1 for c in bn_candidates if c.get("coingecko"))
        log(f"  → {cg_count} 个已确认现货市场数据")
    else:
        log("  → 跳过 CoinGecko 验证（时间不足）")

    # ── Step 5: Compute confidence ──
    for c in bn_candidates:
        c = compute_confidence(c)

    # ── Step 6: Build Telegram report ──
    # 只推中高置信候选；低置信单源异动仅落盘给后续分析，避免雷达刷屏。
    alert_candidates = [c for c in bn_candidates if c.get("confidence", 0) >= 4]
    report = build_report(alert_candidates, ts) if alert_candidates else ""
    
    # 落盘JSON供LLM分析读取
    import os as _os
    _data_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "data")
    _os.makedirs(_data_dir, exist_ok=True)
    _output_path = _os.path.join(_data_dir, "orion_radar.json")
    try:
        candidates_for_json = []
        for c in bn_candidates:
            cj = {
                "symbol": c.get("symbol", "?"),
                "price": c.get("price", 0),
                "chg_1h": c.get("chg_1h"),
                "chg_24h": c.get("chg_24h"),
                "oi_usd": c.get("oi_usd"),
                "oi_chg": c.get("oi_chg"),
                "funding": c.get("funding"),
                "volume_24h": c.get("volume_24h"),
                "exchange": c.get("exchange"),
                "confidence": c.get("confidence", 0),
                "score_breakdown": c.get("score_breakdown"),
            }
            if c.get("binance"):
                cj["binance"] = c["binance"]
            if c.get("coingecko"):
                cj["coingecko"] = c["coingecko"]
            candidates_for_json.append(cj)
        with open(_output_path, "w", encoding="utf-8") as _f:
            json.dump({"ts": ts, "count": len(candidates_for_json), "candidates": candidates_for_json}, _f, ensure_ascii=False)
    except Exception:
        pass
    
    if report:
        print(report)
    log(f"⏱ 总耗时 {elapsed():.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
