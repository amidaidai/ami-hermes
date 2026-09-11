# Pine：一条 na 腿毒化整条聚合链（2026-09-10 实战 P0）

## 症状

副指标（5 所聚合成交量）在用户主战场 `BINANCE:BTCUSDT.P` 上**永久自废**：

```
Coverage Feed Mode   = 4      ← 设计只有 1聚合 / 2回退单图，4 = 两者皆假
Coverage Exchanges   = 4/5
Coverage Spot = 5  Coverage Perp = 4
Exchange Dominance % = 0
HALDRO Valid Code    = 0
面板：🔴 S0无效 · 副源无效 · 合0%
```

下游连锁：副指标判自己无效 → 主指标判定为「降权/未授权」→ **A 级授权永久被禁**。
注意主指标行为是**正确的**（fail-closed），错的是副指标的数据链。

## 机制

```pine
GetRequest(Ticker) =>
    GetVolume = request.security(Ticker, timeframe.period, f(),
                                 gaps=barmerge.gaps_on, ignore_invalid_symbol=true)

EditVolume(type) =>
    Type = array.sum(type)          // ← 元凶
    ...

PERP = GetPerpEX_1 + ... + GetPerpEX_5
AggregatedVolume = SPOT + PERP

usingAggregatedFeed = datatype == 'Aggregated' and AggregatedVolume >  0
fallbackToChartFeed = datatype == 'Aggregated' and AggregatedVolume <= 0
plot(usingAggregatedFeed ? 1 : fallbackToChartFeed ? 2 : 4, "Coverage Feed Mode")
```

1. `ignore_invalid_symbol=true` 对外汇/无该腿的所（**COINBASE 没有永续**）返回 `na` —— 这是**设计行为**，不是错误。
2. Pine 的 `array.sum` 在**数组只含 na** 时返回 `na`；**有非 na 元素则忽略 na**，求和其余
   （官方语义，2026-09-10 核实。本文档早先写的「遇任一 na 返回 na」**是错的**，已纠正）。
   COINBASE 的 `USDT.P` 与 `USD.P` **两个永续后缀都不存在** → 该格 array 只含 na → 返回 na。
3. 于是 `PERP` 求和变 `na` → `AggregatedVolume` 变 `na`。
4. **`na > 0` 和 `na <= 0` 在 Pine 里都是 `false`** —— 两个分支同时落空，
   代码静默走进 `4` 这个「不该发生」的分支。
5. `haldroUsable = isCrypto and (usingAggregatedFeed or fallbackToChartFeed)` → `false`
   → 状态机把「数据缺失」当成「指标无效」。

**为什么难发现**：没有任何报错。所有比较都合法，只是一律为假。
`Coverage Spot = 5` 说明同一份代码里的 SPOT 侧完全正常 —— 只有 PERP 侧塌了。

## 修法

把每个求和改成 na 安全累加，**缺失的腿只降级自己，不毒化整条链**：

```pine
EditVolume(type) =>
    Type = 0.0
    for _vi = 0 to array.size(type) - 1
        Type += nz(array.get(type, _vi))
    ...
```

修后行为：

| 情形 | 修前 | 修后 |
|---|---|---|
| 某所两条腿都 na（如 COINBASE 无永续） | FeedMode **4**（异常） | FeedMode **1**（聚合可用） |
| 某所只缺一条腿 | FeedMode 1（本来就正常） | FeedMode **1**（**行为完全不变**） |
| 全腿缺失 | FeedMode 4（异常） | FeedMode **2**（设计内的回退单图） |

**重要推论（让改动可被信任）**：`Σ nz(x_i)` 对「部分 na」场景**行为完全不变**
（`nz(na) + 有效值 == 原 array.sum 结果`），**只把「全 na」从 na 改成 0**。
→ 因此可以声称本次改动**没有改动任何原本工作正常的路径**，但必须用算式复算钉住，
不要只说「应该不影响」。

**不违反「不静默削源」**：覆盖率行仍照实报 `聚合4/5`、`Stale Venue Count` 照常计数，
缺失是可见的。毒化 ≠ 保护。

## 通类规则（写作时的自检）

- 任何跨来源求和/聚合（成交量、OI、多所价格、余额）**一律 `nz()` 逐元素累加**，
  不要用 `array.sum()` / 裸 `+` 链。同一份代码里 OI 侧可能已经用了 `nz()` 而成交量侧漏了 ——
  **审计时要把对称的两条链放在一起比对**。
- 只要代码里有 `x > 0` / `x <= 0` 这类互补判断，就要问一句「x 为 na 时会怎样」：
  答案是两个分支都不走。真正的三态判断要显式写 `na(x) ? ... : ...`。
- `ignore_invalid_symbol=true` 的下游必须假定 `na` 是**常态输入**，不是异常。

## 验收：怎么确认跑的是修好的版本

不要信源码读取 —— `pine_open` 只返回行数、`pine_list_scripts` 有缓存。
**用一个「旧版必然为 X、新版不可能为 X」行为判据**：

- 旧版：`AggregatedVolume` 必为 na ⇒ `Feed Mode = 4` 且 `Exchange Dominance % = 0`
- 新版：`AggregatedVolume` 必为「各可用腿之和」 ⇒ `Feed Mode ∈ {1, 2}`，
  有可用腿时 `Exchange Dominance % > 0`

所以看到 `Feed Mode = 4` + `Dominance = 0` 就可以断定**图表上跑的还是旧版**，
哪怕编辑器里显示的是新源码。修好后实测 `Feed Mode 4→1`、`Dominance 0→40`、
`Valid Code 0→2`、`OI/Flow/Composite/LSR` 由空变真值。

## 附：本类的快速筛查

```bash
# 找出所有裸求和（可疑点）
grep -nE "array\.sum\(" script.pine
grep -nE "^\s*[A-Z_]+\s*=\s*[A-Za-z_]+[0-9]?\s*\+\s*[A-Za-z_]" script.pine
# 找出互补比较（na 时两分支都落空）
grep -nE "[<>]=?\s*0" script.pine
# 同一文件里对称链的 nz 覆盖率应当是「都用了」或「都没用」，不该一半一半
grep -c "nz(" script.pine
```
