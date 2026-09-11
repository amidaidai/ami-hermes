# auto_card 闲置能力盘点 + 接通审计法

> 2026-06-28 全方位能力审计产出。回答"分析skill有没有用上全部该用的能力"这类问题时先读本文件。

## 审计方法（可复用）

判断"该用的能力有没有用上"不能只看能力图声称接通，要**对照 auto_card.py 实际 import/调用**：

1. `grep -oE "from [a-z_]+ import" hermes/scripts/auto_card.py` → 列出真正被引入的本地模块。
2. 列出 `scripts/*.py` 全部分析脚本，与上一步对照，找出**存在但未被 import 的孤儿脚本**。
3. 对每个孤儿脚本读 docstring + 公开函数名，判断它算什么能力、是否该接。
4. 区分"能力图标✅但代码没接通"（真缺口）vs"已 import 已调用"（真接通）。能力图是声称，代码 import 才是事实。

## 已接通的 15 项主力能力（2026-06-28 确认）

TV双指标缓存(`_tv_pine`/tv_dmi_cache)、Binance全套(`_collect_binance_data`)、多空比、CVD逐笔(`cvd_aggtrades`)、CMC/恐慌贪婪、CoinGecko轮动(`cg_top_coins/cg_trending`)、宏观四件套(`macro_overview`/dxy)、金十禁做(`event_ban_live`)、买卖墙(`depth_wall`)、Grok催化剂(`call_grok_validation`)、4层降级Web情绪(`sentiment_search`)、Polymarket(`polymarket_bridge`)、市场体制(`regime_classifier`)、Session策略(`session_strategy`)、Protections风控(`risk_constitution`)。

## 闲置能力：6 个已实现但 auto_card 未 import 的孤儿脚本

这些脚本真实存在、实现完整、能跑，但 `auto_card.py` 从头到尾没引入。它们正好是"多市场验证/支撑确认"最缺的零件：

| 脚本 | 行数 | 公开函数 | 能力 | 该接进卡片哪一行 |
|---|---|---|---|---|
| `scripts/meta_labeler.py` | 219 | `extract_features` / `check_meta_label` | 执行门控(特征→放行/否决) | **正是"共振闸门"——渲染前最终 go/no-go 门** |
| `scripts/orderflow_absorption.py` | 288 | `detect_absorption` / `detect_cvd_trendline_break` | 吸收/消耗检测 + CVD趋势线突破 | CVD确认行加"吸收✓"——社区#1支撑确认手段 |
| `scripts/cvd_analyzer.py` | 361 | `slope_pct` / `check_cvd_confluence` | CVD共振分级+斜率% | 把CVD从"只取方向"升级成背离共振分级 |
| `scripts/fvg_detector.py` | 125 | `detect_fvg` / `best_fvg` | 三烛FVG识别 | 进场行ICT入场质量 |
| `scripts/order_block.py` | 121 | `detect_obs` / `nearest_ob` | 机构吸筹/派发OB | 关键位行 |
| `scripts/correlation_matrix.py` | 228 | `compute_correlation` / `multi_asset_risk_multiplier` | 多资产相关性+风险乘数 | 风控行：DXY/SPX背离时自动降仓 |

## 关键洞察

- **meta_labeler 就是用户上轮要的"共振闸门"**——早已写好(218行)，只是没被调用。建议"做共振闸门"前先查是否已有现成实现，别重复造。
- **接通优先级**：接闲置脚本是纯增量、零新增依赖、零成本。第一优先级永远是激活已写好的能力，而非写新代码。
- **x_search 真实状态**：能力图说已启用，但 auto_card 实际走 `call_grok_validation`(Grok web验证)，不是真 x_search MCP。X情绪是"web回退·非X实时"，算半个缺口。

## 接通后必跑验证（审计铁律）

接任何脚本后必须 `python scripts/auto_card.py BTCUSDT` 和 `XAUUSD` 双实测，确认无动态错误（NoneType/import失败/possibly-unbound）再收工。

## ⚡ 2026-06-28 新增：Orion 全市场雷达（独立于 auto_card 的平行能力）

本 session 创建了 `orion-screener-radar` skill + 同名 no_agent 脚本，定位为 auto_card 的上游筛选层：

| 维度 | auto_card（8步分析） | Orion雷达（全市场扫描） |
|---|---|---|
| 品种 | 单个（用户指定） | 604 品种全量 |
| 深度 | 完整（TV+Binance+多源） | 浅（三层快速验证） |
| 触发 | 用户说"分析X"或 cron | 每30min cron |
| 运行模式 | agent（消耗 tokens） | no_agent（零 token） |
| 输出 | 完整分析卡+截图 | 异动信号列表 |

**衔接模式**：Orion 捕捉异动→推送到群→用户看到后说"分析XXX"→走 auto_card 8步深度分析。两能力互补，不重叠。
