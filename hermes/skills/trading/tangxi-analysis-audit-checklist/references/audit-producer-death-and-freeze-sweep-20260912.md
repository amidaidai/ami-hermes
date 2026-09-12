# 生产者调度死亡 + 状态冻结扫描（2026-09-12 实测）

本文件记录一次「同一系统、两轮审计、结论完全不同」的全过程。价值不在结论，而在**第二轮为什么能找到第一轮找不到的东西**。

---

## 1. 两轮对比：同样是 P0，第一轮全是推断，第二轮全是实测

| 轮次 | 方法 | 报出的 P0 | 事后核实 |
|:--:|:--|:--|:--|
| 第 1 轮 | 读源码 + 静态推断（未跑验证命令） | ① keylevels_config 全部 level 过期、守卫空转 ② 双解释器 uv cpython 缺 6 包 ③ monitor_levels.json 退役未清理 | ① **假**：实为 8/8 有效、0 过期、valid_until 在未来 ② 已在本轮前被补齐 ③ 本技能「设计性退役」表已列的留观项，重复上报 |
| 第 2 轮 | 先跑命令、贴原始输出，再定级 | ① `cron_read` 第⑥步永久空转 ② 影子校准闭环断裂 ③ 风控状态冻结 ④ XAU 四层退化 | 全部当场跑出证据（见下） |

**结论**：第一轮的「问题」几乎都是**记忆和文档里的旧结论被当成现状**。静态读源码只能产生假设，假设不是发现。

---

## 2. 第 2 轮的真 P0-1：管线步骤的生产者全数停摆

### 观测

`audit_preflight` 报「管线路由 15 步 · 完成 11/15」，未完成项里 `Cron缓存` 备注为：

```
新鲜:无；缺失/过期:dune_cache(stale_cache),deribit_options(unavailable),
x_sentiment(stale_cache),qlib_factors(stale_cache),liquidation_pressure(stale_cache)
```

### 取证

```bash
cd "/d/Hermes agent"
for c in dune_cache deribit_options qlib_factors liquidation_pressure stablecoin_flows cot_report x_sentiment; do
  f="data/${c}.json"; [ -f "$f" ] && echo "  ${c}: mtime $(stat -c '%y' "$f" | cut -c1-19)" || echo "  ${c}: 缺失"
done
```

原始输出：

```
  dune_cache: mtime 2026-07-15 09:49:58
  deribit_options: mtime 2026-09-02 16:13:00
  qlib_factors: mtime 2026-07-15 09:51:09
  liquidation_pressure: mtime 2026-07-15 09:50:41
  stablecoin_flows: 缺失
  cot_report: 缺失
  x_sentiment: mtime 2026-07-15 09:50:20
```

### 根因定位：生产者被摘掉调度，不是缓存写坏

```bash
cd /c/Users/Administrator/AppData/Local/hermes/cron
for s in dune_collector stablecoin_collector x_sentiment_collector cot_collector deribit; do
  echo "  $s: 历史备份命中 $(grep -l "$s" jobs.json.bak* 2>/dev/null | wc -l) 个 · 当前jobs.json命中 $(grep -c "$s" jobs.json) 次"
done
```

原始输出：

```
  dune_collector: 历史备份命中 11 个 · 当前jobs.json命中 0 次
  stablecoin_collector: 历史备份命中 11 个 · 当前jobs.json命中 0 次
  x_sentiment_collector: 历史备份命中 11 个 · 当前jobs.json命中 0 次
```

采集器文件都还在（`scripts/dune_collector.py`、`stablecoin_collector.py`、`x_sentiment_collector.py` 均存在），**只是没有任何 cron 调它们**。这就是「文件存在 ≠ 链路活着」的标准形态，也是静态读源码永远发现不了的。

另外三个相关 cron 处于禁用：`Deribit期权刷新`、`清算压力监控`、`COT报告刷新`。

### 修复选项（二选一，不允许维持现状）

| 选项 | 动作 | 代价 |
|:--|:--|:--|
| A 恢复链路 | 给三个采集器建回 cron，并决定 Deribit/清算/COT 三个是否启用 | 恢复原本声明的能力，可能带回噪音 |
| B 降级声明 | 把 `cron_read` 从 Full 管线移除或降为可选，卡片来源矩阵不再列该步 | 管线步数变小，但自述与实际一致 |

---

## 3. 真 P0-2：影子校准闭环断裂

### 观测

```bash
ls -la data/shadow/
# decision_signals.jsonl  1042280  9月12 23:47   ← 每轮出卡都在追加
# decision_outcomes.jsonl   18358  7月11 21:01   ← 两个月没动
```

### 根因

cron `影子结果标注`（`*/15`）处于**禁用**状态。`shadow_outcome_labeler.py` 存在但无人调 → 信号只进不出。

**后果**：`FinalVerdict` 拿不到任何自校准数据；系统看起来在跑影子评估，实际只做了记账。

**成对检查原则**：任何「生产者 + 消费者」型状态，单看一侧 mtime 都会漏。必须成对。

---

## 4. 真 P0-3：风控与复盘状态冻结

```bash
cd "/d/Hermes agent"
cat data/risk_state.json | head -8
for f in data/trade_plans.jsonl data/trade_events.jsonl data/trade_reviews.jsonl \
         data/strategy_governance.json data/strategy_model_stats.json; do
  echo "  $f: $(wc -l < "$f") 行 · mtime $(stat -c '%y' "$f" | cut -c1-19)"
done
```

原始输出要点：

```
risk_state.json:
  "date": "2026-07-15", "daily_starting_balance": 67.52,
  "daily_realized_pnl": 0.0, "loss_streak": 0, "lock_trading": false

trade_plans.jsonl          : 928 行 · mtime 2026-09-12 23:47:11   ← 每轮写
 trade_events.jsonl        : 310 行 · mtime 2026-07-15 09:54:48
 trade_reviews.jsonl       : 372 行 · mtime 2026-07-15 09:54:48
 strategy_governance.json  :  11 行 · mtime 2026-07-10 23:44:29
 strategy_model_stats.json :   4 行 · mtime 2026-07-10 23:44:29
```

**判读**：`risk_state.json` 的 `date` 字段是「日重置」推进器；它停在 7-15 意味着日亏/周亏/连亏全部不重置。同时卡片固定报「未接账户余额·非真实额度」→ 风险额度层整体降级。计划日志在涨、复盘日志不动 = 计划噪声 + 复盘缺位。

### 死心跳清单（同轮扫出，属 P1 清理项）

```
2026-07-16  data/monitor_heartbeat.json
2026-08-30  data/.btc_daemon_heartbeat.json
2026-08-29  data/watchdog_state.json
2026-07-10  data/protections_state.json
2026-09-02  data/source_circuit_state.json
```

---

## 5. 真 P1：XAU 四层退化 + 源限速无告警

```bash
cd "/d/Hermes agent" && python - <<'PY'
import json
d=json.load(open("data/xau_tv_state.json",encoding="utf-8"))
for tf,v in d["timeframes"].items():
    print(tf, v["high"], v["low"], f"振幅={(v['high']-v['low'])/v['close']*100:.4f}%")
PY
```

原始输出：

```
1D  4403.795   4297.93269  振幅=2.42%
4h  4348.56969 4348.29698  振幅=0.0063%
1h  4348.55869 4348.29795  振幅=0.0060%
15m 4348.55825 4348.29884  振幅=0.0060%
5m  4348.55678 4348.29904  振幅=0.0059%
```

四层振幅≈0.01%，与 D 层相差 400 倍 → 多周期定位实际失效（报告全出「中位·方向待选」）。

同源探针（`scripts/xau_ohlcv_source.py` 的 twelvedata 分支）：

```
1day  : n=3 -> OK
4h    : n=3 -> OK
1h    : n=3 -> OK
15min : NO RESPONSE
5min  : NO RESPONSE
```

`15min`/`5min` 间歇无响应（限速），而 `cross_check` 只用 5m 对 TV 校核、通过后即「采用 API 五周期」——**源限速没有触发降级告警**，退化直接进了卡面。

---

## 6. 审计工具坑：三个数字不一致

| 来源 | 数量 |
|:--|:--|
| `audit_preflight` | `Cron: total=14 enabled=9` |
| `hermes cron list` | 列出 **9** 个 |
| `cron/jobs.json` | **14** 个（其中 5 个 `enabled: false`） |

`hermes cron list` 只列 enabled 项。**禁用项必须直接读 jobs.json**，否则会误判「任务丢了」。

---

## 7. 跑脚本的几个固定坑（本轮各踩 1~3 次）

| 症状 | 原因 | 正确做法 |
|:--|:--|:--|
| `bash: cd: too many arguments` | 仓库路径 `D:/Hermes agent` 含空格，未加引号 | `cd "/d/Hermes agent/scripts"` |
| `bash: D:/Hermes: No such file or directory` | 直接执行含空格路径 | 整体加引号，或先 `cd` |
| 后台进程秒退、`output_preview` 只有 `bash: no job control` | `background=true` 下用 `cd path && cmd` | 用 terminal 的 `workdir` 参数，命令给绝对路径 |
| `uv pip install -p $(uv python find)` 报 `externally managed` | uv 托管解释器拒绝改 | 直接用 hermes venv 的 python 显式解释器 |

---

## 8. 并发写入方（本轮观察，未定论）

本轮审计进行中（23:46:58，两文件相隔 9ms）`scripts/auto_card.py` 与 `scripts/maintenance/repo_audit_20260911.py` 被外部程序改写，内容是把归档目录引用从 `_disabled_20260829` 同步为 `_disabled`；同时 memory 的「双 Python」条目被改写为「uv 依赖已补全」。

**纪律**：不要把外部改动记成自己的修复；报告里显式写「写入方未明」。审计开始时先存基线（`date` + `git status --short` + 关键 mtime），结束前再比一次 diff，否则修复清单与仓库实际状态对不上账。
