# cron 失败 incident：读取、分诊、收口

## 为什么必须单独看
Hermes 把每个 cron 的非零退出写进 `~/AppData/Local/hermes/cron/executions.db` 的 `cron_incidents`，
但**默认没有任何东西去读它**。只查 `hermes cron list` 的 `[active]` 或派发 `completed`，
会把「脚本连错上千次」读成「全 active、0 error」。看门狗层自己的停摆就在这里。

## 读
```bash
hermes cron incidents --state detected                          # 官方：未关闭列表
hermes cron incidents ack <incident_id>                         # 官方：关单（单条）
cat ~/AppData/Local/hermes/cron/output/<job_id>/<最新>.md        # 单次失败详情（stderr/stdout 都在）
```
- 状态三态：`detected` / `alerted` / `closed`。`closed` 对同一错误签名是终态；复发由**新的错误文本**开新条。
- incident id 形如 `<job前6>_<错误签名哈希>`：同签名反复只累加 `last_seen_at` 与计数，
  所以「3,700 条」可能只是**一个**作业的一种错误——先按 job 聚合再下结论。

## 为什么会出现上千条：易变的错误文本 = 去重失效
去重靠**错误签名**。如果作为签名的错误/退出消息里嵌了**易变数据（时间戳、价格、计数）**，
每次都是「新错误文本」→ 一个**持续性条件**会产出 N 条 incident。
实测：一个「配置里没有有效批准位」条件持续 12 天、作业每 2 分钟一跑 → **3,745 条**，
整张表被单一条件刷爆、彻底失去信号价值（于是长期无人发现）。

→ **写 cron 脚本的铁律：将作为签名的错误/退出消息必须稳定可复现**。
时间戳与数量放常规 stdout 日志，不要放进签名行。
（一个状态持续复现是**状态**，不是**故障**：用 stdout + 状态文件可见，别用非零退出码——见 SKILL.md 铁律 6。）

## 写一个聚合看门狗（推荐）
把上表读出来转成一行告警（已关闭的不算），落在 `data/cron_incidents_report.json` + 心跳：
- **只统计未关闭的**。否则修好之后还会按时间窗口继续报一整天（告警疲劳）。
- **发现失败也必须 exit 0**（见 SKILL.md 生命体征铁律 6）；DB 读不到才 exit 2。
- 报告内必须含 `data_freshness_watchdog.TIMESTAMP_KEYS` 认的键（`updated_epoch` / `ts` / `timestamp` / `time`），
  否则它会判「显式时间戳缺失」= `unavailable`，新登记反而变成新的误报源。

## 分诊（顺序不能颠倒）
1. **先分清「真失败」与「让路/竞争」**：共享同一资源的作业抢不到锁是**排队**（见铁律 7）。
   脚本按「让路 → exit 0」改完，这类竞争就不再产出 incident。
2. **再看是不是「没产出」类**：`Status: silent (empty output)` = 脚本无 stdout，与失败无关，
   属可观测性缺口（补心跳文件），不要动业务逻辑。
3. 只有真失败才改脚本；每一类都要能说出「改了什么 → 怎么验证的」。

## 收口（批量关单）
```bash
# 1) 先备份 DB —— 这是 Hermes 的内部状态，动手前必须留退路
python -c "import shutil;shutil.copy2(r'C:/Users/Administrator/AppData/Local/hermes/cron/executions.db', r'C:/Users/Administrator/AppData/Local/hermes/cron/executions.db.bak_<日期>')"
```
```python
# 2) 批量关单走 Hermes 自己的 API（= `hermes cron incidents ack` 背后同一个函数），不手写 SQL：
sys.path.insert(0, r"C:/Users/Administrator/AppData/Local/hermes/hermes-agent")
from cron.incidents import ack_incident
ack_incident(incident_id)     # 同时写 state/acked_at/closed_at，并遵守 closed 终态语义
```
几百条量级时逐条走 CLI 太慢；用上面的函数写个循环。手写 SQL 容易漏字段、
也绕过它自己的事务与终态判断——不要这么做。

```bash
# 3) 复核（必须真的复跑，不能只看代码）
hermes cron incidents --state detected   # 期望 “No cron failure incidents recorded.”
```

**关闭策略**（避免把还在发生的关掉）：
- **关**：① 根因已修**且已验证**（修后下一轮 cron 实跑 `completed`）② `last_seen_at` 已沉寂 >72h 的。
- **留开**：仍在复发且未修的——留着就是活的工作项。
- 关闭不等于删除：历史仍在表里，`hermes cron incidents --state closed` 可查。

## 先把「未关闭」分成三类，再决定动不动手（2026-09-16）

exit 1 不等于故障。实测 12 条未关闭里 **0 条是系统在坏**：
| 类别 | 特征（stderr/stdout） | 处置 |
|:--|:--|:--|
| **业务检测命中** | 叙事断言闸门：`⚠️ …存在「外部数字缺出处」`（脚本按设计命中即 exit 1） | 不是故障；修文案/补出处，或看单条 alert 明细 |
| **设计性让路** | `↷ …本轮让路：交互式分析进行中` / `共享图表锁被…占用` | 不是故障；修的是**判定口径**（让路不应计失败） |
| **真失败** | 抛异常 / rc 非预期 / 超时 | 才是工作项 |

自动闭环：`scripts/cron_incident_watchdog.auto_close_recovered` —— 作业失败后**连续 ≥2 轮
completed** 才自动 `closed`（优先走 `cron.incidents.set_incident_state`，账本不一致时退回等价 SQL）。
只成功一轮不关、失败后再挂过不关，所以「未关闭」的语义变成「**当前仍未恢复**」。
关闭是终态：同一签名再出问题由 Hermes 铸成新 incident，不会因为关旧单而失明。

## 验证“已修复”的硬标准
关单前必须有下一轮**实跑**证据，不能以“手动跑脚本成功”代替：
```bash
python -c "import sqlite3;p=r'C:/Users/Administrator/AppData/Local/hermes/cron/executions.db';c=sqlite3.connect('file:'+p+'?mode=ro',uri=True);print(c.execute(\"select job_id,status,started_at,substr(coalesce(error,''),1,60) from executions where job_id='<id>' order by started_at desc limit 5\").fetchall())"
```
另：patch 完被 cron 引用的脚本后，先 `find scripts -name "*.pyc" -delete` 再等下一轮，
否则可能跑的是旧字节码（看似修好、cron 仍失败）。
