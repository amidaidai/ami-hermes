# 交易分析 API 数据源契约

用于审计多源交易系统中“接口都能调用，但价格、K线、OI来自不同市场口径”的隐蔽错误。

## 1. 执行市场口径必须一致

若执行标的是 Binance U 本位永续（如 `BTCUSDT`）：

- 主价格：Binance Futures ticker/mark price。
- 主 K 线：`/fapi/v1/klines`。
- 衍生品：OI、Funding、Taker、LSR 同属 Futures。
- TradingView：使用对应永续品种（如 `BINANCE:BTCUSDT.P`）。
- 现货、CMC、CoinGecko：只作基差/现货交叉验证或故障备用，不得静默成为合约执行主价格。

常见错误：使用 Futures OI/Funding，却把 `/api/v3/klines` 现货 K 线送入同一结构引擎。HTTP 全部成功，但语义已经错位。

## 2. 推荐优先级

### 合约执行价格

1. Binance Futures public endpoint
2. 标明来源的 Binance Futures 聚合/镜像源
3. TradingView 永续报价
4. 现货源仅作参考，不得伪装成 Futures

### 合约 K 线

1. Binance Futures `/fapi/v1/klines`
2. TradingView 永续 OHLCV
3. 明确标记的期货聚合源

## 3. 标准数据状态

每个源至少返回：

```json
{
  "status": "available|stale|timeout|invalid|missing|not_applicable",
  "source": "binance_futures",
  "symbol": "BTCUSDT",
  "market": "usd_m_perpetual",
  "timestamp": 0,
  "age_sec": 0,
  "quality": "A|B|C",
  "data": {},
  "error": null
}
```

不得用空字典、`None` 或 `except: pass` 抹平 timeout、invalid 和 not_applicable 的差异。

## 4. 语义校验

HTTP 200 后继续验证：

- symbol 与请求标的一致；
- market 与执行市场一致；
- 时间戳和闭柱状态符合要求；
- 价格数量级与实时基准合理；
- OI、Funding、LSR、Taker 的单位明确；
- 数组非空，关键字段非零；
- 派生字段合理，例如 Max Pain 相对现价极端偏离时标 `invalid`，不进入裁决。

## 5. 多源职责

- 实时裁决：TradingView + 执行交易所实时衍生品。
- 辅助验证：CoinGecko/CMC、Depth、相关性。
- 低频背景：Dune、Deribit、COT、宏观、情绪。
- 故障回退：必须保留来源和质量等级，不得把 B/C 级备用源写成 A 级主源。

## 6. 验收

- 合约分析中不存在 Spot K线 + Futures OI 的混合快照。
- 主价格来源可审计，备用源不会静默接管。
- 数据过期由读取端按 timestamp/mtime 重算，不只相信写入端 `fresh=true`。
- invalid/stale/timeout 会传到最终闸门并触发降级或阻断。
- 回归测试覆盖主源成功、主源失败后备用、跨市场混用阻断和异常值隔离。