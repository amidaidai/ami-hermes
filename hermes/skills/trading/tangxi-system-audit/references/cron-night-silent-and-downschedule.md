# Cron 夜间静默门 + 盘中降频模式（2026-07-08 落地 · 2026-07-09 深度降频扩展）

## 一、夜间静默门（23:00–08:00 不提示，后台照跑）

**用户要求**：晚上 23:00 到次日 08:00 不提示，但后台任务继续运行；其他时段发到 Telegram。

**唯一正确做法：在统一推送入口加时段 gate，一处生效全局。**

不要在 19 个脚本里逐个加 `if hour>=23...`。所有推 TG 的 no_agent 脚本都经
`scripts/telegram_reliable.py` 的 `push_tg_rich(target, text)` → 在它入口加 gate 即可全量生效。

```python
# scripts/telegram_reliable.py :: push_tg_rich()
from datetime import datetime, timezone, timedelta
TZ = timezone(timedelta(hours=8))
def push_tg_rich(target, text, token=None):
    now_h = datetime.now(TZ).hour
    if now_h >= 23 or now_h < 8:
        return True, "silent_night"   # 不打 TG、不落盘 pending、cron 视为正常完成
    return send_telegram_reliable(target, text, token=token, parse_mode="RichMarkdown", retries=3)
```

**为什么返回 (True, ...) 而非 (False, ...)**：
- 返回 True → cron 标记 `ok`，不会误判失败、不会堆积 pending、不会刷屏。
- 后台计算（采集/刷新/验证脚本）全程照跑，只在「发送」环节拦截。

**边界**：`now_h>=23 or now_h<8` = 23:00–07:59 静默；08:00–22:59 推送。

## 二、盘中任务降频（加 8-22 时段窗口）

**hermes cron edit 命令**（不是 `update`，是 `edit`）：
```bash
hermes cron edit <job_id> --schedule "2,32 8-22 * * *"
```

### 二a. 第一轮降频（2026-07-08）：加 8-22 时段窗口

| 任务 | job_id | 旧 schedule | 新 schedule | 降频理由 |
|:--|:--|:--|:--|:--|
| Orion全市场雷达 | ef4cf5f7cd24 | `2,32 9-23` | `2,32 8-22` | 盘中异动筛，夜间无必要 |
| Deribit期权刷新 | 0764c6922694 | `9,39 *` | `9,39 8-22` | 期权情绪，盘中足够 |
| X情绪数据刷新 | d6247e06ac30 | `47 *` | `47 8-22` | 每小时→仅白天 |
| 清算压力监控 | 5db6dd683b1d | `12,42 *` | `12,42 8-22` | 爆仓预警，夜间推送已静默 |
| 数据新鲜度看门狗 | 155082fc5e34 | `28 *` | `28 8-22` | 防过期，白天巡 |
| QLib因子信号 | fd78e36de132 | `18 *` | `18 8-22` | 因子信号，盘中 |
| X情绪LLM分析 | c6ad11110a80 | `17 8-23` | `17 8-22` | 已限定时段，对齐 |
| 作战室融合信号 | 721d5b6e1c66 | `17 *` | `17 8-22` | 融合报告，盘中 |
| 行情守望看门狗 | 020e260f5ac0 | `3 */1` | `*/3 * * * *` | 每分钟起 Python 太重→每3分 |

### 二b. 第二轮深度降频（2026-07-09）：从「每小时」降到「每2-3小时」

**用户反馈**：TG 信息太频繁。第一轮只加了 8-22 窗口但窗口内仍是每小时/每30分。第二轮把窗口内频率从 165条/天降到 48条/天（-71%）。

| 任务 | job_id | 第一轮 schedule | 第二轮 schedule | 降幅 |
|:--|:--|:--|:--|:--|
| Orion全市场雷达 | ef4cf5f7cd24 | `2,32 8-22` | `2 8,10,12,14,16,18,20,22` | 30→8次/天 -73% |
| Deribit期权刷新 | 0764c6922694 | `9,39 8-22` | `9 8,10,12,14,16,18,20,22` | 30→8次/天 -73% |
| 清算压力监控 | 5db6dd683b1d | `12,42 8-22` | `12 8,10,12,14,16,18,20,22` | 30→8次/天 -73% |
| X情绪LLM分析 | c6ad11110a80 | `17 8-22` | `17 8,11,14,17,20` | 15→5次/天 -67% |
| 作战室融合信号 | 721d5b6e1c66 | `17 8-22` | `17 9,12,15,18,21` | 15→5次/天 -67% |
| QLib因子信号 | fd78e36de132 | `18 8-22` | `18 8,11,14,17,20` | 15→5次/天 -67% |
| 数据新鲜度看门狗 | 155082fc5e34 | `28 8-22` | `28 8,12,16,20` | 15→4次/天 -73% |
| X情绪数据刷新 | d6247e06ac30 | `47 8-22` | `47 8,11,14,17,20` | 15→5次/天 -67% |
| **合计** | | | **48条/天** | **-71%** |

**关键技巧**：cron schedule 用 hour list `8,10,12,14,16,18,20,22` 而非 `*/2 8-22`，因为：
1. 精确控制每个任务的触发分钟，避免同分钟排期冲突。
2. 可以按任务类型调整间隔（数据采集每2h，LLM分析每3h，看门狗每4h）。
3. 错峰分散：Orion 在 :02，Deribit 在 :09，清算在 :12，避免同分钟 3+ cron 冲突。

**保持常驻不降频（保活/执行/结构位基底，夜间推送已被静默门挡住）**：
- BTC守护看门狗 `*/5` — 进程保活，必须常驻
- 行情守望看门狗 `*/3` — 进程保活，必须常驻
- 交易执行桥接 `27,57` — 执行层，必须常驻
- XAU TV现场同步 `*/15` — 结构位现场读，环境依赖 TV
- TV Desktop保活 `*/10` — TV 保活，必须常驻
- BTC关键位同步 `0 8,12,16,23` — 4次/天，含 23 点（睡前最后一刷）

## 三、per-script dedup 限频（脚本内推送去重）

**与 cron schedule 降频互补**：即使 cron 每2h跑一次，如果每次都无条件推送就是 8 条/天。dedup 确保「内容变化才推，同内容强制间隔内最多1条」。

**已有 dedup 的脚本（2026-07-09 确认）**：
| 脚本 | dedup key | force_every_seconds | 状态 |
|:--|:--|---:|:--:|
| orion_screener_radar.py | `orion_radar` | 3600 (1h) | ✅ |
| deribit_options.py | `deribit_options` | 3600 (1h) | ✅ |
| liquidation_collector.py | `liquidation` | 1800 (30m) | ✅ |
| qlib_factors.py | (dedup_wrapper) | — | ✅ |
| x_sentiment_collector.py | (dedup) | — | ✅ |
| data_freshness_watchdog.py | `data_freshness` | 14400 (4h) | ✅ |
| stablecoin_collector.py | (dedup) | — | ✅ |

**2026-07-09 新增 dedup 的脚本**：
| 脚本 | dedup key | force_every_seconds | 修复前 | 修复后 |
|:--|:--|---:|:--|:--|
| signal_confluence.py | `signal_confluence` | 7200 (2h) | 每小时无条件推 | 内容变化或每2h推 |
| x_sentiment_context.py | `x_sentiment_llm` | 7200 (2h) | 每小时无条件推 | 内容变化或每2h推 |

**标准 dedup 添加模式**（在 `push_tg_rich` 调用前包裹）：
```python
from telegram_reliable import push_tg_rich
try:
    from alert_dedup import should_send
    if should_send("job_key", content, force_every_seconds=7200):
        push_tg_rich("telegram:-1003733144325:846", content)
except ImportError:
    push_tg_rich("telegram:-1003733144325:846", content)  # 退化直接推，宁滥勿丢
```

**审计推送频率时必查**：每30分/每小时跑的脚本若 `push_tg_rich` 前无 `should_send`/`dedup_wrapper` 包裹且无信号 gate，标 P1 补限频。

## 四、夜间静默 + 降频 + dedup 的协同效果

- 23:00–07:59：所有任务后台跑，但 `push_tg_rich` 返回 silent_night → TG 零打扰。
- 08:00–22:59：盘中任务按新 schedule（每2-3h）跑 + dedup 限频 → 仅内容有变化时推。
- 保活类（看门狗/执行桥/TV同步）全时段常驻，但夜间推送被静默门挡住。
- **总计**：从 165 条/天降到 48 条/天，夜间零打扰，盘中内容不变不推。

## 五、两个 cron error 任务的修复（与降频同期处理）

| 任务 | 根因 | 修复 |
|:--|:--|:--|
| 数据新鲜度看门狗 | 第90行 `max((a-t)/t...)` 解包写反，`a` 取到 fname(str) 导致 str-float 相减 TypeError | 改为 `(_,a,t,_) in stale`，a=age(float) t=threshold(float) |
| XAU TV现场同步 | TV Desktop 端口9222未开时 stdio 会话异常 exit 1 | 加 9222 端口探测前置：`connect_ex(("127.0.0.1",9222))!=0` 则 `return 0` 静默跳过 |

**铁律**：改了被 cron 引用的脚本后，必须 `find scripts -name "*.pyc" -delete` 清字节码缓存，再 `hermes cron run <id>` 复跑验证修复真的在 cron 环境生效——手动跑脚本通过 ≠ cron 生效（cron 持有旧 .pyc）。

## 六、批量降频的操作命令模板

```bash
# 用 hermes_cli.main 批量 edit（避免 hermes CLI uv trampoline 问题）
python -m hermes_cli.main cron edit <job_id> --schedule "2 8,10,12,14,16,18,20,22 * * *"
# 验证
python -m hermes_cli.main cron list | grep -A2 "Name:.*Orion"
# 或直接 cron run 验证
python -m hermes_cli.main cron run <job_id>
```