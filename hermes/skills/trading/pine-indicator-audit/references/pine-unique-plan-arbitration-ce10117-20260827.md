# Pine唯一方向仲裁与CE10117瘦身实证（2026-08-27）

## 触发场景

- 多空候选可能同时成立；评分、Entry/Stop/Target、面板和Data Window方向不一致。
- 方向化修复后客户端出现CE10117，而`translate_light`仍为0错误。

## 唯一方向仲裁

1. 分别计算原始多/空等级：A=3、B=2、C=1、无=0。
2. X先归零方向。
3. 先比较等级；只有等级相同时才用多头优先兜底。
4. 生成`selectedPlanDir/Long/Short/Grade`。
5. Entry、Stop、Target、R:R、触发、位置、HTF、CVD/SMT、VWAP延展、AggVol、OI、行动格和MCP Side全部消费该方向。
6. 客观结构可与候选方向相反，但必须进入方向化冲突并在结论中明确`⚠冲突`；不得静默算作支持。

## Value Area

TradingView官方口径：从POC向外比较候选桶；候选加入后若超过剩余目标，立即停止且不纳入。不要无条件累计至首次达到/超过70%。

## CE10117实证

一次方向化改动客户端返回`101109 > 100256`，而`translate_light`为0/0。有效瘦身顺序：

1. 删除不参与执行合同的低价值Data Window plot（重复诊断、静态输入回显、原始中间值）。
2. 删除已不显示、只生成废弃字符串的面板UDF及其循环。
3. 保留唯一方向、Entry/Stop/Target、Packed Bus、五所成交量/四所OI及核心风险闸门。
4. 重新注入完整源码，等待客户端编译完成；不能以smart_compile初始`has_errors=false`为终态，需等待并再次读取Monaco markers和控制台。
5. 运行态读取Data Window和Pine table，证明新study已替换旧实例。

本次删除13个低价值DW plot和2条废弃面板计算链后，源码从245822降至241136字节；客户端markers=0且成功保存。字节数不是token证明，只是瘦身前后记录。
