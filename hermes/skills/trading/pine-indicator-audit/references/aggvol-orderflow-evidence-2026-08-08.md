# AggVol 聚合量 / OI / CVD / LSR / 爆仓证据增量（2026-08-08）

适用：五所成交量（Binance / Bybit / OKX / Coinbase / Bitget）+ 四所 OI 的 AggVol/HALDRO 副指标，以及它与 SVP 主指标的协作。只讨论指标数据语义、质量门控和架构边界；不做回测、复盘或盈利主张。

证据等级：A=官方技术/API事实，B=专业订单流平台教学，C=开放源码实现。官方页无发布日期时写访问日期。

## 一、官方增量事实

### OI 不能 raw sum

- TradingView 明确：加密单所 OI 可能以基础币、报价币或合约数呈现；OI 本身无方向。
  - https://www.tradingview.com/support/solutions/43000685269-open-interest/
  - https://www.tradingview.com/support/solutions/43000762388-understanding-crypto-open-interest/
- Bybit 当前 OI API 同时返回：`openInterest`=多空两侧之和，`singleOpenInterest`=单侧；inverse BTCUSD 单位 USD，linear BTCUSDT 单位 BTC；极端波动可能延迟。
  - https://bybit-exchange.github.io/docs/v5/market/open-interest
- Binance 历史 OI 同时提供 `sumOpenInterest` 与 `sumOpenInterestValue`；最细5m。
  - https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics
- OKX 同时提供 `oi`（contracts）、`oiCcy`（coin）、`oiUsd`（USD）及时间戳。
  - https://www.okx.com/docs-v5/en/#public-data-rest-api-get-open-interest
- Bitget `size` 为具体基础币数量并带数据时间戳。
  - https://www.bitget.com/api-doc/classic/contract/market/Get-Open-Interest

**审计结论**：跨所 raw OI 总和不得参与正式方向或强弱裁决。每所先算同周期变化率，再消费 breadth / agreement / dispersion；raw total 只能展示。Bybit 的双侧/单侧口径差异进一步证明变化率比 raw sum 更稳健。

### OI 四象限必须全链一致

OI 是双方共同存在的未结算合约，不自带多空方向。正式解释：

- 价涨 + OI涨 = 扩仓上涨（多方占优的价格语境，不等于能识别“真新多”）；
- 价跌 + OI涨 = 扩仓下跌 / 新空扩张；
- 价涨 + OI跌 = 减仓上涨 / 空头回补；
- 价跌 + OI跌 = 减仓下跌 / 多头平仓或去杠杆。

常见 P1：行动格写“新空”，`oiDiverge`却把价跌+OI涨当背离扣分；Confirm、Composite、风险码和提醒各用一套语义。四象限必须由同一个状态变量供所有消费者使用。

### LSR 只是账户数比

- TradingView：Long/Short Ratio Accounts 是净多账户数 / 净空账户数，不是成交量或名义仓位；当前覆盖 Binance、Bybit。
  - https://www.tradingview.com/support/solutions/43000762399-long-short-ratio-accounts/
- Bybit 给出同样公式，周期最细5m，并披露极端波动时可能延迟。
  - https://bybit-exchange.github.io/docs/v5/market/long-short-ratio
- Binance 的 global account、top account、top position、taker buy/sell 是不同指标，不得混算。
  - https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Long-Short-Ratio

**落地**：LSR 只作同向拥挤降级。若增加 Bybit，分别对 `log(LSR)` 做自身标准化后看是否同向拥挤，不直接平均 raw ratio；缺失不自动得分。

### 成交量单位必须逐源正规化

- Pine `syminfo.volumetype` 仅有 `base / quote / tick / n/a`；期货 volume 还可能是 contracts。
  - https://www.tradingview.com/pine-script-docs/concepts/chart-information/
- Bybit：linear volume=base、turnover=quote；inverse volume=quote、turnover=base。
  - https://bybit-exchange.github.io/docs/v5/market/kline
- OKX：衍生品 `vol`=contracts、`volCcy`=base、`volCcyQuote`=quote；现货 `vol`=base。
  - https://www.okx.com/docs-v5/en/
- Bitget Kline 同时给 base volume 与 quote turnover。
  - https://www.bitget.com/api-doc/classic/contract/market/Get-Candle-Data
- Coinbase product volume 为 base currency；其 trade `side` 是 maker side，外部 taker CVD 必须反向解释。
  - https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-stats
  - https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades

**落地**：每个远端请求 tuple 同时取本所 `volume + close + source time`；base量乘本所close，quote量直接用。`tick/n/a`或未知合约乘数标单位未知，不得伪装USD。禁止先合并base volume再统一乘图表close。

### CVD 仍是估算；副CVD不是第二票

TradingView官方CVD按 lower-TF intrabar价格方向分类成交量，是估算买卖压力；越细越精确但历史越短：
https://www.tradingview.com/support/solutions/43000725058-cumulative-volume-delta/

开放源码聚合CVD也明确披露 lower-TF估算并非交易所tick delta：
https://www.tradingview.com/script/CRKW4dvv-Cumulative-Volume-Delta-Candles-Aggregated-Lite/ （更新 2025-10-17）

**落地**：主指标 lower-TF CVD 是关键位执行背景；AggVol CVD 改为跨所流向宽度/分歧，不再作为独立同源票。CVD quality code 编码 method / venues / unit quality / freshness / anchor / confirmed；背离是事件码，不是质量码。

### 真爆仓与代理必须分层

- TradingView 已有聚合/单所 liquidation fundamentals，覆盖 Binance、Bybit、Deribit、HTX、OKX；单位仍可能是base或quote。
  - https://www.tradingview.com/support/solutions/43000762400-liquidation-data-what-to-watch-and-why-it-matters/
- Bybit `allLiquidation` 500ms推送所有事件，给position side、executed size、bankruptcy price。
  - https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation
- Bitget WS 每秒只保留每交易对多/空方向各自最大一条；历史仅近3天且可能延迟。
  - https://www.bitget.com/api-doc/uta/websocket/public/Liquidation-Channel
  - https://www.bitget.com/api-doc/uta/public/Get-Liquidations
- OKX 明确 liquidation channel 不代表总爆仓数，且来源可能乱序。
  - https://www.okx.com/docs-v5/en/#public-data-websocket-liquidation-orders-channel
- Binance forceOrder 每交易对每1000ms只推最新一笔快照。
  - https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Liquidation-Order-Streams

**Pine代理最低门**：跨所OI一致下降 + 永续量/宽度尖峰 + 同向价格位移 + 同向估算CVD。OI上涨必须归扩仓，不能叫爆仓。界面可保留直白“空头爆仓偏强/多头爆仓偏强”，但 tooltip / method code 明示 PROXY。

## 二、专业订单流边界

- Bookmap CVD：背离应发生在前高低、VWAP或可见流动性位，等 failure-to-continue 与CVD转向；不是 standalone signal。
  - https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy （更新 2026-01-21）
- ATAS absorption：高主动量但价格无进展（effort vs result），理想位置在支撑/阻力；需Bid×Ask/逐笔确认。
  - https://atas.net/blog/how-to-read-footprint/ （修改 2026-06-10）
  - https://atas.net/blog/absorption-of-demand-and-supply-in-the-footprint-chart/ （修改 2025-12-09）

Pine只能做“吸收代理”：高估算Delta + 低价格效率 + 关键位收回。DOM挂单重载、冰山、真实被动吸收必须外部订单簿/逐笔。

## 三、AggVol 必查签名

1. `oiAgg = sum(raw OI)` 是否驱动方向或评分；若是，P1。
2. `priceDn + oiUp` 是否被`oiDiverge`扣分；若是，P1四象限冲突。
3. Coverage 是否用 `volume > 0` 同时代表feed存在与有成交；若是，拆开。
4. `barssince(not na(value))`或前向填充是否被称为freshness；若是，改source time/gaps代理。
5. `PERP-SPOT`差额+蜡烛颜色是否直接命名真实爆仓；若是，改OI下降硬门+PROXY方法码。
6. CVD是否用图表蜡烛方向给全部venue统一分配；若是，至少改为各venue自身OHLC方向宽度。
7. CVD quality code是否编码“出现背离”；事件与质量必须分开。
8. `strong / confirmScore / conclusion / Composite / alerts`是否各自判断；统一到唯一`finalAggState`。
9. `ACT_LB*6`是否冒充HTF；这只是同周期长回看，应用主指标真实HTF。
10. 交易所槽位是否可重复导致双计；Spot/Perp覆盖分母是否按预期路由而非固定5。

## 四、主副协作

Pine官方 `input.source()` 能把另一脚本的plot作为输入：
https://www.tradingview.com/pine-script-docs/concepts/inputs/#source-input

推荐主指标导出一个小范围整数Context Pack（side / EntryValid / real HTF / trigger age / key-level proximity）；AggVol手工绑定并裁决：

- 主X → NO-GO，副指标不得翻案；
- 主WAIT + 副同向 → “订单流就绪，等主触发”；
- 主可执行 + 副同向且数据健康 → 联合确认；
- 主可执行 + 副冲突/过期/OI分歧 → 降级或WAIT；
- 非加密 → 忽略AggVol，不扣分。

`input.source`需用户手工选择，不能按脚本名自动读取。无需手工的全自动协作、真实taker CVD、真实爆仓、毫秒级freshness与DOM吸收归外部Python/WebSocket验证器。

## 五、配额与交付

- 保留五所成交量与四所OI；不以削源作为这些增强的前提。
- 同一symbol/timeframe请求用tuple扩充OHLC/volume/time，通常不增加unique context。
- 新机器字段优先打包，避免为每项新增Data Window plot。
- Pine v6配额按运行时unique request context审计；分别报告默认与最坏可达配置，并以TradingView编译/运行回执验收。
