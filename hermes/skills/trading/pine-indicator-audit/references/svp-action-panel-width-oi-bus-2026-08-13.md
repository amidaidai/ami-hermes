# 行动格宽度优化 + OI 决策总线增强（2026-08-13 会话）

适用：主指标 12 行行动格 + 副指标行动格（加密 7 行/非加密 3 行）的宽度治理，以及主副 OI 跨指标链路增强。
本文件记录本次会话落地的方法论与已实施改动，避免未来重复推演。

## 一、OI 四象限语义（决策价值，用户首次问"OI 对我们决策有什么吗"）

OI（持仓量）= 新钱进场 vs 旧仓离场，是趋势真伪过滤器。主指标 OI 行编码的就是这张表：

| 价 | OI | 含义 | 决策意义 |
|---|---|---|---|
| 涨 | 涨 | ▲新多（新钱做多） | 上涨可信，支撑做多 |
| 涨 | 跌 | ▲空回补（空头平仓） | 不可持续，**追多危险** |
| 跌 | 涨 | ▼新空（新钱做空） | 下跌可信，支撑做空 |
| 跌 | 跌 | ▼多平仓（多头离场） | 不可持续，**追空危险** |

决策链定位：主指标 CVD 行（主动买卖）+ OI 行（持仓变化）+ 确认行（门控）= 多源交叉确认。OI 行回答"这波是趋势还是回补"，避免追在平仓行情尾巴。

## 二、打包标量总线模式（input.source 单标量限制的解法）

**限制**：主指标通过 `input.source` 从副指标拉数据，每次只能拉**一个标量**（一条 plot 的值），多维度状态（跨所一致%、LSR、聚合/单源）传不过去。

**解法（已实施）**：副指标把多维状态压缩编码进一个标量，主指标解码。
- 例：`HALDRO OI Pack = oiDirCode(±1) × 100 + int(oiAgreementPct)`（185=OI升且一致85%，-15=OI降且一致15%，0=不可用）
- 主指标解码：`int(math.abs(pack)) % 100` 得一致%，符号得 OI 方向
- 同类既有先例：`HALDRO State Pack`（0无效/1支持多/2支持空/3冲突/4降权）、`HALDRO Flow Pack`（OI×100+CVD×10+SP）
- **实施注意**：新 source 占 TV 计数 +1（主指标余量 1，加 source 后须把 1 个低频 input 转 const 腾位，如 SHOW_BOS_CHOCH_TEXT→const true）；副指标 +1 plot 余量足

## 三、OI 行路径验证（用户要求："OI 行要说明是否支持当前路径"）

主指标 OI 行在四象限后追加路径裁决：
- `oiNewPos`（新仓）= OI 与价同向；`oiClosePos`（平仓/回补）= OI 与价反向
- `oiBiasLong` = planSideLong 或（非空计划且 structureBias>0 或 trendLongScore≥trendShortScore+2）；Short 对称
- 多路径：新多→` ✓支持`；平仓/回补→` ⚠存疑`（平仓推动不可持续）；空路径对称
- 输出格式：`▲新多 0.35% 共识85% ✓支持`

## 四、LSR 缺失显示（"缺失全绿"陷阱的延续）

副指标持仓行 LSR 文本：`na(lsrA) ? '·LSR缺' : ...`——缺失时显示"·LSR缺"，**绝不显示空串**。
与 2026-08-09 的"缺失数据'全绿'陷阱"同源（na 被当正常/健康处理）。风险行 `⚠LSR缺失` 同步压缩为 `⚠LSR缺`。

## 五、行动格宽度治理方法论

### 5.1 宽度审计法（用户：结论/风控太宽，全部行都要检查）

1. 枚举全部行动格行（主 12 行 + 副指标各模式行）的**最坏情况动态内容**（每个分支取最长字符串，含所有拼接段）
2. 估算字符长度，>25~30 即标"宽"
3. 只修标宽的行；定稿行（磁吸↑↓"名称 价格 分NN ★HTF 距离A"、看位"方向·位·到位行动"、位置"价态·就绪·VWAP锚"、方向"行动词+DMI+体制+类型词+置信%"）不动

### 5.2 压缩原则

- **只压冗余，不删信息**：被删的信息必须已存在于其他行（或语义可由表头推断）
- 结论行：完整交易单（lineAction：多/止/标/失效全串）与进场/风控行重复 → 换短动作词"等确认/等触发"；A 级失效位（finalInvalidSpecificText）保留（唯一信息）；解锁词已含于 actionStateText 时不再追加（`str.contains` 去重，与 panelRiskOne 同模式）
- 进场行：挂单态内嵌 expectedTriggerPath（触发链），行尾不再追加，与 activeTriggerText 去重
- 风控行紧凑格式：`止81200·1.8A 标↑VAH 82350·2.1R`（去括号、ATR 全拼、双空格；rrText="2.1R" 已带 R）
- KZ 倒计时去"剩"字：`⚡亚48m`（表头即含义）
- 扫位压缩：`已扫2/剩1` → `扫2/1`
- 副指标：去前导空格、`一致85%`→`共识85%`、`同步放量3/3`→`同步3/3`
- 风险词压缩：`⚠单所主导`→`⚠单所`、`⚠上级冲突`→`⚠高周逆`（用户懂"高周"）、`⚠LSR拥挤`→`⚠LSR挤`、`⚠OI跨所分歧`→`⚠OI分歧`、`⚠数据掉线`→`⚠掉线`
- **红线**：磁吸分NN/★HTF、OB 分级分数（A88）、看位方向词+到位行动词不可砍（用户曾要求恢复原样）

### 5.3 实施验证

- 文本级修改不占 TV 计数：改完跑 pine_external_elements_scan.py 复核（主 253/254、副 88/254 不变）
- 括号/引号平衡 + 死变量扫描确认无回归
- 交付两份 .pine（LF 行尾），文件名带日期

## 六、已实施改动清单（2026-08-13）

主指标 SVP：
1. `oiPackSource` input.source 新增（OI共识来源）
2. f_panel_oi：共识%解码 + oiPathVerdict 路径验证
3. f_panel_risk：panelUnlockText 去 lineAction → 短动作词
4. 结论行组装：unlockText str.contains 去重
5. f_panel_entry：挂单态内嵌 expectedTriggerPath；panelStopVal/panelTgtVal 紧凑格式
6. 进场行组装：去 expectedTriggerPath 重复追加
7. kzShort 去"剩"、sweepCntText "扫N/M"、结构行 "波NN%"
8. SHOW_BOS_CHOCH_TEXT → const true（腾 input 计数）

副指标 AggVol：
1. `HALDRO OI Pack` plot 新增（方向×100+一致%）
2. lsrTxtA 缺失显示"·LSR缺" + 去前导空格
3. dataTrustA 从覆盖行移信号行（仅降权显示"·数据降权"），声明删除
4. oiTxtA/basisTxtA/volTxtA/riskWarnA 词压缩
