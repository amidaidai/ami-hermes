# 社区与官方验证的双指标增强分级（2026-08-22）

适用：审计 SVP+ICT+VWAP+CVD 主指标与 AggVol 副指标，判断提议是新增增强、已有能力补齐，还是伪增强。

## 核心决策边界

- 主指标是唯一执行授权源：方向、等级、触发路径、Entry、Stop、Target、R:R、X/WAIT。
- 副指标只做确认、降级、否决；不得独立开单、不得给执行价格、不得把 B/C 升级为 A。
- 先修数值源、状态机和最终计划合同，再做结构扩展和界面扩展。

## 本次审计定案

### P0：必须修复

1. **唯一 FinalPlan**：将候选 Entry/Stop/Target 收束为单一最终计划；行动格、Data Window、MCP、告警全部消费同一组最终变量。多单必须 `Stop < Entry < Target`，空单必须 `Target < Entry < Stop`；几何/R:R失败时价格输出 `na`。
2. **X/WAIT/A/B/C 合同**：拆分 `HardBlockCode`、`WaitCode`、`WarningCode`。优先级为 `X > WAIT > A > B/C`。X/WAIT不得显示可执行价格，B/C价格只能进入人工候选字段。
3. **AggVol 语义边界**：成交量是五所聚合，OI是四所聚合，CVD是当前图表品种的低周期或K线方向估算；不得将其称为五所聚合 CVD 或真实 Bid/Ask 流。
4. **CVD Method Code 与质量门控**：`0=无效，1=当前K线方向估算，2=低周期CVD估算`；输出必须区分样本不足、缺失、未收盘和回退。非加密时聚合方向确认归零/忽略。

### P1：真实决策增强

5. **日/周 CVD 双层状态**：保留加密 5m/15m 日锚执行 CVD；增加周锚结构状态，只输出同向/冲突，不重复计票。统一主副市场路由，特别检查期货和指数。
6. **结构状态机补齐**：OB/FVG/iFVG/扫线统一记录新建、触碰、缓解/回补、收盘穿透、失效、事件年龄和确认状态。Sweep要区分 wick rejection 与 close-through breakout；结构概念是 OHLC 派生，不是真实订单簿。
7. **AggVol 逐源质量与宽度**：补充每源新鲜/过期/缺失，显示同步放量宽度（如 `4/5`），检查 base/quote/tick/未知成交量单位，缺失不得静默当真实零。

### P2：后置架构

8. **轻量 winnerZone 与市场/性能路由**：先统一输出唯一胜出区域字段，再考虑完整 Zone Registry。期货、股票、贵金属需分别处理交易时段和锚点；性能降级必须真实减少计算/对象/request，不得仅隐藏输出。

## 官方与社区约束

- TradingView 官方 CVD使用低周期价格行为和成交量估算买卖压力，不等于真实逐笔 Bid/Ask aggressor 数据；更低周期提升采样粒度，不改变估算属性。
- 公开社区脚本常把 CVD用于关键位确认、背离和吸收，但没有官方或社区证据证明 CVD、VP、FVG、OB、SMC、OI组合本身稳定盈利。
- OI只表示未平仓衍生品合约变化。方向需结合价格、成交量、资金费率和一致性；OI上涨不能直接写成多头增加。
- FVG/OB/MSS/BOS/扫线没有 TradingView官方统一数据源，必须公开定义确认延迟、触碰/回补/失效规则。
- Pine v6普通账户最多40个唯一 `request.*()` 上下文、64个plot count；隐藏输出仍可能占plot，input开关只有阻止请求执行时才可能节省动态上下文。

## 伪增强识别

不要把以下内容作为优先增强：第三套CVD、更多交易所、更多总分、更多颜色/标签、将OHLC估算包装成真实订单流、把OI上涨直接解释成多头、只增加input开关但不减少计算、用更多FVG/OB框制造机构痕迹、把历史回画结果称为无重绘。

## 实施顺序

1. FinalPlan与X/WAIT合同；
2. AggVol数据语义、Method Code、质量门控；
3. 主副CVD锚点统一与日/周状态；
4. OB/FVG/iFVG/sweep状态机；
5. 逐源freshness与量能宽度；
6. winnerZone；
7. 市场时段路由和真实性能降级；
8. 静态扫描、TradingView云编译、实时/收盘/重载/回放验收。

参考：TradingView Pine v6 Limitations、Other timeframes and data、Repainting、Cumulative Volume Delta、Open Interest、Volume Profile官方文档；本次会话源码审计文件为 Web UI 上传的 SVP+ICT+VWAP+CVD 与 AggVol 当前版本。