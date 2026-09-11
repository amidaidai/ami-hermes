# Pine 单一计划方向合同

## 触发场景

用于审计同时计算多空 A/B/C 候选、Entry/Stop/Target、评分、风险和行动格的成熟 Pine 决策脚本。目标是防止不同模块各自选择方向，出现“入场按空、评分按多、面板又从两边取确认”的语义裂缝。

## 核心原则

整个下游决策链只消费一个规范方向：`selectedPlanDir`（多=1、空=-1、无计划=0）。方向选择必须先按等级，再在同级异常冲突时使用稳定兜底：

`X/禁做 > A > B > C > 等待`；同级双边异常才可采用“多头优先”。禁止“任意多候选优先于任意空候选”，否则 B多可能覆盖 A空。

示意：

```pine
int selectedPlanDir = setupX ? 0 : displayLongA ? 1 : displayShortA ? -1 : bcLongDirectRaw ? 1 : bcShortDirectRaw ? -1 : cLongDirectRaw ? 1 : cShortDirectRaw ? -1 : 0
bool selectedPlanLong = selectedPlanDir == 1
bool selectedPlanShort = selectedPlanDir == -1
```

若同级条件本身可能双边同时为真，应先显式构造 `bothA/bothB/bothC` 并记录诊断码；多头优先只是确定性故障兜底，不是交易观点。

## 必须统一接线的消费者

以下模块不得继续独立使用 `activeLongPlan or activeShortPlan` 取任一边证据：

1. Entry、Stop、Target、R:R、价格几何；
2. 位置分、CVD确认、扫位/接受、价值接受、FVG/OB/HTF OB；
3. HTF顺逆、VWAP延展、ADR、PD、结构冲突；
4. AggVol S1/S2协同与反向降级；S3/S4仍是全局冲突/数据降权；
5. CVD/SMT冲突；
6. 行动格方向、核对、OI着色、进场文案、风险文案；
7. Data Window/MCP Side、Quality、FVG/OB分值。

方向化示例：

```pine
bool planCvdConfirm = selectedPlanLong ? cvdBullConfirmQualified : selectedPlanShort ? cvdBearConfirmQualified : false
bool planVwapExtended = selectedPlanLong ? vwapExtendedUp : selectedPlanShort ? vwapExtendedDn : false
bool planCvdConflict = selectedPlanLong ? cvdBearConflict : selectedPlanShort ? cvdBullConflict : false
```

## 常见遗漏

- `locationScore = nearAKeyLevel ? 3 : ...` 若 `nearAKeyLevel`含扫高和扫低，会给反方向位置加分；拆成 `nearLongKey/nearShortKey`。
- 全局 `structureConflict` 可能由反方向冲突触发；拆成 long/short 后再按所选方向消费。真正系统级错误（EMA参数非法、低流动性、总线合同错误）仍可全局阻断。
- `planSideLong`/`planSideShort`是“存在候选”，不一定是“最终被选候选”；不能直接用 `selectedPlanLong = planSideLong`。
- 稳定化 A 信号可能与当根原始 B/C 反向候选短暂共存，必须保证 A 等级优先。
- 面板局部变量若仍写 `panelLongSide = activeLongPlan`，说明统一方向尚未闭环。

## 验证矩阵

至少构造：仅A多、仅A空、仅B多、仅B空、A空+B多、A多+B空、B多+B空、无计划、X。逐场景断言：

- `selectedPlanDir`唯一且等级正确；
- Entry/Stop/Target几何方向一致；
- 评分只从该方向取得正向证据；
- 反方向证据只作为冲突/降级，不可加分；
- 行动格、OI颜色、AggVol协同和MCP Side Code完全一致；
- 双边异常通过诊断字段可见，不能静默掩盖。
