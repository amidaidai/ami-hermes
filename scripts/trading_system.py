#!/usr/bin/env python3
"""交易执行系统公共模块 v9.5。"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Any

import requests

ROOT = Path("D:/Hermes agent")
DATA_DIR = ROOT / "data"
RISK_FILE = DATA_DIR / "risk_state.json"
SOURCE_FILE = DATA_DIR / "source_snapshot.json"
SOURCE_HISTORY_DIR = DATA_DIR / "source_snapshots"
SYMBOL_TEMPLATE_FILE = DATA_DIR / "symbol_templates.json"
GOVERNANCE_FILE = DATA_DIR / "strategy_governance.json"
XAU_MACRO_FILE = DATA_DIR / "xau_macro_context.json"
MODEL_STATS_FILE = DATA_DIR / "strategy_model_stats.json"
SYSTEM_HEALTH_FILE = DATA_DIR / "system_health_score.json"
PLAN_LOG = DATA_DIR / "trade_plans.jsonl"
EVENT_LOG = DATA_DIR / "trade_events.jsonl"
REVIEW_LOG = DATA_DIR / "trade_reviews.jsonl"

DEFAULT_RISK = {
    "date": "",
    "daily_realized_pnl": 0.0,
    "trades_count": 0,
    "loss_streak": 0,
    "max_daily_loss": 30.0,
    "max_trade_risk": 10.0,
    "allowed_risk_next_trade": 10.0,
    "lock_trading": False,
    "unreviewed_trade_count": 0,
    "requires_review": False,
}

RISK_TIERS = [
    ("锁定", 0.0),
    ("轻仓", 2.0),
    ("常规", 5.0),
    ("高置信", 7.0),
    ("极限", 10.0),
]

# ── 完整模型体系 v2.0 ──
# 18类交易模型，覆盖 ICT/SMC/Price Action/Volume Profile/Wyckoff/Harmonic/Gap
# 每类包含：id, name_zh, category, type_tag (用于监控位 type 字段), score_weight
ALL_MODELS = {
    # ── 成交量/市场画像类 (Volume Profile / Market Profile) ──
    "vwap_reclaim":          {"name_zh": "VWAP反抽回收",           "category": "volume_profile", "type_tag": "vwap_reclaim_filter",     "score_weight": 1.0},
    "vah_val_reclaim":       {"name_zh": "VAH/VAL回收",            "category": "volume_profile", "type_tag": "vah_val_reclaim",          "score_weight": 0.9},
    "poc_rejection":         {"name_zh": "POC拒绝/支撑",           "category": "volume_profile", "type_tag": "poc_rejection",            "score_weight": 1.0},
    "naked_vpoc":            {"name_zh": "裸POC（裸价值区）",      "category": "volume_profile", "type_tag": "naked_vpoc",               "score_weight": 0.8},
    "volume_node_transition":{"name_zh": "成交量节点迁移",         "category": "volume_profile", "type_tag": "volume_node_transition",   "score_weight": 0.7},
    "lvn_breakout":          {"name_zh": "低量节点(LVN)突破",      "category": "volume_profile", "type_tag": "lvn_breakout",             "score_weight": 0.7},

    # ── ICT/SMC 机构订单流类 ──
    "order_block":           {"name_zh": "订单块(OB)供需区",       "category": "ict_smc",        "type_tag": "order_block",             "score_weight": 1.0},
    "breaker_block":         {"name_zh": "破坏块(Breaker)反转",    "category": "ict_smc",        "type_tag": "breaker_block",           "score_weight": 0.9},
    "mitigation_block":      {"name_zh": "缓解块(Mitigation)",     "category": "ict_smc",        "type_tag": "mitigation_block",        "score_weight": 0.8},
    "fair_value_gap":        {"name_zh": "公允价值缺口(FVG)",      "category": "ict_smc",        "type_tag": "fair_value_gap",          "score_weight": 0.9},
    "inversion_fvg":         {"name_zh": "反转型FVG",              "category": "ict_smc",        "type_tag": "inversion_fvg",           "score_weight": 0.85},
    "liquidity_sweep":       {"name_zh": "扫流动性回收",           "category": "ict_smc",        "type_tag": "sweep_reclaim",           "score_weight": 1.0},
    "liquidity_void":        {"name_zh": "流动性真空区",           "category": "ict_smc",        "type_tag": "liquidity_void",          "score_weight": 0.7},
    "rejection_block":       {"name_zh": "拒绝块(Rejection)",      "category": "ict_smc",        "type_tag": "rejection_block",         "score_weight": 0.8},

    # ── 市场结构类 ──
    "bos":                   {"name_zh": "结构突破(BOS)",          "category": "market_structure","type_tag": "bos",                     "score_weight": 0.9},
    "choch":                 {"name_zh": "性质转变(CHoCH)",        "category": "market_structure","type_tag": "choch",                   "score_weight": 0.95},
    "structure_flip":        {"name_zh": "结构翻转(S/R Flip)",     "category": "market_structure","type_tag": "structure_flip",          "score_weight": 0.85},
    "breakout_accept":       {"name_zh": "突破接受确认",           "category": "market_structure","type_tag": "breakout_accept",         "score_weight": 1.0},

    # ── Wyckoff 方法论类 ──
    "wyckoff_spring":        {"name_zh": "Wyckoff弹簧(Spring)",   "category": "wyckoff",        "type_tag": "wyckoff_spring",          "score_weight": 0.8},
    "wyckoff_upthrust":      {"name_zh": "Wyckoff上冲(UT)",        "category": "wyckoff",        "type_tag": "wyckoff_upthrust",        "score_weight": 0.8},
    "wyckoff_sos":           {"name_zh": "Wyckoff强信号(SOS)",     "category": "wyckoff",        "type_tag": "wyckoff_sos",             "score_weight": 0.75},
    "wyckoff_sow":           {"name_zh": "Wyckoff弱信号(SOW)",     "category": "wyckoff",        "type_tag": "wyckoff_sow",             "score_weight": 0.75},

    # ── 斐波那契/谐波类 ──
    "fib_retrace":           {"name_zh": "斐波那契回撤位",         "category": "fibonacci",      "type_tag": "fib_retrace",             "score_weight": 0.85},
    "harmonic_pattern":      {"name_zh": "谐波形态",               "category": "fibonacci",      "type_tag": "harmonic_pattern",        "score_weight": 0.7},
    "abcd_pattern":          {"name_zh": "AB=CD形态",              "category": "fibonacci",      "type_tag": "abcd_pattern",            "score_weight": 0.75},

    # ── 缺口理论类 ──
    "gap_fill":              {"name_zh": "缺口回补",               "category": "gap_theory",     "type_tag": "gap_fill",                "score_weight": 0.7},
    "breakaway_gap":         {"name_zh": "突破缺口",               "category": "gap_theory",     "type_tag": "breakaway_gap",           "score_weight": 0.65},

    # ── 经典价格形态类 ──
    "double_top_bottom":     {"name_zh": "双顶/双底",              "category": "classic_pa",     "type_tag": "double_top_bottom",       "score_weight": 0.8},
    "head_shoulders":        {"name_zh": "头肩顶/底",              "category": "classic_pa",     "type_tag": "head_shoulders",          "score_weight": 0.75},
    "trendline_retest":      {"name_zh": "趋势线破位回收",         "category": "classic_pa",     "type_tag": "trendline_retest",        "score_weight": 0.85},

    # ── CVD/订单流类 ──
    "cvd_divergence":        {"name_zh": "CVD背离确认",            "category": "order_flow",     "type_tag": "cvd_divergence",          "score_weight": 0.9},
}

# 按类别分组便于查询
MODEL_CATEGORIES = {
    "volume_profile":  "成交量/市场画像",
    "ict_smc":         "ICT/机构订单流",
    "market_structure":"市场结构",
    "wyckoff":         "Wyckoff方法论",
    "fibonacci":       "斐波那契/谐波",
    "gap_theory":      "缺口理论",
    "classic_pa":      "经典价格形态",
    "order_flow":      "CVD/订单流",
}


def model_by_id(model_id: str) -> dict[str, Any] | None:
    """根据模型ID获取完整模型配置"""
    return ALL_MODELS.get(model_id)


def model_by_type_tag(type_tag: str) -> dict[str, Any] | None:
    """根据监控位type字段反查模型"""
    for model in ALL_MODELS.values():
        if model["type_tag"] == type_tag:
            return model
    return None


def list_models_by_category(category: str | None = None) -> list[dict[str, Any]]:
    """列出所有模型，可按类别筛选"""
    if category:
        return [{"id": k, **v} for k, v in ALL_MODELS.items() if v["category"] == category]
    return [{"id": k, **v} for k, v in ALL_MODELS.items()]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def today_str() -> str:
    return datetime.now().astimezone().date().isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_source_history(snapshot: dict[str, Any]) -> Path:
    """Keep an immutable source snapshot for later trade review."""
    symbol = str(snapshot.get("symbol") or "UNKNOWN").replace("/", "_")
    stamp = str(snapshot.get("time") or now_iso()).replace(":", "").replace("+", "_")
    day = today_str()
    path = SOURCE_HISTORY_DIR / day / f"{symbol}-{stamp}.json"
    write_json(path, snapshot)
    return path


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def default_governance() -> dict[str, Any]:
    return {
        "schema": "strategy_governance_v1",
        "updated": now_iso(),
        "rules": {},
        "policy": {
            "min_sample_to_activate": 20,
            "min_expectancy_r": 0.15,
            "max_drawdown_r": -6.0,
            "manual_approval_required": True,
            "no_auto_risk_increase": True,
        },
    }



def normalize_asset(symbol: str) -> str:
    text = str(symbol or "BTCUSDT").upper().strip()
    aliases = {"XAUUSD": "XAU", "GOLD": "XAU", "USOIL": "USOIL", "WTI": "USOIL", "SPX": "SPX", "SP500": "SPX"}
    if text in aliases:
        return aliases[text]
    if text.endswith("USDT"):
        return text[:-4]
    if text.endswith("USD") and text[:-3] in {"BTC", "ETH", "SOL", "BNB"}:
        return text[:-3]
    return text


def load_symbol_templates() -> dict[str, Any]:
    data = read_json(SYMBOL_TEMPLATE_FILE, {})
    return data if isinstance(data, dict) else {}


def get_symbol_template(symbol: str) -> dict[str, Any]:
    templates = load_symbol_templates()
    asset = normalize_asset(symbol)
    cfg = dict(templates.get(asset) or {})
    if not cfg:
        cfg = {"symbol": symbol.upper(), "name": asset, "market": "未配置", "exchange": "未知", "leverage": "1x", "default_risk_usd": 2, "risk_usd": 10, "derivatives": ["未配置"]}
    cfg.setdefault("asset", asset)
    cfg.setdefault("symbol", symbol.upper())
    cfg.setdefault("default_risk_usd", 2)
    cfg.setdefault("risk_usd", 10)
    return cfg


def parse_leverage(value: Any) -> float:
    text = str(value or "1").lower().replace("x", "").replace("倍", "").strip()
    try:
        return float(text)
    except Exception:
        return 1.0


def is_crypto_template(cfg: dict[str, Any]) -> bool:
    symbol = str(cfg.get("symbol", "")).upper()
    market = str(cfg.get("market", ""))
    return symbol.endswith("USDT") or "加密" in market or cfg.get("exchange") == "Binance"


def template_risk_limit(symbol: str) -> float:
    cfg = get_symbol_template(symbol)
    return float(cfg.get("default_risk_usd") or cfg.get("risk_usd") or 2)


def clash_proxies() -> dict[str, str]:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "http://127.0.0.1:7897"
    return {"http": proxy, "https": proxy}


def yahoo_chart_price(yahoo_symbol: str) -> float | None:
    """Yahoo often blocks direct mainland routes; force the Clash proxy here only."""
    encoded = quote(yahoo_symbol, safe="")
    headers = {"User-Agent": "Mozilla/5.0 hermes-monitor/1.0"}
    urls = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{encoded}",
    ]
    for url in urls:
        try:
            r = requests.get(
                url,
                params={"range": "1d", "interval": "1m"},
                timeout=12,
                headers=headers,
                proxies=clash_proxies(),
            )
            r.raise_for_status()
            data = r.json()
            result = (data.get("chart", {}).get("result") or [])[0]
            meta = result.get("meta", {})
            price = meta.get("regularMarketPrice") or meta.get("previousClose")
            if price:
                return float(price)
        except Exception:
            continue
    return None


def coingecko_price(asset: str) -> float | None:
    ids = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin"}
    coin_id = ids.get(str(asset or "").upper())
    if not coin_id:
        return None
    try:
        data = http_get("https://api.coingecko.com/api/v3/simple/price", {"ids": coin_id, "vs_currencies": "usd"}, timeout=8)
        price = data.get(coin_id, {}).get("usd")
        return float(price) if price else None
    except Exception:
        return None


def parse_sse_json(text: str) -> dict[str, Any]:
    payload = ""
    for line in text.splitlines():
        if line.startswith("data:"):
            payload += line[5:].lstrip()
    return json.loads(payload) if payload else {}


def jin10_quote(code: str) -> dict[str, Any]:
    """Call Jin10 MCP directly so pure scripts can quote non-crypto assets."""
    token_path = ROOT / "hermes" / "secrets" / "jin10_token.txt"
    token = token_path.read_text(encoding="utf-8").strip()
    url = "https://mcp.jin10.com/mcp"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "hermes-monitor", "version": "0.1"}},
    }
    r = requests.post(url, headers=headers, json=init, timeout=12)
    r.raise_for_status()
    session_id = r.headers.get("Mcp-Session-Id")
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    requests.post(url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, timeout=8)
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_quote", "arguments": {"code": code}}}
    r = requests.post(url, headers=headers, json=call, timeout=12)
    r.raise_for_status()
    result = parse_sse_json(r.content.decode("utf-8", "replace"))
    content = result.get("result", {}).get("structuredContent") or {}
    data = content.get("data") or {}
    price = data.get("close")
    return {"source": "金十Quote", "price": float(price) if price else None, "quality": "A" if price else "C", "raw": data}


def oanda_spot_price(symbol: str = "XAU_USD") -> float | None:
    """Get OANDA spot gold/gold price via practice API.

    优先从 hermes/secrets/oanda_token.txt 和 oanda_account_id.txt 读取凭据。
    无凭据则返回 None，由调用方降级。
    """
    token_file = ROOT / "hermes" / "secrets" / "oanda_token.txt"
    account_file = ROOT / "hermes" / "secrets" / "oanda_account_id.txt"
    if not token_file.exists() or not account_file.exists():
        return None
    try:
        token = token_file.read_text(encoding="utf-8").strip()
        account_id = account_file.read_text(encoding="utf-8").strip()
        url = f"https://api-fxpractice.oanda.com/v3/accounts/{account_id}/pricing"
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(url, headers=headers, params={"instruments": symbol}, timeout=10)
        if r.status_code != 200:
            return None
        prices = r.json().get("prices", [])
        if not prices:
            return None
        p = prices[0]
        bid = float(p.get("bids", [{}])[0].get("price", 0))
        ask = float(p.get("asks", [{}])[0].get("price", 0))
        return round((bid + ask) / 2, 2)
    except Exception:
        return None


def gold_api_price() -> float | None:
    """Get XAU spot price from gold-api.com (free, no auth).

    返回当前现货黄金价格（USD），失败返回 None。
    """
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.gold-api.com/price/XAU",
            headers={"User-Agent": "TangXi-TradingSystem/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            price = data.get("price")
            return float(price) if price else None
    except Exception:
        return None



def _spread_pct(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = sum(values) / len(values)
    return (max(values) - min(values)) / avg * 100 if avg else None


def non_crypto_quality(valid: list[dict[str, Any]]) -> tuple[str, int, str, dict[str, Any]]:
    """Quality grading for non-crypto symbols; separates spot consensus from Yahoo futures basis."""
    spot_names = {"OANDA现货", "gold-api.com现货", "金十Quote"}
    spot = [p for p in valid if p.get("source") in spot_names]
    yahoo = [p for p in valid if str(p.get("source", "")).startswith("Yahoo代理")]
    spot_prices = [float(p["price"]) for p in spot if isinstance(p.get("price"), (int, float)) and p.get("price") > 0]
    yahoo_prices = [float(p["price"]) for p in yahoo if isinstance(p.get("price"), (int, float)) and p.get("price") > 0]
    sources = {str(p.get("source")) for p in spot}
    spot_spread = _spread_pct(spot_prices)
    basis_pct = None
    if spot_prices and yahoo_prices:
        spot_mid = sum(spot_prices) / len(spot_prices)
        futures_mid = sum(yahoo_prices) / len(yahoo_prices)
        if spot_mid:
            basis_pct = (futures_mid - spot_mid) / spot_mid * 100
    metrics = {
        "spot_spread_pct": spot_spread,
        "futures_basis_pct": basis_pct,
        "source_spread_pct": _spread_pct([float(p["price"]) for p in valid if isinstance(p.get("price"), (int, float)) and p.get("price") > 0]),
    }
    has_oanda = "OANDA现货" in sources
    has_gold_api = "gold-api.com现货" in sources
    has_jin10 = "金十Quote" in sources
    spot_tight = spot_spread is not None and spot_spread <= 0.12
    if has_oanda and has_gold_api and has_jin10 and spot_tight:
        return "A", 92, "OANDA+gold-api+金十现货三源一致；Yahoo期货basis仅作参考", metrics
    if has_oanda and has_jin10 and spot_tight:
        return "A-", 88, "OANDA+金十现货双源一致；Yahoo期货basis仅作参考", metrics
    if has_gold_api and has_jin10 and spot_tight:
        return "A-", 88, "金十+gold-api现货双源一致；Yahoo期货basis仅作参考", metrics
    if len(spot_prices) >= 2:
        return "B", 78, "现货双源可用但价差偏宽；Yahoo期货basis仅作参考", metrics
    if has_oanda:
        return "C", 65, "OANDA现货单源", metrics
    if has_gold_api:
        return "C", 62, "gold-api.com单源", metrics
    if has_jin10:
        return "C", 60, "金十单源", metrics
    if yahoo_prices:
        return "C", 55, "Yahoo期货代理单源，不等同现货", metrics
    return "C", 0, "无可用源", metrics


def quality_from_consensus(valid: list[dict[str, Any]], spread_pct: float | None) -> tuple[str, int, str]:
    count = len(valid)
    if count >= 3 and spread_pct is not None and spread_pct <= 0.10:
        return "A", 92, "三源一致"
    if count >= 2 and spread_pct is not None and spread_pct <= 0.20:
        return "A", 88, "两源一致"
    if count >= 2 and spread_pct is not None and spread_pct <= 0.50:
        return "B", 75, "两源轻微分歧"
    if count >= 1:
        return "C", 55, "单源"
    return "C", 0, "无可用源"


def price_consensus(symbol: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or get_symbol_template(symbol)
    asset = str(cfg.get("asset") or normalize_asset(symbol)).upper()
    native = str(cfg.get("symbol") or symbol).upper()
    probes: list[dict[str, Any]] = []
    if is_crypto_template(cfg):
        probes.append({"source": "Binance现货", "price": binance_spot_price(native)})
        probes.append({"source": "CoinGecko", "price": coingecko_price(asset)})
        yahoo_crypto = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "BNB": "BNB-USD"}.get(asset)
        if yahoo_crypto:
            probes.append({"source": f"Yahoo代理 {yahoo_crypto}", "price": yahoo_chart_price(yahoo_crypto)})
        fut = binance_futures_snapshot(native)
        if fut.get("mark_price"):
            probes.append({"source": "Binance合约Mark", "price": fut.get("mark_price")})
        if fut.get("index_price"):
            probes.append({"source": "Binance合约Index", "price": fut.get("index_price")})
    else:
        # XAU/XAUUSD: OANDA 现货黄金优先，金十兜底，gold-api.com免费三源
        if asset in {"XAU", "XAUUSD"}:
            oanda = oanda_spot_price("XAU_USD")
            if oanda and oanda > 0:
                probes.append({"source": "OANDA现货", "price": oanda})
            gold_api = gold_api_price()
            if gold_api and gold_api > 0:
                probes.append({"source": "gold-api.com现货", "price": gold_api})
        jin10_map = {"XAU": "XAUUSD", "XAUUSD": "XAUUSD", "USOIL": "USOIL", "UKOIL": "UKOIL", "SPX": "SPX", "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY"}
        jcode = jin10_map.get(asset) or jin10_map.get(native)
        if jcode:
            try:
                quote = jin10_quote(jcode)
                probes.append({"source": "金十Quote", "price": quote.get("price"), "raw": quote.get("raw")})
            except Exception as e:
                probes.append({"source": "金十Quote", "price": None, "error": str(e)})
        yahoo_map = {
            "XAU": ["GC=F", "MGC=F"],
            "XAUUSD": ["GC=F", "MGC=F"],
            "USOIL": ["CL=F"],
            "SPX": ["^GSPC"],
        }
        ysyms = yahoo_map.get(asset) or yahoo_map.get(native) or []
        for ysym in ysyms:
            probes.append({"source": f"Yahoo代理 {ysym}", "price": yahoo_chart_price(ysym)})
    valid = [p for p in probes if isinstance(p.get("price"), (int, float)) and p.get("price") > 0]
    prices = [float(p["price"]) for p in valid]
    oanda_valid = next((p for p in valid if p.get("source") == "OANDA现货"), None)
    jin10_valid = next((p for p in valid if p.get("source") == "金十Quote"), None)
    gold_api_valid = next((p for p in valid if p.get("source") == "gold-api.com现货"), None)
    if is_crypto_template(cfg):
        primary = sorted(prices)[len(prices) // 2] if prices else None
    else:
        primary = float(oanda_valid["price"]) if oanda_valid else (float(jin10_valid["price"]) if jin10_valid else (sorted(prices)[len(prices) // 2] if prices else None))
    spread_pct = (max(prices) - min(prices)) / (sum(prices) / len(prices)) * 100 if len(prices) >= 2 else None
    if not is_crypto_template(cfg):
        quality, confidence, label, quality_metrics = non_crypto_quality(valid)
    else:
        quality, confidence, label = quality_from_consensus(valid, spread_pct)
        quality_metrics = {"source_spread_pct": spread_pct}
    source = "+".join(p["source"] for p in valid[:4]) if valid else "未配置价格源"
    return {"source": source, "price": primary, "quality": quality, "confidence": confidence, "label": label, "spread_pct": spread_pct, "sources": probes, **quality_metrics}


def template_price(symbol: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    quote = price_consensus(symbol, cfg)
    return {"source": quote.get("source"), "price": quote.get("price"), "quality": quote.get("quality"), "confidence": quote.get("confidence"), "label": quote.get("label"), "sources": quote.get("sources"), "spread_pct": quote.get("spread_pct")}

def ensure_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    risk = read_json(RISK_FILE, {})
    changed = False
    for k, v in DEFAULT_RISK.items():
        if k not in risk:
            risk[k] = v
            changed = True
    if risk.get("date") != today_str():
        risk.update({"date": today_str(), "daily_realized_pnl": 0.0, "trades_count": 0, "loss_streak": 0, "lock_trading": False})
        changed = True
    if changed or not RISK_FILE.exists():
        write_json(RISK_FILE, risk)
    for p in (PLAN_LOG, EVENT_LOG, REVIEW_LOG):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch(exist_ok=True)
    if not GOVERNANCE_FILE.exists():
        write_json(GOVERNANCE_FILE, default_governance())


def load_risk_state() -> dict[str, Any]:
    ensure_files()
    return read_json(RISK_FILE, dict(DEFAULT_RISK))


def save_risk_state(state: dict[str, Any]) -> None:
    write_json(RISK_FILE, state)


def risk_gate(score: float | None = None, data_quality: str = "B", rr: float | None = None, requested_risk: float | None = None, cvd_quality: str = "C") -> dict[str, Any]:
    state = load_risk_state()
    reasons: list[str] = []
    allowed = True
    max_risk = float(state.get("max_trade_risk", 10.0))
    if requested_risk is None and score is None:
        requested_risk = None
    daily_pnl = float(state.get("daily_realized_pnl", 0.0))
    max_daily_loss = float(state.get("max_daily_loss", 30.0))
    loss_streak = int(state.get("loss_streak", 0))

    if state.get("lock_trading"):
        allowed = False
        max_risk = 0.0
        reasons.append("风控已锁定")
    if daily_pnl <= -abs(max_daily_loss):
        allowed = False
        max_risk = 0.0
        reasons.append(f"日亏达到 `{abs(max_daily_loss):.0f}U` 上限")
    if loss_streak >= 3:
        allowed = False
        max_risk = 0.0
        reasons.append("连续亏损3笔，锁交易")
    if state.get("requires_review") or int(state.get("unreviewed_trade_count", 0) or 0) > 0:
        max_risk = min(max_risk, 2.0)
        reasons.append("存在未复盘成交，下一笔最高轻仓")
    elif loss_streak == 2:
        max_risk = min(max_risk, 2.0)
        reasons.append("连续亏损2笔，下一笔降至轻仓")

    q = str(data_quality or "B").upper()[0]
    if q == "C":
        max_risk = min(max_risk, 3.0)
        reasons.append("数据C级，最高轻仓")
    
    # v2.1: CVD质量自动扣减
    cvd_q = str(cvd_quality or "C").upper()[0]
    if cvd_q == "C":
        max_risk = min(max_risk, max_risk * 0.5)
        reasons.append("CVD C级→仓位上限半仓")
    
    if rr is not None and rr < 2.0:
        allowed = False
        max_risk = 0.0
        reasons.append("R:R低于1:2，禁做")
    if score is not None and score < 6:
        allowed = False
        max_risk = 0.0
        reasons.append("评分低于6，禁做")
    elif score is not None and score < 10:
        max_risk = min(max_risk, 5.0)
        reasons.append("非A级评分，最高常规仓")

    if requested_risk is not None:
        max_risk = min(max_risk, float(requested_risk))
    if max_risk <= 0:
        tier = "锁定"
    elif max_risk <= 2:
        tier = "轻仓"
    elif max_risk <= 5:
        tier = "常规"
    elif max_risk <= 7:
        tier = "高置信"
    else:
        tier = "极限"

    return {"allowed": allowed, "tier": tier, "max_risk_usd": round(max_risk, 2), "reasons": reasons or ["风控允许"], "state": state}


def position_size(entry: float, stop: float, risk_usd: float, leverage: float) -> dict[str, Any]:
    distance = abs(float(entry) - float(stop))
    if distance <= 0:
        return {"ok": False, "reason": "止损距离无效"}
    qty = float(risk_usd) / distance
    notional = qty * float(entry)
    margin = notional / float(leverage) if leverage else notional
    return {"ok": True, "qty": qty, "notional": notional, "margin": margin, "max_loss": risk_usd, "stop_distance": distance}


def http_get(url: str, params: dict[str, Any] | None = None, timeout: int = 10) -> Any:
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def binance_spot_price(symbol: str) -> float | None:
    s = str(symbol).upper()
    if not s.endswith("USDT") or "XAU" in s:
        return None
    try:
        data = http_get("https://api.binance.com/api/v3/ticker/price", {"symbol": symbol})
        return float(data["price"])
    except Exception:
        return None


def binance_futures_snapshot(symbol: str) -> dict[str, Any]:
    base = "https://fapi.binance.com"
    out: dict[str, Any] = {"source": "Binance Futures", "symbol": symbol, "ok": False}
    try:
        premium = http_get(base + "/fapi/v1/premiumIndex", {"symbol": symbol})
        oi = http_get(base + "/fapi/v1/openInterest", {"symbol": symbol})
        ls = http_get(base + "/futures/data/globalLongShortAccountRatio", {"symbol": symbol, "period": "5m", "limit": 3})
        taker = http_get(base + "/futures/data/takerlongshortRatio", {"symbol": symbol, "period": "5m", "limit": 3})
        out.update(
            {
                "ok": True,
                "mark_price": float(premium.get("markPrice", 0)),
                "index_price": float(premium.get("indexPrice", 0)),
                "funding": float(premium.get("lastFundingRate", 0)),
                "basis_pct": (float(premium.get("markPrice", 0)) - float(premium.get("indexPrice", 0))) / float(premium.get("indexPrice", 1)) * 100,
                "open_interest": float(oi.get("openInterest", 0)),
                "long_short_ratio": float(ls[-1].get("longShortRatio", 0)) if ls else None,
                "taker_buy_sell_ratio": float(taker[-1].get("buySellRatio", 0)) if taker else None,
                "quality": "A",
            }
        )
    except Exception as e:
        out.update({"error": str(e), "quality": "C"})
    out["interpretation"] = interpret_derivatives(out)
    return out


def interpret_derivatives(d: dict[str, Any]) -> str:
    if not d.get("ok"):
        return "衍生品数据不可用"
    notes: list[str] = []
    funding = float(d.get("funding") or 0)
    lsr = d.get("long_short_ratio")
    taker = d.get("taker_buy_sell_ratio")
    basis = float(d.get("basis_pct") or 0)
    if abs(funding) < 0.00002:
        notes.append("Funding接近中性")
    elif funding > 0:
        notes.append("Funding偏正，多头付费")
    else:
        notes.append("Funding偏负，空头付费")
    if lsr is not None:
        if lsr > 1.25:
            notes.append("账户多头偏拥挤")
        elif lsr < 0.8:
            notes.append("账户空头偏拥挤")
        else:
            notes.append("多空账户接近均衡")
    if taker is not None:
        if taker > 1.2:
            notes.append("Taker短线买盘主动")
        elif taker < 0.8:
            notes.append("Taker短线卖盘主动")
        else:
            notes.append("Taker短线中性")
    if abs(basis) > 0.08:
        notes.append("Mark/Index偏离较大")
    return "；".join(notes)


def source_snapshot(symbol: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = get_symbol_template(symbol)
    native = str(cfg.get("symbol") or symbol).upper()
    extra = extra or {}
    price_probe = price_consensus(native, cfg)
    spot = price_probe.get("price")
    if not isinstance(spot, (int, float)) and isinstance(extra.get("price_at_analysis"), (int, float)):
        spot = float(extra["price_at_analysis"])
        price_probe = {"source": "分析价临时兜底", "price": spot, "quality": "C", "confidence": 40, "label": "临时兜底", "sources": []}
    prices = [float(p["price"]) for p in price_probe.get("sources", []) if isinstance(p.get("price"), (int, float)) and p.get("price") > 0]

    if is_crypto_template(cfg):
        futures = binance_futures_snapshot(native)
        prices.extend(x for x in [futures.get("mark_price"), futures.get("index_price")] if isinstance(x, (int, float)) and x > 0)
        derivatives = futures
    else:
        derivatives = {
            "source": "品种模板",
            "symbol": native,
            "ok": False,
            "quality": "B" if prices else "C",
            "interpretation": "非加密品种，不套用Funding/OI；按模板查看宏观/事件背景",
            "template_context": cfg.get("derivatives", []),
        }
    spread_pct = price_probe.get("spread_pct") if isinstance(price_probe.get("spread_pct"), (int, float)) else ((max(prices) - min(prices)) / (sum(prices) / len(prices)) * 100 if len(prices) >= 2 else None)
    quality = str(price_probe.get("quality") or "C")
    confidence = int(price_probe.get("confidence") or (92 if quality == "A" else 75 if quality == "B" else 55 if prices else 0))
    macro_context = read_json(XAU_MACRO_FILE, {}) if normalize_asset(symbol) in {"XAU", "XAUUSD"} else {}
    snap = {
        "time": now_iso(),
        "symbol": native,
        "asset": cfg.get("asset"),
        "template": {k: cfg.get(k) for k in ("name", "market", "exchange", "leverage", "default_risk_usd", "risk_usd", "price_sources", "catalyst_sources")},
        "prices": {"primary": spot, "primary_source": price_probe.get("source"), "sources": price_probe.get("sources", [])},
        "price_spread_pct": spread_pct,
        "confidence": confidence,
        "confidence_label": price_probe.get("label"),
        "derivatives": derivatives,
        "quality": quality,
        "macro_context": macro_context,
        "extra": extra,
    }
    history_path = write_source_history(snap)
    snap["history_path"] = str(history_path)
    write_json(SOURCE_FILE, snap)
    # v1.1: 同时写品种独立快照，避免单文件被后一种覆盖
    per_symbol_file = DATA_DIR / f"source_snapshot_{symbol}.json"
    write_json(per_symbol_file, snap)
    return snap


def log_plan(plan: dict[str, Any]) -> dict[str, Any]:
    row = dict(plan)
    row.setdefault("time", now_iso())
    row.setdefault("schema", "trade_plan_v1")
    append_jsonl(PLAN_LOG, row)
    return row


def log_event(event: dict[str, Any]) -> dict[str, Any]:
    row = dict(event)
    row.setdefault("time", now_iso())
    row.setdefault("schema", "trade_event_v1")
    append_jsonl(EVENT_LOG, row)
    return row



def _latest_matching_trace(row: dict[str, Any]) -> dict[str, Any]:
    """Find latest event/plan trace for a review row by setup_id or plan_id+symbol."""
    setup_id = row.get("setup_id")
    plan_id = row.get("plan_id")
    symbol = row.get("symbol")
    candidates: list[dict[str, Any]] = []
    for source in (EVENT_LOG, PLAN_LOG):
        for item in load_jsonl(source):
            if setup_id and item.get("setup_id") == setup_id:
                candidates.append(item)
            elif plan_id and item.get("plan_id") == plan_id and (not symbol or item.get("symbol") == symbol):
                candidates.append(item)
    return candidates[-1] if candidates else {}


def enrich_review_trace(row: dict[str, Any]) -> dict[str, Any]:
    """Carry setup/model/trigger fields into trade review records."""
    trace = _latest_matching_trace(row)
    for key in (
        "setup_id", "model_id", "entry_tag", "exit_tag", "direction", "status",
        "data_grade", "level_confidence", "engine_confidence", "confidence_5",
        "trigger_kind", "trigger_price", "trigger_level", "trigger_level_name",
        "trigger_levels", "trigger_reason", "trigger_level_confidence", "setup_trace",
    ):
        if row.get(key) is None and trace.get(key) is not None:
            row[key] = trace.get(key)
    if row.get("model") is None and row.get("model_id") is not None:
        row["model"] = row.get("model_id")
    if any(row.get(k) is not None for k in ("setup_id", "model_id", "entry_tag", "exit_tag")):
        row["schema"] = "trade_review_v2"
    return row

def log_review(review: dict[str, Any]) -> dict[str, Any]:
    row = dict(review)
    row.setdefault("time", now_iso())
    row.setdefault("schema", "trade_review_v1")
    enrich_review_trace(row)
    append_jsonl(REVIEW_LOG, row)
    return row


SCORE_FIELDS = (
    ("structure", "结构"),
    ("timeframe", "周期"),
    ("order_flow", "订单流"),
    ("derivatives", "衍生品"),
    ("catalyst", "催化"),
    ("risk", "风控"),
    ("sentiment", "情绪"),
)


def score_setup(scores: dict[str, Any] | None = None, data_quality: str = "B", rr: float | None = None) -> dict[str, Any]:
    """Turn the seven manual/automated dimensions into the A/B/X state."""
    raw = scores or {}
    normalized: dict[str, float] = {}
    for key, _ in SCORE_FIELDS:
        try:
            value = float(raw.get(key, 0))
        except Exception:
            value = 0.0
        normalized[key] = max(0.0, min(2.0, value))
    total = round(sum(normalized.values()), 2)
    q = str(data_quality or "B").upper()[:1]
    reasons: list[str] = []
    if q == "C":
        reasons.append("数据C级，最高只能B等待")
    if rr is not None and rr < 2:
        reasons.append("R:R低于1:2，禁做")
    if total >= 11 and q != "C" and (rr is None or rr >= 2):
        state = "A做多/做空"
    elif total >= 7 and (rr is None or rr >= 1.5):
        state = "B等待"
    else:
        state = "X禁做"
    if q == "C" and state.startswith("A"):
        state = "B等待"
    if rr is not None and rr < 2:
        state = "X禁做"
    labels = {key: label for key, label in SCORE_FIELDS}
    return {"state": state, "total": total, "scores": normalized, "labels": labels, "data_quality": q, "rr": rr, "reasons": reasons or ["评分完成"]}


def format_score(result: dict[str, Any]) -> str:
    parts = []
    labels = result.get("labels", {})
    for key, value in result.get("scores", {}).items():
        parts.append(f"{labels.get(key, key)}{value:g}")
    return f"{result.get('state')} · {result.get('total')}/14 · " + " · ".join(parts)


def update_strategy_governance(review: dict[str, Any]) -> dict[str, Any]:
    """Update model-level expectancy without auto-promoting risky rules."""
    gov = read_json(GOVERNANCE_FILE, default_governance())
    rules = gov.setdefault("rules", {})
    model = str(review.get("model") or review.get("setup_model") or "未标注模型")
    row = rules.setdefault(model, {"status": "candidate", "sample_size": 0, "wins": 0, "losses": 0, "total_r": 0.0, "avg_r": 0.0, "expectancy_r": 0.0, "max_loss_streak": 0, "current_loss_streak": 0, "last_reviews": []})
    r_value = float(review.get("r_multiple", 0) or 0)
    row["sample_size"] = int(row.get("sample_size", 0)) + 1
    row["total_r"] = round(float(row.get("total_r", 0.0)) + r_value, 4)
    row["avg_r"] = round(row["total_r"] / max(row["sample_size"], 1), 4)
    row["expectancy_r"] = row["avg_r"]
    if r_value > 0:
        row["wins"] = int(row.get("wins", 0)) + 1
        row["current_loss_streak"] = 0
    elif r_value < 0:
        row["losses"] = int(row.get("losses", 0)) + 1
        row["current_loss_streak"] = int(row.get("current_loss_streak", 0)) + 1
        row["max_loss_streak"] = max(int(row.get("max_loss_streak", 0)), int(row["current_loss_streak"]))
    row["win_rate"] = round(row.get("wins", 0) / max(row["sample_size"], 1), 4)
    if row["sample_size"] < gov.get("policy", {}).get("min_sample_to_activate", 20):
        row["status"] = "testing"
        row["decision"] = "样本不足，不升权"
    elif row["expectancy_r"] < gov.get("policy", {}).get("min_expectancy_r", 0.15) or row.get("max_loss_streak", 0) >= 4:
        row["status"] = "retired"
        row["decision"] = "期望值或连续亏损不达标，降权/停用"
    else:
        row["status"] = "candidate"
        row["decision"] = "满足统计门槛，仍需棠溪手动批准"
    row["last_reviews"] = (row.get("last_reviews") or [])[-9:] + [{"time": now_iso(), "plan_id": review.get("plan_id"), "symbol": review.get("symbol"), "r": r_value}]
    gov["updated"] = now_iso()
    write_json(GOVERNANCE_FILE, gov)
    return gov


def mark_trade_opened(symbol: str, plan_id: str = "", note: str = "") -> dict[str, Any]:
    """Manual hook: mark a real filled trade so the next setup is review-gated."""
    state = load_risk_state()
    state["unreviewed_trade_count"] = int(state.get("unreviewed_trade_count", 0) or 0) + 1
    state["requires_review"] = True
    state["last_unreviewed_trade"] = {"time": now_iso(), "symbol": symbol, "plan_id": plan_id, "note": note}
    save_risk_state(state)
    return state


def record_trade_review(review: dict[str, Any]) -> dict[str, Any]:
    """Record a closed trade and update daily risk state."""
    ensure_files()
    row = log_review(review)
    pnl = float(review.get("pnl_usd", 0) or 0)
    state = load_risk_state()
    state["daily_realized_pnl"] = round(float(state.get("daily_realized_pnl", 0)) + pnl, 2)
    state["trades_count"] = int(state.get("trades_count", 0)) + 1
    if pnl < 0:
        state["loss_streak"] = int(state.get("loss_streak", 0)) + 1
    elif pnl > 0:
        state["loss_streak"] = 0
    state["unreviewed_trade_count"] = max(0, int(state.get("unreviewed_trade_count", 0) or 0) - 1)
    state["requires_review"] = state["unreviewed_trade_count"] > 0
    if state["daily_realized_pnl"] <= -abs(float(state.get("max_daily_loss", 30))):
        state["lock_trading"] = True
    if int(state.get("loss_streak", 0)) >= 3:
        state["lock_trading"] = True
    save_risk_state(state)
    row["risk_state_after"] = state
    row["strategy_governance_after"] = update_strategy_governance(review)
    return row


def format_risk_gate(gate: dict[str, Any]) -> str:
    reason = "；".join(gate.get("reasons", []))
    allowed = "允许" if gate.get("allowed") else "禁止"
    return f"{allowed} · {gate.get('tier')} · 最大风险 `{gate.get('max_risk_usd')}U` · {reason}"


if __name__ == "__main__":
    ensure_files()
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["snapshot", "risk", "init", "score", "review", "open", "governance"])
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--score", type=float)
    ap.add_argument("--quality", default="B")
    ap.add_argument("--rr", type=float)
    ap.add_argument("--scores", default="{}", help="JSON: structure/timeframe/order_flow/derivatives/catalyst/risk/sentiment")
    ap.add_argument("--plan-id", default="")
    ap.add_argument("--pnl", type=float, default=0.0)
    ap.add_argument("--r", type=float, default=0.0)
    ap.add_argument("--note", default="")
    ap.add_argument("--model", default="")
    args = ap.parse_args()
    if args.action == "init":
        print("ready")
    elif args.action == "snapshot":
        print(json.dumps(source_snapshot(args.symbol), ensure_ascii=False, indent=2))
    elif args.action == "risk":
        print(json.dumps(risk_gate(args.score, args.quality, args.rr), ensure_ascii=False, indent=2))
    elif args.action == "governance":
        print(json.dumps(read_json(GOVERNANCE_FILE, default_governance()), ensure_ascii=False, indent=2))
    elif args.action == "open":
        print(json.dumps(mark_trade_opened(args.symbol, args.plan_id, args.note), ensure_ascii=False, indent=2))
    elif args.action == "score":
        score_input = json.loads(args.scores)
        result = score_setup(score_input, args.quality, args.rr)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(format_score(result))
    else:
        review = {"plan_id": args.plan_id, "symbol": args.symbol, "pnl_usd": args.pnl, "r_multiple": args.r, "note": args.note, "model": args.model}
        print(json.dumps(record_trade_review(review), ensure_ascii=False, indent=2))
