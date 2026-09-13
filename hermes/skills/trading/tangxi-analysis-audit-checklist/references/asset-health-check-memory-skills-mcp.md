# 资产面三查：记忆 / 技能 / MCP（2026-09-13 首检）

## 触发
用户问「记忆有什么问题吗？技能、MCP 什么都」或全面审计收口自查。

## 1. 记忆（两档用量）
- 看 memory + user 用量：memory 满（100%）= 下次写入会被拒 → 先压缩。**满 ≠ 故障**，属预警。
- 压缩律（2026-09-13 实作沉淀）：
  - **全批一次原子提交**：删旧+加新必须同一批（限额按批后结果检查；单独 add 会先被拒）。
  - `old_text` 必须**唯一子串**——单字符/标点（如 "."）会命中所有含点条目 → `Multiple entries matched`，无法定位。给不出唯一锚点的条目（如纯 "." 垃圾条）只能留观。
  - 压缩顺带**修正过时值**（本轮 TV 复用窗口 13min→5min）与**迁移**：偏好类条目迁 user 档腾 memory。
  - 本轮总量：第一轮 10 操作（2182→2200/2200）；同日再压一轮并迁移 1 条 → memory 2200/2200、user 1258/1375。
- 存储分工：用户偏好类 → user 档；环境/流程/契约类 → memory；「今日完成」类不进任何档。

## 2. 技能（`skills_list` 全量扫重叠组）
- 判定：同族技能 ≥4 个即记入报告（触发歧义 + 双份维护风险）。
- 2026-09-13 实测重叠组：
  - 审计×6：tangxi-system-audit / trading-system-audit / tangxi-analysis-audit-checklist / trading-analysis-system-audit-methodology / tangxi-runtime-audit-and-cleanup / trading-system-implementation-closure
  - TG 投递×5：tangxi-tg-delivery-format / -report-standard / -reports / -rich-reporting / telegram-delivery-reliability
  - TV 证据×5：tradingview-consumer-evidence / -state-integrity / tv-raw-plot-evidence / tv-raw-study-evidence / pine-indicator-audit
  - 卡片×4：trading-card-generation / xau-analysis-format / tradingview-execution-card / tradingview-indicator-analysis
  - PPT×8：gov/official/html/guizang/gpt-image2/pptx 系列
- 处置：整理（定主从 + 互引注记，不删内容）**需用户点头**，不擅自动手。总数基线：205 个（2026-09-13）。

## 3. MCP 烟雾测试（每 server 一个廉价调用）
| server | 测试调用 | 2026-09-13 结果 |
|---|---|---|
| binance | `get_price BTCUSDT` | ✅ 76,686 |
| jin10 | `get_quote XAUUSD` | ✅ 4,348（周末=周五收盘值，正常） |
| stock-api | `get_stock SH510500` | ✅ 7.611（腾讯源） |
| tradingview | `tv_health_check` | ✅ CDP · BTCUSDT.P 15m |
| financekit | `market_overview` / `stock_quote` | ⚠ 上游 Yahoo 限流（`Too Many Requests`）——源侧节流，按降级契约处理（VIX/SPX 禁伪造）、稍后重试；不得写成「工具坏了」 |
| x_search | 不实测（成本） | 看卡面 x_sent 是否如实降级（`stale_cache` 标注正常）即可 |

## 执行提示
- 批量诊断命令写成 `.py` 放 `outputs/` 再跑（或 `bash` 跑 blocked-scripts 保存脚本）——终端对长内联/嵌套 `$()` 命令会 hardline block。
