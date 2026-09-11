# 结构标签语义与决策面板审计

## 触发场景

审计主指标行动格中 `HH/HL/LH/LL`、`守HL/LH`、`等新HL/LH`、BOS/CHoCH 或“下一步怎么做”文案时使用。

## 核心不变量：结构名必须由代码证明

`lastSwingHigh/lastSwingLow` 只表示最近确认摆动高低点，不自动等于 HH/HL/LH/LL。

真正分类至少需要保存连续两个同类确认枢轴并比较：

- 当前确认高点 > 前一确认高点 → HH；否则为 LH。
- 当前确认低点 > 前一确认低点 → HL；否则为 LL。
- pivot 未确认前不得提前贴结构标签；确认延迟必须与结构参数一致。

危险模式：

```pine
roleLongSwingOk = structureBias > 0 and not na(lastSwingLow)
rolePullbackName = roleLongSwingOk ? "HL" : "等新HL"
```

这里 `structureBias > 0` 只能说明最后一次结构突破偏多，不能证明 `lastSwingLow` 高于前低。把它显示为 HL 属于“文案能力超过算法能力”。空头侧同理。

## 两种合规修法

### 最小安全修法（优先）

不新增结构分类器，先把文案改诚实：

| 过度文案 | 安全文案 |
|---|---|
| 守HL | 守确认摆动低 |
| 守LH | 守确认摆动高 |
| 等新HL | 等新回踩低点确认 |
| 等新LH | 等新反抽高点确认 |
| 价格发现·等新HL | 价格发现·等回踩结构形成 |
| 价格发现·等新LH | 价格发现·等反抽结构形成 |

### 完整修法

建立独立、已确认的结构状态机：保存前后两个 pivot high/low，输出 HH/HL/LH/LL 枚举；BOS/CHoCH、趋势角色位和行动格共同消费该枚举。短线结构参数不要无审计地复用较慢的 OB lookback；必须验证确认延迟、噪声和各周期行为。

## “下一步”文案闭环

行动格不能只写 `等触发`、`等确认`。它必须将当前倾向、现位和触发条件连成一条人工决策链：

- 偏多有回踩位：`等回踩现位→MSS↑→收线→核对CVD/OI`。
- 偏空有反抽位：`等反抽现位→MSS↓→收线→核对CVD/OI`。
- 多头价格发现：`不追·等回踩低点形成→MSS↑`。
- 空头价格发现：`不追·等反抽高点形成→MSS↓`。
- 副指标 S3：`不执行·等订单流冲突解除`。
- 副指标 S4：`仅人工·等数据恢复`。
- R:R不足：`不做·等更好价使R:R≥2`。
- 触发过期：`等新扫线/位移/收线确认`。

职责必须闭环：

- `结构`：最近真实结构事件；
- `现位`：看哪里；
- `进场`：到位后看什么；
- `协同`：副指标是否确认/降级/否决；
- `风控`：哪里失效。

## 与SVP价值区联审

若目标是复刻 TradingView 原生 Volume Profile，必须遵循其官方离散桶算法：从 POC 开始比较上下候选桶，选择量较大者；**只有加入后不超过剩余目标量才纳入，若会超过目标则停止**。因此最终纳入量可能略低于 70%，这是离散桶与官方规则的正常结果，不得擅自改成“首次达到或超过70%”。

标准守卫：

```pine
float candidateVolume = chooseUp ? vUp : vDn
bool candidateFitsVa = currentValueAreaVolume + candidateVolume <= valueAreaThresholdVol
if not candidateFitsVa
    break
```

并列规则：量相同先选离 POC 更近者；距离仍相同选上方。任何算法变更都要先明确目标是“TradingView一致”还是“自定义至少覆盖70%”，不能混为一谈。错误的 VAH/VAL 会继续污染 VA内外、接受/拒绝、关键位、A级门槛和 Entry/Stop/Target，按P0处理。官方依据：TradingView Help Center，`Volume profile indicators: basic concepts` → `Calculating value area`。

## 验证清单

1. 全文搜索 `HH|HL|LH|LL`，逐个追溯到真实分类变量，不能只追到 `structureBias` 或 `lastSwing*`。
2. 构造连续高点/低点组合，覆盖 HH、HL、LH、LL 四种情况。
3. pivot 未确认时不得提前改变结构标签。
4. BOS/CHoCH、结构行、现位行、Entry Valid 使用同一结构状态。
5. 所有等待态都写出具体触发链，不能只显示“等触发”。
6. 若目标是TradingView一致，SVP价值区候选桶会越过剩余阈值时必须停止；记录最终覆盖率略低于阈值属于正常离散结果。
7. Pine全量编译0错0警后，仍需在图表逐项核对行动格语义；编译通过不等于逻辑正确。
