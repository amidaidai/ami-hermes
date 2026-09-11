# CVD / OI / Volume Profile / VWAP / Order Block / FVG 实盘过滤共识交叉验证报告

**适用场景**：加密短线、主交易所 Binance、100x 杠杆、高风险
**现有指标栈**：估算 CVD、聚合 OI 副指标、SVP、VWAP、EMA、FVG/OB/Breaker、BOS/CHoCH
**输出语言**：中文

---

## 执行摘要

| 指标/概念 | 结论 | 置信度 | 核心依据 |
|-----------|------|--------|----------|
| **CVD (Cumulative Volume Delta)** | ✅ **保留/强化** | 高 | Bookmap/ATAS 官方文档、Reddit 实盘共识、微观结构文献均支持；关键是用 CVD Pro 过滤大单/小单、结合吸收/冰山单确认 |
| **OI (Open Interest) + 资金费率** | ✅ **保留/强化** | 高 | 永续合约特有、Reddit 共识“资金费率+OI 方向确认趋势强度”、学术文献支持永续资金费率机制 |
| **Volume Profile (SVP/VPVR)** | ✅ **保留** | 高 | Bookmap/ATAS 核心功能、Reddit 实盘公认“找 HVN/LVN/POC 做支撑阻力”、学术有实证论文 |
| **VWAP + Anchored VWAP** | ✅ **保留（作制度过滤/锚定）** | 高 | 机构算法基准、Reddit 共识“作方向过滤/回踩确认而非单边信号”、学术文献充分 |
| **Order Block (OB)** | ⚠️ **保留但严格过滤** | 中 | ICT/SMC 概念无学术实证、Reddit 两极分化严重，**必须**结合：BOS/CHoCH 结构确认 + CVD 吸收/Delta 确认 + FVG 重叠 + 高时间框架共振 |
| **Fair Value Gap (FVG)** | ⚠️ **保留但严格过滤** | 中 | 有学术论文量化定义（SSRN 论文）、Reddit 共识“FVG 优于 OB、但需流动性扫荡/结构确认”，**不可单独作为入场信号** |
| **Breaker Block / BOS / CHoCH** | ✅ **保留（结构核心）** | 高 | 纯价格行为/市场结构，非指标衍生，Reddit/书籍共识一致 |

---

## 详细证据与交叉验证

---

### 1. CVD (Cumulative Volume Delta)

#### ✅ **结论：保留并强化** —— 核心订单流确认工具

| 来源 | 关键观点 | URL |
|------|----------|-----|
| **Bookmap 官方知识库** | CVD 显示买方/卖方主动成交量累计差，核心用法：**背离确认反转、吸收确认支撑阻力** | https://bookmap.com/knowledgebase/docs/KB-Indicators-CVD |
| **Bookmap 博客** | CVD 结合热力图、冰山单检测，实盘案例：背离+吸收=高胜率 | https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy |
| **ATAS CVD Pro 文档** | **关键进阶**：支持按成交量分档过滤（大单/小单）、多市场合并 CVD、**过滤散户噪音** | https://atas.net/blog/cvd-pro/ |
| **ATAS 官网指标页** | CVD Pro 可“过滤大单追踪强势资金、过滤小单看散户情绪” | https://atas.net/features/indicators/ |
| **Reddit r/OrderFlow_Trading** | 共识：CVD 单根 K 线无意义，**波段/摆动层面看背离**、**结合吸收/冰山单** | https://www.reddit.com/r/OrderFlow_Trading/comments/1u7cet4/cvd_feels_pointless_to_me/ |
| **Reddit r/FuturesTrading** | 实盘：CVD 背离 + 价格结构 = 高胜率；单独用 CVD 信号噪音大 | https://www.reddit.com/r/FuturesTrading/comments/1enx4ve/how_is_that_the_market_moves_higher_when_the/ |
| **Beyond Candlesticks 博客** | 批判视角：CVD 解释过去不预测未来，**必须结合价格结构/吸收** | https://beyondcandlesticks.substack.com/p/why-cumulative-volume-delta-fails |
| **学术/微观结构** | Order Flow Imbalance (OFI) 文献确认：主动买卖量失衡具备短期价格预测力 (arXiv:2508.06788) | https://arxiv.org/html/2508.06788 |

#### 实盘过滤建议（针对 100x 加密短线）
| 过滤规则 | 理由 |
|----------|------|
| **仅用 CVD Pro 大单档（如 >50 USDT/笔或顶 10% 成交量）** | ATAS/Bookmap 文档明确：过滤散户噪音，看聪明钱 |
| **必须结合价格结构：BOS/CHoCH + 吸收/冰山单确认** | Reddit/Bookmap 共识：裸 CVD 背离假信号极多 |
| **时间框架：执行层 1m/5m CVD，方向层 15m/1h CVD 共振** | 多时间框架共识过滤噪音 |
| **资金费率极值时 CVD 失效降权** | 永续合约资费极端时现货/永续套利扭曲 CVD |

---

### 2. OI (Open Interest) + 资金费率

#### ✅ **结论：保留并强化** —— 永续合约特有的资金面/仓位面确认

| 来源 | 关键观点 | URL |
|------|----------|-----|
| **Reddit r/CryptoMarkets** | “忽略资金费率等于留钱在桌上”，资金费率+OI 方向确认趋势强度 | https://www.reddit.com/r/CryptoMarkets/comments/1l2pomy/why_you_need_understand_funding_rates_in_crypto/ |
| **Reddit r/algotradingcrypto** | 自建资金费率评分系统实盘验证：极值反向+OI 增加=趋势延续 | https://www.reddit.com/r/algotradingcrypto/comments/1uq5i6y/i_built_a_scored_funding_rate_signal_system_for/ |
| **SSRN 学术论文** | 永续资金费率是算法反馈规则，而非被动转移，**具备预测价格偏离方向的信息量** | https://papers.ssrn.com/sol3/Delivery.cfm/6185958.pdf |
| **Bookmap 博客** | OI 代表未平仓合约总数，OI↑+价格↑=新多头入场趋势强；OI↓+价格↑=空头平仓反弹弱 | https://bookmap.com/blog/understanding-open-interest-in-trading |
| **CME 官方教育** | OI 定义与解读标准：增仓确认趋势、减仓预警反转 | https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest |

#### 实盘过滤建议
| 过滤规则 | 理由 |
|----------|------|
| **OI 变化率 + 价格变化率四象限判断**：增仓涨/增仓跌/减仓涨/减仓跌 | 经典期货分析框架，CME/Bookmap 均推荐 |
| **资金费率 > 0.03%/8h 或 < -0.03%/8h 时降低 CVD/趋势信号权重** | 极端资费扭曲订单流，套利机器人主导 |
| **OI 突破前高 + 资金费率回正 = 趋势延续确认** | Reddit 实盘共识 + 学术机制支撑 |
| **聚合多交易所 OI（Binance/Bybit/OKX/Deribit）加权平均** | 单一交易所 OI 易被操纵，聚合更稳健 |

---

### 3. Volume Profile (SVP / VPVR / TPO)

#### ✅ **结论：保留** —— 核心支撑/阻力/价值区定位工具

| 来源 | 关键观点 | URL |
|------|----------|-----|
| **ATAS 官方文档** | Volume Profile 显示“成交量最密集价格区域”，核心要素：POC、VAH/VAL (70% Value Area)、HVN/LVN | https://help.atas.net/en/support/solutions/articles/72000602305-volume-profile-tpo |
| **ATAS 博客** | Session Volume Profile (SVP) 针对单个交易时段，**日内短线最实用** | https://atas.net/blog/session-volume-profile-how-to-set-it-up-and-use-it-in-trading/ |
| **ATAS 固定区间 VP** | Fixed Range VP 可手动锚定波段/结构，配合 Order Flow 找吸收区 | https://atas.net/blog/fixed-range-volume-profile-definition-and-trading-strategies/ |
| **Reddit r/Daytrading** | 实盘共识：VP 找 HVN 做支撑阻力、LVN 做突破目标、POC 做均值回归锚点 | https://www.reddit.com/r/Daytrading/comments/1fd1t3m/best_way_i_can_explain_how_i_use_volume_profile/ |
| **Reddit r/FuturesTrading** | 周度/月度 VP 找大级别价值区，日内 SVP 找入场精度 | https://www.reddit.com/r/FuturesTrading/comments/1sv4agi/volume_profile_usage_dilemma/ |
| **学术论文 (ResearchGate)** | 实证：Volume Profile 在股票市场具备投资决策参考价值 | https://www.researchgate.net/publication/398683237_Use_of_the_volume_profile_in_making_investment_decisions_on_the_stock_market |
| **Reddit r/algotrading** | “为什么学术界没有 Volume Profile 论文？”——实盘广泛用、学术少研究 | https://www.reddit.com/r/algotrading/comments/11bsm1s/why_are_there_no_academic_papers_on_volume_profile/ |

#### 实盘过滤建议
| 过滤规则 | 理由 |
|----------|------|
| **SVP (Session VP) 做日内执行，Fixed Range VP 做波段结构** | ATAS 官方最佳实践 |
| **VAH/VAL 作为首个止盈/止损参考，POC 作为均值回归锚点** | Reddit 实盘共识 |
| **LVN (低成交量节点) 突破配合 CVD 吸收确认 = 高胜率突破** | Order Flow + VP 组合，Bookmap/ATAS 核心教学 |
| **加密 24/7 无明确 Session：用 UTC 0:00/8:00/16:00 三个 Session VP 叠加** | 适配币圈全天候交易 |

---

### 4. VWAP + Anchored VWAP (AVWAP)

#### ✅ **结论：保留（作制度过滤/锚定，非单边信号）**

| 来源 | 关键观点 | URL |
|------|----------|-----|
| **Bookmap 知识库** | AVWAP 允许自定义锚定点（开盘、结构突破点、新闻时间），多锚定共振更强 | https://bookmap.com/knowledgebase/docs/Addons-AVWAP |
| **Bookmap 博客** | VWAP 标准差带：价格回踩 VWAP ±1σ/2σ 做均值回归，突破 ±2σ 做趋势跟随 | https://bookmap.com/learning-center/vwap-avwap-mastery/vwap-avwap-mastery-with-robert-rother/vwap-standard-deviations-statistical-edges |
| **Reddit r/TradingView** | Anchored VWAP 结合市场结构“高胜率”，但**不是万能钥匙** | https://www.reddit.com/r/TradingView/comments/1i73swq/has_anyone_here_tried_anchored_vwap/ |
| **Reddit r/Daytrading** | 共识：VWAP 作**方向过滤/回踩确认**，不作单边突破信号；“大多数人误把 VWAP 当策略” | https://www.reddit.com/r/Daytrading/comments/1psznoy/anyone_trading_mainly_with_vwap_and_how_do_you/ |
| **Reddit r/algotrading** | 实盘验证：VWAP 回踩策略回测难盈利，**改作制度过滤 + 突破动量跟随**才稳健 | https://www.reddit.com/r/algotrading/comments/1q4veut/i_spent_weeks_trying_to_make_vwap_reclaim/ |
| **学术文献** | VWAP 是机构执行基准，大量微观结构论文研究最优 VWAP 执行 (T&F, ScienceDirect, arXiv:2502.13722) | https://arxiv.org/html/2502.13722v2 |
| **Quantitative Finance 论文** | ADX 条件下的 VWAP 策略在外汇有统计显著超额收益 | https://papers.ssrn.com/sol3/Delivery.cfm/6454659.pdf |

#### 实盘过滤建议
| 过滤规则 | 理由 |
|----------|------|
| **日内 VWAP (Session VWAP) 作多/空方向偏见：价格>VWAP 只找多，<VWAP 只找空** | 机构算法基准，Reddit/Bookmap 共识 |
| **Anchored VWAP 锚点：日开/周开/月开 + 关键 BOS/CHoCH 结构点 + 重大新闻时间** | 多锚定共振区 = 高概率支撑阻力 |
| **VWAP ±1σ/2σ 带作动态止损/止盈，非入场信号** | Bookmap 统计优势教学 |
| **加密 24/7：用 UTC 0:00/8:00/16:00 三个 Session VWAP 叠加** | 适配币圈无开收盘特性 |

---

### 5. Order Block (OB) + Breaker Block

#### ⚠️ **结论：保留但严格过滤** —— 结构工具而非指标，**不可单独用**

| 来源 | 关键观点 | URL |
|------|----------|-----|
| **Reddit r/InnerCircleTraders** | ICT 核心概念：OB 必须伴随 BOS/CHoCH 结构破坏，**FVG 优先于 OB** | https://www.reddit.com/r/InnerCircleTraders/comments/1n47lde/fair_value_gaps_vs_order_block/ |
| **Reddit r/Daytrading** | 两极分化：“OB/FVG 是骗局” vs “结合结构+流动性扫荡有效” | https://www.reddit.com/r/Daytrading/comments/17mmpi3/people_say_that_fair_value_gaps_and_orderblocks/ |
| **Reddit r/Daytrading** | “FVG/OB 只是识别低流动性节点/机构意图的简化标签，**本质是价格行为**” | https://www.reddit.com/r/Daytrading/comments/1pvs1ge/fair_value_gaps_make_no_sense/ |
| **LiquidityFinder 文章** | 有效 OB 标准：1) 制造结构破坏 2) 被流动性扫荡 3) 留下未平仓订单簿痕迹 | https://liquidityfinder.com/news/anatomy-of-a-valid-order-block-in-smart-money-concepts-67221 |
| **Bookmap 实盘** | OB 区配合**吸收/冰山单/CVD 背离**确认，裸 OB 胜率极低 | https://bookmap.com/learning-center/supply-demand-setups/supply-demand-setups/gap-fill-setup |

#### 过滤规则（必须全满足才算有效 OB）
| 规则 | 说明 |
|------|------|
| **1. 结构确认**：必须伴随明确 BOS/CHoCH（高时间框架 15m/1h/4h） | ICT 核心定义，Reddit 共识 |
| **2. 流动性扫荡**：价格回测 OB 前必须扫过对侧流动性（等高/等低、止损簇） | 智能资金概念核心，Bookmap 实盘验证 |
| **3. 订单流确认**：回测时 CVD 吸收/冰山单/Delta 反向压力 | Bookmap/ATAS 核心教学，过滤假 OB |
| **4. FVG 重叠优先**：OB 内部或边缘包含 FVG，**FVG 优先级高于 OB** | ICT 明确教导，Reddit 验证 |
| **5. 高时间框架共振**：4h/日线级别同方向 OB/结构 | 过滤噪音，提高风险回报 |
| **6. 100x 杠杆下：仅做 15m+ 级别 OB，严禁 1m/5m 裸 OB 入场** | 风控红线 |

---

### 6. Fair Value Gap (FVG)

#### ⚠️ **结论：保留但严格过滤** —— 有学术定量定义，**优于 OB，但不可单独入场**

| 来源 | 关键观点 | URL |
|------|----------|-----|
| **SSRN 学术论文** | **量化定义 FVG 度量指标**，实证 FVG 具有价格反应预测力，连接技术分析与微观结构 | https://papers.ssrn.com/sol3/Delivery.cfm/6032676.pdf |
| **MKSciences 论文** | 同一文作第二版，提供 FVG 程度量化公式 | https://mkscienceset.com/articles_file/862-_article1772532938.pdf |
| **Reddit r/InnerCircleTraders** | ICT 教导：**FVG 优先于 OB**；FVG 内部形成的 OB 更强 | https://www.reddit.com/r/InnerCircleTraders/comments/1n47lde/fair_value_gaps_vs_order_block/ |
| **Reddit r/Daytrading** | “FVG 是低成交量节点/非效率的简化标识”，需结合流动性扫荡 | https://www.reddit.com/r/Daytrading/comments/1pvs1ge/fair_value_gaps_make_no_sense/ |
| **TrendSpider 学习中心** | FVG 与 OB 重叠 = 高概率设置 | https://trendspider.com/learning-center/fair-value-gap-trading-strategy/ |
| **Medium 量化文章** | 算法化 FVG 识别 + 微观结构失衡捕捉 | https://medium.com/@FMZQuant/advanced-fair-value-gap-strategy-quantitative-algorithm-for-micro-imbalance-capture-3a82e0c3332c |

#### 过滤规则（必须全满足）
| 规则 | 说明 |
|------|------|
| **1. 方向性 FVG**：多头 FVG = 第 1 根阳线高点 < 第 3 根阴线低点（反之亦然） | 标准定义，TrendSpider/学术一致 |
| **2. 未被填补/部分填补**：完全填补失效，保留 50% 以上未填补 | 价格非效率核心逻辑 |
| **3. 结构确认**：形成于强推动波（Impulse）中，伴随 BOS/CHoCH | 过滤震荡市噪音 FVG |
| **4. 流动性扫荡后回测**：价格扫过对侧流动性再回测 FVG | 智能资金流程，Reddit/Bookmap 共识 |
| **5. CVD/订单流确认**：回测时 CVD 吸收/Delta 支撑方向 | 过滤假突破 |
| **6. 高时间框架共振**：15m/1h FVG 优于 1m/5m | 100x 杠杆下低周期 FVG 噪音极大 |
| **7. FVG 内部形成 OB = 双重确认** | ICT 进阶教学，胜率最高组合 |

---

### 7. BOS / CHoCH (Break of Structure / Change of Character)

#### ✅ **结论：保留（市场结构核心，非衍生指标）**

| 依据 | 说明 |
|------|------|
| 纯价格行为/道氏理论延伸，**无参数优化空间**，不过度拟合 | 结构定义客观：更高高/更高低 vs 更低高/更低低 |
| 所有 SMC/ICT/价格行为体系共识核心 | Reddit/书籍/课程一致 |
| 配合 CVD/VP/VWAP/OI 做多因子共振 | 本报告核心框架 |

#### 实盘定义建议（量化可执行）
| 结构级别 | 定义 | 用途 |
|----------|------|------|
| **Major (4H/D)** | 前高/前低被实体突破并收盘确认 | 趋势方向、大级别 OB/FVG 锚点 |
| **Internal (15m/1H)** | 5min/15min 级别结构破坏 | 执行级别方向偏见 |
| **Minor (1m/5m)** | 1min 级别结构破坏 | 精确入场触发、止损定位 |

---

## 过度优化/应剔除/降权的项

| 项目 | 判定 | 理由 | 证据 |
|------|------|------|------|
| **裸 CVD 单根 K 线/单周期信号** | ❌ 过度优化/噪音 | Reddit 共识“单根 K CVD 无意义”、Bookmap 教学强调波段/摆动层面 | https://www.reddit.com/r/OrderFlow_Trading/comments/1u7cet4/cvd_feels_pointless_to_me/ |
| **裸 VWAP 回踩/突破单边信号** | ❌ 过度优化 | Reddit 实盘回测“几周无法盈利”、学术界定位为执行基准非信号 | https://www.reddit.com/r/algotrading/comments/1q4veut/i_spent_weeks_trying_to_make_vwap_reclaim/ |
| **裸 Order Block (无结构/流动性/订单流确认)** | ❌ 过度优化/主观 | Reddit 两极分化、“骗局”声量大、ICT 本身要求结构确认 | https://www.reddit.com/r/Daytrading/comments/17mmpi3/people_say_that_fair_value_gaps_and_orderblocks/ |
| **裸 FVG (无结构/流动性扫荡/订单流确认)** | ❌ 过度优化 | 学术论文定义了度量但未验证裸信号盈利、实盘需配合 | https://papers.ssrn.com/sol3/Delivery.cfm/6032676.pdf |
| **单一交易所 OI/资金费率** | ⚠️ 降权 | 易被操纵，**必须聚合多交易所** | Reddit algotrading 求多交易所 OI 数据源 |
| **固定参数 EMA/均线系统 (如 EMA 9/21 固定金叉死叉)** | ❌ 经典过度优化 | Reddit algotrading 共识“最简单策略最难打败”、参数固定必过拟合 | https://www.reddit.com/r/algotrading/comments/149g0lf/cannot_find_a_way_to_beat_simplest_trading/ |
| **复合指标堆叠 (如 CVD+VP+VWAP+OB+FVG+EMA 同时信号)** | ❌ 严重过度优化 | 参数组合爆炸、样本外必死、Reddit 反面教材 | https://www.reddit.com/r/algotrading/comments/17oly51/problem_with_overfitting/ |
| **无风控的高杠杆 (100x) 全仓/重仓** | ❌ 生存红线 | 数学期望必破产、Kelly 公式/风控系统强制要求 | 交易常识 + 任何风控文献 |

---

## 综合实盘过滤框架（针对 100x Binance 短线）

### 核心原则：**结构为骨、订单流为肉、仓位面为血、风控为命**

```
┌─────────────────────────────────────────────────────────────┐
│  高时间框架 (4H/D) 方向偏见                                   │
│  ├─ BOS/CHoCH 结构方向                                        │
│  ├─ Major OB/FVG 区域                                         │
│  ├─ Weekly/Monthly VP POC/VAH/VAL                            │
│  └─ 聚合 OI 趋势 + 资金费率极值                              │
└─────────────────────────────────────────────────────────────┘
                              ↓ 共振过滤
┌─────────────────────────────────────────────────────────────┐
│  中时间框架 (15m/1H) 执行区域                                 │
│  ├─ Internal BOS/CHoCH 确认方向                              │
│  ├─ Session VP (SVP) HVN/LVN/POC                             │
│  ├─ Anchored VWAP (日开/周开/结构点锚定) 多锚定共振          │
│  ├─ CVD Pro (大单档) 背离/吸收确认                           │
│  └─ 有效 OB/FVG (满足所有过滤规则)                           │
└─────────────────────────────────────────────────────────────┘
                              ↓ 精确触发
┌─────────────────────────────────────────────────────────────┐
│  低时间框架 (1m/5m) 入场触发                                  │
│  ├─ Minor BOS/CHoCH 结构破坏                                 │
│  ├─ CVD (大单) 实时吸收/Delta 翻转                           │
│  ├─ 订单流：冰山单/吸收/止损猎杀确认                         │
│  ├─ FVG 回测 50%+ 未填补 + CVD 支撑                          │
│  └─ 入场即设：止损结构位、目标 VP LVN/下一 HVN、风险回报 ≥ 1:2 │
└─────────────────────────────────────────────────────────────┘
                              ↓ 生存红线
┌─────────────────────────────────────────────────────────────┐
│  风控铁律 (100x 杠杆下不可违)                                 │
│  ├─ 单笔风险 ≤ 0.5% 账户净值 (含滑点/手续费)                 │
│  ├─ 最大回撤日/周/月熔断机制                                  │
│  ├─ 杠杆实时监控：维持保证金率 < 3% 强制减仓                │
│  ├─ 资金费率极值时自动降权/停单                               │
│  └─ 每日复盘：结构/流/仓三维度归因                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 最终建议清单

### ✅ **必须保留/强化的核心模块**
1. **CVD Pro (大单档过滤)** — 订单流核心，配合吸收/冰山单
2. **聚合 OI + 资金费率** — 永续合约特有仓位/资金面确认
3. **Session VP (SVP) + Fixed Range VP** — 价值区定位，多周期叠加
4. **VWAP + Anchored VWAP (多锚定)** — 制度过滤/动态支撑阻力
5. **BOS/CHoCH 多级结构** — 纯价格行为骨架，无参数过拟合
6. **有效 FVG (严格 7 条过滤)** — 学术有定量支持，优于 OB
7. **有效 OB (严格 6 条过滤)** — 结构确认工具，FVG 从属

### ⚠️ **保留但降权/受限使用**
- EMA/均线：仅作趋势视觉辅助，**不作信号**
- 单一交易所 OI/资金费率：仅作参考，**决策用聚合值**
- 低周期 (1m/5m) 裸 OB/FVG：**严禁入场依据**

### ❌ **彻底剔除/禁止**
- 裸 CVD 单周期信号
- 裸 VWAP 回踩/突破信号
- 裸 OB / 裸 FVG (无结构/流动性/订单流确认)
- 固定参数指标堆叠组合信号
- 无硬止损/无风控的 100x 全仓/重仓

---

## 关键参考链接汇总（按类别）

### 官方平台文档 (Bookmap/ATAS)
- CVD: https://bookmap.com/knowledgebase/docs/KB-Indicators-CVD
- CVD 策略: https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy
- CVD Pro (ATAS): https://atas.net/blog/cvd-pro/
- Volume Profile: https://help.atas.net/en/support/solutions/articles/72000602305-volume-profile-tpo
- SVP: https://atas.net/blog/session-volume-profile-how-to-set-it-up-and-use-it-in-trading/
- AVWAP: https://bookmap.com/knowledgebase/docs/Addons-AVWAP
- VWAP 标准差: https://bookmap.com/learning-center/vwap-avwap-mastery/vwap-avwap-mastery-with-robert-rother/vwap-standard-deviations-statistical-edges
- 吸收/冰山单: https://bookmap.com/blog/detecting-stop-runs-using-cvd-and-iceberg-absorption-for-strategic-trading
- Order Flow 策略: https://bookmap.com/en/content/order-flow-strategies

### Reddit 实盘共识
- CVD 讨论: https://www.reddit.com/r/OrderFlow_Trading/comments/1u7cet4/cvd_feels_pointless_to_me/
- CVD 背离: https://www.reddit.com/r/FuturesTrading/comments/1enx4ve/how_is_that_the_market_moves_higher_when_the/
- VWAP 实盘: https://www.reddit.com/r/Daytrading/comments/1psznoy/anyone_trading_mainly_with_vwap_and_how_do_you/
- VWAP 回测失败: https://www.reddit.com/r/algotrading/comments/1q4veut/i_spent_weeks_trying_to_make_vwap_reclaim/
- OB/FVG 争论: https://www.reddit.com/r/Daytrading/comments/17mmpi3/people_say_that_fair_value_gaps_and_orderblocks/
- FVG 无意义: https://www.reddit.com/r/Daytrading/comments/1pvs1ge/fair_value_gaps_make_no_sense/
- ICT FVG>OB: https://www.reddit.com/r/InnerCircleTraders/comments/1n47lde/fair_value_gaps_vs_order_block/
- OI/资金费率: https://www.reddit.com/r/CryptoMarkets/comments/1l2pomy/why_you_need_understand_funding_rates_in_crypto/
- 资金费率评分系统: https://www.reddit.com/r/algotradingcrypto/comments/1uq5i6y/i_built_a_scored_funding_rate_signal_system_for/
- VP 使用: https://www.reddit.com/r/Daytrading/comments/1fd1t3m_best_way_i_can_explain_how_i_use_volume_profile/
- 过拟合讨论: https://www.reddit.com/r/algotrading/comments/17oly51/problem_with_overfitting/
- 简单策略难打败: https://www.reddit.com/r/algotrading/comments/149g0lf/cannot_find_a_way_to_beat_simplest_trading/

### 学术/微观结构文献
- OFI 论文: https://arxiv.org/html/2508.06788
- FVG 量化论文: https://papers.ssrn.com/sol3/Delivery.cfm/6032676.pdf
- VWAP 执行: https://arxiv.org/html/2502.13722v2
- VWAP 最优执行: https://www.cis.upenn.edu/~mkearns/papers/vwap.pdf
- ADX-VWAP 策略: https://papers.ssrn.com/sol3/Delivery.cfm/6454659.pdf
- 永续资金费率机制: https://papers.ssrn.com/sol3/Delivery.cfm/6185958.pdf

### 进阶文章/教学
- CVD 失效分析: https://beyondcandlesticks.substack.com/p/why-cumulative-volume-delta-fails
- 有效 OB 解剖: https://liquidityfinder.com/news/anatomy-of-a-valid-order-block-in-smart-money-concepts-67221
- FVG 量化策略: https://medium.com/@FMZQuant/advanced-fair-value-gap-strategy-quantitative-algorithm-for-micro-imbalance-capture-3a82e0c3332c
- 多结构共振: https://medium.com/@FMZQuant/multi-structure-price-resonance-quantitative-strategy-order-block-and-fair-value-gap-convergence-853a1d8e1685

---

## 更新日志
- **2025-01-10** 初版完成，基于 Reddit/Bookmap/ATAS/学术文献交叉验证
- 后续建议：每季度复核 Reddit 实盘共识变化、新学术论文、平台新功能 (CVD Pro 多市场合并等)