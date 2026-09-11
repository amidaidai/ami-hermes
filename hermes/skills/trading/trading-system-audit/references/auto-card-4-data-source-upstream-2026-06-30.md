# 4 数据源上游注入模式 · 2026-06-30

从"管线有步骤但从未执行"到"10/10 全 ✅"的 4 个数据源上游集成模式。

## 背景

auto_card 管线路由定义了 10 步（tv→binance→cg_pro→macro→x_sent→cron_read→cvd→depth→corr→card），但其中的 4 步只有占位路由无实际数据采集代码。

## 模式 1: X情绪（缓存文件读取）

**数据源**：`data/x_sentiment_context.json`（由 cron `x_sentiment_context.py` 每隔数分钟更新）

**注入代码**（插入 auto_card 的 Step 5 之后、Step 6 之前）：
```python
try:
    _x_path = ROOT / "data" / "x_sentiment_context.json"
    if _x_path.exists():
        import json as _xj
        _x_data = _xj.loads(_x_path.read_text(encoding="utf-8"))
        _fg = _x_data.get("fear_greed", {})
        _gm = _x_data.get("global_market", {})
        _queries = _x_data.get("suggested_x_queries", [])
        print(f"  ✅ X情绪: BTC恐贪{_fg.get('value','?')}({_fg.get('classification','?')}) · 市占{_gm.get('btc_dominance','?')[:6]}% · {' | '.join(_queries[:2])}")
        engine_data["x_sentiment"] = _x_data
except Exception as _xe:
    print(f"  ⚠️ X情绪: {_xe}")
```

## 模式 2: 深度数据（REST API）

**数据源**：`https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=5`

**注入代码**（插入 auto_card 的 Binance 数据采集后、渲染前）：
```python
try:
    import urllib.request, json as _dj
    _sym = symbol.upper().replace(".P", "").split("-")[0].split(" ")[0]
    _url = f"https://api.binance.com/api/v3/depth?symbol={_sym}&limit=5"
    _req = urllib.request.Request(_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(_req, timeout=10) as _resp:
        _depth = _dj.loads(_resp.read().decode())
    _bids = _depth.get("bids", [])
    _asks = _depth.get("asks", [])
    if _bids and _asks:
        _bp = float(_bids[0][0]); _bq = float(_bids[0][1])
        _ap = float(_asks[0][0]); _aq = float(_asks[0][1])
        _spread = _ap - _bp
        print(f"  ✅ 深度: 买{_bp:,.1f}({_bq:.2f}) / 卖{_ap:,.1f}({_aq:.2f}) · 点差{_spread:.2f}({_spread/_bp*100:.3f}%)")
        engine_data["depth"] = {"bid_price": _bp, "bid_qty": _bq, "ask_price": _ap, "ask_qty": _aq, "spread": _spread, "spread_pct": _spread/_bp*100}
except Exception as _de:
    print(f"  ⚠️ 深度: {_de}")
```

**注意**：symbol 需要从 BINANCE:BTCUSDT.P → BTCUSDT 转换，XAUUSD 跳过（Binance 不支持黄金）。

## 模式 3: 相关性（孤儿模块）

**数据源**：`_advanced_orderflow()` 返回值中的 `out["orphan"]["corr_multiplier"]`

**判断方式**：读 `engine_data["_advanced"]["orphan"]["corr_multiplier"]`

```python
# 在孤儿信号展示块中
_orp = adv.get("factors", {})
_abs = _orp.get("absorption", {})
_corr = _orp.get("corr_multiplier", 1.0)
print(f"  ✅ 孤儿: corr={_corr} · {_abs.get('summary','正常')[:40]}")
```

**审计判断**：
```python
if engine_data.get("_advanced",{}).get("orphan",{}).get("corr_multiplier") is not None:
    completed_steps.add("corr")
```

## 模式 4: CoinGecko（已采集·修复审计关键字大小写）

CoinGecko 数据早就在 Step 1 的数据采集中完成（`multi_source_collector.cg_top_coins(10)` → `engine_data["cg_top"]`），但管线审计表的关键字检查用了 `"Coingecko"`（小写 g）而卡文本输出 `"CoinGecko"`（大写 G）→ 假 ⚠️。

**修法**：`"Coingecko"` → `"CoinGecko"`（修复大小写敏感）

## 审计表缺陷及根治

**问题**：旧审计表用 `if "CoinGecko" in card` 在渲染后的卡文本中搜索关键字。但 Step 1 的数据采集只在 stdout 输出，不进 `render_card_locked()` 的渲染结果。

**根治**：全部改用 `engine_data` 键值判断：
```python
if engine_data.get("cg_top") or "CoinGecko" in card: completed_steps.add("cg_pro")
if engine_data.get("x_sentiment"): completed_steps.add("x_sent")
if engine_data.get("cvd"): completed_steps.add("cvd")
if engine_data.get("depth"): completed_steps.add("depth")
if engine_data.get("_advanced",{}).get("orphan",{}).get("corr_multiplier"): completed_steps.add("corr")
```
