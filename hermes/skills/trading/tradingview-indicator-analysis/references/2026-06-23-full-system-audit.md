# 2026-06-23 棠溪分析系统全面审计

## 审计触发
用户要求"审计一下"分析策略和模板。

## P0 发现

### 1. 行情守望守护已停止 >24h
- heartbeat: `status: "stopped"`，最后活跃 6/22 09:20
- monitor.log 最后记录: `[09:20:53]` — 超过24小时
- 无任何 BTC/XAU 实时10s轮询
- **后果**：到价告警、方向翻转检测、双置信对比、CVD吸收检测全部停摆

### 2. 交易分析cron任务全部缺失
hermes cron list 只有4个维护任务（备份/审计/更新/模型同步），零个交易分析cron：
- 无 BTC告警推送
- 无 BTC价位提醒
- 无 管线守护/MTF分析
- 无 TV数据桥
- 无 采集器
- 无 高胜率事件cron

### 3. 模板三头不一致
4种竞争模板格式同时存在：
| 模板源 | 格式 |
|--------|------|
| SKILL.md + `indicator-pair-execution-template.md` | V5.1 10段头部+5段正文 |
| `master-template-v68.md` | v8.0 5段叙事风格 |
| `alert-card-format-v42.md`（skill references） | v4.2 首行方向+①②③编号 |
| `btc-analysis-compact-template.md` | 6段精简 |
SKILL.md 自相矛盾：同时声明"V5.1 唯一认可"和"v7.1 替代V5.1"。

## P1 发现

### 4. 数据散落两处，全部过期
- `D:/Hermes agent/data/` — auto_card_*.md 最后更新 6/22 23:06
- `~/AppData/Local/hermes/data/` — 只有2个文件(空)
- 所有监控位 valid_until 全部过期

### 5. btc_push_cron.py 角色错位
原是推送脚本，现272行变成了"多周期分析卡片生成器"内嵌MCP client，无cron调用，属于死代码。

### 6. scripts/ 目录重度混杂
~100个文件新旧并存：btc_alert_watch.py(旧) + btc_alert_watch_v3.py(新) + btc_vwap_daemon.py + btc_fast_daemon.py + btc_price_watchdog.py，同功能3-4个竞争实现无统一入口。

## 修复建议
1. 启动行情守望（恢复实时10s监控）
2. 统一模板（砍到1个权威，其他标记废弃）
3. 重建关键cron（BTC告警推送 + 价位提醒）
4. 清理废弃脚本（合并竞争实现，删旧留新）
5. 存档过期数据（轮转events/log，归档历史K线缓存）

## 当前市场快照
BTC 62,372 — 距"大底 62,272 ±100"仅 +100点（上沿触及），典型触底测试位。
