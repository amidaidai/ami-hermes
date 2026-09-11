# 双 CVD 指标读取（2026-06-21 用户纠正）

## 问题

每次分析 TV 图表时，只读了主窗口的 SVP+ICT+VWAP+EMA+CVD 指标，漏掉了独立窗格的 Cumulative Volume Delta 指标。用户纠正：「不对，我的指标有两个，你没有看到吗？」

## 两个 CVD 的区别

### ① SVP+ICT+VWAP+EMA+CVD 内的 CVD（Session CVD）
- 位置：主价格窗口的 SVP 指标数据窗
- 周期：自动锚定（4h以下=日重置 · 4h到日线=周重置 · 日线+=月重置）
- 读取：`study_values → SVP+ICT+VWAP+EMA+CVD → CVD Value + CVD Slope`
- 计算方法：`request.security_lower_tf()` 聚合低周期 bar 的主动量差（buyVol - sellVol）
- 含义：当前锚定周期内的买卖失衡累积
- 附带：斜率动能 `CVD_SLOPE_LEN=5` 根 K 线变化量
- 源码位置：`f_cvd_delta()` → `cvdReset` → `cvdValue` → `cvdSlope`
- 用于：日内趋势判断、15m/5m 触发确认

### ② 独立 Cumulative Volume Delta（1D CVD）
- 位置：价格下方的独立窗格（entity_id: `6zhsHW`）
- 版本：TradingView 内置标准 CVD（`STD;Cumulative%1Volume%1Delta`）
- 周期：锚定 1D，低周期自动（1m/5m 用 `"1"`（1秒）、15m-1h 用 `"5"`（5分钟）、4h+ 用 `"60"`）
- 实现：`ta.requestVolumeDelta(lowerTimeframe, "1D")`
- 绘制：`plotcandle(openVolume, maxVolume, minVolume, lastVolume)` — 每根 bar 是独立的高低开收蜡烛
- 读取：`study_values → Cumulative Volume Delta → CVD`（当前 bar 的累计值）
- 含义：日线级别的累计买卖失衡，每根 bar 有独立的 open/high/low/close 四值
- 用于：高周期（4h/日线）背景判断

## 交叉解读规则

| Session CVD | 1D CVD | 信号 |
|------------|--------|------|
| 卖 + 斜率收窄 | 卖（深） | 小周期买方试探，但日线空头未投降 — 反弹非反转 |
| 卖 + 斜率加速 | 卖（深） | 大小周期共振空 — 强空头 |
| 买 + 斜率上升 | 卖（仍深） | 日内反弹，日线未反转 — 短线多/趋势空 |
| 买 + 斜率上升 | 买（翻正） | 大小周期共振多 — 潜在反转 |
| 卖 + 斜率平 | 买（浅） | 大小周期背离 — 可能短空，但日线多头背景 |

## 读取流程

每一次分析 TV 图表时必须：

1. `chart_get_state()` → 获取所有 studies 列表（确认 SVP + Cumulative Volume Delta 两个都存在）
2. `study_values` → 同时读取所有 study 的 plot 值
3. 从 SVP study 提取：`CVD Value`（累计值）+ `CVD Slope`（动能）+ cvdStateText（确认/背离/吸收/派发）
4. 从 Cumulative Volume Delta study 提取：`CVD`（日线累计值）
5. **不只看数字** — 结合 DMI 表的 CVD 状态文字（`pine_tables` 返回的 CVD 行）理解完整信号
6. 交叉解读两者的关系和矛盾
7. 在分析卡中明确标注 "Session CVD" 和 "1D CVD"

## 源码理解增强（比纯读值深2倍）

读懂 CVD 源码后，可以理解：

**Session CVD 的状态机（源码行 800-808）：**
```
cvdBearDiv = 价格新高 + CVD 未新高 → 顶背离
cvdBullDiv = 价格新低 + CVD 未新低 → 底背离
cvdBearConfirm = CVD 跌 + 价格跌 → 顺空确认
cvdBullConfirm = CVD 涨 + 价格涨 → 顺多确认
cvdRising/Falling = 斜率方向判断
cvdLongOk/cvdShortOk = 多空是否被 CVD 否决
```

**CVD 吸收/派发增强（源码行 844-846）：**
```
吸收买 = 价格压缩(<0.8 ATR) + CVD 大量减少(>3×平均Delta) + 收盘靠区间高位(>45%)
派发卖 = 价格压缩(<0.8 ATR) + CVD 大量增加(>3×平均Delta) + 收盘靠区间低位(<55%)
```
→ 吸收/派发覆盖基础 stateText，优先级最高。

**CVD 背离需靠近关键位（源码行 196-197）：**
```
FILTER_CVD_DIVERGENCE_BY_KEY_LEVEL = true
CVD_KEY_LEVEL_ATR = 0.45
→ 背离如果离 VAH/VAL/POC/VWAP 超过 0.45 ATR → 标记"背离弱"、降权
→ 只有靠近关键位的背离才算有效背离
```

## 常见陷阱

- 不要只读 SVP 的 CVD 值就下结论说 "CVD 卖压重"
- 如果 Session CVD 卖但斜率在收窄、1D CVD 还在深卖 → 这是"底部有人在买但日线还没翻"的信号
- 反之 Session CVD 买但 1D CVD 深卖 → "日内反弹，不是趋势反转"
- Session CVD 的 "顺多确认" 可能和 htfBear（4h 空头背景）冲突 → 这时 DMI 表会标 X
- **1D CVD 不会自动回正** — 它是日线级别的买卖失衡累积，需要持续几根日线买方主导才能翻正
- CVD 吸收/派发信号比普通增/减信号强 3 倍，源码优先权最高
