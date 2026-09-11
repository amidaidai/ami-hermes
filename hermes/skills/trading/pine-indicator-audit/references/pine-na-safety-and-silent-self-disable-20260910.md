# Pine `na` 安全与「指标静默自废」审计（2026-09-10 实案）

Pine 里最贵的一类 bug：指标**不报错、不报警**，只是悄悄把自己判为无效，
下游根据状态码把一切降级。表现是“功能整体没用”，而源码看着完全正常。

## 一、`array.sum` 遇 na 返回 na → 一条腿毒化整条聚合

### 现场证据链（BINANCE:BTCUSDT.P 15m）

```
HALDRO Valid Code  = 0
Coverage Feed Mode = 4        ← 设计只有 1=聚合 / 2=回退单图，4 = 两者皆假
Coverage Spot = 5 / Coverage Perp = 4
副表面板：🔴 S0无效 · 副源无效 · 合0%
```

### 根因链

```pine
GetRequest() → request.security(..., ignore_invalid_symbol=true)
   // 某所不存在的腿（如 COINBASE 没有永续）返回 na —— 这是设计行为，不是错

EditVolume(type) =>
    Type = array.sum(type)          // ← Pine 的 array.sum 遇 na 返回 na

PERP = Σ GetPerpEX_n                 // 一条腿 na → 整个求和 na
AggregatedVolume = SPOT + PERP       // na

usingAggregatedFeed = datatype == 'Aggregated' and AggregatedVolume >  0   // na>0  = false
fallbackToChartFeed = datatype == 'Aggregated' and AggregatedVolume <= 0   // na<=0 = false
plot(... ? 1 : ... ? 2 : 4, "Coverage Feed Mode")                           // → 4
haldroUsableA = isCryptoA and (usingAggregatedFeed or fallbackToChartFeed)  // → false
panelStateA   = not haldroUsableA ? 0 : ...                                 // → S0无效
→ 主指标 aggGateDegraded → A 级永久被禁
```

**na 的比较永远是 false**：所以 `x > 0` 和 `x <= 0` 同时为假，两个分支都进不去 ——
这是 `Coverage Feed Mode = 4` 这种“设计外值”出现的典型指纹。

**同一个文件里 OI 聚合侧是 `nz(oiBinA)+nz(oiBybA)+...`（na 安全），成交量侧漏了** ——
同类聚合散落在不同段落时，很容易只修一处。

### 修法

```pine
EditVolume(type)=>
    Type = 0.0
    for _vi = 0 to array.size(type) - 1
        Type += nz(array.get(type, _vi))     // 缺失的腿只把自己降为 0
```

修后：5 腿缺 1 → FeedMode **1**（聚合可用）；全腿缺失 → FeedMode **2**（设计内回退），
而不是掉进 4 这个异常态。覆盖率仍照实报 `聚合n/5`，**不静默削源**。

## 二、审计方法：从「可用性闸」往上追

不要逐个函数看。先找**决定指标是否可用的那个变量**（本例 `haldroUsableA`），
再沿它的每个输入往上追 na 路径：

1. 它的输入里有没有 `request.*()` 的返回值？（`ignore_invalid_symbol=true` ⇒ 可 na）
2. 这些值有没有经过 `array.sum` / 裸 `+` 而没有 `nz()` / `math.max` 保护？
3. 有没有 `> 0` / `<= 0` 这种**互补比较**同时出现在两个分支？
   → 出现就是 na 风险：两者同时为假会掉进设计外的第三态。
4. 有没有输出一个“设计外的枚举值”（如 Feed Mode 4）？→ 一定是某处比较吃了 na。

自检 grep：

```bash
grep -nE "array\.sum\(" file.pine                 # 逐个确认是否 na 安全
grep -nE "(>|<|<=|>=)\s*0" file.pine | grep -v nz    # 互补比较是 na 指纹
```

**通用规则**：任何**聚合量**（成交量、OI、成交额）如果下游要拿它判“数据是否可用”，
就必须 na 安全；否则局部的单点缺失会升级为全局功能失效。

## 三、顺带该查的两类「多面板表述不一致」

同一个状态码在不同行/不同面板被翻译成不同说法，会让分析读卡时误判。
实案：状态码 0 在协同行写 `副S0无效`、在结论行写 `副S4降权` ——
把「副指标根本没数据」说成「副指标投了降权票」。

根因：结论行的分支条件是**合并闸**（`not wired or code==0 or code==4`），
而另一行是按**状态码逐档**输出。

审计动作：对每个状态码，把所有出现它的地方列出对照，要求语义一致；
合并分支前先把状态码拆开（`not wired ? "未接" : code==4 ? "降权" : "无效"`）。
注意这类修改**不得顺带改授权逻辑** —— 只改文案分支。

## 四、相关参考

- 数字格式丢前导零（`"#.2"` 把 0.54 渲染成 `.54`）与 `"#00"` 的正确用法：
  `references/comprehensive-audit-deliverable-format.md`
- 死码清理与级联削源核实流程：`references/pine-deadcode-and-cascade-audit-20260910.md`
