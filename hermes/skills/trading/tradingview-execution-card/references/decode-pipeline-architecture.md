# TV 解码管线架构 (v4.3 · 2026-06-27 锁定)

## 数据流向

```
┌──────────────────────────────────────────────────┐
│               TradingView Chart                   │
│  ┌─────────────────┐  ┌──────────────────────┐   │
│  │ 主指标(SVP)      │  │ 副指标(Volume Aggr)  │   │
│  │ 行动格 v2        │  │ 行动格 (加密专用)    │   │
│  │ 结论/方向/进场/   │  │ 信号/结论/持仓/流向/  │   │
│  │ 止损/目标/磁吸    │  │ 量能/爆仓/操作       │   │
│  └────────┬────────┘  └──────────┬───────────┘   │
│           │ CDP                    │ CDP           │
└───────────┼────────────────────────┼──────────────┘
            │                        │
    ┌───────▼────────┐      ┌────────▼───────────┐
    │ MCP Server     │      │ fetch_tv_data.cjs  │
    │ (持久连接)      │      │ (独立CDP连接,      │
    │ data_get_pine_ │      │  probe page target)│
    │ tables()       │      │ dwgtablecells读取   │
    └───────┬────────┘      └────────┬───────────┘
            │                        │
            │ 实时手动分析            │ {TICKER}_tv_data.json
            ▼                        ▼
    ┌───────────────┐     ┌─────────────────────────┐
    │  Agent (本会)  │     │ tv_dmi_cache.json       │
    │ 直接读tables   │     │ { grade, treatment,     │
    └───────────────┘     │   table_raw,             │
                          │   sub_table_raw }        │
                          └───────────┬─────────────┘
                                      │
                                      ▼
                          ┌─────────────────────────┐
                          │ auto_card.py            │
                          │ _parse_tv_dmi_table()   │
                          │ _parse_tv_sub_table()   │
                          │ shim: 合成 等级|处理 行  │
                          │ _apply_tv_dmi_override() │
                          └─────────────────────────┘
```

## 行动格 v2 行标 (2026-06 版本)

主指标表格行标（用 `data_get_pine_tables(study_filter="SVP")` 读取）:
```
结论 | A多 回踩       ← 等级嵌在此字段，解析: 包含"A多"→等级=A多
方向 | 偏多 DMI✓ ...
进场 | 扫低收回 62,480
止损 | 61,950 (1.8ATR)
目标 | POC 63,820 R:R 1:2.5
核对 | FVG✓HTF · CVD✓
磁吸↑ | VAH 63,820 分7 ★HTF 距1.2ATR
磁吸↓ | VAL 61,500 分5 距0.9ATR
```

等级推导规则（fetch_tv_data.cjs 和 auto_card.py 各有一份）:
```
结论含 "A多" → A多
结论含 "A空" → A空
结论含 "B多" → B多
...
结论含 "禁追" 或以 "X" 开头 → X
默认 → C等待
```

## 已删除的字段（不要试图读取）

以下字段在指标源码第 3058 行后已移除（注释: "为释放 TradingView 64 绘图配额"）:
- CVD Value, CVD Slope → 用 cvd_aggtrades.py (Binance逐笔A级) 替代
- Scores, Magnet+ICT+Score, ICT Count, Risk, Replay Side+Grade

以下字段仍可用（从 labels 回收）:
- POC Price, VAH Price, VAL Price → data_get_pine_labels(study_filter="SVP")
- DO Price → 从 labels 文本 "DO:" 提取
- S VWAP, EMA 9/21/34/55 → data_get_study_values

## CDP 故障恢复

症状: `tv_health_check` → `api_available: false`，`target_url` 含 `tooltip/index.html`
根因: MCP server CDP 连接嗅探到了 tooltip iframe 而非 chart tab
修复: `tv_launch(kill_existing=true)` → 等5-8s → `tv_health_check` 确认恢复
耗时: <10s（2026-06-27 实测）

## tv_dmi_cache.json 格式

```json
{
  "grade": "X",
  "treatment": "禁追·过热远离",
  "table_raw": ["结论 | 禁追·过热远离", "方向 | ...", ...],
  "sub_table_raw": ["信号 | 🟡 偏多 · 3/4共振", "结论 | 涨但缩量", ...],
  "updated": "ISO-8601"
}
```

- `table_raw`: 主指标 pine_tables rows（原始行文本，从CDP dwgtablecells读出）
- `sub_table_raw`: 副指标 pine_tables rows（仅加密品种有意义）
- `grade` + `treatment`: 顶层字段，由写入方（cron agent）从 table_raw 解析填入
- auto_card 消费者: 合并 table_raw 前合成 "等级|X" / "处理|禁追" 行，保障 _apply_tv_dmi_override 旧消费链兼容
