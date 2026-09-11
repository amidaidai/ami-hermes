# 13模型覆盖矩阵 v1.0 · 2026-06-18

## 模型分层 · 资产适配

13个模型天然按数据依赖分成两派：

### BTC专属（4个·需Binance futures数据）
| 模型 | 关键数据 | conf阈值 | 触发条件 | 回测表现(31天15m) |
|------|---------|---------|---------|------------------|
| 费率极端反转 | funding_rate + rate_change | abs_rate>0.01 | 费率翻转 | 0笔·funding模拟不够极端 |
| 多空拥挤反转 | long_pct极端(<40%或>60%) | conf>0.15 | LS极值+价格反向 | 0笔·LS比在31天内未极端 |
| Taker背离 | taker_futures.ratio vs 24h_change | conf>0.15 | ratio>1.1且价跌 或 ratio<0.9且价涨 | 30笔·33%WR·需调阈 |
| OI背离 | oi.btc vs 24h_change | conf>0.15 | 价跌OI不降 | 26笔·35%WR·需调阈 |

### XAU专属（3个·黄金特性更好）
| 模型 | 关键数据 | 为什么黄金更好 | 回测表现(BTC) |
|------|---------|---------------|--------------|
| M_VWAP磁吸 | 价格距VWAP | 黄金频繁回归VWAP·磁吸效应强 | 7笔·29%WR·BTC趋势性太强 |
| 关联套利 | dxy + correlation | XAU vs DXY天然负相关 | 0笔·缺DXY实时数据 |
| 突破接受 | VAH/VAL突破+回踩 | 黄金突破更干净·假突破少 | 0笔·被VWAP反抽优先级压制 |

### 共用（6个·两边都行）
| 模型 | BTC 31d 15m回测 | XAU预期 | 实盘建议 |
|------|:--:|:--:|------|
| VWAP反抽 | 🏆 36笔·94%·+63R | 🏆 | 趋势市主力·R:R≥2.0 |
| POC拒绝 | 🏆 34笔·76%·+2.3R | ✅ | 震荡转趋势确认 |
| VAH回收 | ✅ 21笔·57%·+1.4R | ✅ | 强趋势回调加仓 |
| VAL回收 | ⚠ 17笔·35%·+0.4R | ⚠ | 弱信号·需EMA确认 |
| EMA趋势 | ❌ 26笔·23%·-0.1R | ❓ | BTC 15m不适配·黄金待测 |
| 扫流动性回收 | ❌ 26笔·27%·-0.1R | ❓ | 参数需调·待黄金验证 |

## 数据桥格式要求

`multi_model_engine.py` 的模型函数期望**嵌套dict**结构，不是平键：

```python
# ❌ 错误（平键·模型不识别）
data = {"taker_ratio": 1.02, "price": 64000, "long_short": 1.8}

# ✅ 正确（嵌套·匹配engine期望）
data = {
    "binance_spot": {"price": 64000, "24h_change_pct": -2.5},
    "taker_futures": {"ratio": 1.02, "direction": "buy"},
    "long_short": {"top_long_pct": 64.3, "global_long_pct": 65.1},
    "oi": {"btc": 150000, "change_pct": 0.5},
    "funding_rate": 0.0001, "rate_change": 0.00005,
    "dxy": 100.0, "correlation_threshold": 0.3,
}
```

## 回测数据拉取

```bash
# Binance K线 (含taker买卖量)
https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=500

# Futures多空比
https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol=BTCUSDT&period=15m&limit=500

# Global多空比
https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=15m&limit=500

# Taker买卖比
https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=15m&limit=500

# OI历史
https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=15m&limit=500
```

## 回测诚实准则

1. VWAP反抽在单边趋势中数字虚高（31天BTC从78k→59k=做空全赢）
2. 真实滑点0.1% + 双边计入后R下降~20%
3. VAH/VAL/POC在回测中用简化估算·实盘需TradingView数据
4. 引擎模型conf<0.5不触发是正常的——只在极端条件才应触发
5. 回测覆盖≠实盘覆盖·分析卡仍应按五模型优先→引擎辅助
