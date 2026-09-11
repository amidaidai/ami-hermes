# 棠溪驾驶舱 v9.6 运行态加固记录

适用场景：用户要求“全面优化 / 驾驶舱必须最新 / 按审计建议全部做”时，用于把审计结论落成可运行改动，而不是只输出建议。

## 本次形成的可复用模式

### 1. 先修 P0 运行态，再动模板

顺序固定：
1. 跑测试暴露阻塞。
2. 修影响运行的兼容层、watchdog、router、推送。
3. 刷新数据快照与守护心跳。
4. 再升级模板与流程总控。
5. 最后 smoke BTC/XAU 与 commit 锁定。

不要先大改分析文案，否则运行态仍然断，用户会继续觉得“任务总出问题”。

### 2. watchdog already-running guard 的位置

watchdog 可加“如果心跳新鲜且 PID 存活则不重复拉起”的保护，但必须放在速率限制判断之后，否则会破坏限流测试和真实阻断告警。

正确顺序：
1. 读取 guard 计数。
2. 如果对应桶已达上限 → 写 blocked、发 watchdog 告警、返回 False。
3. 未触发限流后，再检查现有 heartbeat 是否 running + age <= STALE_SECONDS + pid_alive。
4. 已存活则写 `already_running` 并返回 True。
5. 否则启动新监控。

测试辅助可用环境变量：
- `WATCHDOG_START_GRACE_SECONDS=0`：测试中跳过 3 秒等待。
- `WATCHDOG_SKIP_PID_ALIVE_CHECK=1`：测试中避免真的查 PID。

### 3. scripts/ 与 hermes/scripts/ 同名模块包装

当 `scripts/` 在 `sys.path` 前面时，`scripts/multi_source_collector.py` 如果写成：

```python
from multi_source_collector import *
```

会导入自己，导致 canonical `hermes/scripts/multi_source_collector.py` 里的 `cmc_quote` 等函数不可见。

稳定包装方式：用 `importlib.util.spec_from_file_location()` 按绝对路径加载 canonical 文件到私有模块名，再把非下划线符号导出。

### 4. auto_card 风控 0U fallback

`_adaptive_risk()` 不能在 `account_balance` 缺失时直接把余额当 0，否则正式卡会显示 `0.00U上限`。fallback：

```python
balance = float(engine_data.get("account_balance") or 0)
if balance <= 0:
    tmpl = engine_data.get("template") if isinstance(engine_data.get("template"), dict) else {}
    balance = float(engine_data.get("balance") or tmpl.get("account_balance") or 100.0)
```

然后再走 ATR 自适应和 10U 硬上限。

### 5. 期货 symbol 识别

router 判断期货时要处理 TradingView 连续合约格式：
- `ES1!`
- `CME:ES1!`
- `NQ1!`

做法：

```python
su_clean = su.split(":")[-1].replace("1!", "").replace("!", "")
if su_clean in futures_codes:
    return "futures"
```

期货 full 至少应返回：`tv → macro → x_sent → cron_read → corr → card`。

### 6. system_data_bridge 向后兼容

旧监控/回验代码可能 `from system_data_bridge import snapshot`。如果桥接模块改名为 `asset_macro_enrich()` 后缺 alias，会在 monitor.log 出现 import error。

保留：

```python
def snapshot(symbol: str) -> dict:
    return asset_macro_enrich(symbol)
```

## 验证清单

执行完 v9.6 类加固后，必须真实验证：

```bash
python -m pytest tests/ -q --tb=short --disable-warnings
python -m py_compile hermes/scripts/auto_card.py scripts/telegram_direct.py scripts/watchdog.py scripts/pipeline_router.py scripts/system_data_bridge.py scripts/multi_source_collector.py
python hermes/scripts/auto_card.py BTCUSDT
python hermes/scripts/auto_card.py XAUUSD
```

然后检查：
- `data/monitor_heartbeat.json` 新鲜且 `status=running`。
- `data/.btc_daemon_heartbeat.json` 新鲜。
- `data/source_snapshot_BTCUSDT.json` 新鲜，quality A/B 以上。
- `data/source_snapshot_XAUUSD.json` 新鲜，quality A-/B 以上。
- BTC/XAU 卡不再出现 `0.00U上限`。
- `ES1!` 和 `CME:ES1!` full route 非空。

## Git 锁定

只把本轮实际修复的核心文件 stage + commit，避免把历史大量 modified/untracked 混进稳定提交。提交前做 staged secret scan，提交后报告 commit SHA 与剩余未锁定项。
