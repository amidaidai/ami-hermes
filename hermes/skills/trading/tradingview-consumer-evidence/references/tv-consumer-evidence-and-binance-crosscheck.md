# TV消费层证据与Binance交叉校验

## 现场确认的陷阱

- TradingView CLI的`quote --symbol BINANCE:BTCUSDT.P`在某些版本会忽略请求参数，返回当前图表的报价。一次现场请求BTC参数却返回OANDA:XAUUSD、description=Gold、type=commodity。正确做法是先确认图表state，再调用不带symbol的quote，并严格验证返回身份。
- `chart_set_symbol`和`chart_set_timeframe`的成功回执不能代替读回。必须再调`chart_get_state`，核对symbol、resolution、studies。
- 指标切换后出现空table/空study往往是重算或后台抢图。仅在身份仍正确时做有界重试；一旦周期或品种变化，停止并标记stale。

## 证据规范

- quote同一响应保留last、O/H/L/C；日高/日低从Binance Futures 24h ticker获取，不能用15m high/low冒充。
- Pine box结果可能使用`zones`键而不是`boxes`；消费层兼容两种键。没有label的zone只能保留边界，不能分类为FVG、OB、Breaker。
- `verified`表示图表身份、周期、研究、价格栏和结构化证据可复核，不表示每个ICT子类型都存在。`partial`/`visual_only`/`unavailable`最多WAIT，identity mismatch必须NO-GO。

## Binance交叉校验

建议使用公开端点：

- `/fapi/v1/ticker/24hr?symbol=BTCUSDT`：现价、24h O/H/L、涨跌幅
- `/fapi/v1/premiumIndex?symbol=BTCUSDT`：mark、index、funding、下次费率时间

记录字段：`status`、`source`、`symbol`、`last_price`、`high`、`low`、`mark_price`、`index_price`、`funding_rate`、`tv_price_delta_pct`、`cross_status`。价格小幅差异是正常跨源微差；品种错配、数量级异常或时间窗口不一致必须降级。

## 验收

1. `python -m pytest tests/ -q`。
2. `python scripts/indicator_source_audit.py`。
3. 实时现场必须同时输出TV state、TV quote身份、Binance snapshot和最终缓存状态。
4. 检查`fresh/stale`，禁止把stale缓存当成实时授权。
5. 最终保留全屏TV截图，并确认图表仍在用户目标品种/周期。
