# Pine 双指标客户端编译证据与 Basic 双脚本验收（2026-09-01）

## 适用范围

用于 Pine 主执行指标 + 副确认指标的客户端交付，尤其是 Basic 账号、长源码、单一 Packed Bus 和 TradingView Pine Editor。它补充服务器端 `translate_light`、静态扫描和源码合同审计，不替代它们。

## 证据等级

必须把以下结果分开记录：

1. **源码/静态层**：行数、字符数、换行、request/plot/input/object 粗估、语义断言。
2. **服务器编译层**：`translate_light` 的 HTTP 状态、`errors2`、`warnings2`。
3. **客户端编译层**：Pine Editor 实际源码、Add/Update on chart、Monaco markers、Pine Console。
4. **图表运行层**：`chart_get_state`、Pine table、Data Window/study values、截图、必要时 Bar Replay/Profiler。

`translate_light` 返回 0 错 0 警，只能证明服务器接受语法；不能证明客户端 CE10117、运行时对象、输入接线或脚本已挂图。

## 已验证的客户端闭环

### A. 源码身份证明

- 本地源文件先做 LF 规范化后的字符数、行数和 SHA-256。
- 用 Windows Unicode clipboard 粘贴到 Pine Editor。
- 粘贴后必须通过 `pine_get_source` 读回完整模型，再在本地比较规范化后的字符数、行数和 SHA-256。
- 只看到编辑器末尾文本或 textarea 的短尾部，不算完整读回。
- 本轮实测证明：本地与编辑器读回可做到 `exact=True`；AggVol 的 CRLF 读回也应先规范化再比对。

### B. 客户端编译与更新

1. 先记录 `chart_get_state` 的 symbol、resolution、study entity id/name。
2. 确认编辑器读回和本地源一致后，点击“添加到图表/图表更新”，不要把“保存脚本”当作编译成功。
3. 等 Pine Console 出现“编译中”结束；长脚本不要在 pending 时重复点击。
4. 同时读取 `pine_get_errors`、Pine Console 和 `chart_get_state`。
5. 只有当 errors=0、图表 study 名称正确、图例不再显示 `Error: cannot compile script`，才算客户端更新成功。
6. 最后读取 `data_get_pine_tables` 和 `data_get_study_values`；表格/数据窗口仍是运行态证据。

本轮实际遇到过客户端 CE10117：`Compiled code contains too many tokens: 101245. The limit is 100256`。通过删除会被实际编译的冗余行动格路径、未消费返回字段和单选项输入后，SVP 客户端出现“完成/已在图表上更新”，并且 `pine_get_errors` 返回 `has_errors=false`。这是“必须实际编译后再判断”的证据，不应由源码字符数代替。

## CE10117 瘦身原则

- 先删重复消费端、未消费的 UDF 返回字段、只有一个选项的输入、死的 Data Window/面板变量。
- 静态显示“死变量”删除后，编译 Token 可能完全不变，因为编译器本来就会优化掉它；必须用客户端重新编译测量。
- 真正能稳定降 Token 的通常是删除仍被编译的分支、重复字符串拼装、重复的表格路径和冗余输入，不是删除注释。
- 不得为压 Token 静默删除五所成交量、四所 OI、Packed Bus、主指标 Entry/Stop/Target 或 X/WAIT 闸门。
- 任何瘦身后都要重跑：合同断言、Packed Bus 随机/边界往返、服务器编译和客户端编译。

## Basic 双指标身份护栏

Basic 的最大指标数和内置 Volume 的计数方式必须以现场 `chart_get_state` 为准。Pine Editor 的“新建/打开/添加”可能因为当前脚本身份、未保存脚本或已存在实体而更新/替换某个 study，而不是新增实体。

因此：

- 不要仅凭 Add 按钮返回成功就声称“双指标并列”。
- 每次 Add/Update 后都重新读取 study entity id/name；必须明确看到主指标和副指标同时存在。
- 需要保留旧版时，本地先复制到日期目录；TradingView 端使用明确的已保存、不同名称的脚本身份，并在每次切换后回读标题、源码和 chart state。
- 如果新增一个脚本后旧 study 消失，停止继续操作，先恢复主/副各自实体；这是一条验收护栏，不是“添加成功”的证据。
- 最终主指标的唯一 `input.source()` 必须实际选择副指标的 Basic Packed Bus plot；字符串、名称或同名脚本不等于真实接线。

本轮没有把“最终双指标并列”作为已完成事实，因为现场反复出现脚本实体被更新/替换的情况；后续必须以两实体 chart state + 主表 S 状态 + Data Window 一致性共同验收。

## 双指标运行态最小清单

### SVP 主指标

- X 优先于 WAIT，WAIT 优先于 A，A 优先于 B/C。
- `finalHardBlock` 必须覆盖主 X、AggVol S3/S4、选定方向结构冲突和 SMT 反向冲突。
- X/WAIT 时执行 Entry/Stop/Target 为空；B/C 价格只能是人工观察字段。
- 扫线要区分“穿越后收回位内”与“收盘留在位外的突破”。
- FVG 距离必须是区间距离；OB 边缘触碰不应默认等同于完全缓解。

### AggVol 副指标

- 非加密资产必须显示不参与方向，不能继续显示加密聚合的买卖叙事。
- 单一有效 OI 源不能显示跨所 100% 共识。
- 强确认必须收线；盘中只显示候选/降权。
- 五所成交量和四所 OI 不得为了压配额而静默削减。
- CVD 是 OHLC/低周期价格行为估算，只能确认、降级或否决，不能独立授权。

### 总线

- 当前合同号为 `22002`；旧合同不能静默解码。
- 建议字段：合同、S0–S4、同窗口价格方向、OI 方向、OI 共识、定点 OI 变化率和 CVD 背景码。
- 编码/解码必须覆盖边界，并证明最大值低于 `2^53`。
- 本轮用 13,600 组随机＋边界样本验证，失败数为 0。

## 截图与最终报告

最终截图应同时包含：价格 K 线、右侧价格轴、主指标行动格和下方 CVD/成交量窗格，并确认没有红色编译错误。截图是客户端现场证据，不可用旧图冒充新版本。

最终报告必须分别写：

- 服务器编译是否通过；
- 客户端编译是否通过；
- 图表是否同时存在主/副实体；
- 总线是否真实接线、合同和状态是否一致；
- 哪些检查尚未完成（例如 BTC、Bar Replay、Profiler、真实源时间戳）。

不要把“云编译通过”“编辑器保存成功”或“某一个 study 更新成功”扩写成“生产双指标交付完成”。
