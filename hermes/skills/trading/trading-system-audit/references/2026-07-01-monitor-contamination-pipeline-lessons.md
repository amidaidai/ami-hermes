# 监控污染 + 管线数据源实测教训 · 2026-07-01

## 1. 测试调用污染监控位

**问题**: `auto_card('EURUSD-')` (测试品种带短横) 在执行 `build_setup_metadata()` 时会将 `EURUSD-` 写入 `data/monitor_levels.json` 的 `symbols` 字典。

行情守望在 `process_symbols()` 中循环处理所有 `symbols`，遇到 `EURUSD-` 触发 `_valid_symbol()` 失败 → log "跳过非法品种 EURUSD-" → continue → 下一个循环再次遇到同一非法品种 → **无限刷屏**。

**根因**: `monitor_levels.json` 作为持久化状态文件，任何品种（包括测试用的 `EURUSD-`）都会残留。

**修复**:
```bash
# 清理无效品种
python -c "
import json
with open('data/monitor_levels.json') as f:
    d = json.load(f)
syms = d.get('symbols', {})
if 'EURUSD-' in syms:
    del syms['EURUSD-']
d['symbols'] = syms
with open('data/monitor_levels.json','w') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
"
```

**预防**:
- `auto_card()` 应该过滤/拒绝无效品种名（含短横、空格等）不做持久化操作
- 行情守望重启后才生效（已有残留需手动清理）

---

## 2. `btc_signal` price=0 — source_snapshot API 误用

**问题**: `p0_refresh_all.py` 写入 btc_signal 时用 `ts.source_snapshot("BTCUSDT").get("price", 0)`。但 `source_snapshot()` 返回的 dict **没有顶层 `price` 字段**——价格嵌套在 `prices.primary`：
```python
snap = {
    "symbol": "BTCUSDT",
    "prices": {"primary": 58700, "spot": 58728, "futures": 58700},
    "quality": "A",
    ...
}
# snap.get("price") → None → 回退 0
```

**正确 API**: `price_consensus(symbol)` 返回含 `price` 字段的 dict：
```python
pc = ts.price_consensus("BTCUSDT")
price = pc["price"]  # 58700.37
```

**修复**:
```python
# 错误
snap = ts.source_snapshot("BTCUSDT")
price = snap.get("price") or snap.get("spot") or 0  # → 0

# 正确
pc = ts.price_consensus("BTCUSDT")
price = pc.get("price", 0)  # → 58700.37
```

---

## 3. X情绪数据桥接 (x_sentiment_context.json)

`cron: X情绪LLM分析` (c6ad11110a80) 运行时写入 `data/x_sentiment_context.json`，包含：

| 字段 | 内容 |
|------|------|
| `fear_greed.value` | 15 (Extreme Fear) |
| `global_market.btc_dominance` | 55.534% |
| `suggested_x_queries` | 搜索线索列表 |
| `market_snapshot` | 主要币种 24h 涨跌 |
| `coingecko_trending` | 热门币种 |

auto_card 读取模式（注入点：Step 5 社区情绪后）：
```python
try:
    _x_path = ROOT / "data" / "x_sentiment_context.json"
    if _x_path.exists():
        import json as _xj
        _x_data = _xj.loads(_x_path.read_text(encoding="utf-8"))
        _fg = _x_data.get("fear_greed", {})
        _gm = _x_data.get("global_market", {})
        _queries = _x_data.get("suggested_x_queries", [])
        print(f"  ✅ X情绪: BTC恐贪{_fg_v}({_fg_c}) · 市占{_btc_dom[:6]}% · {' | '.join(_queries[:2])}")
        engine_data["x_sentiment"] = _x_data
except Exception:
    pass
```

注意：X情绪缓存更新周期由 cron 决定（`17 8-23 * * *`，每小时 17 分），不在 auto_card 中实时刷新。

---

## 4. 深度数据采集 (Binance 公开 API)

auto_card 新增的深度采集模式（注入点：Step 6.① Binance 数据采集后）：

```python
import urllib.request, json as _dj
_sym = symbol.replace(".P", "").split("-")[0].split(" ")[0]
if not _sym.endswith("USDT"):
    print(f"  ℹ️ 深度: {_sym} 非加密品种·跳过")
else:
    _url = f"https://api.binance.com/api/v3/depth?symbol={_sym}&limit=5"
    _req = urllib.request.Request(_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(_req, timeout=10) as _resp:
        _depth = _dj.loads(_resp.read().decode())
    _bp = float(_depth["bids"][0][0]); _bq = float(_depth["bids"][0][1])
    _ap = float(_depth["asks"][0][0]); _aq = float(_depth["asks"][0][1])
```

**要点**:
- 仅限 USDT 结尾的加密品种（XAUUSD/EURUSD 跳过）
- 5档深度足够计算点差和薄厚度
- Binance 公开 API 不需要 key

---

## 5. 孤儿信号展示 (吸收/相关性)

`data/orphan_signals_{symbol}.json` 由 `orphan_integration.py` 在 auto_card 运行时写入，含：

| 字段 | 说明 | 示例 |
|------|------|------|
| `absorption.summary` | 订单流吸收摘要 | `订单流正常·无明显吸收/背离信号` |
| `absorption.detected` | 是否检测到吸收 | `False` |
| `cvd_confluence` | CVD 共振判定 | `无共振` |
| `corr_multiplier` | 相关性乘数 | `1.0` |
| `meta_label` | 执行门控 | `门控通过·置信50%` |

在 高级订单流确认 段展示：
```python
print(f"  ✅ 孤儿: corr={_corr} · {_abs_summary[:40]}")
```
