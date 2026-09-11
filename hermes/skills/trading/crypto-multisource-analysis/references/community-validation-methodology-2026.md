# 2026 社区分析方法论共识（多市场验证 / 支撑确认 / 跨市场仲裁）

> 2026-06-28 联网审计产出，17+权威源（Bookmap/ATAS/ITI/Tradeciety/CoinGlass/ICT-SMC 2026/r/FuturesTrading）。
> 用于回答"我多市场分析怎么验证、怎么确认有支撑、怎么避免假信号"。与 pine-indicator-audit 的 community-optimization-checklist-2026.md 互补：那个聚焦指标面板，本文件聚焦分析决策方法论。

## 一、多周期共振验证（入场前必走）

**自上而下三层（铁律，永远不从下往上）**：
- Layer 1 方向 = D/W：只定方向（EMA斜率+结构BOS/CHoCH+CVD趋势）
- Layer 2 区域 = 4h/1h：定 POI（OB/FVG/流动性池）+ 溢价折价
- Layer 3 触发 = 15m/5m：CHoCH/MSS + CVD确认 + displacement入场
- **HTF 永远压制 LTF**。周期比例 4-6 倍最理想（5m→15m→1h→4h→D）。

**共振计数（6 因子，社区标准）**：
1. HTF方向一致(D+4h同向) 2. 价在HTF关键位 3. CVD配合 4. LTF结构转变 5. VWAP溢价/折价有利 6. 量能/Delta确认。
- **≥4/6 入场 · 5/6 高概率 · 6/6 满仓 · ≤3 不做**。

**相邻周期冲突 = 不交易（最高优先级，棠溪系统当前缺此硬门）**：
```
D多·4h多·1h多 → ✅满仓    D多·4h多·1h空 → ⚠️等1h转向
D多·4h空      → ❌不交易   D空·4h空·1h空 → ✅满仓做空
```
这是"覆盖"(挑方向硬给)与"叫停"(打周期冲突·观望)的区别。社区要叫停，不要硬给。

## 二、支撑/阻力真实性确认（区分真支撑 vs 假反弹）

**确认一个价位真有支撑，需 ≥4/6**：
1. 价格触结构位(HVN/POC/前低) 2. CVD看涨背离(价更低低点+CVD更高低点) 3. 成交量放大(>3×均量) 4. **OI增加+价格企稳=新多进场**(非空头回补) 5. 吸收(大单被动接、aggressive卖单被消化、价不跌) 6. 扫单后快速收回并站稳。

**假反弹特征**：CVD无背离 · LVN空气口袋反弹 · **OI减少+价格反弹=空头回补(将衰竭)** · 无吸收 · 重测即破。

**ITI铁律**：单次影线刺穿不算扫线确认。"Wicks show movement, they do not prove rejection." 必须收盘回线内 + 重测守住（棠溪主指标 closeReclaim 已实现）。

**OI 真假突破口径**：价↑+OI↑=真多 · 价↑+OI↓=空头回补(弱) · 高量+OI↓=平仓潮(可能反转)。

**Volume Profile 接受/拒绝**：价格在区域持续双向交易+tape放缓=接受(强支撑)；快速穿过少成交=拒绝(弱)。裸POC(nPOC)刺入即弹=昨日公平价仍有效(强反转)。

## 三、跨市场 / 多源仲裁（怎么验证、冲突怎么裁）

**跨市场领先/滞后链（crypto+gold 2026）**：
DXY/US10Y/VIX(领先1-7天) → SPX/XAU(领先0-3天) → BTC/ETH(同步/滞后0-1天)。
- DXY↔BTC -0.65~-0.75(DXY领先2-5天) · US10Y↔BTC -0.55~-0.70 · VIX↔BTC -0.50~-0.65 · SPX↔BTC +0.60~+0.75 · XAU↔BTC +0.40~+0.55(黄金略领先)。
- 规则：VIX>30→BTC 7日回调概率>65% · US10Y实际利率>4.5%→加密承压 · SPX<4500→去相关性增加。

**源优先级权重层级（冲突仲裁）**：结构性35%(Funding/OI/顶级交易员仓位) > 聪明钱30%(Smart Money多空/Taker/鲸鱼) > 宏观25%(DXY+US10Y/VIX/SPX) > 情绪10%(F&G/散户多空比，仅极值有效) > 事件5%(Polymarket/金十)。
- **冲突 ≠ 谁错，而是时间框架分歧**：短期看空+中期看多=逢低买。输出"矛盾点→主倾向→等待条件→失效"。

**反向极值阈值（具体数字）**：
- Funding：>+0.10%(8h)=多头极拥挤→准备做空 · <-0.10%=空头极拥挤→准备做多。
- 散户账户多空比：>2.5=顶部临近(反向卖) · <0.6=恐慌底(反向买)。
- F&G：<15=强买入(历史准确>70%) · >85=强卖出。仅极值有信号价值。
- **≥3 个独立源同向极值才行动**。

## 来源
Tradeciety/Bookmap(MTF order flow)、ITI(liquidity sweep/volume profile acceptance)、ATAS(footprint/heatmap)、FXNX/ZitaPlus(CVD divergence)、CoinGlass(funding/LS/smart money)、Medium SMC Top30 2026、r/FuturesTrading、r/Daytrading、Quantified Strategies(MTF回测73%胜率/PF2.0)。
