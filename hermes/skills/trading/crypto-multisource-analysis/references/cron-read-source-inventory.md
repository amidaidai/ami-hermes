# cron_read 数据源清单 v1.1

> 2026-09-16 · 清算换源 + 双落盘迁移后的现状

## 设计原则

cron_read 替代「分析时重跑脚本」：cron 后台采集，分析时直接读最近输出文件。
**只有真落盘的 JSON 才算 cron_read 已消费** —— 仅推 TG 而无本地文件的采集器不得伪装成已消费。

权威清单以代码为准：`pipeline_router.CRON_SOURCES`（按资产类别）+ `CRON_SOURCES_BY_SYMBOL`
（只覆盖部分币种的源按品种追加）。本表是代码的易读投影，冲突时以代码为准。

## 数据源状态（crypto）

| 来源 | 脚本 | 落盘路径 | 状态 | 备注 |
|------|------|---------|:--:|------|
| **X情绪** | x_sentiment_refresh.py | `data/x_sentiment_context.json` | ✅ 活跃 | >6h 写「本轮不采用」 |
| **清算双源** | liquidation_refresh.py | `data/liquidation_flow.json` + `data/coinglass_liq.json` | ✅ 活跃 | cron `清算双源刷新` */10；只覆盖 BTC/ETH |
| ~~Dune链上~~ | dune_collector.py | `data/dune_cache.json` | ⛔ 停用 | cron 已摘 |
| ~~Deribit期权~~ | deribit_options.py | `data/deribit_options.json` | ⛔ 停用 | cron 已摘 |
| ~~QLib因子~~ | qlib_factors.py | 无 | ⛔ 停用 | 仅 cron stdout |
| ~~稳定币~~ | stablecoin_collector.py | 无 | ⛔ 停用 | 仅 cron stdout |
| ~~COT持仓~~ | cot_collector.py | `data/cot_data.json` | ⛔ 停用 | CFTC 周报，黄金走 `cot_bridge` |
| ~~清算压力(旧)~~ | liquidation_collector.py | 无 | ⛔ 退役 | 旧 OI×价格挤压估算，2026-07-15 退役；不得恢复 |

## 完成度语义

`auto_card.py` 判定 `cron_read` 步骤是否完成：

- **新鲜**（文件在 `CRON_SOURCE_MAX_AGE` 阈值内）→ 计入；
- **设计性停用**（名字在 `CRON_SOURCES_PAUSED`）→ 单独记账，不算缺失；
- 清单里只要有一个停用/缺失源，`cron_read` 步骤**不计完成** —— 有意为之，
  不把设计缺口记成完成度（避免卡面分数虚高）。

停用/缺失/新鲜三态分别写进卡面脚注；清算另加「清算=卡面路径(③多源表清算行)」标注，
因为清算维度的实际落点是 v96 渲染器 ③ 多源表「清算」行（直接读 liquidation_flow + coinglass），
不是 cron_read 这行审计 —— 写清楚才不会被「设计性停用」串误导成清算整体停采。

## 新鲜度阈值（CRON_SOURCE_MAX_AGE）

| 源 | 阈值 | 依据 |
|---|---|:--:|
| x_sentiment | 6h | 卡面「>6h 不采用」同一口径 |
| liquidation_flow | 0.7h(42min) | 对齐 `data_freshness_watchdog` 0.7h |
| xau_macro_context | 24h | trading_system TTL |
| cot_data | 7天 | CFTC 周报 |

**阈值必须与产出方一致**：拿 6h 判一个 24h TTL 的缓存 = 每轮永久误报，最终让人忽略整张完成度表。

## 回退策略

当 cron_read 数据不可用（过期/不存在）：
1. 标注「cron缓存过期·跳过」；
2. 不重跑已停用脚本（浪费 API 额度，违背 cron_read 初衷）；
3. 只在 card 步骤汇总时列出哪些源可用、哪些跳过；
4. 关键源（X情绪）缺失时用 web_search 补充并标注「web源·非X实时」。
