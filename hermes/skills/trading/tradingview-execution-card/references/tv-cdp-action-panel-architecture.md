# TV 行动格v2 CDP解码架构

> 来源: 2026-06-27 主指标 Data Window 导出移除后的管线重构。
> 供 `fetch_tv_data.cjs` / `auto_card.py` / cron agent 维护参考。

## 断裂原因

主指标 svp_v10 为省 TradingView 64-plot 配额，在源码末尾删除了 Data Window 编码导出：
```pine
// Data Window 编码导出已移除（无外部系统读取），以释放 TradingView 64 绘图配额。
```

旧管线读 `data_get_study_values` 找 `CVD Value / POC Price / VAH Price / VAL Price / Weekly VWAP Data / Monthly VWAP Data / DO Price` —— 全 null。

旧管线读表格行 `等级 | ...` 和 `处理 | ...` —— 行动格 v2 根本没有这两行。

## 行动格 v2 行标（当前生产版）

```
结论  → "A多 回踩" / "A空 反抽" / "X 过热远离" / "C等待"
方向  → "偏多 DMI verify ✓" / "偏空"
进场  → "扫低收回 62,480"
止损  → "61,950 (1.8ATR)"
目标  → "POC 63,820 R:R 1:2.5"
核对  → "FVG✓HTF · CVD✓ · SMT✓"
磁吸↑ → "VAH 63,820 分7 ★HTF 距1.2ATR"
磁吸↓ → "VAL 61,500 分5 距0.9ATR"
```

等级不在单独行，嵌在 `结论` 里：`"A多 回踩"` → 等级=A多，处理=回踩。

## 解码链路（v4.3 修复后）

```
TradingView Desktop (Electron CDP)
  └─ dwgtablecells → tableCells
       └─ fetch_tv_data.cjs 读 cells → 重建 tables
            └─ {TICKER}_tv_data.json (tv_grade, tv_conclusion, tv_entry, tv_stop, tv_target, tv_magnet_up, tv_magnet_down)
                 └─ auto_card.py TV合并块 (line ~2167)
                      └─ 重组为 等级|处理 行数组
                           └─ _parse_tv_dmi_table → _apply_tv_dmi_override
                                └─ meta.status = "A做多" / "A做空" / "X禁做" ...
```

## MCP 实时分析路径（手动）

```
mcp_tradingview_data_get_pine_tables(study_filter="SVP")
  → runs buildGraphicsJS('dwgtablecells', 'tableCells', filter)
  → CDP evaluate → rebuild table rows → return {studies: [{tables: [{rows: ["结论 | A多 回踩", ...]}]}]}
```

## 脚本自动路径（cron / auto_card）

```
cron: 主+副指标缓存刷新 (每2分钟, agent-driven)
  → data_get_pine_tables(study_filter="SVP") → table_raw
  → data_get_pine_tables(study_filter="Volume") → sub_table_raw
  → 写入 tv_dmi_cache.json

auto_card.py:
  → 读 tv_dmi_cache.json (table_raw + sub_table_raw)
  → 或读 {TICKER}_tv_data.json (fetch_tv_data.cjs 产物)
  → 重组等级|处理行 → _parse_tv_dmi_table → _apply_tv_dmi_override
```

## CVD 独立来源

指标不再导出 CVD。脚本管线用 `cvd_aggtrades.py`（Binance逐笔 A 级 CVD）。

## POC/VAH/VAL 回收

指标在价格轴有 `display=display.price_scale` 的 plot（POC Price、VAH Price、VAL Price、DO Price 等），但不在 Data Window。`fetch_tv_data.cjs` 从 Pine labels 文本中回收这些值（label text 含 "POC" / "VAH" / "VAL" 关键词）。

## 副指标市场门控

副指标(Volume Aggregated) 内部 `isCryptoA = syminfo.type=='crypto'`：
- 加密 → 行动格正常输出（信号/结论/高周/持仓/流向/量能/占比/爆仓/操作）
- 黄金/外汇/股指 → 行动格显示 "非加密品种 / 聚合仅对加密有效 / 请看主指标判定"

## 回归测试

`tests/test_tv_action_panel_decode.py` — 覆盖8种等级映射 + 真实面板值 round-trip。
