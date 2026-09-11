# Pine Script 源码 + 实时数据交叉验证（2026-06-21）

## 能力描述

用户可上传 Pine Script `.txt` 源文件让 Agent 读懂指标内部逻辑，然后与 TV MCP 实时数据交叉验证。比单纯读 `study_values` 深 3 倍。

## 工作流

1. **用户上传 Pine Script 源文件** → `read_file` 全量读取
2. **识别核心逻辑**：
   - 评分公式（trendLongScore/trendShortScore/reversalLongScore/reversalShortScore）
   - 分级规则（A/B/C/X + GRADE_STABLE_BARS 稳定确认 + A_ONLY_NEAR_KEY_LEVEL 距离过滤）
   - 冲突检测（structureConflict = 结构 + EMA + DMI + CVD 四维冲突）
   - CVD 状态（吸收 buy / 派发 sell / 背离 bull/bear / 确认 confirm）
   - 事件驱动（sweptHighNow/sweptLowNow → 扫亚高/扫伦低）
   - 市场差异化权重（加密+1放量、贵金属/外汇+1 sweep）
   - 失效条件（longInvalidPrice/shortInvalidPrice 动态计算）
3. **调 TV MCP 获取实时数据**：
   - `chart_get_state` → 确认 studies 列表
   - `study_values` → 获取 POC/VAH/VAL/VWAP/EMA/CVD/Slope
   - `pine_labels` → ICT 会话标签（亚高/亚低/纽高/纽低/POC/VAH/VAL/nPOC）
   - `pine_lines` → 画线层（当前 VA 区 + 历史 VA 区 + 虚线延伸）
   - `pine_tables` → ⭐ DMI 决策表（grade/treatment/cvdState/invalid/nowAdvice）
4. **交叉验证**：「源码规则」×「实时信号」→ 得出确定结论
5. **捕获到分析卡**：DMI 表数据直接嵌入分析卡博弈段

## 案例：SVP+ICT+VWAP+EMA+CVD v6

### 源码关键发现

**评分公式（顺势多=0-10）：**
```
+VWAP上方+2  +VAH上方+2  +EMA多头云+2  +DMI顺多+2  +放量上收+1  +加密/股票+1  +CVD确认+1  -CVD顶背离-1
```

**分级规则：**
```
A多 = 顺势多≥8 AND 顺势多≥顺势空+2 AND CVD顺多确认 AND VWAP上方 AND 上方接受 AND 高周允许多 AND 靠近关键位 AND 非过热
B多 = 顺势多≥6 AND 顺势多≥顺势空+2 AND CVD多OK AND 高周允许多 AND 非A多
C反多 = 反转多≥6 AND 反转多≥反转空+2 AND 高周允许多
X = 过热 OR 延展 OR 结构冲突 OR 高周冲突
```

**A级稳定确认：** GRADE_STABLE_BARS = 2。A 级信号需连续 2 根 K 线确认才升级，X 风险立即生效。

**冲突检测（四维）：**
```
structureConflict = 结构冲突(EMA/VWAP背离) OR sweep方向与VWAP矛盾 OR DMI方向反对 OR CVD顶/底背离
```
当 `structureConflict = true` → `setupGradeStable = "X"` → `treatmentText = "结构冲突"` → `nowAdviceText = "观望"`

**CVD 吸收/派发检测：**
```
吸收买 = 价格压缩(<0.8 ATR) AND CVD大量减少(>3×平均Delta) AND 收盘靠近区间高位
派发卖 = 价格压缩(<0.8 ATR) AND CVD大量增加(>3×平均Delta) AND 收盘靠近区间低位
```

### 实时数据获取

| API | 数据 | 示例值 |
|-----|------|--------|
| study_values SVP | EMA9/21/34/55, CVD, VAH/VAL/POC, VWAP, S VWAP | CVD -3,100 |
| pine_labels | ICT 会话高低、POC/VAH/VAL 标签 | 周六纽高 64,371 |
| pine_lines | 当前+历史 VA 画线（13条水平线） | VAL 64,136 实线 |
| pine_tables | DMI 决策表 8 行 | 等级 X · 处理 结构冲突 |
| study_values CVD pane | 独立 Cumulative Volume Delta | CVD -3.57K (1D) |

### 交叉验证输出

从源码规则 + 实时数据得出：
- 4h 背景空（htfBear=true） + CVD 顺多确认 = 高周冲突 → setupX = true
- 结构冲突 + 高周冲突 → grade = "X", treatment = "结构冲突"
- 此时 `nowAdviceText = "观望"`, `invalidText = "不进场"`
- → 分析卡应标 X 禁做，不应强推方向

## 与 auto_card 自算的差距

| 维度 | DMI 表（TV源码） | auto_card 自算 |
|------|-----------------|---------------|
| 评分 | 4维 0-10 加权 | 单维 bias |
| 分级 | A/B/C/X + 稳定确认 | 无 |
| 冲突检测 | 结构+EMA+DMI+CVD 四维 | 无 |
| 市场差异化 | 加密/贵金属/外汇分权 | 无 |
| 失效条件 | 动态计算 invalidPrice | 固定阈值 |
| CVD 吸收 | 价格压缩+CVD量变+位置 | 无 |
