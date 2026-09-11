# 棠溪监控系统重建 · 2026-06-23

## 背景

旧监控系统因10+个竞争脚本（btc_alert_watch/alarm_watch_v3/collector/confirm_watch/fast_daemon/pipeline_daemon/price_watchdog/push_cron/realtime_watch/vwap_daemon/card_gen）互相覆盖、推送不工作、模板冲突，被用户全部删除。

重新设计：**双核架构，3个文件 = 全系统**。

## 双核架构

```
┌─ Layer 1: 价格监控 ────────────────────────┐
│  scripts/monitor/btc_monitor.py  (no_agent) │
│  频率: 每2分钟                              │
│  数据: Binance免费API                       │
│  检测: 7区间分类(VWAP/前低/大底/周VWAP等)   │
│  趋势: 15m K线 + 量能估算                   │
│  输出: stdout → 直接投递TG:386              │
│  冷却: 同区间3分钟内不重复                   │
│  零token运行                                │
└──────────────────────────────────────────────┘

┌─ Layer 2: 深度分析 ─────────────────────────┐
│  scripts/monitor/btc_card_gen.py  (agent)   │
│  频率: 每3分钟                              │
│  触发: 读取 data/btc_signal.json            │
│  数据: TV MCP (study_values/pine_tables)    │
│  输出: v4.2格式卡片 + MEDIA截图 → TG:386    │
│  状态: 完成后 signal→completed               │
│  仅触发时耗token                             │
└──────────────────────────────────────────────┘
```

## 关联Cron

| cron | 模式 | 频率 | 投递 | 用途 |
|------|------|------|------|------|
| BTC价格监控 | no_agent | 每2分钟 | TG:386 | 关键区间告警 |
| BTC深度分析 | agent | 每3分钟 | TG:386 | signal触发时出卡 |

## 打扫清单（从git删除的旧文件）

-10 `scripts/btc_alert_watch.py`     - 旧告警监控
-10 `scripts/btc_alert_watch_v3.py`  - 重写版（仍被取代）
-10 `scripts/btc_collector.py`       - 数据采集（不独立需要）
-10 `scripts/btc_confirm_watch.py`   - 确认监控（合并到monitor）
-10 `scripts/btc_fast_daemon.py`     - 快速守护（合并到monitor）
-10 `scripts/btc_pipeline_daemon.py` - 管线守护（合并到monitor）
-10 `scripts/btc_price_watchdog.py`  - 看门狗（v4版 → monitor代替）
-10 `scripts/btc_push_cron.py`       - 推送cron（改名为card_gen）
-10 `scripts/btc_realtime_watch.py`  - 实时监控（合并到monitor）
-10 `scripts/btc_vwap_daemon.py`     - VWAP守护（合并到monitor）
-10 `references/master-analysis-template.md` - 废弃模板

**保留：** `scripts/btc_push_386.py`（推送管线）· `scripts/monitor/`（新系统）

## 模板统一

**权威链（2026-06-23 锁定）：**

| 优先级 | 场景 | 使用格式 |
|--------|------|----------|
| 最高 | 告警/决策卡推送 | v4.2: 首行↑↓○×+①②③编号+≤38字/行 |
| 次高 | 完整分析卡 | v8.0 叙事风格: 5段 结构→关键位→量价→方案→评分 |
| 补充 | BTC精简卡 | 6段 方向→关键位→数据→入场→核对→预案 |

**禁止：**
- `references/master-analysis-template.md`（已删除）
- V5.1 的 80行长卡格式
- 分隔线 `━━━━` 和 `—— 你来选方向 ——`
- 表格/`｜`/装饰emoji（仅↑↓○×例外）

## 审计Step 0（每次审计第一件事）

1. `hermes cron list` — 交易分析cron是否存活？
2. `tasklist | grep python` — 行情守望daemon是否运行？
3. `cat data/monitor_heartbeat.json` — heartbeat新鲜度（>5min=可能已停）
4. `tail data/monitor.log` — 最后写入时间
5. `ls -la data/auto_card_*.md data/monitor_levels.json` — 文件新鲜度
6. **区分配置应然 vs 运行实然：** 模板写好了但守护停了=系统不在线

## 监控脚本设计原则

1. **no_agent优先**：价格监控用 no_agent cron（零token），agent cron仅用于需要TV MCP的深度分析
2. **单文件单职责**：btc_monitor.py 只做价格检测+推送，不做TV数据分析
3. **冷却防刷优先**：同区间3分钟内不重复，用 state JSON 持久化
4. **stdout只输出ASCII**：中文内容仅通过Telegram API发送，杜绝Windows GBK乱码
5. **10+到2**：若scripts/下同功能有3+个文件→全部归档，写一个干净的替代
