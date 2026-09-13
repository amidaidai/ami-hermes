# 档位、管线审计与引擎降级的三个坑

本文件补 SKILL.md 篇幅放不下的执行细节。适用任何品种的分析卡流程。

## 1. 「分析」= 采集走 router full 的全部步骤

用户说「分析X」时采集不可跳步。**当前步数以 router 实测为准**，文档里的历史数字（加密10步）已过期：

```bash
python -c "import sys;sys.path.insert(0,'scripts');import pipeline_router as r;print(r.route_pipeline('BTCUSDT','full'))"
```

当前加密 full = **15 步**：`tv → binance → cg_pro → macro → x_sent → cron_read → cvd → depth → corr → engine → regime → dual → advanced → risk → card`。呈现仍收敛为手机三表速读版（不因采集量大就堆8张表）。

## 2. `auto_card.py` 的审计表只能代表它自己跑的那个档位

`python scripts/auto_card.py BTCUSDT`（不带 mode）走 **quick（3步 tv→binance→card）**，输出末尾的审计表第一行就是「管线路由：3步 · 完成 3/3」，其中 `cg_pro / macro / x_sent / corr` 全部标 `not_run`。

→ **不得拿这张 3 步审计冒充完整管线**。补齐路径：

| 缺口步骤 | 补法 |
|:---|:---|
| cg_pro | `python scripts/coingecko_collector.py`（全球/BTC社区/情绪一句话） |
| macro | `python scripts/macro_filter.py`（DXY/VIX/SPX + risk_on/off） |
| x_sent | `x_search("$BTC crypto sentiment today bullish bearish")` 实时，不可用才回退 web_search 并标注 |
| corr | `python scripts/correlation_matrix.py` |
| 事件 | `mcp_jin10_list_calendar`（看 3 日内 star≥4 的美联储/CPI/零售） |
| 恐贪 | `https://api.alternative.me/fng/`（走代理） |

补完后卡尾按 15 步逐项标 ✅/⚠️/❌，每个 ⚠️/❌ 写原因（如「仅公共 CG 端点·Pro 私有端点未调」「落盘文件缺失·有意退役」）。

## 3. 引擎评分与实时源打架 → 弃引擎分

`scoring_engine.py` 的情绪子项可能引用**陈旧快照**：实测输出「恐慌贪婪 15 极度恐惧」而同期实时 F&G = 61 Greed（同一份输出里的多周期方向也可能与 TV 现场读到的相反）。

规则：分项与实时源冲突时**以实时源为准**，显式声明「引擎情绪子项引用陈旧快照，该分不采用」，**不得**把引擎总分/评级（如 `7.5/14 🥈A ⚠风控违规`）直接当方向或执行依据。引擎的风控子项可作为降级提示（如 R:R 不合格、仓位超限），但仍以 `go_nogo_gate` 七门结果为准。

## 4. 降级要可见

任何缺失/降级都必须在卡面写明并为它找替代：`live / cache / stale_cache / unavailable / quota_cooldown` 五态照实标（例：风险快照 2026-07-15 陈旧 → 标「可见降级，不硬拦截」）。禁止把 stale 当 live，也禁止因为某一路缺失就整车不发。
