# Pine v6 迁移 + 新增 ICT 功能实案 (2026-07-09)

## 背景

用户上传主指标 (SVP+ICT+VWAP+CVD, v5, 3225行) 和副指标 (HALDRO AggVol, v6, 502行) 要求审计。
审计发现三个问题：(1) cvdBearStars/cvdBullStars 未定义致编译失败；(2) token 超限 81303 > 80000；(3) 小币种 SVP 只显示几行。
修复后用户要求社区全面扫描看有什么可添加的，随后要求实现最值得做的 5 件事。

## v5→v6 迁移

### Breaking change 扫描结果（主指标）

| 检查项 | 结果 | 说明 |
|--------|------|------|
| na(bool) | ✓ 0处 | 431个 bool 变量无 na() 调用 |
| nz(bool) | ✓ 0处 | 无 nz() 调用在 bool 上 |
| fixnan(bool) | ✓ 0处 | 2处 fixnan 在 float 表达式上，v6 合法 |
| UDT field[] | ✓ 0处 | 无 myUDT.field[n] 模式 |
| if floatVar | ✓ 0处 | 无隐式 float→bool 转换 |
| style=na | ✓ 0处 | 无 na 替代内置常量 |
| plot offset series | ✓ 0处 | 无 series offset |

### 迁移改动（仅2行）

```
//@version=5  →  //@version=6
indicator("SVP+ICT+VWAP+CVD", overlay=true,  →  + dynamic_requests=true,
```

## 新增 ICT 功能

### Order Block 检测算法

```
Bullish OB = BOS↑ 后往回找最后一根阴线（位移K），它前面那根阳线 = OB
Bearish OB = BOS↓ 后往回找最后一根阳线，它前面那根阴线 = OB
```

Pine 实现（关键片段）：
```pine
if obBullDetected
    int obOffset = na
    for k = 1 to 10
        if close[k] < open[k]
            obOffset := k
            break
    if not na(obOffset) and obOffset + 1 <= 10 and close[obOffset + 1] > open[obOffset + 1]
        float obTop = high[obOffset + 1]
        float obBot = low[obOffset + 1]
        box nb = SHOW_OB ? box.new(...) : na
        array.push(obList, OBZone.new(nb, obTop, obBot, true, false, false, bar_index - obOffset - 1))
```

### BOS/CHoCH 检测

```pine
// BOS: close突破同方向swing; CHoCH: close突破反方向swing
bool bosBull = SHOW_BOS_CHOCH and not na(lastSwingHigh) and close > lastSwingHigh and close[1] <= lastSwingHigh
bool bosBear = SHOW_BOS_CHOCH and not na(lastSwingLow) and close < lastSwingLow and close[1] >= lastSwingLow
```

### Breaker Block

OB 被反向突破后变色标记：
```pine
if SHOW_BREAKER and array.size(obList) > 0
    for oi = array.size(obList) - 1 to 0 by -1
        OBZone ob = array.get(obList, oi)
        if not ob.mitigated and not ob.isBreaker
            bool broken = ob.isBull ? close < ob.bot : close > ob.top
            if broken and barstate.isconfirmed
                ob.isBreaker := true
                box.set_bgcolor(ob.bx, color.new(ob.isBull ? BRK_BULL_COL : BRK_BEAR_COL, OB_FILL_TRANSP))
```

### Liquidity Void

两K间价格跳跃空隙（与FVG三K失衡不同）：
```pine
bool lvBull = SHOW_LIQ_VOID and low[1] > high[3] and close > open
bool lvBear = SHOW_LIQ_VOID and high[1] < low[3] and close < open
```

### 面板/MCP/Alert 集成

- 面板确认行：新增 `ckOb` = `OB✓`/`OB~` + `bosChochText` = `BOS↑`/`BOS↓`/`CHoCH↑`/`CHoCH↓`
- MCP Data Window：新增 3 个 plot（`MCP OB Signal` / `MCP BOS/CHoCH` / `MCP Liq Void`）
- alertcondition：新增 6 个（BOS↑↓ / CHoCH↑↓ / OB缓解↑↓）
- confirmScore：追加 OB 汇合加分 +1
- bcDirectRaw：追加 OB/Breaker 汇合条件

## Token 压缩

添加新功能后 token 从 ~77,455 涨到 ~81,313，超过 80,000 限制。
压缩措施：
1. 删除独立注释行（非 section header、非 input tooltip）：~96 行
2. 删除多余空行：~27 行
3. 短缩长 tooltip 字符串

最终：2,807 行 / 182,139 字符 / ~78,175 tokens ✓

## execute_code 变量不持久陷阱

**关键教训**：execute_code 的 Python 变量在不同调用之间不持久。多步文件修改必须在同一个脚本内完成读取→修改→写入的完整闭环。分步执行会导致后续步骤找不到前面步骤的 `lines` 变量，静默失败（插入不生效但无报错）。

本次实案中，OB 检测代码和输入参数被"插入"后但在下一个 execute_code 调用中丢失，导致最终文件有面板/MCP/alert 引用但缺少核心检测代码和输入定义。

**正确模式**：
```python
# 在一个脚本内完成全部操作
code = open('file.pine').read()
code = code.replace('old1', 'new1')  # 改1
code = code.replace('old2', 'new2')  # 改2
code = code.replace('old3', 'new3')  # 改3
# ... 所有修改 ...
open('file.pine', 'w').write(code)   # 一次性写入
```

## 编译错误追踪（迁移后 TradingView 实测）

用户在 TradingView 编译时遇到 3 个错误，分两轮修复：

### 第一轮：3 个错误

**错误1（L6:23）**：`dynamic_requests` 重复参数
- 根因：execute_code 的 `code.replace()` 在 indicator() 第一行后插入了 `dynamic_requests=true,`，但原文件的闭合括号行也被替换添加了 `dynamic_requests=true)`，产生两处
- 修法：用 patch 工具直接删除 L6 的多余 `dynamic_requests=true)`

**错误2&3（L2029/2030:108）**：`na(series bool)` 不合法
- 根因：HTF FVG 检测中 `na(hBull[1])` 和 `na(hBear[1])` 在 v5 合法（bool 可为 na），v6 不合法（bool 不可为 na）
- `hBull`/`hBear` 是 `request.security()` 返回 tuple 的 bool 字段
- 修法：`na(hBull[1])` → `not hBull[1]`，`na(hBear[1])` → `not hBear[1]`
- 清理：原 `na(hBull[1]) or not hBull[1]` → `not hBull[1] or not hBull[1]` → 去重为 `not hBull[1]`

### 第二轮：1 个残留错误

**错误（L6:23）**：桌面文件未同步
- 根因：execute_code 修复了源文件但 `shutil.copy2()` 因 Python raw string 语法错误未执行
- 修法：改用 `patch` 工具修源文件 + `terminal` 工具 `cp` 到桌面 + `head -7` 验证
- 教训：修改后必须用 terminal cp 单独同步桌面文件并验证

## 最终文件统计

| 指标 | 原始 v5 | 修复后 | v6+新功能后 |
|------|---------|--------|------------|
| 行数 | 3,225 | 3,072 | 2,807 |
| 字符 | 189,427 | 180,462 | 182,139 |
| 预估 token | 81,303 | ~77,455 | ~78,175 |
| Data Window plots | 11 | 11 | 14 (+3) |
| alertcondition | 14 | 14 | 20 (+6) |
| request.security | 10 | 10 | 10 |

## 社区 2025-2026 前沿扫描来源

- Pine v6 release notes: https://blog.traderspost.io/article/pine-script-v6-release-notes-explained
- Pine v6 footprint: https://www.tradingview.com/blog/en/volume-footprints-in-pine-scripts-56908/
- ICT Top 30 strategies 2026: https://medium.com/@smcTradingStrategies/top-30-smart-money-trading-strategies-for-2026-29b51e372284
- joshyattridge/smart-money-concepts (1.8k GitHub stars): https://github.com/joshyattridge/smart-money-concepts
- LuxAlgo Pine performance: https://www.luxalgo.com/blog/5-causes-of-slow-pine-scripts-on-tradingview/
- Footprint strategies: https://supa.is/article/tradingview-pine-script-footprint-order-flow-strategy-institutional-volume-2026
- TV token limit discussion: https://www.reddit.com/r/TradingView/comments/1d7tsk2/compiled_code_contains_too_many_tokens_92610_the/