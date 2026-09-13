# 已评估平台档案

每个平台一节：定位 / 实测对账 / 能补的空白 / 门卡 / 风险 / 结论。新平台按末尾模板追加，**不要为单个平台另建文件**。

## OpenMarket（openmarket.xyz，原 kiyotaka.ai）

- **定位**：专业级加密订单流终端，中文原生界面；聚合 6 家场所（Binance.f / OKX / Bybit / Deribit / Hyperliquid / Polymarket）。卖点 = 聚合订单簿热图（单一/聚合可切、含 HL 清算与 TP/SL 图层）、Footprint、TPO/Market Profile、分交易所 CVD、清算热图、Deribit 期权 12 指标（GEX profile/heatmap/curve、max pain、call/put wall、gamma flip、IV smile、期限结构、vol matrix、implied move、options flow）、kScript 指标语言 + IDE、K 线回放、多图工作台（16 图）。变现 = PLUS 订阅 + 推荐制（kScreener Tier 1-5 递增标的数/刷新频率/列数；Tier 2 解锁 1 秒 K 线与 4K 热图）。
- **实测对账（BTCUSDT 永续 vs Binance fapi）**：最新价差约 10 美元（快照延迟）；OI 美元值完全一致（openInterest × markPrice）；资金费率一致（换算小数位后）；24h 最低价一分不差；24h 最高价偏高（滚动窗内早期极值未滚出）；24h 成交额偏差约 1.3%。**结论：单交易所口径准确，可当证据。**
- **能补的空白**：① 分交易所 / 聚合订单簿热图与 CVD（我们只有 TV 副图 + Binance 单所 CVD）② 期权 GEX / IV 整层（我们完全空白）③ 清算与 TP/SL 挂单热图 ④ 官方聚合数据 API。
- **门卡（决定结论的那条）**：官方 FAQ 明确「Data API not open to new subscriptions right now」—— 老订阅继续可用，新订阅关闭。现阶段**接不进管线，只能人眼看图**。已记档的数据类型：`TRADE_AGG`（分买卖方向 K 线）、`TRADE_SIDE_AGNOSTIC_AGG`、`OPEN_INTEREST_AGG`、`FUNDING_RATE_AGG`、`LIQUIDATION_AGG`、`VOLUME_PROFILE_AGG`、`TPO_AGG`、`BLOCK_BOOK_SNAPSHOT_AGG`、`HYPERLIQUID_LIQUIDATION_AGG`、`HYPERLIQUID_TRIGGER_LIQUIDITY_AGG`（Advanced+）、`IMPLIED_VOLATILITY_OPTION_SUMMARY_AGG`、`SKEW_OPTION_SUMMARY_AGG`。等它重开订阅再评估接入。
- **风险**：跑 kScript 不跑 Pine → SVP 主指标与执行授权搬不过去；执行端宣称跨所路由且「成交可撤销」，属第三方托管/代理语义，不用；无头浏览器只拿到移动外壳（容器 class `app-container--mobile`，图表 canvas 在视口外 `x=1920`），桌面工作台需真实浏览器。
- **结论**：注册免费号，当订单流 + 期权交叉验证的副战场；重点用分所 CVD 背离、清算簇、Deribit GEX 磁吸位；主战场仍是 TradingView + SVP；不接它的下单通道。

## 模板（新平台照此追加）

- **定位**：
- **实测对账**：（项目 | 平台 | 官方）逐项写，末尾给一句结论
- **能补的空白**：
- **门卡**：
- **风险**：
- **结论**：
