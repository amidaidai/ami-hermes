# Telegram Cron Routing Matrix — 棠溪交易任务降噪

## 触发场景

用户反馈“任务报告太频繁”“喜欢看 X 情绪和雷达警报”“这些维护任务可以发电报”时，按本矩阵重排 Hermes cron 的 delivery、频率和脚本输出。

## 社区原则压缩

| 原则 | 来源共识 | 棠溪映射 |
|---|---|---|
| Alert 不是 monitoring | Grafana / Kentik / PagerDuty | 数据采集可以高频落盘，但不要把每次采集结果都推 Telegram |
| FYI alerts are trash | Kentik | “市场平静”“等待信号”“daemon alive”必须静默 |
| 去重、分组、路由、抑制 | Prometheus Alertmanager | 同类数据按内容去重；低置信落盘不推；不同等级走不同 delivery |
| 持续/多源确认才升级 | Grafana / Datadog | 低置信单源交易异动只写 JSON；中高置信才推 |
| 非紧急延后或低打扰 | PagerDuty | Dune/Deribit/QLib/稳定币/COT 等只 local，供分析卡读取 |

## 推荐推送分层

| 等级 | 任务类型 | delivery | 输出规则 |
|---|---|---|---|
| P0 交易机会 | X情绪、Orion全市场雷达 | `telegram:-1003733144325:846` | 内容变化/中高置信才推；保留用户爱看的雷达和情绪 |
| P0 运行异常 | BTC daemon watchdog | Telegram | daemon alive 时 stdout 为空；只在重启/异常时输出 |
| P0 数据异常 | 数据新鲜度看门狗 | Telegram | 仅过期输出；建议 force dedup 4h，避免 stale 风暴 |
| P1 每日维护 | 每日技能SkillMCP更新、每日系统审计、每日系统备份 | Telegram | 用户确认可发；最好全正常静默或只在有变更/异常时发 |
| P1 关键位基础设施 | BTC关键位同步 | Telegram | 用户确认可发；如果 agent-mode 输出过大，改成摘要/变更才推 |
| P2 数据采集 | Dune、COT、Deribit、清算、稳定币、QLib | local | 落盘供分析卡读取；不直接打扰 |
| P2 执行桥 | 交易执行桥接 | local | `no_signal`/`quiet` 必须静默；只有记录事件才输出 |
| P2 复盘/模型维护 | 每日复盘提醒、OpenRouter同步 | local | 非实时交易警报，不刷 TG；模型同步仅变化/失败时可推 |

## 推荐错峰

| 任务 | 推荐频率 |
|---|---|
| OpenRouter免费模型同步 | `40 6 * * *` local，避开 07:00 维护窗口 |
| 每日技能SkillMCP更新 | `0 7 * * *` TG |
| 每日系统审计 | `20 7 * * *` TG |
| 每日系统备份 | `45 7 * * *` TG |
| BTC关键位同步 | `0 8,12,16,22 * * *` TG |
| Orion全市场雷达 | `2,32 9-23 * * *` TG |
| Orion雷达分析 | `7 9-23 * * *` TG；不要每 30 分钟 agent 分析刷屏 |
| X情绪刷新 | `17,47 * * * *` TG，但按内容 hash 去重，建议同结构 2h 强制一次 |
| Deribit期权刷新 | `9,39 * * * *` local；期权 OI 不需要 15m Telegram |
| 数据新鲜度看门狗 | `28 * * * *` TG，仅过期输出，4h 去重 |
| 稳定币供应监控 | `35 */4 * * *` local |
| Dune链上刷新 | `5 */4 * * *` local |
| QLib因子信号 | `22 * * * *` local |
| COT报告刷新 | `55 8 * * 6` local，避开 BTC 08:00 同分钟 |

## 脚本降噪模式

### 内容 hash 不包含时间戳

如果输出每次都包含 `ts`，直接对全文 hash 会导致每次都“变化”。应使用语义 key：

```python
dedup_key = json.dumps({
    "fear_greed": fg_val,
    "mood": mood,
    "fomo_score": fomo,
    "trending": top,
}, ensure_ascii=False, sort_keys=True)
if should_send("x_sentiment", dedup_key, force_every_seconds=7200):
    print(output)
```

### 健康状态静默

```python
if alive:
    # stdout must be empty; only restart/error should print
    exit(0)
```

### 低置信交易异动落盘不推

```python
alert_candidates = [c for c in candidates if c.get("confidence", 0) >= 4]
report = build_report(alert_candidates, ts) if alert_candidates else ""
# always write JSON cache; only print(report) when non-empty
```

## 验证清单

1. `hermes cron list --all | cat` 确认 Telegram 只剩 P0/P1。
2. 手动跑健康脚本：健康时 `wc -c` 应为 0。
3. `python -m py_compile` 检查改过的脚本。
4. 对 `orion_screener_radar.py` 做一次手动运行，确认中高置信才输出、耗时在 cron timeout 内。
5. 备份 `jobs.json` 到 `outputs/maintenance-logs/jobs-before-*.json`，方便回滚。
