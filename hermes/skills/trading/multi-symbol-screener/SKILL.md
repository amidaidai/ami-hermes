---
name: multi-symbol-screener
description: TradingView 多品种扫描/筛选技能 — 批量扫描加密货币和商品的趋势状态、关键位突破、量价背离、波动率变化。结合 TradingView MCP 的 batch_run 和 OHLCV 数据，输出筛选结果表格。
category: trading
---

# Multi-Symbol Screener

> 前提：TradingView MCP 已连接可用。

## 扫描流程

### 1. 定义扫描池
```python
# 加密货币
CRYPTO_PAIRS = [
    'BINANCE:BTCUSDT', 'BINANCE:ETHUSDT', 'BINANCE:SOLUSDT',
    'BINANCE:DOGEUSDT', 'BINANCE:BNBUSDT', 'BINANCE:XRPUSDT',
    'BINANCE:ADAUSDT', 'BINANCE:AVAXUSDT', 'BINANCE:LINKUSDT',
    'BINANCE:SUIUSDT', 'BINANCE:UNIUSDT', 'BINANCE:OPUSDT'
]
# 黄金
GOLD_PAIRS = ['TVC:GOLD', 'NYMEX:GC1!', 'OANDA:XAUUSD']
# 指数
INDEX_PAIRS = ['SP:SPX', 'NASDAQ:IXIC', 'DJ:DJI']
```

### 2. 获取 OHLCV 数据

**⚠ 坑：`batch_run(action='get_ohlcv')` 不可用** — 实测对所有品种返回 `JS evaluation error`。不要依赖 batch_run 拿 K 线数据。

**可靠方案 — 逐个切换取数：**

```python
# 对每个品种执行：
mcp_tradingview_chart_set_symbol(symbol="BINANCE:BTCUSDT")
# 等待加载后检查周期（切换品种可能重置周期到日线！）
state = mcp_tradingview_chart_get_state()
if state["resolution"] != target_tf:
    mcp_tradingview_chart_set_timeframe(timeframe=target_tf)
# 然后获取数据
ohlcv = mcp_tradingview_data_get_ohlcv(count=30)  # 或 summary=True
# 在 Python 中统一计算
```

**切换品种时周期重置的修复步骤（已知 bug）：**
```
chart_set_symbol("BINANCE:SOLUSDT")
→ chart_get_state()  # 检查 resolution
→ if resolution != "15":
    chart_set_timeframe("15")
→ data_get_ohlcv(...)
```

**每次切换后必须检查并重置周期**，否则后续取数可能拿到错误周期的 K 线。

**备用数据源**（TradingView 不可用时）：
| 数据源 | 工具 | 适用场景 |
|--------|------|---------|
| Binance 原生 | `mcp_binance_get_klines()` | 纯加密品种 |
| 金十数据 | `mcp_jin10_get_kline()` | XAUUSD 等贵金属 |
| FinanceKit | `mcp_financekit_price_history()` | 美股/指数 |

### 3. 分析每品种状态（每个品种执行）
```python
def analyze_trend(ohlcv):
    """判断趋势状态：上涨/下跌/震荡/突破"""
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    atr = (high - low).rolling(14).mean()
    # 均线排列
    bullish_stack = sma20 > sma50 > sma200
    bearish_stack = sma20 < sma50 < sma200
    # 价格相对位置
    above_all = close > sma20 > sma50 > sma200
    # 波动率扩张
    atr_expansion = atr.iloc[-1] > atr.iloc[-20:].mean() * 1.3
    return {'trend': ..., 'strength': ..., 'volatility': ...}
```

### 4. 输出扫描表格
```
品种 | 周期 | 趋势 | 强度 | 关键位 | 波动率 | 动作
BTC  | 15m | ↑牛排 | 强 | 68500 | ↑扩张 | 关注
ETH  | 15m | →震荡 | 弱 | 3450  | 正常  | 等待
GOLD | 5m  | ↑牛排 | 中 | 2350  | 正常  | 可做多
```

### 5. 关键位提取
使用 `mcp_tradingview_data_get_ohlcv(summary=True)` 获取每个周期的高低点：
- 近期高点 = 阻力
- 近期低点 = 支撑
- VWAP 区域
- 前日/前周高低

## 常见扫描主题

### A. 趋势延续扫描
- 条件：20EMA > 50EMA > 200EMA（多头排列）
- 近期回踩均线未破
- ATR 适中没有过度扩张

### B. 突破扫描
- 价格突破 20 日高点
- 成交量放大
- RSI > 50 但未超买

### C. 背离扫描（配合 CVD）
- 价格创新高但 RSI 走低 → 顶背离
- 价格创新低但 RSI 走高 → 底背离
- 配合 CVD 交叉确认

### D. 波动率扫描
- ATR 较前 20 周期均值扩张 > 30%
- 布林带扩张
- 准备突破或假突破

## 注意事项
- 逐个切换品种时，每次切换后必须调用 `chart_get_state()` 检查 resolution 并重置周期（已知 bug：`chart_set_symbol` 可能把周期重置为日线）
- 品种间留 1-2s 延迟，避免 TV CDP 过载
- 扫描全量（12+品种 × 4 周期）约需 2-3 分钟
- 扫描结果只做预筛选，入场决策仍需单品种执行卡分析
- 默认仅刷新低周期（15m/5m），高周期限时继承
- 扫描结果需附带截图（full region）确认

## 自动化：Cron Job 模式

当用户需要定时自动扫描时，创建 cron job 更高效。

### 创建扫描 cron job
```python
cronjob(
    action="create",
    name="crypto-scanner",
    schedule="every 30m",
    prompt="""
使用 financekit MCP 扫描加密货币：
1. mcp_financekit_crypto_top_coins — top 10 行情
2. mcp_financekit_market_overview — 大盘情绪
3. mcp_financekit_technical_analysis — BTC/ETH 技术面
输出简洁格式的扫描结果
""",
    enabled_toolsets=["web"]
)
```

### TradingView 不可用时的降级方案

TradingView MCP 需要桌面端保持运行，cron job 环境中不可用。使用 financekit MCP 作为降级：

| 场景 | 方案 |
|------|------|
| TradingView 在线 | 逐个切换 + data_get_ohlcv（最全面） |
| 仅需价格/技术面 | financekit MCP（无需桌面） |
| 需要 Binance 数据 | binance MCP（get_price/get_klines） |

### 日报 cron job
```python
cronjob(
    action="create",
    name="daily-report",
    schedule="0 23 * * *",
    skills=["data-analysis-tools"],
    prompt="运行交易日志脚本生成复盘..."
)
```

### Cron Job 设计要点
- `enabled_toolsets` 限制工具加载 → 省 token
- `skills` 加载相关技能 → 保证能力
- 日志脚本路径用绝对路径（`D:/...`）
- 扫描频率匹配交易周期（加密 15m → 30min 一次足够）
