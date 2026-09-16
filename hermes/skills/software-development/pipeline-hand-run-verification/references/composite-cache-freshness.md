# 组合型缓存的逐字段体检

## 问题

一个 JSON 里装多个数据源的快照（外层一个 `ts`，内层每个源各自的 `ts` / 状态位）。cron 每次整篇重写 → **外层 mtime 永远很新**。于是“看 mtime 判新鲜”在单源文件上够用，在组合型文件上会骗人。

已实测的失效形态：外层 mtime 12 分钟，内层价格快照停在 64,658（当时实盘 76,000+，偏离 >15%），另一个内层字段的时间戳停在 3 天前，而脚本自己的 `refresh_status` 已经写着 `kept_previous`。

## 三层校验

```python
import json, time
from pathlib import Path

p = Path("data/xxx_context.json")
d = json.loads(p.read_text(encoding="utf-8", errors="replace"))

# ① 外层 mtime
age_min = (time.time() - p.stat().st_mtime) / 60
print(f"外层 mtime: {age_min:.0f}min")

# ② 逐源状态位 —— 没列出的字段 = 没被本轮刷新，视同 kept_previous
for k, st in (d.get("refresh_status") or {}).items():
    if st != "live":
        print(f"  不采用 {k}: {st}")

# ③ 量级体检：内层数值 vs 实时值
live_price = 76000.0            # 来自实时行情源
for row in (d.get("market_snapshot") or []):
    if row.get("symbol") == "BTCUSDT":
        inner = float(row["price"])
        dev = abs(inner / live_price - 1)
        print(f"  内层价 {inner:,.0f} vs 实盘 {live_price:,.0f} → 偏离 {dev*100:.1f}%")
        if dev > 0.05:
            print("  → 判 stale，本轮不采用")
```

阈值取 5%：正常报价源之间的差异在 0.1% 量级，超过 5% 只可能是陈旧数据。

## 判定与记法

| 情况 | 记法 |
|---|---|
| 外层新 + 内层 live | 正常采用，标注「缓存·{时间}」 |
| 外层新 + 内层陈旧/未刷新 | **「本轮无有效字段」**，换用实时路径补这一维 |
| 文件不存在 | 「缺失·跳过」 |
| 该源已被有意停用 | 「源设计性停用」——**与上面两类严格分开写** |

最后两行不能混：把「本轮没拿到」写成「设计性停用」，会让一个可修复的采集问题看起来像一个已做的设计决定，下一轮就没人去修了。

## 顺带：静默状态位

除了 `refresh_status`，还要留意模块自己写的**降级提示字段**，它们往往已经把真相告诉你了：`kept_previous`（沿用上次）、`stale`、`partial`、`degraded`、`quota_cooldown`。

体检脚本第一版就跑一遍这些字段的枚举，成本几乎为零，命中一次就省下一整轮误判。

## 与 gating 的关系

数据新鲜度本身就是多数闸门的**第一道强制门**。所以：组合缓存判 stale 时，要同步确认闸门的 `data_freshness` 门走的是哪一个日期/snapshot——两个地方各判一次、结论不一致时，以**更保守**的那个为准，并在报告里写明分歧。
