#!/usr/bin/env python3
"""
棠溪 · 多模型置信拼接引擎 v2.0 (动态TV数据版)
输入：data_gatherer.py 的 JSON 快照 (含 tv 子段)
输出：所有模型的方向+置信 + 合并结果
"""

import json, sys, math, os, urllib.request
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ═══════════════════════════════════════
# TV 数据读取辅助（从引擎 data 的 tv 子段或 JSON 缓存）
# ═══════════════════════════════════════

TV_DATA_CACHE = {}

def load_tv_data(data: dict) -> dict:
    """从 data dict 或 btc_tv_data.json 加载动态TV数据。"""
    # 优先使用 data dict 中已合并的 tv 子段
    tv = data.get("tv")
    if tv and isinstance(tv, dict) and tv.get("vwap"):
        return tv
    
    # 次优：从缓存文件读取
    if TV_DATA_CACHE.get("vwap"):
        return TV_DATA_CACHE
    
    try:
        tv_path = os.path.expanduser(
            "~/AppData/Local/hermes/data/btc_tv_data.json"
        )
        if os.path.exists(tv_path):
            with open(tv_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            tv = {
                "vwap": _sf(raw.get("vwap")),
                "vah": _sf(raw.get("vah")),
                "val": _sf(raw.get("val")),
                "poc": _sf(raw.get("poc")),
                "band1_high": _sf(raw.get("band1_high")),
                "band1_low": _sf(raw.get("band1_low")),
                "band2_high": _sf(raw.get("band2_high")),
                "band2_low": _sf(raw.get("band2_low")),
                "w_vwap": _sf(raw.get("w_vwap")),
                "m_vwap": _sf(raw.get("m_vwap")),
                "ema9": _sf(raw.get("ema9")),
                "ema21": _sf(raw.get("ema21")),
                "ema34": _sf(raw.get("ema34")),
                "ema55": _sf(raw.get("ema55")),
                "cvd": _sf(raw.get("cvd")),
                "cvd_slope": _sf(raw.get("cvd_slope")),
                "dopen": _sf(raw.get("dopen")),
            }
            TV_DATA_CACHE.update(tv)
            return tv
    except Exception:
        pass
    return {}


def _sf(val):
    """safe float"""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _compute_dynamic_atr(data: dict, tv: dict) -> float:
    """动态 ATR：优先从 24h 范围估算，兜底 287。"""
    spot = data.get("binance_spot", {}) or {}
    hi = _sf(spot.get("24h_high"))
    lo = _sf(spot.get("24h_low"))
    price = _sf(spot.get("price")) or _sf(data.get("prices", {}).get("primary"))
    if hi and lo:
        return round((hi - lo) / 3.0, 1)
    # 从 band 间距估算
    b2h, b2l = _sf(tv.get("band2_high")), _sf(tv.get("band2_low"))
    if b2h and b2l:
        return round((b2h - b2l) / 4.0, 1)
    return 287.0  # 最后兜底


# ═══════════════════════════════════════
# 模型定义 — 全改为动态 TV 数据读取
# ═══════════════════════════════════════

def model_vwap_bounce(data: dict) -> Tuple[str, float]:
    """VWAP反抽：趋势延续中回踩VWAP"""
    tv = load_tv_data(data)
    price = _sf(data.get("binance_spot", {}).get("price"))
    vwap_s = _sf(tv.get("vwap")) or _sf(tv.get("w_vwap")) or 0
    atr = _compute_dynamic_atr(data, tv)
    if not vwap_s or not price or not atr:
        return "null", 0.0
    
    dist = abs(price - vwap_s) / atr if atr > 0 else 99
    
    conditions = 0
    if dist <= 0.5:
        conditions += 1  # 靠近VWAP
    if price < vwap_s:
        conditions += 1  # 价格在VWAP下（回踩场景）
    # CVD 配合：CVD 收缩或转正
    cvd_slope = _sf(tv.get("cvd_slope"))
    if cvd_slope > 0:
        conditions += 1  # CVD 斜率改善
    # Taker 配合
    taker = data.get("taker_futures", {})
    if _sf(taker.get("ratio")) > 1.0:
        conditions += 1
    
    rate = conditions / 4
    quality = 0.8
    conf = rate * quality
    direction = "long" if price < vwap_s else "null"
    return direction, min(conf, 1.0)


def model_val_reclaim(data: dict) -> Tuple[str, float]:
    """VAL回收：跌破VAL下沿后涨回"""
    tv = load_tv_data(data)
    price = _sf(data.get("binance_spot", {}).get("price"))
    val = _sf(tv.get("val")) or _sf(tv.get("band1_low")) or 0
    atr = _compute_dynamic_atr(data, tv)
    if not val or not price or not atr:
        return "null", 0.0
    
    conditions = 0
    if price < val:
        conditions += 1  # 价格在VAL下方
    if val - price < atr * 1.5:
        conditions += 1  # 距VAL不太远可回收
    # CVD 改善
    cvd_slope = _sf(tv.get("cvd_slope"))
    if cvd_slope > 0:
        conditions += 1
    # Taker 买盘
    taker = data.get("taker_futures", {})
    if _sf(taker.get("ratio")) > 1.0:
        conditions += 1
    
    rate = conditions / 4
    quality = 0.8
    direction_bonus = 0.1
    conf = rate * quality + direction_bonus
    direction = "long"
    return direction, min(conf, 1.0)


def model_poc_reject(data: dict) -> Tuple[str, float]:
    """POC拒绝：价格回到POC失败"""
    tv = load_tv_data(data)
    price = _sf(data.get("binance_spot", {}).get("price"))
    poc = _sf(tv.get("poc")) or 0
    atr = _compute_dynamic_atr(data, tv)
    if not poc or not price or not atr:
        return "null", 0.0
    
    dist = abs(price - poc) / atr if atr > 0 else 99
    if dist > 2.0:
        return "null", 0.0
    
    conditions = 0
    if dist <= 0.5:
        conditions += 1  # 靠近POC
    if _sf(tv.get("cvd")) < 0 and _sf(tv.get("cvd_slope")) < 0:
        conditions += 1  # CVD 顺空
    taker = data.get("taker_futures", {})
    if _sf(taker.get("ratio")) < 0.9:
        conditions += 1  # Taker 卖方
    
    rate = conditions / 3
    quality = 0.8
    direction_bonus = -0.1 if price < poc else 0.1
    
    conf = rate * quality + direction_bonus
    direction = "short" if price < poc else "null"
    return direction, min(conf, 1.0)


def model_sweep_reclaim(data: dict) -> Tuple[str, float]:
    """扫流动性回收：刺破关键位快速收回"""
    price = _sf(data.get("binance_spot", {}).get("price"))
    low_24 = _sf(data.get("binance_spot", {}).get("24h_low"))
    high_24 = _sf(data.get("binance_spot", {}).get("24h_high"))
    atr = _compute_dynamic_atr(data, load_tv_data(data))
    if not price or not atr:
        return "null", 0.0
    
    dist_to_low = (price - low_24) / atr if low_24 else 99
    dist_to_high = (high_24 - price) / atr if high_24 else 99
    
    conditions = 0
    if dist_to_low < 0.3:
        conditions += 1
    if dist_to_high < 0.3:
        conditions += 1
    
    rate = conditions / 3 if conditions > 0 else 0
    quality = 0.8
    direction = "long" if dist_to_low < 0.3 else "short" if dist_to_high < 0.3 else "null"
    
    conf = rate * quality
    if conf < 0.1:
        return "null", 0
    return direction, min(conf, 1.0)


def model_breakout_accept(data: dict) -> Tuple[str, float]:
    """突破接受：突破关键位回踩不破"""
    tv = load_tv_data(data)
    price = _sf(data.get("binance_spot", {}).get("price"))
    val = _sf(tv.get("val")) or _sf(tv.get("band1_low"))
    vah = _sf(tv.get("vah")) or _sf(tv.get("band1_high"))
    atr = _compute_dynamic_atr(data, tv)
    if not price or not atr or (not val and not vah):
        return "null", 0.0
    
    d_val = abs(price - val) / atr if val else 99
    d_vah = abs(price - vah) / atr if vah else 99
    
    conditions = 0
    if d_val < 0.3 if val else False:
        conditions += 1
    if d_vah < 0.3 if vah else False:
        conditions += 1
    
    rate = conditions / 4
    quality = 0.8
    conf = rate * quality
    if conf < 0.15:
        return "null", 0
    direction = "long" if d_val < d_vah else "short"
    return direction, min(conf, 1.0)


def model_ema_trend(data: dict) -> Tuple[str, float]:
    """EMA趋势延续：EMA排列方向（动态TV数据）"""
    tv = load_tv_data(data)
    price = _sf(data.get("binance_spot", {}).get("price"))
    ema9 = _sf(tv.get("ema9"))
    ema21 = _sf(tv.get("ema21"))
    ema55 = _sf(tv.get("ema55"))
    if not price or not ema9:
        return "null", 0.0
    if not ema21:
        ema21 = ema9 * 0.99
    if not ema55:
        ema55 = ema9 * 0.98
    
    conditions = 0
    if ema9 < ema21 < ema55:
        if price < ema9:
            conditions += 3  # 完美空头排列
        elif price < ema21:
            conditions += 2
        elif price < ema55:
            conditions += 1
    elif ema9 > ema21 > ema55:
        if price > ema9:
            conditions += 3  # 完美多头排列
        elif price > ema21:
            conditions += 2
        elif price > ema55:
            conditions += 1
    else:
        # 混合排列
        if price > ema9:
            conditions += 1
        if price > ema21:
            conditions += 1
    
    rate = conditions / 3
    quality = 0.9
    direction = "short" if price < ema21 else "long" if price > ema21 else "null"
    conf = rate * quality
    return direction, min(conf, 1.0)


def model_funding_extreme(data: dict) -> Tuple[str, float]:
    """费率极端反转：费率极端→资金拥挤反转"""
    funding = data.get("funding", {}).get("current", 0)
    prev_funding = data.get("funding", {}).get("previous", 0)
    
    abs_rate = abs(funding) * 100  # pct
    rate_change = (funding - prev_funding) * 100 if prev_funding else 0
    
    conditions = 0
    if abs_rate > 0.01:
        conditions += 1  # 费率明显
    if abs_rate > 0.05:
        conditions += 1  # 极端
    if rate_change > 0.001:
        conditions += 1  # 正在翻转
    
    rate = conditions / 3
    quality = 1.0  # A级数据
    # funding just flipped from negative to positive → bullish reversal signal
    direction = "long" if funding > 0 and prev_funding < 0 else "short" if funding < 0 and prev_funding > 0 else "null"
    
    conf = rate * quality
    if conf < 0.1:
        return "null", 0
    return direction, min(conf, 1.0)


def model_ls_crowding(data: dict) -> Tuple[str, float]:
    """多空拥挤反转：L/S极端→反向"""
    ls = data.get("long_short_top", {})
    long_pct = ls.get("long", 50)
    
    conditions = 0
    if long_pct > 60:
        conditions += 2  # 多头拥挤
    elif long_pct < 40:
        conditions += 2  # 空头拥挤
    
    # 价格方向与持仓相反 = 背离信号
    price_change = data.get("binance_spot", {}).get("24h_change_pct", 0)
    if long_pct > 60 and price_change < -0.5:
        conditions += 1  # 多头拥挤+价格下跌 = 杀多风险 = 偏空
    if long_pct < 40 and price_change > 0.5:
        conditions += 1
    
    rate = conditions / 3
    quality = 1.0  # A级
    direction = "short" if long_pct > 60 and price_change < 0 else "long" if long_pct < 40 and price_change > 0 else "null"
    
    conf = rate * quality
    if conf < 0.15:
        return "null", 0
    return direction, min(conf, 1.0)


def model_taker_divergence(data: dict) -> Tuple[str, float]:
    """Taker背离：价格跌但Taker买→背离"""
    taker = data.get("taker_futures", {})
    ratio = taker.get("ratio", 1.0)
    price_change = data.get("binance_spot", {}).get("24h_change_pct", 0)
    
    conditions = 0
    # 价格跌 but taker buying → bullish divergence
    if price_change < -0.5 and ratio > 1.2:
        conditions += 3  # 强背离
    elif price_change < -0.3 and ratio > 1.1:
        conditions += 2
    elif price_change < 0 and ratio > 1.0:
        conditions += 1
    # 价格涨 but taker selling → bearish divergence
    elif price_change > 0.5 and ratio < 0.8:
        conditions += 3
    elif price_change > 0.3 and ratio < 0.9:
        conditions += 2
    
    rate = conditions / 3
    quality = 0.8  # B级
    direction = "long" if ratio > 1.1 and price_change < 0 else "short" if ratio < 0.9 and price_change > 0 else "null"
    
    conf = rate * quality
    if conf < 0.15:
        return "null", 0
    return direction, min(conf, 1.0)


def model_oi_divergence(data: dict) -> Tuple[str, float]:
    """OI背离：价格跌但OI不降→潜在吸筹"""
    price_change = data.get("binance_spot", {}).get("24h_change_pct", 0)
    oi_btc = data.get("oi", {}).get("btc", 0)
    # OI变化需历史对比，这里用简化版
    
    # 简化：价格跌+OI稳定（不是暴跌减仓）= 可能吸筹
    conditions = 0
    if price_change < -1.0 and oi_btc > 100000:
        conditions += 2  # 价格跌但OI仍高
    elif price_change < -0.5 and oi_btc > 100000:
        conditions += 1
    
    rate = conditions / 2
    quality = 0.8
    direction = "long" if conditions > 0 else "null"
    
    conf = rate * quality
    if conf < 0.15:
        return "null", 0
    return direction, min(conf, 1.0)


def model_m_vwap_magnet(data: dict) -> Tuple[str, float]:
    """M_VWAP磁吸：价格向月VWAP回归（动态TV数据）"""
    tv = load_tv_data(data)
    price = _sf(data.get("binance_spot", {}).get("price"))
    m_vwap = _sf(tv.get("m_vwap")) or _sf(tv.get("vwap")) or 0
    atr = _compute_dynamic_atr(data, tv)
    if not m_vwap or not price or not atr:
        return "null", 0.0
    
    dist = (price - m_vwap) / atr
    
    # 价格在M_VWAP上方 → 磁吸向下
    conditions = 0
    if 0 < dist < 5:
        conditions += 2  # 在上方可回归范围内
    if dist < 3:
        conditions += 1
    
    rate = conditions / 3
    quality = 0.8
    direction = "short" if price > m_vwap else "long"
    
    conf = rate * quality
    if conf < 0.1:
        return "null", 0
    return direction, min(conf, 1.0)


def model_correlation_arb(data: dict) -> Tuple[str, float]:
    """关联套利：DXY/BTC背离"""
    dxy = data.get("dxy", {}).get("value", 100)
    price_change = data.get("binance_spot", {}).get("24h_change_pct", 0)
    
    # DXY弱+BTC跌 = 背离 → 偏多
    dxy_weak = dxy < 100
    conditions = 0
    if dxy_weak and price_change < -1:
        conditions += 2
    elif dxy_weak and price_change < -0.5:
        conditions += 1
    
    rate = conditions / 2
    quality = 0.7  # 关联弱
    direction = "long" if conditions > 0 else "null"
    
    conf = rate * quality
    if conf < 0.1:
        return "null", 0
    return direction, min(conf, 1.0)


# ═══════════════════════════════════════
# 模型注册表
# ═══════════════════════════════════════

ALL_MODELS = [
    ("VWAP反抽", model_vwap_bounce),
    ("VAL回收", model_val_reclaim),
    ("POC拒绝", model_poc_reject),
    ("扫流动性回收", model_sweep_reclaim),
    ("突破接受", model_breakout_accept),
    ("EMA趋势", model_ema_trend),
    ("费率极端反转", model_funding_extreme),
    ("多空拥挤反转", model_ls_crowding),
    ("Taker背离", model_taker_divergence),
    ("OI背离", model_oi_divergence),
    ("M_VWAP磁吸", model_m_vwap_magnet),
    ("关联套利", model_correlation_arb),
]

# ═══════════════════════════════════════
# 合并引擎
# ═══════════════════════════════════════

def run_all_models(data: dict, symbol: str = "BTCUSDT") -> List[dict]:
    """运行所有模型，返回结果列表。F轮：应用 asset_weight_adapter 按资产调整置信度。"""
    results = []
    for name, fn in ALL_MODELS:
        try:
            direction, confidence = fn(data)
            # F轮多资产权重适配 (同一模块直接调用)
            try:
                confidence = asset_weight_adapter(symbol, confidence, name)
            except Exception:
                pass
            results.append({
                "name": name,
                "direction": direction,
                "confidence": round(confidence, 3),
                "strength": "强" if confidence >= 0.6 else "中等" if confidence >= 0.4 else "弱" if confidence >= 0.2 else "无",
            })
        except Exception as e:
            results.append({"name": name, "direction": "error", "confidence": 0, "strength": "错误", "error": str(e)[:50]})
    return results


# ═══════════════════════════════════════
# 事件禁做检查（v1.2：从硬编码改为实际检查）
# ═══════════════════════════════════════

HIGH_IMPACT_EVENTS = [
    "非农", "NFP", "CPI", "FOMC", "利率决议", "GDP", "PMI", "失业率",
    "鲍威尔", "Powell", "央行", "零售销售", "PCE", "就业",
]

def check_event_ban(data: dict, symbol: str = "BTCUSDT") -> tuple:
    """
    检查是否存在活跃的禁做事件。
    Returns: (is_banned: bool, reason: str)
    """
    reasons = []
    
    # 1. 极端波动检查（15分钟内 >2% for BTC, >1% for XAUUSD）
    price_data = data.get("binance_spot", {}) or data.get("prices", {})
    primary_price = price_data.get("price", 0) or data.get("prices", {}).get("primary", 0)
    
    if isinstance(primary_price, (int, float)) and primary_price > 0:
        volatility_threshold = 0.05 if "BTC" in symbol.upper() or "ETH" in symbol.upper() else 0.01
        # Check 24h change if available
        change_pct = price_data.get("24h_change_pct", 0)
        if abs(change_pct) > volatility_threshold * 100:
            reasons.append(f"24h波动{abs(change_pct):.1f}%→极端波动禁做")
    
    # 2. 数据质量C级 → 自动降级
    quality = data.get("quality", data.get("grades", {}).get("overall", "B"))
    if quality == "C":
        reasons.append("数据质量C级→半仓/禁做")
    
    # 3. 宏观风险off → 禁做
    macro = data.get("macro_context", {})
    if macro.get("bias") == "risk_off":
        reasons.append("宏观risk_off→禁做")
    
    # 4. 价格暴涨暴跌检查（从 prices 或 binance_spot 取数据）
    price_sources = data.get("prices", {}).get("sources", [])
    for src in price_sources:
        raw = src.get("raw", {})
        if raw.get("ups_percent"):
            try:
                ups = float(raw["ups_percent"])
                if abs(ups) > 5:
                    reasons.append(f"日内涨跌幅{ups:.1f}%→极端事件禁做")
            except (ValueError, TypeError):
                pass
    
    # 5. 跨市场价差异常
    spread = data.get("price_spread_pct", 0)
    if spread > 5:
        reasons.append(f"跨市场价差{spread:.1f}%→数据异常禁做")
    
    if reasons:
        return True, " · ".join(reasons)
    return False, ""


# ═══════════════════════════════════════
# v1.3: Grok 交叉验证层
# ═══════════════════════════════════════

AUTH_JSON = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "hermes/auth.json"
GROK_MODEL = "grok-4.20-0309-non-reasoning"
GROK_TIMEOUT = 8  # seconds

def _read_grok_token() -> Optional[str]:
    try:
        if AUTH_JSON.exists():
            auth = json.loads(AUTH_JSON.read_text(encoding="utf-8"))
            return auth.get("providers", {}).get("xai-oauth", {}).get("access_token")
    except Exception:
        pass
    return None


def call_grok_validation(
    symbol: str,
    merged: dict,
    model_results: List[dict],
    price: float = 0,
    data: Optional[dict] = None,
) -> dict:
    """
    调用 Grok 验证引擎结论.
    Returns: {agree: bool, divergence: str, blindspot: str, grok_direction: str, grok_confidence: float, error: str}
    仅在 global_conf > 0.5 时调用.
    """
    if merged.get("global_confidence", 0) < 0.5:
        return {"agree": True, "divergence": "", "blindspot": "",
                "grok_direction": "", "grok_confidence": 0, "skipped": "置信过低"}
    
    token = _read_grok_token()
    if not token:
        return {"agree": True, "divergence": "", "blindspot": "",
                "grok_direction": "", "grok_confidence": 0, "error": "无token"}
    
    # 构建 prompt
    model_summary = ", ".join(
        f"{r['name']}={r['direction']}({r['confidence']:.2f})"
        for r in sorted(model_results, key=lambda x: -x["confidence"])
        if r["confidence"] > 0.15
    )
    
    # 数据上下文
    data_ctx = ""
    if data:
        macro = data.get("macro_context", {})
        if macro:
            dxy = macro.get("prices", {}).get("DXY", {}).get("price", "?")
            data_ctx += f"DXY={dxy} "
        quality = data.get("quality", data.get("grades", {}).get("overall", "?"))
        data_ctx += f"数据质量={quality} "
    
    prompt = f"""你是交易分析专家。验证以下 {symbol} 的多模型引擎结论：

现价: {price}
引擎方向: {merged.get('bias','?')} | 全局置信: {merged.get('global_confidence',0):.3f}
多头信号: {merged.get('long_confidence',0):.3f} ({merged.get('long_models',0)}个)
空头信号: {merged.get('short_confidence',0):.3f} ({merged.get('short_models',0)}个)
模型详情: {model_summary}
{data_ctx}

输出 JSON（仅 JSON，无其他文字）:
{{
  "agree": true/false,
  "grok_direction": "偏多"/"偏空"/"震荡",
  "grok_confidence": 0.0-1.0,
  "divergence": "与引擎分歧点（空字符串=无分歧）",
  "blindspot": "引擎可能遗漏的要点（空字符串=无遗漏）"
}}"""
    
    try:
        data_bytes = json.dumps({
            "model": GROK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 200,
        }).encode()
        
        req = urllib.request.Request(
            "https://api.x.ai/v1/chat/completions",
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        
        with urllib.request.urlopen(req, timeout=GROK_TIMEOUT) as r:
            resp = json.loads(r.read())
        
        text = resp["choices"][0]["message"]["content"].strip()
        
        # Parse JSON from response (handle markdown code blocks)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        
        grok = json.loads(text)
        return {
            "agree": grok.get("agree", True),
            "divergence": grok.get("divergence", ""),
            "blindspot": grok.get("blindspot", ""),
            "grok_direction": grok.get("grok_direction", ""),
            "grok_confidence": float(grok.get("grok_confidence", 0)),
        }
    
    except Exception as e:
        return {"agree": True, "divergence": "", "blindspot": "",
                "grok_direction": "", "grok_confidence": 0, "error": str(e)[:100]}


def merge_directions(results: List[dict], event_ban: bool = False, event_ban_reason: str = "") -> dict:
    """合并多方向多模型输出"""
    long_models = [r for r in results if r["direction"] == "long" and r["confidence"] > 0.15]
    short_models = [r for r in results if r["direction"] == "short" and r["confidence"] > 0.15]
    null_models = [r for r in results if r["direction"] == "null" or r["confidence"] <= 0.15]
    
    def weighted_conf(models):
        """v2.0: HHI多样性惩罚+模型数加成，防止单模型霸凌"""
        if not models:
            return 0
        confs = [m["confidence"] for m in models]
        n = len(confs)
        sum_c = sum(confs)
        sum_c2 = sum(c*c for c in confs)
        
        # HHI: 1.0 = 单模型垄断, ~0 = 多模型均衡
        hhi = sum_c2 / (sum_c * sum_c) if sum_c > 0 else 1.0
        diversity_bonus = (1.0 - hhi) * 0.12  # 多模型均衡→奖励
        
        # 单模型贡献上限0.65，防极端权重
        capped = [min(c, 0.65) for c in confs]
        sum_cap = sum(capped)
        sum_cap2 = sum(c*c for c in capped)
        base = sum_cap2 / sum_cap if sum_cap > 0 else 0
        
        return round(min(base + diversity_bonus, 1.0), 3)
    
    long_conf = weighted_conf(long_models)
    short_conf = weighted_conf(short_models)
    
    diff = long_conf - short_conf
    
    # v2.1: 模型数比动态调整bias阈值
    n_long = len(long_models)
    n_short = len(short_models)
    if n_long > 0 and n_short > 0:
        ratio = n_long / n_short if n_long > n_short else n_short / n_long
        threshold = 0.15 + ratio * 0.05  # 模型数越悬殊→阈值越宽→倾向"方向不明"
    else:
        threshold = 0.2
    
    if diff > threshold:
        bias = "偏多"
    elif diff < -threshold:
        bias = "偏空"
    else:
        bias = "方向不明/震荡"
    
    global_conf = max(long_conf, short_conf)
    
    if event_ban:
        action = f"事件禁做（{event_ban_reason}）"
    elif global_conf >= 0.6:
        action = "可交易 · 常规仓"
    elif global_conf >= 0.4:
        action = "可交易 · 轻仓"
    else:
        action = "不交易"
    
    # v2.1: 置信映射补充标准
    if global_conf >= 0.85:
        confidence_5 = 5
    elif global_conf >= 0.7:
        confidence_5 = 4
    elif global_conf >= 0.5:
        confidence_5 = 3
    elif global_conf >= 0.4:
        confidence_5 = 2
    else:
        confidence_5 = 1
    
    return {
        "long_models": len(long_models),
        "long_confidence": long_conf,
        "short_models": len(short_models),
        "short_confidence": short_conf,
        "diff": round(diff, 3),
        "bias": bias,
        "global_confidence": global_conf,
        "confidence_5": confidence_5,
        "action": action,
        "null_models": len(null_models),
        "event_ban": event_ban,
    }


def format_results(results: List[dict], merged: dict) -> str:
    """格式化输出"""
    lines = []
    lines.append("多模型拼接结果：")
    lines.append("┌──────────────┬──────┬────────┬──────────┐")
    lines.append("│ 模型         │ 方向 │ 置信   │ 信号强度 │")
    lines.append("├──────────────┼──────┼────────┼──────────┤")
    
    # Sort by confidence desc
    for r in sorted(results, key=lambda x: -x["confidence"]):
        dir_label = "多" if r["direction"] == "long" else "空" if r["direction"] == "short" else "—"
        if r["confidence"] < 0.15:
            continue
        lines.append(f"│ {r['name']:<12} │ {dir_label:>4} │ {r['confidence']:.3f} │ {r['strength']:<8} │")
    
    lines.append("└──────────────┴──────┴────────┴──────────┘")
    lines.append("")
    lines.append(f"做多综合：{merged['long_confidence']:.3f}（{merged['long_models']}个信号）")
    lines.append(f"做空综合：{merged['short_confidence']:.3f}（{merged['short_models']}个信号）")
    lines.append(f"差值：{merged['diff']:+.3f} → **{merged['bias']}**")
    lines.append(f"全局置信：{merged['global_confidence']:.3f} → {merged['action']}")
    lines.append(f"无效/噪音：{merged['null_models']}个模型")
    
    return "\n".join(lines)


# ═══════════════════════════════════════
# 入口
# ═══════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.loads(sys.stdin.read())
    
    # 检测品种
    symbol = data.get("symbol", "BTCUSDT")
    
    # v1.2: 实际事件检查替代硬编码
    event_ban, event_reason = check_event_ban(data, symbol)
    
    results = run_all_models(data, symbol)
    merged = merge_directions(results, event_ban=event_ban, event_ban_reason=event_reason)
    
    # v1.3: Grok 交叉验证
    grok_result = {}
    try:
        price = data.get("binance_spot", {}).get("price", 0) or data.get("prices", {}).get("primary", 0)
        grok_result = call_grok_validation(symbol, merged, results, price, data)
        
        if not grok_result.get("skipped") and not grok_result.get("error"):
            if grok_result.get("agree"):
                merged["grok_agree"] = True
                merged["global_confidence"] = round(merged["global_confidence"] + 0.05, 3)
            else:
                # v2.1: Grok分歧→强制降级（最高B等待/轻仓，不给出入场）
                merged["grok_agree"] = False
                merged["grok_divergence"] = grok_result.get("divergence", "")
                if "禁做" not in merged["action"] and "不交易" not in merged["action"]:
                    merged["action"] = "⚠Grok分歧→B等待"
                merged["confidence_5"] = min(merged.get("confidence_5", 4), 3)
            
            merged["grok_direction"] = grok_result.get("grok_direction", "")
            merged["grok_confidence"] = grok_result.get("grok_confidence", 0)
            merged["grok_blindspot"] = grok_result.get("blindspot", "")
        elif grok_result.get("skipped"):
            merged["grok_skipped"] = grok_result["skipped"]
        elif grok_result.get("error"):
            merged["grok_error"] = grok_result["error"]
    except Exception:
        pass
    
    # v1.1: 自动记录预测（供胜率回验）
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hermes" / "scripts"))
        from prediction_tracker import log_prediction
        price = data.get("binance_spot", {}).get("price", 0) or data.get("prices", {}).get("primary", 0)
        log_prediction(symbol, merged, results, price=price)  # v2.0: price written at log time, no post-patch needed
    except Exception:
        pass
    
    print(format_results(results, merged))
    print()
    
    # v1.2: 仓位建议
    try:
        from position_sizer import position_advice, format_position
        price = data.get("binance_spot", {}).get("price", 0) or data.get("prices", {}).get("primary", 0)
        pos = position_advice(merged, entry=price, event_ban=event_ban,
                              data_grade=data.get("quality", data.get("grades", {}).get("overall", "B")),
                              cvd_grade="C")
        print("── 仓位建议 ──")
        print(format_position(pos))
    except Exception:
        pass
    
    print("\n--- JSON ---")
    print(json.dumps({"results": results, "merged": merged}, ensure_ascii=False, indent=2))

def get_perfect_community_signals(data: dict, symbol: str) -> dict:
    """Perfect v6.9.2 community signals for renderer and monitor."""
    from auto_card import _compute_perfect_signals  # reuse
    price = data.get("price", 0)
    return _compute_perfect_signals(data, symbol, price)

# ═══ 多资产权重适配器 (本次全面优化新增) ═══
def get_asset_class(symbol: str) -> str:
    su = str(symbol).upper()
    if "XAU" in su or "GOLD" in su: return "gold"
    if su.endswith("USDT") or "BTC" in su or "ETH" in su: return "crypto"
    forex = ["EUR","GBP","JPY","AUD","NZD","CAD","CHF"]
    if any(x in su for x in forex) and not su.endswith("USDT"): return "forex"
    if su.isalpha() and len(su) <= 5: return "stock"
    if "CALL" in su or "PUT" in su: return "option"
    return "other"

def asset_weight_adapter(symbol: str, base_conf: float, model_name: str = "") -> float:
    """按资产调整模型权重（社区2026多资产优化）"""
    ac = get_asset_class(symbol)
    w = base_conf
    if ac == "gold":
        if any(k in model_name.lower() for k in ["kill", "sweep", "dxy"]):
            w *= 1.25
    elif ac == "forex":
        if any(k in model_name.lower() for k in ["silver", "smt", "dxy"]):
            w *= 1.15
    elif ac == "crypto":
        if any(k in model_name.lower() for k in ["cvd", "funding", "oi", "sweep"]):
            w *= 1.1
    elif ac == "stock":
        w *= 0.85  # 个股谨慎
    return min(max(w, 0.0), 1.0)
