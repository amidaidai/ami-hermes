# Dynamic Model Engine Fix (2026-06-22)

## Problem

`multi_model_engine.py` had 8 hardcoded static price levels (VWAP/VAH/VAL/POC/EMA9/21/55/mVWAP) that were 1,000-2,200 points off from actual market data. All model calculations (VWAP反抽, VAL回收, POC拒绝, 突破接受, EMA趋势, M_VWAP磁吸) produced garbage output because they referenced wrong reference prices.

## Fix Pattern (3-part change)

### Part 1: TV Data Loader in multi_model_engine.py

Add a module-level helper with memory cache:

```python
TV_DATA_CACHE = {}

def load_tv_data(data: dict) -> dict:
    """从 data dict 的 tv 子段或 btc_tv_data.json 缓存加载动态TV数据。"""
    # 优先级1: data dict 中已合并的 tv 子段
    tv = data.get("tv")
    if tv and isinstance(tv, dict) and tv.get("vwap"):
        return tv
    # 优先级2: 内存缓存（进程内多次调用复用）
    if TV_DATA_CACHE.get("vwap"):
        return TV_DATA_CACHE
    # 优先级3: 从 TV 数据桥缓存文件读取
    try:
        tv_path = os.path.expanduser("~/AppData/Local/hermes/data/btc_tv_data.json")
        if os.path.exists(tv_path):
            with open(tv_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            tv = {k: _sf(raw.get(k)) for k in [
                "vwap", "vah", "val", "poc",
                "band1_high", "band1_low", "band2_high", "band2_low",
                "w_vwap", "m_vwap", "ema9", "ema21", "ema34", "ema55",
                "cvd", "cvd_slope", "dopen"
            ]}
            TV_DATA_CACHE.update(tv)
            return tv
    except Exception:
        pass
    return {}  # 无数据时返回空dict，模型会返回 null
```

Also add a **safe float** helper and **dynamic ATR** estimator:

```python
def _sf(val):
    """safe float — 处理 None / TypeError / ValueError"""
    if val is None: return 0.0
    try: return float(val)
    except (ValueError, TypeError): return 0.0

def _compute_dynamic_atr(data: dict, tv: dict) -> float:
    """动态 ATR：24h范围优先，band间距次之，287兜底"""
    spot = data.get("binance_spot", {}) or {}
    hi = _sf(spot.get("24h_high"))
    lo = _sf(spot.get("24h_low"))
    if hi and lo:
        return round((hi - lo) / 3.0, 1)
    b2h, b2l = _sf(tv.get("band2_high")), _sf(tv.get("band2_low"))
    if b2h and b2l:
        return round((b2h - b2l) / 4.0, 1)
    return 287.0  # 最后兜底
```

### Part 2: Modify Each Model Function

Each model function changes from:

```python
def model_vwap_bounce(data: dict) -> Tuple[str, float]:
    price = data.get("binance_spot", {}).get("price", 0)
    vwap_s = 66054  # ← HARDCODED
    atr = 287       # ← HARDCODED
    ...
```

To:

```python
def model_vwap_bounce(data: dict) -> Tuple[str, float]:
    tv = load_tv_data(data)
    price = _sf(data.get("binance_spot", {}).get("price"))
    vwap_s = _sf(tv.get("vwap")) or _sf(tv.get("w_vwap")) or 0
    atr = _compute_dynamic_atr(data, tv)
    if not vwap_s or not price or not atr:
        return "null", 0.0  # 数据不足时静默降级
    dist = abs(price - vwap_s) / atr if atr > 0 else 99
    ...
```

Also **add conditions**: CVD斜率 + Taker买卖比作为额外信号因子:

```python
    cvd_slope = _sf(tv.get("cvd_slope"))
    if cvd_slope > 0: conditions += 1  # CVD 斜率改善
    taker = data.get("taker_futures", {})
    if _sf(taker.get("ratio")) > 1.0: conditions += 1  # Taker 买方
```

Models that were already dynamic (funding_extreme, ls_crowding, taker_divergence, oi_divergence, correlation_arb) stay as-is since they read from `data` dict fields, not hardcoded prices.

### Part 3: Merge TV Data Upstream (auto_card.py)

Before calling `run_all_models(engine_data, symbol)`, merge TV data into engine_data:

```python
# 在 auto_card.py 的 Step 2 之前
try:
    _tv_path = Path.home() / "AppData/Local/hermes/data/btc_tv_data.json"
    if _tv_path.exists():
        with open(_tv_path, "r", encoding="utf-8") as _tf:
            _tv_raw = json.load(_tf)
        engine_data["tv"] = {
            "vwap": float(_tv_raw.get("vwap") or 0),
            "vah": float(_tv_raw.get("vah") or 0),
            "val": float(_tv_raw.get("val") or 0),
            "poc": float(_tv_raw.get("poc") or 0),
            # ... all 17 TV fields
        }
except Exception as _tve:
    print(f"  ⚠️ TV数据加载: {_tve}")
```

## Verification

After applying the fix:

1. **Syntax check**: `python -c "import py_compile; py_compile.compile('hermes/scripts/multi_model_engine.py', doraise=True); print('OK')"`
2. **Live pipeline test**: `python hermes/scripts/auto_card.py BTCUSDT 2>&1 | head -20`
   — Confirm output shows live TV values: `VWAP 64202.8 | VAH 64460.2 | VAL 63894.0`
   — Previously would have shown `7` hardcoded values
3. **Compare with TV MCP**: Run `mcp_tradingview_data_get_study_values()` and verify:
   - engine VWAP ≈ TV "S VWAP" (±0.2%)
   - engine VAH/VAH ≈ TV VAH Price / VAL Price

## Files Changed

- `hermes/scripts/multi_model_engine.py` — core fix (+258 lines, -133)
- `hermes/scripts/auto_card.py` — TV data merge (+45 lines)
- `hermes/scripts/data_gatherer.py` — account_balance live fetch (+12 lines)
- `scripts/run_daily_validation.py` — defensive missing-data handling (+15 lines)
- `scripts/btc_push_cron.py` — dead code removal
- `scripts/topic_router.py` — subprocess→telegram_direct

## Community Source

Pattern inspired by LLM-TradeBot's data sync layer (live TV data → analysis engine) and Hermes best practices (no_agent cron for data collection, agent for analysis). Four-layer pipeline design:
1. Data Sync (no_agent cron) → 2. Dynamic Analysis (live TV params) → 3. Signal & Alert → 4. Card Generation
