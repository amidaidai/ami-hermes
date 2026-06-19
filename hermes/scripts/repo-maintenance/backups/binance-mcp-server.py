#!/usr/bin/env python3
"""
Binance MCP Server v2.0 — 纯 REST 实现 · 无 python-binance 依赖
避免 websockets 版本冲突 (Hermes 需 15.0.1, binance 包需旧版)
"""
import os, json, hmac, hashlib, time, logging, urllib.request, urllib.error, socket
from pathlib import Path
from fastmcp import FastMCP

logging.basicConfig(level=logging.WARNING)
mcp = FastMCP("binance")

# ─── 密钥加载 ───
def _load_env() -> None:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env",
        Path.home() / "AppData" / "Local" / "hermes" / ".env",
        Path.home() / ".hermes" / ".env",
    ]
    for path in candidates:
        if path.exists():
            for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                if k in {"BINANCE_API_KEY", "BINANCE_SECRET_KEY"}:
                    os.environ.setdefault(k, v.strip().strip('"').strip("'"))
            break

_load_env()

API_KEY = os.environ.get("BINANCE_API_KEY", "")
SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY", "")
UA = "Mozilla/5.0"

def _ok(js=None):
    return json.dumps(js or {}, ensure_ascii=False)

def _err(msg):
    return json.dumps({"error": str(msg)[:200]}, ensure_ascii=False)

def _has_keys():
    return bool(API_KEY and SECRET_KEY)

# ─── HTTP helpers ───
def _urlopen_json(req, timeout=20, retries=3):
    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")
            return {"_error": f"HTTP {e.code}: {body[:200]}"}
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, socket.timeout, OSError) as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(0.6 * (attempt + 1))
                continue
            return {"_error": str(last_error)[:200]}
        except Exception as e:
            return {"_error": str(e)[:200]}
    return {"_error": str(last_error)[:200]}


def _get(url, signed=False):
    """REST GET with optional HMAC signing"""
    if signed:
        if not _has_keys():
            return {"_error": "API keys not configured"}
        param_char = "&" if "?" in url else "?"
        ts = int(time.time() * 1000)
        url = f"{url}{param_char}timestamp={ts}"
        signature = hmac.new(SECRET_KEY.encode(), url.split("?", 1)[1].encode(), hashlib.sha256).hexdigest()
        url = f"{url}&signature={signature}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "X-MBX-APIKEY": API_KEY} if signed else {"User-Agent": UA})
    return _urlopen_json(req)

# ─── 价格 ───
@mcp.tool()
def get_price(symbol: str) -> str:
    """获取单个交易对当前价格"""
    data = _get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}")
    if "_error" in data: return _err(data["_error"])
    return _ok(data)

@mcp.tool()
def get_prices(symbols: str = "") -> str:
    """获取多个交易对价格（逗号分隔）或全量"""
    data = _get("https://api.binance.com/api/v3/ticker/price")
    if "_error" in data: return _err(data["_error"])
    if symbols:
        syms = [s.strip().upper() for s in symbols.split(",")]
        data = [p for p in data if p.get("symbol") in syms]
    return _ok(data)

# ─── K线 ───
@mcp.tool()
def get_klines(symbol: str, interval: str = "15m", limit: int = 100) -> str:
    """K线数据。interval: 1m/5m/15m/1h/4h/1d/1w"""
    data = _get(f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit={min(limit,500)}")
    if "_error" in data: return _err(data["_error"])
    result = [{"time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(k[0]/1000)),
               "open": k[1], "high": k[2], "low": k[3], "close": k[4], "volume": k[5]} for k in data]
    return _ok(result)

# ─── 现货账户 ───
@mcp.tool()
def get_balance(asset: str = "") -> str:
    """现货余额。空=全量非零"""
    if not _has_keys(): return _err("API keys not configured")
    data = _get("https://api.binance.com/api/v3/account", signed=True)
    if "_error" in data: return _err(data["_error"])
    balances = data.get("balances", [])
    if asset:
        return _ok([b for b in balances if b["asset"] == asset.upper()])
    return _ok([b for b in balances if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0])

@mcp.tool()
def get_account_summary() -> str:
    """账户摘要：现货+合约"""
    if not _has_keys(): return _err("API keys not configured")
    result = {}
    spot = _get("https://api.binance.com/api/v3/account", signed=True)
    if "_error" not in spot:
        result["spot_assets"] = [b for b in spot.get("balances", []) if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0]
    else:
        result["spot_assets"] = spot["_error"]
    fut = _get("https://fapi.binance.com/fapi/v2/account", signed=True)
    if "_error" not in fut:
        result["futures_total_wallet"] = fut.get("totalWalletBalance", "0")
        result["futures_unrealized_pnl"] = fut.get("totalUnRealizedProfit", "0")
    else:
        result["futures"] = fut["_error"]
    return _ok(result)

# ─── 合约持仓 ───
@mcp.tool()
def get_futures_positions(symbol: str = "") -> str:
    """U本位合约持仓"""
    if not _has_keys(): return _err("API keys not configured")
    data = _get("https://fapi.binance.com/fapi/v2/positionRisk", signed=True)
    if "_error" in data: return _err(data["_error"])
    result = []
    for p in data:
        size = float(p.get("positionAmt", 0))
        if size != 0 and (not symbol or p["symbol"] == symbol.upper()):
            result.append({"symbol": p["symbol"], "position": size,
                           "entry_price": p.get("entryPrice", "0"),
                           "mark_price": p.get("markPrice", "0"),
                           "pnl": p.get("unRealizedProfit", "0"),
                           "leverage": p.get("leverage", "1")})
    if not result and symbol: return _ok({"info": "无持仓"})
    return _ok(result)

# ─── 订单 ───
@mcp.tool()
def get_open_orders(symbol: str = "") -> str:
    """未成交订单（现货+合约）"""
    if not _has_keys(): return _err("API keys not configured")
    sym_q = f"?symbol={symbol.upper()}" if symbol else ""
    spot = _get(f"https://api.binance.com/api/v3/openOrders{sym_q}", signed=True)
    fut = _get(f"https://fapi.binance.com/fapi/v1/openOrders{sym_q}", signed=True)
    return _ok({
        "spot": [{"orderId": o["orderId"], "symbol": o["symbol"], "side": o["side"],
                   "price": o["price"], "origQty": o["origQty"], "status": o["status"]}
                 for o in (spot if isinstance(spot, list) else [])],
        "futures": [{"orderId": o["orderId"], "symbol": o["symbol"], "side": o["side"],
                      "price": o["price"], "origQty": o["origQty"], "status": o["status"]}
                    for o in (fut if isinstance(fut, list) else [])],
    })

@mcp.tool()
def cancel_order(symbol: str, order_id: str, market: str = "spot") -> str:
    """撤单。market='spot'或'futures'"""
    if not _has_keys(): return _err("API keys not configured")
    ts = int(time.time() * 1000)
    if market == "futures":
        params = f"symbol={symbol.upper()}&orderId={order_id}&timestamp={ts}"
        signature = hmac.new(SECRET_KEY.encode(), params.encode(), hashlib.sha256).hexdigest()
        url = f"https://fapi.binance.com/fapi/v1/order?{params}&signature={signature}"
    else:
        params = f"symbol={symbol.upper()}&orderId={order_id}&timestamp={ts}"
        signature = hmac.new(SECRET_KEY.encode(), params.encode(), hashlib.sha256).hexdigest()
        url = f"https://api.binance.com/api/v3/order?{params}&signature={signature}"
    req = urllib.request.Request(url, headers={"X-MBX-APIKEY": API_KEY, "User-Agent": UA}, method="DELETE")
    data = _urlopen_json(req)
    if "_error" in data:
        return _err(data["_error"])
    return _ok({"status": "cancelled", "symbol": symbol, "orderId": order_id})

# ─── 下单 ───
@mcp.tool()
def create_order(symbol: str, side: str, order_type: str = "MARKET",
                  quantity: str = "", price: str = "", stop_price: str = "",
                  market: str = "futures", reduce_only: bool = False) -> str:
    """下单。market='spot'或'futures'。order_type: MARKET/LIMIT/STOP_MARKET"""
    if not _has_keys(): return _err("API keys not configured")
    ts = int(time.time() * 1000)
    params = f"symbol={symbol.upper()}&side={side.upper()}&type={order_type.upper()}&timestamp={ts}"
    if quantity: params += f"&quantity={quantity}"
    if price: params += f"&price={price}"
    if stop_price: params += f"&stopPrice={stop_price}"
    if reduce_only: params += "&reduceOnly=true"
    signature = hmac.new(SECRET_KEY.encode(), params.encode(), hashlib.sha256).hexdigest()
    base = "https://fapi.binance.com/fapi/v1" if market == "futures" else "https://api.binance.com/api/v3"
    url = f"{base}/order?{params}&signature={signature}"
    req = urllib.request.Request(url, headers={"X-MBX-APIKEY": API_KEY, "User-Agent": UA}, method="POST")
    data = _urlopen_json(req)
    if "_error" in data:
        return _err(data["_error"])
    return _ok({
        "orderId": data.get("orderId"),
        "symbol": data.get("symbol"),
        "side": data.get("side"),
        "type": data.get("type"),
        "status": data.get("status"),
        "price": data.get("price"),
        "stopPrice": data.get("stopPrice"),
        "origQty": data.get("origQty"),
    })

# ─── 交易对信息 ───
@mcp.tool()
def get_symbol_info(symbol: str) -> str:
    """交易对信息"""
    data = _get(f"https://api.binance.com/api/v3/exchangeInfo?symbol={symbol.upper()}")
    if "_error" in data: return _err(data["_error"])
    syms = data.get("symbols", [])
    if not syms: return _err("交易对不存在")
    s = syms[0]
    return _ok({"symbol": s["symbol"], "status": s["status"],
                "baseAsset": s["baseAsset"], "quoteAsset": s["quoteAsset"],
                "filters": s.get("filters", [])})

# ═══════════════════════════════════════
# v1.1 扩展 — 多空比/Taker/OI/费率 (带签名)
# ═══════════════════════════════════════

def _fsg(path, params_extra=""):
    """Futures signed GET"""
    if not _has_keys(): return {"_error": "API keys not configured"}
    ts = int(time.time() * 1000)
    params = f"{params_extra}{'&' if params_extra else ''}timestamp={ts}"
    sig = hmac.new(SECRET_KEY.encode(), params.encode(), hashlib.sha256).hexdigest()
    url = f"https://fapi.binance.com{path}?{params}&signature={sig}"
    req = urllib.request.Request(url, headers={"X-MBX-APIKEY": API_KEY, "User-Agent": UA})
    data = _urlopen_json(req, timeout=15)
    if "_error" in data:
        data["_error"] = str(data["_error"])[:120]
    return data

@mcp.tool()
def get_long_short_ratio(symbol: str = "BTCUSDT", period: str = "5m", limit: int = 5) -> str:
    """大户多空比 (top trader)"""
    data = _fsg("/futures/data/topLongShortAccountRatio", f"symbol={symbol}&period={period}&limit={limit}")
    if "_error" in data: return _err(data["_error"])
    result = [{"long": round(float(d["longAccount"]), 3), "short": round(float(d["shortAccount"]), 3),
               "ratio": round(float(d["longShortRatio"]), 2),
               "side": "long" if float(d["longAccount"]) > 0.55 else "short" if float(d["shortAccount"]) > 0.55 else "neutral",
               "timestamp": d["timestamp"]}
              for d in (data if isinstance(data, list) else [data])]
    return _ok(result[-limit:])

@mcp.tool()
def get_global_long_short(symbol: str = "BTCUSDT", period: str = "5m", limit: int = 5) -> str:
    """全局多空比"""
    data = _fsg("/futures/data/globalLongShortAccountRatio", f"symbol={symbol}&period={period}&limit={limit}")
    if "_error" in data: return _err(data["_error"])
    result = [{"long": round(float(d["longAccount"]), 3), "short": round(float(d["shortAccount"]), 3),
               "ratio": round(float(d["longShortRatio"]), 2),
               "side": "long" if float(d["longAccount"]) > 0.52 else "short" if float(d["shortAccount"]) > 0.52 else "balanced",
               "timestamp": d["timestamp"]}
              for d in (data if isinstance(data, list) else [data])]
    return _ok(result[-limit:])

@mcp.tool()
def get_taker_volume(symbol: str = "BTCUSDT", period: str = "5m", limit: int = 5) -> str:
    """Taker买卖量比"""
    data = _fsg("/futures/data/takerlongshortRatio", f"symbol={symbol}&period={period}&limit={limit}")
    if "_error" in data: return _err(data["_error"])
    result = [{"buy_vol": round(float(d["buyVol"]), 2), "sell_vol": round(float(d["sellVol"]), 2),
               "ratio": round(float(d["buySellRatio"]), 3),
               "direction": "buy" if float(d["buySellRatio"]) > 1.1 else "sell" if float(d["buySellRatio"]) < 0.9 else "neutral",
               "timestamp": d["timestamp"]}
              for d in (data if isinstance(data, list) else [data])]
    return _ok(result[-limit:])

@mcp.tool()
def get_funding_rate_history(symbol: str = "BTCUSDT", limit: int = 5) -> str:
    """资金费率历史"""
    data = _fsg("/fapi/v1/fundingRate", f"symbol={symbol}&limit={limit}")
    if "_error" in data: return _err(data["_error"])
    result = [{"rate": d["fundingRate"], "rate_pct": f"{float(d['fundingRate'])*100:.4f}%",
               "time": d["fundingTime"]}
              for d in (data if isinstance(data, list) else [data])]
    return _ok(result[-limit:])

@mcp.tool()
def get_open_interest_history(symbol: str = "BTCUSDT", period: str = "5m", limit: int = 5) -> str:
    """OI历史"""
    data = _fsg("/futures/data/openInterestHist", f"symbol={symbol}&period={period}&limit={limit}")
    if "_error" in data: return _err(data["_error"])
    result = [{"oi": d["sumOpenInterest"], "oi_value": d["sumOpenInterestValue"],
               "timestamp": d["timestamp"]}
              for d in (data if isinstance(data, list) else [data])]
    return _ok(result[-limit:])

if __name__ == "__main__":
    mcp.run()
