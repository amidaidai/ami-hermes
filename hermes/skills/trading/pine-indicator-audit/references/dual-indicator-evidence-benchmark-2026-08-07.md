# 双指标官方/社区证据对标增量（2026-08-07）

适用：`SVP+ICT+VWAP+CVD` 主指标与 `AggVol/Volume Aggregated Spot & Futures` 加密副指标的研究、审计和升级。本文是证据摘要，不镜像上游全文；复用前重新访问 URL 并标访问日期。

## 1. 证据等级与冲突裁决

- **A 官方事实**：TradingView/Pine 技术文档、交易所 API 文档、同行评审或可核验学术论文。
- **B 专业平台教育材料**：Bookmap、ATAS 等，支持工作流和解释边界，不证明胜率。
- **C 社区实现**：TradingView 开源脚本，用于实现模式、降级和数据披露，不等于行业标准。
- **D 匿名论坛经验**：只能生成待回测假设。
- 同一官方主体发生冲突时：**当前技术文档/API reference > release note > 营销博客/帮助文案**。必须把冲突写进报告，不能静默择取最有利措辞。

## 2. 2026-08-07 官方硬证据

### TradingView Volume Profile / CVD / Footprint

1. 普通 Volume Profile 用 K 线内价格方向区分 up/down volume，不是逐笔 bid/ask：
   - https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/
2. 官方 CVD 用 lower-TF K 线开收方向估算正负量；更低周期精度较高但历史覆盖较少：
   - https://www.tradingview.com/support/solutions/43000725058-cumulative-volume-delta/
3. `request.footprint()` 于 2026-01 加入 Pine，Premium/Ultimate 才能运行，每脚本仅 1 个 unique call：
   - https://www.tradingview.com/pine-script-docs/release-notes/#january-2026
   - https://www.tradingview.com/pine-script-docs/writing/limitations/
4. **重要官方措辞冲突**：2026-03-02 官方博客称 footprint 可读“exact ask/bid”，但当前 Pine 技术文档与 Footprint 完整指南明确写明 buy/sell 是按 lower-TF intrabar price action 分类。审计与用户文案以技术文档为准，不宣传为交易所逐笔真 Delta：
   - https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/
   - https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/#requestfootprint
   - https://www.tradingview.com/support/solutions/43000726164-volume-footprint-charts-a-complete-guide/
5. HTF 非重绘标准仍是 expression `[1]` 与 `lookahead_on` 配套，两者不可拆：
   - https://www.tradingview.com/pine-script-docs/concepts/repainting/#repainting-requestsecurity-calls
6. Basic 当前硬边界（官方定价页 DOM，访问 2026-08-07）：2 指标/图、5K 历史K、20秒计算、0技术告警；Footprint 只在 Premium/Ultimate：
   - https://www.tradingview.com/pricing/

### OI 与爆仓

1. TradingView：OI 是尚未结算的衍生品合约总数，本身不提供方向；加密可分钟级，传统期货多为日级：
   - https://www.tradingview.com/support/solutions/43000685269-open-interest/
2. Bybit 官方明确不同合约单位不同：BTCUSD inverse OI 以 USD，BTCUSDT linear OI 以 BTC。跨所 raw OI 不能直接相加：
   - https://bybit-exchange.github.io/docs/v5/market/open-interest
3. 真爆仓流具有明确的 position side、executed size、bankruptcy price；Bybit `allLiquidation` 500ms 推送：
   - https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation
4. 因此，PERP-SPOT 量差、影线/实体、K线方向形成的“爆仓”只能是压力/强平风险代理，不能声称真实强平金额或真实事件数。

## 3. 专业与社区交叉证据

- Bookmap CVD（更新 2026-01-21）：背离要发生在前高低、VWAP、可见流动性区等已知参考位并等待价格反应；CVD 是 confluence，不是 standalone signal。
  - https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy
- Bookmap 突破清单（2025-07-08）：有效突破需主动成交穿越、流动性支持和突破后接受/延续；单纯扫位或触线不够。
  - https://bookmap.com/blog/breakout-or-fakeout-the-3-point-checklist-for-confirmation
- Bookmap “Setup ≠ Edge”（2026-07-31）：图形/指标只是 setup；edge 需要可解释的重复行为、统计优势、广泛样本和持续复核。
  - https://bookmap.com/blog/if-you-cant-explain-your-edge-you-probably-dont-have-one
- ATAS Footprint：重点看 effort vs result；大量主动成交不能推动价格才支持吸收假设，仍要价格确认。
  - https://atas.net/blog/how-to-read-footprint/
- 社区聚合 CVD（更新 2025-10-17）明确披露 lower-TF 方向法只是估算，不是交易所 tick-level delta；可借鉴 method/scope/anchor/quality 披露。
  - https://www.tradingview.com/script/CRKW4dvv-Cumulative-Volume-Delta-Candles-Aggregated-Lite/
- 社区聚合 OI 展示了按币/USD正规化的实现方向，但作者的趋势解释仍须独立回测。
  - https://www.tradingview.com/script/qiqehv0U-Open-Interest-Aggregated-Lite/

## 4. 双指标对标基准

### 主指标 `SVP+ICT`

必须承担：结构/关键位、方向、触发、Entry/Stop/Target、R:R、A/B/C/X、硬禁做。

达标条件：

- VP/VWAP 只作价值、接受/拒绝和执行基准，不宣称机构意图；
- Sweep/MSS/位移/FVG/OB 规则化、已收柱、带事件年龄；
- HTF 数据确认且不未来泄漏；
- 行动格、MCP、提醒、回放共用唯一最终价格源；
- 多空价格几何和成本后 R:R 均有效；
- CVD 输出 method/scope/anchor/quality，低质量中性退化；
- 非加密现货/CFD tick volume 不包装成真实订单流。

### 副指标 `AggVol`

必须承担：加密跨所成交量、OI、CVD、拥挤、coverage/dominance/freshness、冲突与降级。

达标条件：

- 仅适用于加密衍生品，不强套黄金/外汇/股票；
- 每所 OI 先统一单位，决策优先消费 `%change/breadth/agreement/dispersion`；
- 输出 venue count、contract type、coverage、dominance、freshness；
- 与主指标同源的估算 CVD 只计一票，另一份只用于冲突检测；
- “爆仓”若保留为直白 UI 文案，源码和 Data Window 必须标 proxy；
- 副指标只能确认/降级/否决，不能生成独立开单授权。

### 组合状态

- `GO-A`：主指标执行状态有效、已收柱、价格几何/R:R有效，且副指标数据有效并同向。
- 主副冲突、OI分歧、低覆盖或CVD质量差：最高 `GO-B/WAIT`。
- 主指标 X、硬风险、几何错误：`NO-GO`，副指标不得翻案。
- 非加密市场：忽略 AggVol，不因缺少副指标自动扣分。

## 5. 为什么多因子不等于 edge

- VP、VWAP、ICT结构和估算CVD大量共享价格/成交量输入，简单计数会重复投票。
- OI 是双方共同存在的合约数，`OI↑` 本身无多空方向。
- 因子、阈值、周期、交易所越多，研究自由度越高，越容易数据窥探。
- 没有唯一入场、失效、目标、时效、成本和风险规则时，系统只是在解释市场。
- edge 必须由消融、按时间WFO、最终不可触碰OOS和影子前向样本证明。

## 6. 研究/回测最低验收

1. 四组消融：主指标单独、副指标单独、组合、组合逐因子删除。
2. 按时间滚动 WFO；训练调参、验证选型、最终测试一次锁定，禁止回写参数。
3. purge/embargo 覆盖最大特征回看与持仓周期。
4. 使用标准K、闭柱信号和与实盘同一决策状态机。
5. 纳入手续费、滑点、资金费率、限价未成交、延迟及同K止盈止损保守顺序。
6. 分品种/周期/时段/体制报告交易数、平均R、置信区间、PF、最大回撤、DSR、PBO、参数稳定性。
7. 学术依据：
   - PBO/CSCV：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
   - Deflated Sharpe：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
   - Backtesting Protocol：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3275654

## 7. 取证工作流补充

- TradingView 静态文档可用 `curl --compressed -L` 获取，解析正文后按行核对；不要只引用搜索摘要。
- JS 定价页用浏览器读取已渲染 DOM，并检查 cross/check 图标而非只看缺失文本。
- 并行搜索要按后端速率上限分批；限流后改直达已知官方 URL，不把失败写成工具永久不可用。
- 所有无发布日期页面写“访问日期”；页面只显示“Mar 11/Jun 22”时，结合 DOM datetime、HTML meta 或版权年份核对，不能猜年份。
