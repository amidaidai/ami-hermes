# 已废止 / 已停用脚本 → 现行替代（唯一对照表）

> 建立：2026年9月11日。**读到任何技能里出现左列脚本名，先查这里再动手**。
> 状态均已在 2026-09-11 用 `ls scripts/` + `Find` + `git grep` + 进程/cron 实测核实。
> 扫描工具：`python scripts/maintenance/skill_drift_scan.py`（仓内，可反复跑）。

## 0. 先说结论（三条，别记错）

1. **现行监控链只有一条**：`keylevel_guard.py`（常驻·亚秒 REST·多品种多顶点·每位 30min 冷却）
   + `btc_keylevel_guard_watchdog.py`（cron `*/2` 拉起）+ `keylevel_read_trigger.py`（事件本地分析）
   + `btc_tv_refresh.py`（cron `7,27,47` 五周期快照续航）。
2. 唯一批准监控源 = `data/keylevels_config.json`；候选池不自动升格；到价只提醒「看图」，不代做判断。
3. **区分「已移入 _archive」与「文件仍在但不再运行」** —— 两者都不是现行工具，但说法不能混。

## 1. 已移入 `scripts/_archive/`（`scripts/` 根下已无此文件）

| 脚本 | 当时的职责 | 现行替代 |
|---|---|---|
| `btc_collector.py` | 1m 全数据采集（no_agent cron） | `btc_tv_refresh.py`（五周期 + 多源快照） |
| `btc_vwap_daemon.py` | 10s VWAP/多因子 watcher 守护 | `keylevel_guard.py` |
| `btc_push_cron.py` | 读 pending 文件并推送（no_agent cron） | 推送并入 `keylevel_guard.py` 直发 |
| `btc_alert_watch.py` / `btc_alert_watch_v3.py` | 12 维信号探测器 → 写 pending | `keylevel_guard.py` + `keylevel_read_trigger.py` |
| `btc_fast_daemon.py` | 快轮询守护 | `keylevel_guard.py` |

## 2. 文件仍在 `scripts/`，但**已不在 cron、不在任何进程中运行**

这些是**历史代际**（上一版白名单曾误写成「已删除」——现更正）：

| 脚本 | 实际状态 |
|---|---|
| `btc_keylevel_rest_guard.py` | 亚秒 REST 单品种版；现行是 `keylevel_guard.py`（多品种多顶点版） |
| `btc_keylevel_ws_guard.py` | WebSocket 版；WS 域名在代理/DNS 下不稳，已被 REST 版取代 |
| `btc_keylevel_sentinel.py` | 两位零 token cron 哨兵；已被 `keylevel_guard.py` 取代 |
| `btc_price_arrival_sentinel.py` | 到价提醒哨兵；cron 任务 `BTC价格到位提醒` 已 `enabled=false` |

> 不要删它们（cron 配置与历史审计文档仍在引用），但**不要拿它们当现行链路**。

## 3. 待确认归档（零活跃引用，未动）

| 脚本 | 情况 |
|---|---|
| `attach_pine_v14.py` | 硬编码单次编排（写死 `NEW='AggVol v14...'`），零外部引用；同组工具 `install_pine_source.py` / `install_pine_source_v2.py` / `attach_pine_v14b.py` / `tv_state_check.py` 仍被技能点名保留 → 本文件可安全移到 `scripts/_archive/`，**待用户确认** |

## 4. 指标字段/行名（另一类废止，别与脚本混）

| 已废止 | 现行 |
|---|---|
| 主指标 10 行（进场/止损/目标/确认/核对/风险/背景/执行/等级/处理） | 13 行：位置/结论/方向/路径/**风控**/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位 |
| 副指标旧 10 行（风险/高周/覆盖/占比/爆仓） | 6 行：信号/结论/流向/持仓/量能/操作 |
| `MCP CVD Value`、`OI Total`、`Estimated CVD Value`、`MCP EMA Length 1-4`、`MCP Risk Pack`、`MCP Bull/Bear FVG CE`、`MCP FVG Quality Code`、旧长名 `MCP StructPack (FvgQ…)` | 全不可读。当前 DW 清单见 `docs/tv-indicator-field-map.md`；旧名只在契约 `LEGACY_DW_ALIASES_*` 里为历史缓存保留 |
| 「风控」四态**标签** | 只有 3 个标签：风控 / 风控·观察 / 风控·未授权；`禁做·不出价` 是 setupX 的**行值** |

## 5. 权威索引（不要在自己文件里再抄一份字段清单）

| 需要什么 | 看哪里 |
|---|---|
| 字段/行名/授权三态 | `D:/Hermes agent/scripts/tv_indicator_contract.py` |
| 人读的映射与流程 | `D:/Hermes agent/docs/tv-indicator-field-map.md`（v3.0） |
| 系统全貌/进程/cron/档位 | `D:/Hermes agent/docs/系统总览.md` |
| 漂移扫描 | `python scripts/maintenance/skill_drift_scan.py` / `python scripts/tv_indicator_alignment_check.py` |
