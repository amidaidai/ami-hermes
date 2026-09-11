# 全区间覆盖看门狗模式 (v4+)

## 问题

传统的区间看门狗只监控 2-3 个关键价位（前低、大底、VWAP区）。当价格快速通过这些区间时（亚盘流动性低，一根15m K线可以跑 $200+），脚本可能正好在区间穿越的间隙运行，导致**永远触发不到**。

## 解决方案：ZONES 字典 + MID 兜底

用 `ZONES` 字典定义所有需要关心的区间，并为**区间之间的所有价格**也定义兜底触发：

```python
ZONES = {
    "VWAP_ZONE":    (63930, 64000, "反弹做空区"),
    "BAND2_BREAK":  (64153, 64200, "Band2上轨突破"),
    "WVWAP_ZONE":   (64480, 64530, "周VWAP附近"),
    "L1":           (63170, 63370, "前低63,270±100"),
    "L2":           (62172, 62372, "大底62,272±100"),
}

# 主区间检查
for name, (lo, hi, desc) in ZONES.items():
    if lo <= price <= hi:
        triggered = name
        label = desc
        break

# MID 兜底 — 不在任何区间==仍在关注范围内
if not triggered:
    if price > BAND2_HI and price < WVWAP_LO:
        triggered = "MID"
        label = "Band2上-周VWAP之间"
    elif price > WVWAP_HI:
        triggered = "ABOVE_WVWAP"
        label = "周VWAP上方"
    elif price > VWAP_HI and price < BAND2_LO:
        triggered = "MID_LOW"
        label = "VWAP上方运行"
    elif price > L1_HI and price < VWAP_LO:
        triggered = "VAL_ZONE"
        label = "VAL-折价区运行"
    else:
        sys.exit(0)  # 低于前低或高于周VWAP太多，不报
```

## 关键设计

1. **ZONES 覆盖高价值决策区间**：价格在这些区间内触发有操作建议的输出
2. **MID 兜底覆盖中间区域**：确保用户始终知道价格在什么位置，不会出现"价格过了区间但没报"
3. **最低/最高区间外静默**：`else: sys.exit(0)` — 低于L2或远高于WVWAP时静默
4. **每个区域独立 cooldown**：同区域3分钟内不重复

## 优点

- 价格无论在哪都有对应输出
- 不会因为时间片跳跃而漏报
- 中间区域只报位置和趋势，不报操作建议（减少噪音）
- cooldown 独立于区域，不会互相阻塞
