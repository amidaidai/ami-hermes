# 双指标结构化协议（主 SVP + 副 Volume Aggregated）

> 历史记录（2026-08-31）：旧版协议；当前字段与权限以定版指标合同为准。

适用场景：审计或改造棠溪 TradingView 双指标、驾驶舱分析卡、TV 数据桥、实时监控守护、GO/NO-GO 闸门、复盘字段落盘。

## 核心结论

主指标已经是主驾驶；副指标是订单流副驾驶。后续优化不应继续堆指标，而应把两个指标的表格、Data Window、FVG boxes、关键线/标签结构化为稳定 JSON，再交给驾驶舱、监控、评分、复盘统一消费。

## 主指标必须读取的结构化字段

| 来源 | 字段 | 用途 |
|---|---|---|
| pine_tables | 结论、方向、进场、止损、目标、确认/核对、风险、磁吸↑、磁吸↓ | 行动格文字，优先级高于兜底编码 |
| study_values | MCP Side Code | 多/空/禁追/观望机器码 |
| study_values | MCP Grade Code | A/B/C/X 等级机器码 |
| study_values | MCP Setup Score | TV 现场分 |
| study_values | MCP Entry Price / Stop Price / Target Price | 自动交易方案、R:R、监控区间 |
| study_values | MCP CVD Value | 主指标真 CVD，优先于副指标估算 CVD |
| study_values | MCP Quality Code | 风险 bitmask，用于 GO/NO-GO |
| pine_boxes | FVG / HTF FVG 区间 | 真实 FVG 框，不要自行从 OHLCV 重算 |
| pine_lines / labels | POC、VAH、VAL、DO、周/月 VWAP、ICT 流动性位 | 关键位矩阵和磁吸目标池 |

## 副指标必须读取的结构化字段

| 来源 | 字段 | 用途 |
|---|---|---|
| pine_tables | 信号、结论、风险、高周、持仓、流向、覆盖、量能、爆仓、操作 | 订单流裁决和否决票 |
| study_values | OI Total | 聚合 OI，总仓位背景 |
| study_values | CVD Value | 副 CVD，仅作辅助确认 |
| study_values | Volume Ratio | 放量/缩量过滤 |
| study_values | Coverage Exchanges / Spot / Perp | 数据覆盖质量 |
| study_values | Coverage Feed Mode | 聚合源 vs 单图回退 |
| study_values | Exchange Dominance % | 单所主导降权 |
| study_values | Confirm Score | 副指标 0-5 分确认度 |
| study_values | Composite | 方向与强度编码，多周期梯度核心 |

## 推荐 JSON Schema

```json
{
  "meta": {"symbol": "BTCUSDT", "tf": "15m", "ts": "北京时间", "price": 0, "screenshot": "path"},
  "main": {
    "grade": "A多/B空/C等待/X",
    "side_code": 0,
    "grade_code": 0,
    "setup_score": 0,
    "entry": 0,
    "stop": 0,
    "target": 0,
    "quality_code": 0,
    "check": "HTF✓ CVD✓ 位置✓ FVG✓",
    "magnet_up": "",
    "magnet_down": ""
  },
  "main_fvg": {"nearest": {"high": 0, "low": 0, "ce": 0, "side": "bull/bear", "htf": false}},
  "sub": {
    "signal": "",
    "conclusion": "",
    "oi_text": "",
    "oi_total": 0,
    "cvd_value": 0,
    "volume_ratio": 0,
    "coverage_exchanges": 0,
    "exchange_dominance_pct": 0,
    "confirm_score": 0,
    "composite": 0,
    "operation": ""
  },
  "audit": {"fresh": true, "missing": [], "stale": [], "degraded": []}
}
```

## Freshness 闸门

`fresh: true` 不能只看脚本是否成功写文件。必须同时满足：

1. 缓存 mtime < 10 分钟；
2. symbol 与当前图表一致；
3. 主指标 grade/结论不是 `?` 或空；
4. 价格与 Binance/TV quote 偏差 < 0.3%；
5. 主指标和副指标至少各读到一个有效表格或 Data Window 字段。

任一失败：标 `fresh=false`，出卡完整性表备注原因；不能静默用旧缓存。

## 裁决规则

| 情况 | 裁决 |
|---|---|
| 主指标 A + 副指标 Composite 同向 + Coverage 正常 | 进入 A 级候选 |
| 主指标 A 但副指标“缩量/降级/放弃/低覆盖/单所主导/HTF冲突/OI背离” | 降到 B/C，不推强信号 |
| 主指标 B/C 但副指标很强同向 | 只提示等待主指标触发，不能提前入场 |
| 主指标 X | 禁做；只允许风险提醒或观察 |
| FVG@CE + HTF FVG + 主 CVD 同向 | 入场质量上调一级 |
| 相邻周期冲突 | 不交易硬门，等 5m/15m 与 1h 对齐 |

## 多周期输出要求

加密完整分析必须形成 D/4h/1h/15m/5m 五层矩阵：

| 周期 | 主指标等级/方向 | 副指标信号 | Composite | 价 vs VWAP | 数据质量 |
|---|---|---|---:|---|---|

副指标 Composite 要看梯度：短周期递增=执行动能增强；短周期递减=追单风险；与结构周期反向=降级。

## 实施优先级

1. 新建或升级 TV 双指标采集器：五层读取主表、副表、study_values、boxes、lines、labels、截图。
2. 改 fresh 闸门：旧缓存和 `grade=?` 必须阻断完整卡或显式降级。
3. `auto_card.py` 优先消费结构化 snapshot，缺字段才现场 MCP 兜底。
4. GO/NO-GO 增加主指标核对行与副指标否决票。
5. 每笔 trade_plan 落盘 MCP code、Composite、Coverage、FVG、CVD，用于复盘胜率统计。

## 指标自身可选增强

- 主指标增加 `MCP RR`、`MCP Market Code`、`MCP Version Code`。
- 副指标增加 `Composite Side`、`Composite Strength`，减少外部解码歧义。
- 两个指标都保留 Data Window 输出，作为驾驶舱和监控守护的机器接口。
