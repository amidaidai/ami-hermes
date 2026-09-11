# 双指标社区对标审计（20260813 联网实测数据）

来源：本次会话联网搜索 + TradingView 页面直读（20260813）。用于回答"这两个指标在社区算什么水平/该不该继续用/怎么改"。

## 社区原型链（AggVol 副指标血统）

| 版本 | 出处 | 覆盖 | 热度（直读页面） | 备注 |
|---|---|---|---|---|
| HALDRO 原版 | tradingview.com/u/HALDRO（Volume Aggregated Spot & Futures） | 9 所 | 多语言转载，社区事实标准 | 棠溪版直接改自它 |
| plyst 增强版 | script/Mdwp2lQs | 10 所 + Spot/Perp Delta + L/S Ratio + whale 过滤 + SUM~VARIANCE | **317 boosts / 7250 views / 6 评论**（同主题最热） | 修正 MFI（自定义公式偏离标准→ta.mfi）、NA 处理、.P 命名 |
| tjyukz93 clean-room | script/d9145lGp | 10 所 19 request，纯 SUM，极简 | 7 boosts / 381 views | 自述"简单与透明优先"，无决策层 |

结论：**聚合成交量方向被社区验证**；棠溪版=5 所 + 4 所 OI 归一化 + LSR + 基差 + 行动格 + 状态总线，是同类中的"决策超集"（覆盖少 5 所，决策层社区无竞品）。扩所与否是用户拍板项（当前 29/40 静态 request，余量 11），不要静默改。

## 估算 CVD/Delta 的社区共识（方法学护栏清单）

- r/Daytrading（1kmalg2）："TV 的 delta 只是 poor man's estimate，远非真实 delta，CVD 同理"——社区主流共识。
- r/FuturesTrading（1miv4t7）：部分实盘用户称 delta/CVD "无用、真伪信号随机分布"——**背离只宜作 confluence，不宜独立触发**。
- r/TradingView：TV 原生 CVD 数值被质疑不稳定（周线重算变化）。
- LuxAlgo / LunqFX 同款指标：公开声明"volume delta 是价格与成交量的透明估算，非交易所审计的 bid/ask 订单流"。
- 棠溪代码已对齐护栏（审计通过项）：①非加密门控 isCryptoPlot（XAU/外汇不估算）②metalSpot CVD 权重归零+文本"现货无逐笔" ③背离需近关键位（FILTER_CVD_DIVERGENCE_BY_KEY_LEVEL / cvdNearKey / 副指标 B1）④低样本标记"（样本少）"⑤USE_CVD_HARD_GATE 默认关（估算数据不当硬闸门）——**比社区多数版本诚实**，保持。

## OI 跨所聚合

TV 各所 _OI 单位不可比（张数/币量混报）——棠溪"四所分别算 % 变化后等权合成 + 一致率/离散度"是社区一致的正确做法（直接求和是错的）。社区 OI 类指标（如 2gEg2LTp）均按 % 口径。

## CE10116 社区面

Pine 社区已知限制（Reddit r/pinescript 有 5000 行脚本被 550 scopes 限制拦截的案例；本指标系是 CE10116 260→254 的深度实战）。终解（删 UDF 包装内联 islast）已落地于 20260810_回踩位路径_CE10116 版 L3023-3027。若再报：第一嫌疑 f_panel_checks（TV 口径≈扫描×5，粗估 250 上下），拆法见 pine-20260810-ce10116-refactor.md。

## 指标超载共识

社区（r/Daytrading/Facebook 交易组）反复出现"指标过多=失败主因、价格行为+少数可靠工具"——功能冻结（20260810 拍板）方向正确，不加新模块。

## 20260813 上传版静态基线（供后续 diff）

- AggVol_v2_20260810_非加密短路.pine：732 行 / 47 input / 29 静态 request（20 聚合+4 OI+1 LSR+1 现货+1 单源+1 汇率+1 HTF）/ 41 plot（21 data_window）/ 1 alert() / 12 函数 / max_bars_back=2000
- SVP_ICT_v2_20260810_回踩位路径_CE10116.pine：3218 行 207KB / 194 input + 41 const / 8 request（6 security + 2 security_lower_tf）/ 43 plot（29 data_window）/ 1 alert() / 56 函数 + 10 method / 8 UDT / 上限声明 3500/500/500/100/120
- SVP 脚本级 input+const=235 < 254（CE10116 已解）；AggVol 29/40 request、41/64 plot 余量充足

## 遗留微瑕疵（不阻塞，可选清理）

1. AggVol calctype input 只剩 SUM 一个选项=死参数（转 const 0 功能损失）
2. AggVol haldroContractPackA=22000 硬编码无注释
3. AggVol RUB 汇率复合 ticker（MOEX 括号表达式）无实际使用场景
4. SVP 5m 图+D 分布图+1m 精度是最大负荷组合（有 AUTO_DEGRADE_PRECISION 兜底；偶发超时先关 SHOW_PROFILE_HIST 或减 NUM_ROWS）

## 20260813 四平台扩展审计（X/GitHub/Reddit/TV）

### GitHub 对标（最值得借鉴的三个仓库）
- **SoCloseSociety/TradeBobbyTerminal**：ICT/SMC 宏观交易终端，15+ 免费数据源合成单一决策级仪表盘 + 多因子汇合评分 + 1900 行 Pine V6。明确"不执行交易、纯决策支持"——与棠溪产品边界（主指标唯一决策源、不自动下单）完全一致。CVD divergence 仅作 confluence lens 的证据源（bed5b8b，已内嵌 20260808 共振票铁律）。
- **VolodymyrFilias/feels-indicators**（FeelsStrategy，TV 数千用户）——三个单职责指标，全部是棠溪系统的可借鉴对象：
  1. **Liquidity Magnet**（547 行）：流动性池评分 = Strength×1.0 + Proximity×1.2 + AgeDecay×0.6 + Momentum×0.9（权重 input 可调）；状态机 pending→touched→expired；**追踪窗口 100 根 K 记录命中/过期 → 自验证命中率**。对比棠溪磁吸（分NN★HTF 距离A，权重硬编码 0.4/0.3/0.3/+20，nPOC=85-距离×15）：评分粒度更细（我们有 HTF/距离），但缺"历史命中追踪"——磁吸增强第一候选。
  2. **Air Pocket Profile**（621 行）：空口袋 = 成交量 < 峰值 18%（可调）的区间，穿过时打勾确认（transit mark）——薄量区自验证。棠溪有薄量资产降级（$10M 门槛）但图上无薄量区标注——增强第二候选（复用 profileEngine 行数据，0 request）。
  3. **Power of Three**（401 行）：D 周期 Accumulation(25%)→Manipulation(扫前周期H/L)→Distribution；**statsLookback 60 个已解决周期统计历史频率，投影路径（扫极值→cycle open→对侧边）标注"过去60周期X%走这路"**——棠溪行动格路径无历史频率背书——增强第三候选（远期，需统计引擎）。
- everget/tradingview-pinescript-indicators（873★）：经典指标集合，无订单流决策层，仅作工程参考。
- **NoveltyTrade "Crypto OI Agregated"**（r/TradingView 发布 + TV 1z6RXBA9）：多所 OI 聚合**归一化**——与棠溪"四所%变化等权合成"做法社区一致 ✓ 无需改。

### X 平台（x_search 无额度，web 兜底）
- LunqFX（_LunqFX）：CVD/Volume Delta/吸收/背离指标作者，X 活跃——同款指标公开承认是 OHLC 估算（LuxAlgo 博客同源）。
- TrenVantage：$8 付费 CVD 指标（社区付费价格锚：同类估算指标商业价值低）。
- TradeQM："Order flow supplied the trigger. The stop ladder managed what the market proved."——订单流是触发不是装饰，与棠溪"主指标唯一执行源+风控闸门"哲学互证。

### Reddit
- r/InnerCircleTraders：FVG 指标需求旺盛（"best indicator to see FVGs"、930 FVG 指标：首根 FVG 高亮等回补——棠溪 FVG+CE 回补逻辑同思路）；"ICT 学习者最大问题是把概念当指标用"——行动格"触发链"设计正确。
- r/OrderFlow_Trading：真 footprint 需 TV Pro + CME 数据（$67）——估算 CVD 的定位（confluence）正确，不追真订单流（配额/成本）。
- r/TradingView：社区反复吐槽 TV 缺 OI/funding/liquidation 原生数据——自研 OI 聚合方向被验证。

### 增强推荐（按 ROI 排序，均 0 request）
1. ~~磁吸历史命中率~~ **已实施并回滚（20260813 v4）**——用户"看不懂"要求删除，全套统计代码移除。教训：FEELS 的命中追踪放 Dashboard（独立开关、按方向、100 根 K 窗口），放进行动格行尾属于堆砌概念；**社区功能移植必须先做可读性审计**（用户是否一眼能懂），再谈信息价值。若未来重启：放 Dashboard/数据窗而非行动格行内。
2. **薄量区标注**（中成本）：SVP 分布图成交量 < 峰值 18% 的行画半透明带，穿过时可选打勾——复用 profileEngine 桶数据（未动，用户未确认）。
3. **路径历史频率**（高成本）：PoT 模式统计引擎，远期（未动）。
4. **磁吸权重 input 化**：0 成本但主指标计数余量仅 6（248→254），加 4 input 顶格——暂缓，除非转 4 个低频 const 腾位（未动）。
5. **表格价格精度**（已落地）：f_fmt_price 按量级自适应（≥1000→1位、≥100→2位、≥1→3位、<1→4位）——用户"价格只保留一位小数"意图 + 低价品种（EURUSD 1.0854）防失真，见 svp-pullback-path-binding 修改 16。

### 棠溪磁吸评分现状（20260813 核对 L2600-2664）
`distScore×0.4 + freshness×0.3 + prio×0.3 + HTF+20`；nPOC 单独 `85 - dist/ATR×15`；min(100) 封顶；上方/下方各取最高分 + 最近位（magnetNearest 单独）。权重硬编码。

## 20260813 已修复：价格轴标签颜色不跟随设置

现象：用户问"POC 在价格栏怎么不是我设置的颜色"。根因：L3212 `plot(axisPocPlot, color=#5B6470)` 等 4 处价格轴(price_scale)标签颜色硬编码，未用 POC_COLOR/VAH_COLOR/VAL_COLOR/NPOC_COLOR/DO_COLOR 输入。历史：20260810 审计曾因 POC_COLOR 默认 #0F0F0F 近黑在深色主题不可见而硬编码 #5B6470 双主题中灰——"解耦"造成"设置没生效"观感。
修复：新增 4 个独立 input（AXIS_POC_COLOR #5B6470 / AXIS_VAHVAL_COLOR #2962FF / AXIS_NPOC_COLOR #787B86 / AXIS_DO_COLOR #673AB7，VP_ELEMENTS_GROUP + DO_GROUP），默认保留双主题可见色，用户改自己 POC 色即一致；W/M VWAP 轴标本就走 WEEKLY_VWAP_COLOR/MONTHLY_VWAP_COLOR 输入，无需动。input 194→198，脚本级 239<254 ✓。交付：桌面/hermes下载文件/SVP轴标颜色修复_20260813/SVP_ICT_v2_20260813_轴标颜色可调.pine
教训：外观类硬编码（尤其深色主题可见性修复）应改"独立可调输入+默认保留修复值"，而非永久硬编码——用户改主图颜色时轴标必须能跟随，这是"外观参数必可调"铁律的延伸。

## 20260813 追加：副指标 5 行压宽 + 加密完善度定论

用户要求"不要太宽" + 问"加密是不是就是这样了"。落地与结论：

**压宽两刀（信息零丢失）**：
1. 信号行结论词只取主词：`str.trim(str.split(actText, '·')[0])`——`实涨可信·新钱+买盘✅`→`实涨可信`（解释段省略，完整版在数据窗）
   ⚠️ **20260813 实测推翻**：v6 中 `str.split(series)[0]` 报编译错误（数组元素访问不可直接赋 string）。终版改用**同步赋值的 actWordA 主词变量**（6 处赋值点与 actText 同构三元链），信号行 `signalA + '·' + actWordA`。实测结论（pine_check 最小复现）：`str.trim(series string)` 可编译 ✓，`str.split(series)[0]` 编译错 ✗。**教训：str.* 系列参数类型要求别凭文档猜，用 pine_check 最小复现实测（本技能可调用的验证路径）。**
2. 流向行分隔符统一·去空格：`flowPanelTxtA + (volPanelTxtA != '' ? '·' + volPanelTxtA : '')`——`日买盘 量1.8x·疑空爆`→`日买盘·量1.8x·疑空爆`
最宽行 ~24→~20 字符。

**加密完善度定论（对照社区原则，5 行即完整形态，不加东西）**：
| 社区原则 | 5 行对照 |
|---|---|
| 5 秒规则（结论前置） | 信号行第一：方向+共振票+结论主词 ✓ |
| 假汇合警告（Colibri：相关指标叠加=假汇合） | **CVD+量合并同行=诚实标注同源**（都派生自 volume 估算，非独立维度），不假装独立；OI 是独立维度（衍生品数据）单独一行 ✓ |
| 有数据≠该展示 | 覆盖%只在无风险时显示、警告词优先 ✓ |
| Data-Ink | 结论主词化+分隔符统一 ✓ |
| MCP 总线 | 26 个 data_window plot 全量导出（OI/Flow/State Pack），行动格只是摘要 ✓ |

关键论证：CVD 与聚合量同源合并是"诚实"，不是"砍信息"——若未来有人建议把 CVD 行拆回独立行，用"同源假汇合"反驳（两个派生自同一 volume 的维度并列=伪独立确认）。
