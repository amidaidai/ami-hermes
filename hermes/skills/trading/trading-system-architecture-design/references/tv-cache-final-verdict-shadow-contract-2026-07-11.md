# TV缓存、FinalVerdict与影子回放契约

## 适用范围
用于 TradingView MCP → Python 决策闭环 → 风控/渲染 → 影子校准/回测 的生产验收。重点防止“数据读到了，但品种、权限或回放契约错了”。

## 1. TV缓存必须验证真实图表品种

错误模式：给 `values/data --symbol X` 传目标参数后，直接把返回值标成 X。部分客户端版本不会因此切换当前图，可能把 XAU 的 4100 价位写成 BTC 缓存。

生产协议：
1. 主动切换目标 symbol。
2. `chart_get_state` 读取真实当前 symbol。
3. 归一化交易所前缀和 `.P` 后比较。
4. 匹配后才读取 Data Window、表格、线和报价。
5. 读取完成后再校验一次 symbol，防止共享图表被其他任务切走。
6. 任一次不匹配：本轮结果不得标 fresh；旧缓存只能标 stale，不能改贴目标 symbol。

回归测试必须覆盖“当前XAU、期望BTC”时不读取、不写新鲜BTC缓存。

### 1.1 指标缓存与结构位缓存分权

`POC/VAH/VAL = null` 不代表整份 TV Data Window 无效。当前柱重新计算期间，结构位可能短暂为 `na`，而 HALDRO Valid Code、OI、CVD、Composite、EMA、MCP编码仍有效。

正确流程：
1. 先用 symbol + timestamp + 二次chart state验证整份 `tv_live` 身份。
2. 只要 Data Window/行动格存在，就提升为本轮指标权威输入。
3. POC/VAH/VAL 单独读取；若为空，仅结构位回退到同品种上一份新鲜缓存。
4. 不得因 POC 为空退回旧副指标，否则现场 `Valid Code=2` 会被误记成0，影子记录产生虚假的 `haldro_invalid`。
5. 回归测试必须覆盖“顶层POC为空、indicators有效”场景。

## 2. FinalVerdict是唯一执行权限

旧八闸门、模板评分、SVP原始等级只负责诊断。执行权只能来自：

```text
FinalVerdict.state ∈ {GO-A, GO-B}
AND FinalVerdict.executable = true
```

- `WAIT`：不执行，清空 entry/stop/target；可保留 watch_entry/watch_side。
- `NO-GO`：不执行并记录硬阻断。
- 旧闸门即使全绿，也不得把 WAIT/NO-GO 改回 GO。
- 报告要区分 WAIT 与 NO-GO，不能把等待误报成硬禁做。

## 3. 跨层数值字段先安全解析

Data Window/行动格可能返回 `等触发`、`待确认`、`—`、带逗号价格、Unicode负号及 K/M/B 缩写。禁止直接 `float(value)`。

统一解析规则：
- 等待文案、破折号、空值 → 缺失值/0；
- 去除逗号、百分号，Unicode负号转普通负号；
- K/M/B按数量级解析；
- 影子记录仅在 entry/stop/target 均为正数且风险距离大于0时落盘。

## 4. 体制只消费已闭柱OHLCV

- Binance K线数组通常最后一根未收柱，构建体制特征时默认丢弃最后一根。
- XAU MCP OHLCV优先解析结构化 JSON 的 `last_5_bars[-2]`，禁止对整段JSON做数字正则并猜OHLC顺序。
- TradingView周期参数使用明确分辨率：5m=`5`、15m=`15`、1h=`60`、4h=`240`。
- 历史不足最小样本时返回“体制未知/等待”，不得填固定VIX或演示波动率。

## 5. XAU主副指标职责

- `SVP+ICT+VWAP+CVD` 可在 OANDA:XAUUSD 五周期输出结构与MCP字段时，应真实读取并优先消费。
- HALDRO在非加密品种必须 `Valid Code=0`，只能表示不适用，不能制造方向冲突。
- XAUUSDT等回退K线只能补缺，不能覆盖OANDA TV MCP已存在的结构数据。

## 6. 影子记录必须可被同一decision_loop回放

新记录使用嵌套契约，同时可保留便于检索的扁平摘要：

```json
{
  "signal_id": "...",
  "symbol": "BTCUSDT",
  "main": {"grade":"A多","direction":"long","entry":1,"stop":0.9,"target":1.2,"rr":2},
  "dual": {"asset_is_crypto":true,"valid_code":2,"conflict":false},
  "regime": {"code":"trend","allowed_models":["fvg_pullback"],"position_multiplier":1.0},
  "risk": {"allowed":true,"risk_usd":1.0,"violations":[]},
  "final_state": "GO-A",
  "features": {}
}
```

回测器：
- 新记录直接把 `main/dual/regime/risk` 送入同一 `resolve_final_verdict()`；
- 旧扁平JSONL需有兼容转换层，不能因 `regime` 是字符串而调用 `.get()`；
- 校准器同时支持 `regime="trend"` 与 `regime={"code":"trend"}`；
- 样本不足门槛时只报告样本数，不输出伪概率。

## 7. 最小验收矩阵

1. 品种错配缓存测试。
2. WAIT/NO-GO覆盖旧GO测试。
3. 等待文案安全数值化测试。
4. 未收柱丢弃测试。
5. XAU结构化OHLCV解析测试。
6. 新嵌套shadow可直接回放测试。
7. 旧扁平shadow兼容回放测试。
8. 嵌套regime校准测试。
9. 全量测试、BTC与XAU端到端实跑。
10. Pine编译、五周期Data Window及本地/云端SHA核验。
