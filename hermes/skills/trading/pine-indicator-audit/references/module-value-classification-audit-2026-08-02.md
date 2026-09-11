# 内嵌模块价值分类审计（module-value-classification）

适用场景：用户问「我的指标里面那些插进去的小指标/模块，哪个有用哪个没用」——不是编译/配额/死代码审计，而是**决策价值**审计：每个模块到底有没有驱动交易裁决。

## 审计方法（四步）

### 1. 盘点模块：按 input 分组 + 功能开关
```bash
# 所有分组常量（模块边界）
grep -n "const string .*_GROUP\s*=" 主指标.txt
# 所有功能开关 SHOW_*（可关=非决策强制项）
grep -n "input.bool" 主指标.txt | grep -o "bool  *[A-Z_0-9]*"
```

### 2. 逐模块追踪决策消费链（核心步骤）
找到每个模块的变量被哪些**决策表达式**消费。消费点分级：
- **评分**：`trendScore/reversalScore/confirmScore/setupTotalScore` 的 `+=` 项
- **分级**：`setupLongA/B/C`、`displayLongA/ShortA` 的条件
- **闸门**：`xEmaConfig`、`xHotExtended`、`adrChaseBlock`、`rrHardBlock`
- **磁吸/目标**：`magnetTargetName`、`candidatePlanPrice`

命令参考：
```bash
# 评分构成（各模块权重一目了然）
sed -n '1877,1920p' 主指标.txt   # trendScore/reversalScore 的 += 块
grep -n "confirmScore\s*=" 主指标.txt
```

### 3. 分类到三桶
- **决策核心**：有评分/分级/闸门消费点，删了系统坏 → 保留
- **纯展示**：只进 action 格/标签/线，不参与决策 → 可关 input，不删代码
- **无用**：零消费 → 上轮死代码清理应已删净，若仍有需排查

### 4. 结合用户交易逻辑给建议
- 有消费链的模块 ≠ 权重合理。查**低权重纯加分模块**（如 SMT ±1、KillZone 0）是否有社区实证支撑
- 社区实证（2026）：位移/MSS>FVG>OB>Breaker 是递减置信；CVD 是 confluence 非 standalone；KillZone 是**入场时机过滤器**，窗口内信号应加权而非纯展示
- 减法优先：新功能上线前先想"关什么"（副指标 5 所=32/40 配额紧约束时尤其）

## SVP 主指标实测结论（2026-08-02）

| 模块 | 决策权重 | 社区实证 | 裁决 |
|---|---|---|---|
| SVP 分布图 | locationScore 3 / VA / 磁吸 | 日内标配 | ✅核心 |
| 扫线/流动性 | reversalScore **3**(最大) / confirm 2 / A级门槛 | ICT可回测 #1 | ✅核心 |
| VWAP | trend ±2 / extensionRisk 3 / 30处 | 日内标配 | ✅核心 |
| EMA 4线 | trend ±2 / regime / mcpQuality 64 | 标配 | ✅核心 |
| DMI/ADX | trend ±2 / X过热闸门 | 标配 | ✅核心 |
| CVD | trend ±2(加密+0.5) / reversal ±2 / confirm 2 | confluence非独立 | ✅核心 |
| MSS/位移 | trend +1 / A级门槛 | 2026 #1过滤 | ✅核心 |
| ADR | reversal +1 / X禁追 / 25处 | ATR风控 | ✅核心 |
| FVG+HTF | confirm / B/C汇合 | 需HTF+位移 | ✅保留 |
| OB/Breaker | confirm +1/+1 / B/C | 需多层汇合 | ✅保留 |
| SMT | reversal ±1(仅近关键位) | 争议大 | ✅保留(无害) |
| nPOC | 磁吸 / 关键位矩阵 | 常用 | ✅保留 |
| DO线 / KillZone / 会话CVD | 仅展示 | — | 可关input |

**核心结论**：SVP 主指标所有模块都有消费链，**零无用模块**（上轮已清 36 死变量）。

## 推荐增强（低风险高价值）
- KillZone **决策化**：`confirmScore + 1 if isKillZone and (activeLongPlan or activeShortPlan)` ~15 行，把纯展示升级为入场时机权重，符合窗口交易逻辑
- 免费档性能实测：32 个循环（SVP分桶/VA迭代/数组维护）是 20s 限制头号嫌疑，贴 TV 后跑 Profiler

## 关键陷阱
- 「input 开关都有消费端」≠「模块有用」——要区分消费在**决策表达式**还是**纯展示/文本拼接**。只进 `kzShort` 标签/`*Text` 拼接的模块是纯展示。
- 权重低≠删：SMT ±1、KillZone 0 权重，但实现成本已付、删除有回归风险，且无害。减法清单应列「默认关的 input」而非删代码。
