# DMI 决策表 = 真理源（2026-06-21）

## 发现

TV 的 SVP+ICT+VWAP+EMA+CVD 指标内嵌了一个完整的 DMI 决策引擎（2024行 Pine Script），其评分/分级/冲突检测/事件驱动体系远超 `auto_card.py` 自算逻辑。**DMI 表是真理源，auto_card 应消费而非重算。**

## DMI 表实时数据（`pine_tables`）

每次分析 TV 图表时必须调 `pine_tables` 获取 DMI 决策表。简洁模式返回 8 行：

```
等级 | X/A多/A空/B多/B空/C反多/C反空/C等待
处理 | 回踩做多/反抽做空/轻仓等多/轻仓等空/站回再多/跌回再空/结构冲突/过热禁追/观望
背景 | 多/空/震荡 4h
位置 | VAH上方/VAL下方/POC旁/VA内 + 上方控制/下方控制/下方延展/上方延展/贴近公平
量能 | 放量上收/放量下收/放量分歧/缩量试探/量能普通
CVD  | 顺多确认/顺空确认/买盘回升/卖盘回落/顶背离/底背离/上方派发/下方吸收/中性
执行 | 多:回踩POC 64213 ｜ 空:反抽VAL 64136 ｜ 等:看POC
风控 | 多失效:破VWAP 64224 ｜ 空失效:回VWAP 64224 ｜ 不进场
```

## 与 auto_card 决策对比

| 字段 | DMI 表 | auto_card 当前做法 | 应改为 |
|------|--------|-------------------|--------|
| 方向评分 | 顺势多/空 0-10 + 反转多/空 0-10 | 单一 bias(_kl_bias) | 读取DMI评分 |
| 交易等级 | A/B/C/X + 稳定K确认 | 无分级 | 直接显示DMI grade |
| 冲突 | 结构+EMA+DMI+CVD 四维检测 | 无检测 | 信任X=禁做 |
| CVD | 确认/背离/吸收/派发/强弱分类 | 仅 Binance Taker 代理 | 读取DMI的CVD状态 |
| 失效 | 动态计算 invalidPrice | ATR-based 固定距离 | 读取DMI失效位 |
| 处理建议 | "偏多等回踩" / "观望" / "禁追" | 无此层 | 直接显示DMI treatment |

## 消费约束

- DMI 表的 grade="X" → auto_card 必须标 X 禁做，不自算方向
- DMI 表的 grade="A" 且方向明确 → auto_card 操作段优先此方向
- DMI 表的 "CVD: 顺多确认" != Binance Taker 方向 — 两者冲突时 DMI 表优先

## 接入管道 (v6.9.14-15a)

双管道接入已实现:
- auto_card.py: _parse_tv_dmi_table -> _apply_tv_dmi_override -> 覆盖 status/direction
- 行情守望.py: _load_tv_dmi_cache -> render_message 显示 TV 信号行
- 桥接: tv_dmi_cache.json (cron agent 每5m写 -> 行情守望每10s读)
- 详见 references/tv-dmi-cache-bridge.md
- DMI 表的失效价格 > auto_card 的 ATR 止损 — 以 DMI 表为准
- DMI 表仅支持 1 pane × 1 symbol — 不支持批量，每次需先切品种再读
