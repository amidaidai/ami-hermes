# Pine Script request.security 静态配额规则

## 核心规则

**Pine v6 `request.security` 按编译期静态计数。三元条件、input 开关、if 块均不减配额。**

TradingView 在主脚本执行前预取所有 `request.security` 数据。40 配额上限，超过报：
`Script requests too many securities: 43. The limit is 40`

## 计数方式

1. **相同参数算 1 次**：同 symbol + 同 timeframe + 同 expression → TradingView 自动去重
2. **函数内 req 展开计数**：一个函数内 1 行 `request.security`，被调用 N 次不同参数 → 计 N 次
3. **input.bool 三元不减**：`EX_NO ? GetRequest(...) : 0` — 编译期 `GetRequest(...)` 仍计入
4. **if 块不减**：v6 支持条件内 req，但仍按静态调用点计数
5. **未使用的 req 可被优化**：变量定义但未被任何 plot/table/计算引用 → 不计数

## 副指标 HALDRO 配额展开示例

```
GetRequest(Ticker) =>
    request.security(Ticker, timeframe.period, CurrentVolume, ...)   // 1个调用点

GetExchange(typeSymbol) =>  // 被调用 4 次（SPOT1/SPOT2/PERP1/PERP2）
    EX_1 = ... GetRequest(...)  // → 5 个交易所 × 4 次调用 = 20 个唯一配额
    EX_2 = ...
    ...(共 5 个)
```

## 腾配额方法

1. **物理删除调用点**（唯一真有效）
2. **合并同参数**（TradingView 自动）
3. **计算放进 expression**：`req(tf, exp, a-b)` 代替 `req(tf, exp, a) - req(tf, exp, b)`
4. **拆成两个指标**

## 来源

- TradingCode.net: "Requests too many securities"
- Stack Overflow: Pine v6 dynamic requests (79288126)
- TradersPost: "Pine Script v6: request.security() Inside Loops"

## 验证命令

```bash
# 数调用点
grep -c "request\.security" 指标.txt

# 展开计数（手动：查函数调用次数 × 内部 req 数）
grep -n "GetExchange\|GetRequest" 指标.txt
```
