# 20260814 第一批多市场修复 + Pine 元组三坑 + TV 注入验证法

来源：20260814 会话。P2 表格修复 + 第一批多市场适配（5 项）全部落地，两文件全量编译 0 错 0 警，真实 TV 环境模拟验证通过。

## 一、Pine 元组三坑（本次实测，编译端点 translate_light 全量编译逐坑确认）

1. **三元不能返回元组**：`cond ? f_pack() : [na, na, na, na]` → "Ternary operations cannot return tuples"。
2. **元组字面量赋值语法错误**：`[a, b, c, d] = [na, na, na, na]` → "Syntax error at input {value}"。
3. **if 块内元组重赋值 := 语法错误**：父作用域已声明变量在 if 块内 `[a, b] := f()` → Syntax error；`=` 则 shadow 父作用域变量（警告不报错）。

**终解（已验证）**：request 短路函数化时，把 if/else 收进 pack 函数内部，两分支各自解构+返回元组，顶层一次性解构声明：

```
f_htf_fvg_pack() =>
    if fvgHtfValid
        [pf1, pf2, pf3, pf4] = request.security(...)
        [pf1, pf2, pf3, pf4]
    else
        bool df1 = false
        bool df2 = false
        float df3 = na
        float df4 = na
        [df1, df2, df3, df4]
[hBull, hBear, hTop, hBot] = f_htf_fvg_pack()
```

注意 else 分支 bool 用 `false` 不能用 `na`（`bool x = na` 报类型错误，na 默认 float）。

## 二、TV 桌面模拟验证注入法（大源码不经 MCP 参数）

问题：22 万字符源码直接内嵌 JS 模板 `${JSON.stringify(src)}` 会随机报 ReferenceError；atob 解码后中文变 mojibake（b64 按 UTF-8 字节编码，atob 返回 latin1）。

**可靠四步（node + connection.js evaluateAsync）**：
1. node 侧 `b64 = Buffer.from(src, 'utf8').toString('base64')`，evaluate 设 `window.__pineB64`（纯 ASCII 安全）。
2. 页面内 `atob` → `Uint8Array` → `new TextDecoder('utf-8').decode(bytes)` → Monaco `best.setValue(decoded)`（Monaco 查找复用 core/pine.js FIND_MONACO 逻辑）。
3. 点按钮：中文界面 title="添加到图表"（新脚本）或"图表更新"（已有实例）；编译失败后按钮 title="编译错误: CE10004 · 在Pine编辑器打开"，点击后该按钮消失=编译成功（与 Monaco markers 双验证）。
4. `data_get_pine_tables`（study_filter 用指标名子串）结构化读行动格逐行文本验证渲染——比截图更可靠（视觉模型 403 时替代方案）。

坑：TV 图表只有一个"用户脚本实例槽"，pine 编辑器注入新源码后"图表更新"会把前一个指标实例替换掉；两个指标共存需先保存命名脚本再分别添加（模拟验证逐个上即可）。

## 三、第一批多市场修复（已落地 5 项）

1. **股票/金属分布图周期僵死 D**（主 L617）：`marketStock or marketMetal ? "D"` → `getAutoProfileTF()`（<1h→D、1h-4h→W、4h-1d→M、1d+→12M），与加密同多级自适应。日线图分布图不再只有 1 根 K。
2. **股票/指数无效 KZ**（主 L931 前）：`kzAsiaValid/kzLondonValid = MARKET_ADAPTIVE_ENGINE ? not (marketStock or marketIndex) : true` 只门控 inKillZone*，不动 isAsia/isLondon 会话池。美股盘前噪音不再污染 confirmScore+1。
3. **外汇现货 VWAP tick量标注**（主 f_panel_watch）：`vwapAnchorTag += marketForex and not autoFutures ? "·tick量"`。社区共识（Trader-Dale）：现货外汇无中央交易所，VWAP 不可靠。
4. **副指标外汇现货 CVD tick量标注**（副 L454 前）：`fxTickFeedA = syminfo.type == 'forex'`，cvdQualityTxtA 尾部追加 `·tick量`。边界：股票/期货/加密永续是真实量不受影响。
5. **遗留5：HTF FVG/OB request 函数化**（主 L2146 起）：pack 函数 + fvgHtfValid 门控，免费档 request 8→6。

## 四、第二批落地（20260814 同会话晚段）

- **副指标 CVD 升档**（中档→高档）：CVD_SRC 输入（默认'低周期聚合(1m)'，可回退'K线估算(wick+body)'）。实现=f_cvd_ltf_pack 函数内 if/else 返回 [lH,lL,lC,lV] 四数组（空数组分支=回退信号），f_sum_ltf 循环 1m 收盘对中点分配求和；`Delta = array.size(lC_ltf) > 0 ? deltaLtf : deltaWick`。request 29→30/40 ✓。门控=1m 图(curTfSec<=60)/非加密自动回退 wick 版。
- **副指标结论行信号新鲜度**：`int strongBarsA = ta.barssince(finalStrongA)`，actText 尾部追加 `·新`（本根）/`·信号N根前`（na 不显示）。真实渲染验证："上涨衰竭 · 疑似空头回补·信号14根前"。
- **DST 自动——误判撤销**：TZ_ASIA/TZ_LONDON/TZ_NY 本就是 IANA 名称（Asia/Shanghai、Europe/London、America/New_York）自动夏冬令时。上轮"22:35 北京仍 ⚡纽47m=漂移"是误判：加密市场 effKzNYTime=0820-1130（北京 20:20-23:30 夏令时），22:43+47m=23:30 精确吻合。**审计教训：推算 KZ 窗口前必须核对该市场的 effKz*Time 分支值，加密≠默认 0930-1030。**

## 五、本轮评分基线（供后续 diff）

主指标 96（编译 100/配额 96/逻辑 95/诚实 96/决策辅助 93）；副指标 95（100/95/93/96/90）。副指标保持 7 行（用户拍板，5 行精简定稿不落地）。

## 六、第三批全面联网审计结论（20260814 三项全部暂缓/否决）

| 增强 | 社区证据 | 否决/暂缓理由 |
|---|---|---|
| 期货 RTH 开盘 DO | ICT Premium/Discount 用前日区间均衡或 RTH 开盘价；FluxCharts/TradingFinder 确认 | ①非主力品种（用户主战场币安+XAU）②涉及溢价/折价决策逻辑（pdPos 禁追过滤）③TV 期货 "D" 周期 session 语义（RTH/ETH）需单独验证——三者叠加风险>价值 |
| Air Pocket (LVN 薄量区) | Feels 18% 阈值、NinjaTrader "air pockets rip through violently"、Reddit SMC imbalance | **主指标已 254/254 满配额**（input 201 + plot 43 + alert 1 + request 9），加 3 input（开关/阈值/色）必触发 CE10116；且直方图短行肉眼已可见，增量有限 |
| 隐背离 Hidden Divergence | zitaplus/TV CVD PRO：价格 higher low + CVD lower low = 延续 | 与现有"顺确认"（cvdRising+close>=close[5]）职责重叠；估算 CVD 上假信号多；进阶概念增认知负担——违反"看不懂=失败设计" |

**满配额现状（重要）**：主指标 pine_external_elements_scan 实测 `input=201 + plot=43 + alert=1 + request=9 = 254/254`。input 构成 bool 86/color 33/int 31/string 25/float 12/session 7/timeframe 4/source 3，**0 死 input**。plot 分布：27-29 DW-only（MCP 数据总线）+ 7 price_scale（右轴 POC/VAH/VAL/nPOC/W/M VWAP/DO）+ 7 图上。**结论：主指标已到收敛态，无可安全腾挪配额；任何新功能唯一路径=DW plot 编码合并（改 MCP 总线契约，副指标解码端配合，需单独立项）。** 副指标仍有余量（30/40 request、41/64 plot）但信息密度已到顶（用户 20260813 原话"再加即噪音"）。

**本轮迭代正确动作=不做加法**：功能冻结铁律 + 多重审计的价值正在于阻止诱人但不必要/超配额/重叠的功能堆砌。审计否决本身是交付。

## 七、终局与文案偏好（20260814 收尾）

**第三批最终回滚**：RTH DO + Air Pocket 曾先实现后超 token（CE10117 101,085/100,256 超 829），终局**完整回滚**。回滚后文件精确 242,240 字节 = 22:43 实测通过版字节级一致（回滚正确性的铁证，见 ce10117-token-limit.md 修正终版）。交付版=第二批完成版全注释（242,240 字节），副指标=专业压宽版。

**副指标文案偏好（用户点名：结论专业一点，压缩一下宽度，信号也是）**：
- 术语化、去口语："疑似/别急追/风险大/踩踏杀跌" → "挤空冲顶/价量背离/抛压主导/涨势衰竭/抛售踩踏"；每个结论分支=状态词+动作词（防反转/勿追/慎追/回补），宽度平均压 40%。
- 信号行："多向未确认/空向未确认" → "多头未确认/空头未确认"；缺票维度空格分隔 → 点分隔（"缺OI·HTF"）。
- 铁律扩展：副指标表格文案风格 = 专业术语 + 主词化紧凑，与"主词化压宽"偏好一致；审计/修改副指标文案时不得引入口语词。
