# Pine Script Security Quota Pitfall (P0 · 2026-06-27 实战验证)

## 铁律

**`request.security` 按编译期静态计数。三元条件、`if` 块、`input.bool` 开关包裹都不减计数。**

TradingView 在主脚本运行前预取全部 `request.security` 调用。无论运行时条件是否触发，只要调用点在源码中存在且结果被引用，就计入 40 配额。

## 证据

1. TradingCode 官方文档 (`tradingcode.net/tradingview/request-too-many-securities`)：同参数调用计一次，未使用调用优化掉。但在函数内部被不同参数展开的调用全部计数。
2. Stack Overflow (2025-11 Pine v6)：实测 `request.security` 在条件块内仍执行，因为 TV 在主脚本前预取。
3. TradingView Pine v6 动态请求文档 (TradersPost)：v6 允许在循环/条件内放置 `request.security`，但**不影响配额计法**——放在条件块内只是简化语法，不改变编译期计数。

## 错误做法

```pine
// ❌ 以为切开关能省配额——实际不能
SHOW_OI = input.bool(true, 'OI聚合')
float oiAgg = SHOW_OI ? request.security('BINANCE:BTCUSDT.P_OI', ...) : 0.0
// request.security 即使 SHOW_OI=false 仍计入 40 配额
```

```pine
// ❌ 以为三元回退能省配额——实际不能
VAREUR = coinusd == 'EUR' ? request.security('FX_IDC:EURUSD', ...) : na
// request.security 不管 coinusd 选什么都被计数
```

## 正确做法

**唯一减配额的路径：物理删除 request.security 调用点。**

```pine
// ✅ 必须从 GetExchange 函数里删掉不需要的交易所行
GetExchange(typeSymbol)=>
    EX_1 = EX_NO1 ? GetRequest(GetTicker(IN_NO1, typeSymbol)) : 0
    EX_2 = EX_NO2 ? GetRequest(GetTicker(IN_NO2, typeSymbol)) : 0
    // 删掉 EX_3~EX_9 → 省 7×4=28 配额
    [EX_1, EX_2]  // 返回较少元素
```

删除调用点后需同步修改：
- GetExchange 返回值元组维度
- 所有下游解构赋值
- EXlist/EXnames/EXcolors 数组大小
- 循环边界 `for i = 0 to N`
- 排序和绘图数量

## 实战案例（2026-06-27 副指标 OI 聚合）

**问题**：HALDRO 聚合量 9 所（36配额）+ EUR/RUB（2）+ OI（1）= 39/40。欲加 4 源 OI 聚合（+4）→ 43 编译失败。

**修法**：
1. 从 `GetExchange` 物理删除 4 个 `GetRequest` 调用点（9→5 所）→ 省 16 配额
2. 添加 `f_oi()` 4 源 OI 聚合 → +4 配额
3. 最终 27/40，12 余量

## 审计检查清单

每次审查 Pine 指标时必须确认：
```bash
# 1. 先数静态调用点（不是 input 开关）
grep -c "request\.security" indicator.txt
# 2. 展开函数调用次数（如 GetRequest 被 GetExchange 调用 4 次 × 5 所）
# 3. 确认同参数合并（如 BINANCE:BTCUSDT.P_OI 在不同地方被调用可能合并）
# 4. 总计 ≤ 40
```

## 通用教训

任何声称"关掉某某省配额"的 Pine 指标 tooltip 都需验证——如果调用点仍在源码中，关了也不省。正确 tooltip 应为：`关=仅用单源。注：Pine 静态计数不省配额，关仅减运行时负载。`
