# Pine CE10295「main body of the script is too long」函数化配方

抓取/实测日期：2026-08-02。主指标 2957 行在 TradingView 触发 CE10295，三个大块函数化后静态扫描全绿。

## 错误本质

- `The main body of the script is too long. Try wrapping code in functions (CE10295)` = **脚本主体 IL（中间代码）超限**的编译期错误。
- 官方解法就是包函数：Pine 编译器对**函数体只编译一次**，调用点只留调用指令，把大块逻辑搬进函数能大幅缩减主体 IL。
- 官方文档原文："avoid repetitions by using functions to encapsulate oft-used segments, and call functions instead of repeating code."
- 官方来源：https://www.tradingview.com/pine-script-docs/writing/limitations/ （script compilation 段）

## 三个 Pine 硬约束（必须先懂才能安全函数化）

1. **函数不能修改全局变量**（作用域限制）：函数只能**读**全局，不能 `globalVar := x`。解法 = 函数内用**局部变量**累加，返回 tuple，在调用处 `[g1, g2, ...] = f()` 赋回全局。
2. **元组上限 16 个值**：一个函数最多返回 16 个元素。本会话 f_sweep_scan 返回 12 个，安全。
3. **历史引用保留**：`resPrice[1]` / `supPrice[1]`（如 MSS 级别）依赖全局变量赋值的 series 语义——函数返回赋值给同名全局后，历史引用**不破坏**，可安全函数化。

## 选块标准（只函数化满足全部条件的块）

- 无 `[1]`/`[2]` 等历史索引引用（或虽有但历史引用指向**全局赋值后的同名变量**）
- 纯计算，无 `plot()/fill()/line.new()` 等绘图副作用
- 无 `barstate.islast` 门控、无 `var` 持久变量
- 内部变量消费都在函数外（函数返回的全局变量后续仍被别处引用）
- 输入全部是已存在的全局变量（函数内直接读，无需传参）

## 本会话三个函数化块（模板）

| 块 | 原行数 | 函数 | 返回 tuple |
|---|---|---|---|
| 关键位矩阵（支撑/阻力 20 个 if） | 64 | `f_sup_res()` | 4 |
| 扫线扫描（双向扫/扫高扫低） | 36 | `f_sweep_scan()` | 12 |
| 评分块（趋势/反转 4 评分累加） | 48 | `f_score_setup()` | 4 |

共 148 行主体 → 3 函数 + 3 行调用。选它三块的共同点：都是**纯计算**（只读全局 close/bar_index/levels/emaBull 等，只累加局部变量，返回元组）。

### 关键位矩阵模式（f_sup_res）
```pine
f_sup_res() =>
    float supP = na
    string supN = "--"
    float resP = na
    string resN = "--"
    if not na(curVal) and curVal <= close
        supP := curVal
        supN := "VAL"
    // ... 20 个 if 判断最近支撑/阻力 ...
    [supP, supN, resP, resN]
[supPrice, supName, resPrice, resName] = f_sup_res()   // 调用处赋回全局
```

### 评分块模式（f_score_setup）
```pine
f_score_setup() =>
    int tL = 0
    int tS = 0
    int rL = 0
    int rS = 0
    tL += priceAboveS ? 2 : 0
    // ... 44 行累加 ...
    [math.min(math.max(tL, 0), 10), math.min(math.max(tS, 0), 10), math.min(math.max(rL, 0), 10), math.min(math.max(rS, 0), 10)]
[trendLongScore, trendShortScore, reversalLongScore, reversalShortScore] = f_score_setup()
```

## 关键陷阱

- **CE10295 是编译期错误，静态扫描测不到**（`pine_static_scan.py` 只测配额/未定义变量/重复def，抓不到 IL 超限）。必须让用户贴回 TV 实测编译确认。
- **重复 typed-def 误报**：扫描器把函数内局部变量（`supP`/`hCount`/`tL` 等）与全局同名变量报"重复 def"——这是 Pine 合法的（函数作用域隔离），是误报，不是缺陷。
- **先全部验证再统一应用**：函数化涉及多行替换，用「两阶段」（先 assert 所有 old 存在，全过再 replace+写盘），避免 assert 中途炸掉丢盘。
- **函数定义位置**：Pine 自上而下编译，函数定义必须在调用之前；调用处返回 tuple 赋给全局变量的位置，必须在该全局变量的**首次消费之前**。
- **若还报 CE10295**：下一个候选是行动格文本构建块（`f_pnl_row` 系列约 90 行）+ 磁吸扫描块（for 循环约 70 行）。优先函数化纯计算块，绘图块（plot/fill/table）最后动。

## 验证清单（函数化后必跑）

```python
# 1. 每个函数定义唯一
for fn in ['f_sup_res() =>', 'f_sweep_scan() =>', 'f_score_setup() =>']:
    assert len([l for l in lines if l.strip()==fn]) == 1
# 2. 每个调用唯一
# 3. 旧顶层代码已移除（不再有顶层 'trendLongScore +=' 等）
# 4. 函数内局部变量不残留（supP/hCount/tL 等只在函数体内）
# 5. 全局消费链完好（mssLongLevel/pullbackLevelPrice/longBreakPrice 仍被消费）
```

最终仍以 TradingView 实际编译回执为准。
