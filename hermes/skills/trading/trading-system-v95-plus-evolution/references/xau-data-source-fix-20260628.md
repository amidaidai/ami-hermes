# XAU 数据源修复 · 2026-06-28

## 问题

`auto_card.py` 的 `_enrich_engine_data()` metal 分支用 Yahoo GC=F（COMEX 黄金期货） + 静态 `spot_adj=-125` 生成 XAU K 线。

**致命缺陷**：
1. 期货-现货价差不是固定的 $125，随合约到期日、利率、存储成本变化
2. GC=F 期货价格与 OANDA/金十现货存在系统性偏差（~0.4%），时变
3. 静态调整 `spot_adj=-125` 在极端行情下导致 `close-high < close < close-low` 物理不可能的数据
4. **后果**：XAU 分析卡 `现价 4,091 高 3,984 低 3,954`（现价高于"最高价"）

## 修复方案

### 价格采集：单源 → 三源共识

```python
# 旧代码（auto_card.py L2324-2335）
r = _req.get("https://api.gold-api.com/price/XAU", timeout=8)
price = float(data.get("price", 4310))
engine_data["prices"] = {"primary": price, "source": "gold-api现货"}

# 新代码
from trading_system import price_consensus
consensus = price_consensus(symbol)
price = consensus.get("price")
quality = consensus.get("quality")  # 真实质量分
source_label = consensus.get("source")
```

### 24h 高/低：金十 Quote raw 数据

```python
# 金十 Quote raw 结构
raw = {
    "close": "4081.29",   # 当前价（不要用作 prevClose）
    "high": "4096.00",    # 24h 最高
    "low": "3983.08",     # 24h 最低
    "open": "4028.89",    # 今日开盘
    "code": "XAUUSD",
    "name": "现货黄金",
}

# 注入 binance_spot
engine_data["binance_spot"]["24h_high"] = float(raw["high"])
engine_data["binance_spot"]["24h_low"] = float(raw["low"])
```

### K 线：完全移除 Yahoo GC=F

```python
# 旧代码：Yahoo GC=F 期货 + spot_adj=-125
# 新代码：简化占位 K 线 + 标记待 TV MCP
for tf in ["5m", "15m", "1h", "4h"]:
    klines_dict[tf] = {
        "close": price, "high": price, "low": price,
        "open": price, "change_pct": 0,
        "direction": "待获取",
        "description": f"XAU {tf} K线待TV MCP采集",
    }
engine_data["_xau_klines_pending"] = True
```

### 卡片渲染：智能回退

当 `_compact_card()` 检测到 `k15m.high == k15m.low == price`（占位标志），自动回退到 `binance_spot.24h_high/24h_low`：

```python
# auto_card.py _compact_card() L3114-3123
_raw_hi = k15m.get("high") or k4h.get("high")
_raw_lo = k15m.get("low") or k4h.get("low")
if _raw_hi == _raw_lo and _raw_hi and abs(float(_raw_hi) - p) < max(p * 0.001, 5):
    spot = engine_data.get("binance_spot", {})
    if spot:
        _raw_hi = spot.get("24h_high", _raw_hi)
        _raw_lo = spot.get("24h_low", _raw_lo)
```

## 验证

| 卡片 | 现价 | 高 | 低 | 逻辑 |
|------|------|-----|-----|------|
| XAUUSD 修复前 | 4,091 | 3,984 | 3,954 | ❌ 现价 > 高 |
| XAUUSD 修复后 | 4,081 | 4,096 | 3,983 | ✅ 低 < 现价 < 高 |
| BTCUSDT 修复后 | 59,842 | 60,925 | 59,715 | ✅ 无回归 |

## 铁律

- XAU 现货数据只能用现货源：OANDA / gold-api.com / 金十 Quote
- Yahoo GC=F / MGC=F 仅在 `price_consensus()` 中作为期货 baseline 参考，不参与现货共识
- XAU 多周期 K 线唯一可信源是 TradingView MCP（CDP 连接）
- TV MCP 离线时：宁可占位 `_xau_klines_pending`，绝不拉期货代理
- 改动后务必同时跑 `auto_card.py BTCUSDT` 确认加密路径无回归

## 相关文件

- `hermes/scripts/auto_card.py` — `_enrich_engine_data()` metal 分支 + `_compact_card()` 高/低回退
- `scripts/trading_system.py` — `price_consensus()`, `gold_api_price()`, `non_crypto_quality()`
- `data/auto_card_XAUUSD.md` — 输出卡片
