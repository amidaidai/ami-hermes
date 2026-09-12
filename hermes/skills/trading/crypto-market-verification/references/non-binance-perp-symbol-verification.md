# 非Binance永续品种核验：GEUSDT.P复现

## 现场结论

- 输入`BINANCE:GEUSDT.P`：TradingView图表显示“此商品不存在”；Binance REST返回`-1121 Invalid symbol`。
- 输入裸符号`GEUSDT.P`：TradingView自动解析为`BYBIT:GEUSDT.P`，15m/5m/1h/4h/D均可读取K线和指标。
- Bybit公开API可用：
  - `GET /v5/market/tickers?category=linear&symbol=GEUSDT`
  - `GET /v5/market/kline?category=linear&symbol=GEUSDT&interval=15&limit=...`
  - `GET /v5/market/funding/history?category=linear&symbol=GEUSDT`
  - `GET /v5/market/open-interest?category=linear&symbol=GEUSDT&intervalTime=15min`

## 推荐顺序

1. 先设置用户给出的原始符号，不擅自补Binance前缀。
2. 读回`chart_get_state`，确认实际symbol、交易所、周期和studies；`chart_ready:true`不替代状态读回。
3. 若自动解析为其他交易所，将该交易所写入标题和数据状态，并用其公开API交叉验证。
4. 若Binance调用失败，不重试同一无效Binance符号来制造“已验证”；状态为`unavailable`。
5. 检查交易量、盘口价差、OI覆盖和副指标覆盖。低流动性或`Coverage Exchanges=0`时只允许WAIT/NO-GO。
6. 最终截图必须来自已核验的实际交易所品种，并含价格轴和CVD/副指标窗格。

## GEUSDT现场风险特征

本次复现中Bybit `GEUSDT` 24h成交额约5.8万USDT，Funding为0，副指标显示聚合覆盖0/5并回退单图；即使TV主指标给出结构方向，也不足以生成Entry/Stop/Target。