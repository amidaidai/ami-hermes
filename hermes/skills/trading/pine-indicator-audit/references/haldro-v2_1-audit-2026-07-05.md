# HALDRO 副指标 v2.1 审计与实装记录

> 2026-07-05 双轮审计 + v2.1 实装。主指标 SVP v10（3204行）+ 副指标 HALDRO v2.1（502行）。

## 第一轮：社区对标 + 优化建议

用户上传双指标，要求联网社区看有什么需要添加/优化。

### 社区搜索矩阵（2026-07-05）

| 平台 | 查询 | 发现 |
|------|------|------|
| TradingView | Pine v6 volume profile CVD best practice | v6 动态 request.security、polylines 改进 |
| Reddit r/pinescript | CVD divergence swing detection | 三重过滤共识（摆动极端+不确认+ATR） |
| TradingView scripts | CVD/OI Divergence indicators | PTT CVD/OI 融合线、LSR 指标存在 |
| Coinglass | Long/Short Ratio | Binance LSR ticker = `BINANCE:{base}USDT_LSR` |
| Medium/betashorts | CVD Divergence Detector | Pine 实现模式：pivot + non-confirm + filter |
| ICT 社区 | OB + BOS/CHoCH + MSS | ICT 三件套：FVG + OB + MSS |
| TradingSim/TrendSpider | HVN/LVN Volume Profile | LVN=低量节点=价格真空快速通过 |

### 建议清单与用户裁决

| 建议 | 优先级 | 用户裁决 |
|------|--------|----------|
| OB + BOS/CHoCH 标注 | P1 | ❌ 不要 |
| LVN/HVN 节点标注 | P1 | ❌ 不要 |
| 副指标 CVD 背离 + 5行精简 | P1 | ✅ 做 |
| 多空比 LSR | P2 | ✅ 顺手做 |
| 主指标 v5→v6 升级 | P2 | ❌ 不做 |
| 清算热力图 | P2 | ❌ 无API不做 |

## 第二轮：v2.1 实装后的全量审计

用户再次上传两个指标（含已实装的 v2.1 副指标），要求继续审计优化。

### 静态扫描结果

**主指标**（3204行）：
- request.security: 11 grep / ~13 展开 / 40 上限 → 安全
- plot: 23 / 64 → 安全
- line/box/label: 28 / 500 → 安全
- 重绘: lookahead_on + [1]/[3] ✓, barstate.isconfirmed ✓, closeReclaim ✓
- def-before-use 误报: 4处（kzShort/sweepCntText/actionBiasWord/actionStateText）= 已知误报

**副指标 v2.1**（502行）：
- request.security: 6 grep / ~28 展开 / 40 → 安全
- plot: 30 / 64 → 安全
- def-before-use: 无违例
- 重绘: 无信号点

### 新发现

#### P1-A: 主指标三个风控参数是死代码
- L261-263: `RISK_PER_TRADE_PCT` / `DAILY_MAX_LOSS_PCT` / `WEEKLY_MAX_LOSS_PCT`
- 全文 grep 确认零引用
- 设置面板显示风控项但实际不限制 → 误导
- 建议：删除或写入 Data Window 编码

#### P1-B: 主指标 gapThrough 线条变虚缺口
- L1671-1677 `isSwept` 只检测 `wickPierce`，不检测 `gapThrough`
- L2033-2045 评分逻辑正确处理 gapThrough（`sweptHighRejected` 看 close < price）
- 结果：跳空穿过时评分标记扫线，但线条仍实线 → 视觉不一致
- 修法：L1675 加 `gapThrough` 判定

#### P2-B: tooltip 默认值描述不一致
- L257 `ACTION_PANEL_TRANSP` tooltip 写"默认28"但实际默认50

#### P2-D: narrative card 死代码残留
- ~L2320-2334 的 `stateText`/`cardLine1-3`/`directionGuideText`/`actionGuideText`/`detailText`
- 旧叙事卡残留，v2 行动格取代后不再消费
- 仅 `invalidText`/`watchText` 仍被消费

### 已确认正确的部分（无需改）

- FVG + HTF确认 + CE 50%：三K失衡+位移过滤+高周确认 ✓
- CVD 背离三重过滤：摆动极端+不确认+ATR+slope ✓
- SMT 跨品种背离：正/负相关+同交易所前缀 ✓
- A/B/C/X 分级 + R:R 硬门控：2.0R + BC 1.5R ✓
- 磁吸三因子评分：距离+新鲜度+优先级 ✓
- 市场自适应引擎：6市场自动调参 ✓
- executablePlan 含 rrHardOk ✓（L2799）
- panelEntryVal/panelStopVal/panelTgtVal 含 rrHardBlock ✓（L3025-3032）
- 扫线 closeReclaim 判定 ✓
- 副指标 v2.1 全部功能正确 ✓

## v2.1 副指标实装详情

### 10项改动清单

1. `ACT_COMPACT` 默认 true→false，精简3行→5行（信号/结论/流向/持仓/操作+可选风险行）
2. 新增 `SHOW_LSR` input（默认true）
3. LSR 计算：`BINANCE:{base}USDT_LSR`，`ignore_invalid_symbol=true`，>1.3 空头拥挤，<0.8 多头拥挤
4. CVD 背离三重过滤：摆动极端 + CVD不确认 + 摆动>1.5×ATR + slope方向
5. 背离时流向行替换为 `估算CVD ⚠卖背离`/`⚠买背离`
6. `confirmScoreA` 背离时扣1分
7. `riskWarnA` 增加 `⚠CVD背离`
8. 持仓行合并 LSR 后缀
9. 两条 alertcondition：CVD卖背离/CVD买背离
10. Data Window: `CVD Value`→`Estimated CVD Value`，新增 `CVD Method Code`/`CVD Quality Code`/`LSR`

### 配额安全

| 项目 | 占用 | 上限 |
|------|------|------|
| request.security | ~28（含LSR新增1） | 40 |
| plot() | 30 | 64 |

### 文件位置

- 副指标 v2.1: `C:/Users/Administrator/Desktop/haldro_indicator_v2_1.txt`
- 原上传: `C:/Users/Administrator/.hermes-web-ui/upload/default/c4b10e5dc049e40a.txt`

## 审计方法论沉淀

1. **先跑 `pine_static_scan.py`** 拿全量配额/对象计数/def顺序/重绘信号
2. **读关键段**：Inputs(1-500) → SVP引擎(500-740) → AutoTF/VWAP(740-990) → CVD核心(940-990) → 会话/扫线(1300-1730) → 评分引擎(2320-2780) → FVG(2460-2540) → BC入场(2700-2780) → 行动格(3009-3070) → MCP导出(3100-3170)
3. **死代码验证**：`grep -c` 每个可疑变量，定义1次且仅在自己块内引用=死代码
4. **tooltip 一致性**：grep tooltip 文案中的数字，与 `input.int(默认值,...)` 比对
5. **gapThrough 检查**：grep `wickPierce|gapThrough|isSwept`，确认 isSwept 覆盖两种路径
6. **社区搜索矩阵**：TradingView + Reddit + Medium + Coinglass + ICT社区，6平台并行搜
