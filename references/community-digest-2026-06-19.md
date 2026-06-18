# 社区精华调研 · 2026-06-19

来源：X(web) · Reddit(r/OrderFlow_Trading, r/algotrading, r/Daytrading) · GitHub(Freqtrade, NautilusTrader, 清算热力图项目) · CryptoCred(Medium)。
实跑方式：Brave API 串行（免费层不支持并发，429）。每条都标来源，可验证。

---

## 一、经多源验证的硬货（已融入骨架）

### 1. CVD 背离锚定关键位 = 反转信号（最强订单流边缘）
来源：CryptoCred《Comprehensive Guide to Crypto Futures Indicators》+ r/LearnOrderflow 吸收理论。
原文：「aggressive ramp up in perp CVD into a key level with no spot follow through (or even spot selling) → 反转」。
要点：
- 永续 CVD 猛冲进关键位、但现货 CVD 不跟（甚至反向）→ 假突破/诱多诱空 → 反转概率高。
- 吸收（absorption）：价格在关键位推进但 CVD 平掉 → 主力在对手盘吸收 → 均值回归 setup。
- **落地**：博弈段新增「CVD背离」判定行——perp 方向 vs 现货/价格方向不一致时标记⚠。

### 2. 订单流只有锚定结构才有效（降噪铁律）
来源：r/OrderFlow_Trading「Orderflow strategies」+ r/Daytrading「Orderflow day 3」高赞。
原文：「useful signal usually appears only when liquidity behavior is anchored to structure. Logging absorption, sweep, reaction at the same type of level builds pattern recognition faster than chasing every print」。
要点：
- 孤立的 CVD/Taker/挂单墙信号是噪音。只有发生在 VWAP/POC/VAL/VAH/流动性位才计入。
- 三种结构锚定事件值得记录：吸收（absorption）、扫单（sweep）、反应（reaction）。
- **落地**：操作段确认条件强制「订单流信号须发生在关键位」；博弈段订单流行注明锚定位。

### 3. 回测过拟合三大体检（López de Prado + r/algotrading 共识）
来源：r/algotrading「A real professional backtest is walk-forward」「Backtesting: Methods To Avoid Overfitting」多帖。
要点：
- **盈利运行交易数更少 = 过拟合**：若高盈利的 walk-forward 窗口恰好交易笔数少，是运气不是边缘。
- **Deflated Sharpe Ratio**（López de Prado）：对多次试错做惩罚，剔除「试了40次挑出最好的」假象。
- **锚定 walk-forward**：固定 18 个月 in-sample + 滚动 out-of-sample，禁止每2周重优化（必过拟合近期噪音）。
- **落地**：regime_backtest 增加过拟合体检——样本量与期望值反向关联告警。

### 4. 清算磁吸位 = OI增量 × 价格增量 符号组合（4象限）
来源：GitHub minchillo4/btc-liquidation-heatmap + BitcoinCounterFlow。
要点：
- 按 OI delta 和 price delta 的符号组合，把杠杆持仓分类：净多/净空/多头平仓/空头平仓。
- 亮带 = 未平杠杆 OI 集中处 = 潜在清算级联磁吸位。
- Coinglass 清算热力需付费 key；用 Binance depth 挂单墙 + OI 增量方向做免费替代。
- **落地**：depth_wall 增加 OI/价格增量体制标注，墙标「磁吸/防守」属性。

---

## 二、已具备能力（社区验证我们做对了）

- **风险 0.5–1%/笔、日损≤3%、止损后冷却**：risk_constitution 已实现（保守模式2%日损、15分冷却、连亏3停）。
- **波动率目标仓位**（高波动减仓）：volatility_target_multiplier 已实现。
- **完整K线/防未来函数/真实建模**（手续费滑点）：模板社区硬规则①②③ + 回测引擎已实现。
- **挂单墙磁吸位**：depth_wall 已接入环境④。
- **VWAP 是机构执行锚**（XAU）：M_VWAP磁吸模型已实现。
- **Freqtrade protections（条件暂停）**：风控闸门 + 熔断已实现。

---

## 三、暂不采纳（成本/适配不划算）

- **付费订单流终端**（Bookmap/ATAS/TradingLite $70/mo）：免费 Binance depth + CVD 已覆盖主要场景。
- **NautilusTrader 纳秒级 LOB 回测**：需自带 L2 逐笔数据，本金100阶段过重。
- **多交易所聚合热力**（flowsurface）：当前只监控 BTC/XAU，单所够用。

---

## 四、骨架落地清单（本次执行）

1. ✅ 模板头部加时间戳行 `◷ {date} CST`
2. 博弈段新增「CVD背离」判定（perp vs 现货/价格不一致 → ⚠反转预警）
3. 博弈段订单流行强制注明「锚定结构位」（孤立信号不计）
4. 操作段确认条件加入「订单流信号须在关键位发生」
5. regime_backtest 增加过拟合体检（盈利-交易数反向关联告警）
6. depth_wall 增加 OI/价格增量体制标注（磁吸/防守）
7. 模板社区硬规则新增第⑧⑨条（CVD背离锚定 + 回测过拟合体检）
