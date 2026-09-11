# Cron Job 健康检查清单

## 触发条件
用户说"查任务/查监控/监控有问题/cron审计"时执行。

## 检查流程

### 1. 列全量
```
cronjob(action='list')
```
拿到所有 job 的 ID/name/schedule/last_status/enabled/state/no_agent/deliver。

### 2. 逐项判健康

| 检查项 | 信号 | 严重度 |
|--------|------|--------|
| last_status = "error" | 脚本崩溃/超时/非零退出 | P0 |
| state = "completed" + enabled | 一次性任务跑完没删，占位 | P2 |
| enabled = false + 曾有作用 | 关键监控静默下线 | P0 |
| deliver = "local" + 无脚本自带推送 | 用户收不到结果 | P1 |
| no_agent + script + last_status = "silent" | 脚本静默（可能是数据过滤、也可能是出错吞掉） | P1 |
| no_agent + script + timeout | 脚本耗时>120s默认超时 | P0 |
| LLM cron + 高频(≤2min) | token消耗巨大，考虑改 no_agent | P1 |
| 高频 cron(≤5min) + 同品种已有另一个 cron | 重复监控，竞争TV/Binance | P2 |

### 3. 检查输出文件
```
ls -lt ~/AppData/Local/hermes/cron/output/<job_id>/
```
- 看文件数量和时间密度是否匹配 cron 频率
- 读最新几个输出文件 → 确认内容质量
- no_agent silent 输出 → `cat` 确认是真实静默还是脚本bug

### 3b. 输出文件路径排查（last_status=ok 但找不到文件时）
- 检查脚本内部的 `DATA_DIR` 常量——可能指向 `~/AppData/Local/hermes/data/` 而非项目 `data/`
- 详见 `references/cron-output-path-debugging.md`
- 常见盲区：`ls data/` 查不到不表示脚本没输出，可能是路径不同

### 4. 检查缺失覆盖
对照驾驶舱数据源清单，确认每个采集器都有对应 cron：
- ETF Flow → 应每小时一次 no_agent
- Dune 链上 → 应每30分钟一次 no_agent
- COT 持仓 → 应每周六一次（周五CFTC发布）
- Deribit 期权 → 应每30分钟一次 no_agent
- XAU/USD 监控 → 应有定期分析 cron
- Orion 雷达 → 应正常（不超时）

### 5. 检查重复/冲突
- 两个 cron 同品种同周期 → 合并
- LLM cron 用不同 provider → provider 挂了时备份有效，但成本高
- cron deliver 目标是否一致（中途换了群/话题？）

### 6. 报告格式
```
## Cron 健康审计

| 总数 | 正常 | 异常 | 缺失 |
|------|------|------|------|
| N    | N    | N    | N    |

### 异常项
| Job | 问题 | 修复 |
|-----|------|------|

### 缺失项
| 数据源 | 建议频率 | 脚本 |
|--------|----------|------|
```

## 常见修复

| 问题 | 修复 |
|------|------|
| no_agent timeout 120s | 脚本拆小、加缓存、减API调用层数，或 cronjob update 无超时参数→改脚本 |
| silent 脚本无输出 | 脚本加 print() 中间状态，测试 `python script.py` 确认有 stdout |
| LLM 高频烧 token | 转 no_agent Python 脚本 |
| deliver=local 无推送 | 改 `deliver='telegram:-1003733144325:846'` 或在脚本内 send_telegram() |
| 指标缓存 cron 禁用 | 检查是否 TV CDP 断连导致，先修连接再重启 |

## Cron Prompt 陷阱

### 字面量 `\n` 问题
`cronjob(action='update', prompt="...")` 的 prompt 字段**不支持转义序列**。如果你写成：
```
prompt="只输出分析卡\n不要前言\n\n表格格式"
```
`\n` 会被存储为字面文本（两个字符）而非换行符。LLM 看到的是 "只输出分析卡\n不要前言\n\n表格格式" 而不是三段文本。这会导致：
- LLM 不理解格式指令（换行不生效）
- 输出变成骨架/占位符（"报告已生成并自动投递"）而非实际分析内容
- 在 cron 输出文件中看到 response 只有一两行

**修复方法**：构建 prompt 字符串时直接使用实际换行（如 Python f-string + 三引号），不要依赖 `\n`。在 cronjob JSON schema 中换行符正确传递为 UTF-8 字面量。

### 显式工具指令
LLM cron 如果没有明确告诉代理可用哪些工具，代理可能默认只使用 `web_search`。特别是 `x_search`（Grok 驱动）和 `tool_call` 类的 MCP 工具，**必须**在 prompt 里显式提及名字。例如：
```
你必须使用 x_search 工具（xAI Grok 驱动）来搜索 X/Twitter 实时讨论。
```
不加显式指令 → 代理直接跳过这个工具 → 数据源降级。

### Prompt 自包含要求
Cron 在隔离的会话中运行，没有上下文继承。prompt 必须：
- 完整描述任务目标和输出格式
- 列出所有可用的工具和搜索词
- 包含退化路径（工具不可用时怎么办）
- 指定 deliver 格式（纯文本、Markdown、表格）

### 输出格式验证
跑完后检查 cron 输出文件：
```
ls -lt ~/AppData/Local/hermes/cron/output/<job_id>/
```
新文件应该在 30-120 秒内生成。检查 Response 部分是否包含有效内容，不仅是系统占位符。如果 LLM cron 输出只有"报告已生成"之类的话，说明 prompt 解析失败了。

---

# Cron 高频任务错峰分散模式

> 场景：Hermes cron 列表中多个高频任务（`*/3` `*/5` `*/10` `*/15` `*/30`）全部落在默认分钟标记（`:00` `:15` `:30` `:45`），导致同分钟并发触发，争夺 CPU/网络/API 速率限。

## 检测方法

```bash
# 1. 拉取全量 cron
cronjob(action='list')

# 2. 提取 schedule + name，按分钟模式分组
# 关注模式：*/3, */5, */10, */15, */30, 0 */2, 30 */2 等
```

## 问题示例（本次审计实况）

| Cron ID | 名称 | Schedule | 默认触发分钟 | 冲突组 |
|---|---|---|---|---|
| 54661a43c839 | BTC守护看门狗 | `*/5 * * * *` | `:00 :05 :10 :15 :20 :25 :30 :35 :40 :45 :50 :55` | A |
| 020e260f5ac0 | 行情守望看门狗 | `*/3 * * * *` | `:00 :03 :06 ... :57` | A |
| b78741992dfd | TV Desktop保活 | `*/10 * * * *` | `:00 :10 :20 :30 :40 :50` | A |
| 113655ad34b5 | XAU TV现场同步 | `*/15 * * * *` | `:00 :15 :30 :45` | A |
| 8fe56a00eb8b | 影子结果标注 | `*/15 * * * *` | `:00 :15 :30 :45` | A |
| 5db6dd683b1d | 清算压力监控 | `12 8,10,12,14,16,18,20,22 * * *` | `:12` (错峰已生效) | B |
| 0764c6922694 | Deribit期权刷新 | `9 8,10,12,14,16,18,20,22 * * *` | `:09` (错峰已生效) | B |

**冲突组 A**：每小时在 `:00` 有 5 个任务同时触发，`:15` 有 4 个，`:30` 有 5 个，`:45` 有 4 个。

---

## 错峰分配原则

### 频次到偏移映射表

| 频次 | 推荐偏移分钟 (避开 :00/:15/:30/:45) | 示例 cron 表达式 |
|---|---|---|
| `*/3` (每3分) | `1,4,7,10,13,16,19,22,25,28,31,34,37,40,43,46,49,52,55,58` | `1-59/3 * * * *` |
| `*/5` (每5分) | `2,7,12,17,22,27,32,37,42,47,52,57` | `2-59/5 * * * *` |
| `*/10` (每10分) | `3,13,23,33,43,53` | `3-59/10 * * * *` |
| `*/15` (每15分) | `7,22,37,52` | `7,22,37,52 * * * *` |
| `*/30` (每30分) | `2,32` | `2,32 * * * *` |
| `0 */2` (每2小时整点) | `5,35` (即 `:05` `:35`) | `5,35 */2 * * *` |
| `30 */2` (每2小时半点) | `5,35` (改到 `:05` `:35`) | `5,35 */2 * * *` |

### 分配算法（可手工或脚本化）

```python
def assign_offsets(jobs: list[dict]) -> dict[str, str]:
    """
    jobs: [{id, name, schedule, priority}]  priority: 采集>分析>维护>保活
    返回 {job_id: new_schedule}
    """
    # 1. 按频次分桶
    # 2. 每桶内按 priority 排序
    # 3. 依次分配偏移，避免同分钟 ≥2 个任务
    # 4. 采集类优先整点偏移，分析类滞后 5-10 分钟形成管道
    
    offsets = {
        "*/3":  [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34, 37, 40, 43, 46, 49, 52, 55, 58],
        "*/5":  [2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57],
        "*/10": [3, 13, 23, 33, 43, 53],
        "*/15": [7, 22, 37, 52],
        "*/30": [2, 32],
    }
    # 实际分配逻辑略...
```

---

## 本次审计的错峰建议

| Job ID | 旧 Schedule | 新 Schedule | 理由 |
|---|---|---|---|
| 54661a43c839 | `*/5 * * * *` | `2-59/5 * * * *` | BTC守护优先，给采集留 :00 |
| 020e260f5ac0 | `*/3 * * * *` | **删除/禁用** | 冗余看门狗，保留 watchdog.py 常驻版 |
| b78741992dfd | `*/10 * * * *` | `3-59/10 * * * *` | TV保活非核心，偏移 :03 |
| 113655ad34b5 | `*/15 * * * *` | `7,22,37,52 * * * *` | XAU采集，偏移 :07 |
| 8fe56a00eb8b | `*/15 * * * *` | `8,23,38,53 * * * *` | 影子标注非实时，再错峰 1 分钟 |

---

## 验证方法

修改后运行：
```bash
cronjob(action='list')
```
检查每个 cron 的 `next_run_at`，确认同分钟无 ≥2 个高频任务。

---

## 陷阱提醒

1. **`*/n` 不是标准 cron 语法的全部实现** — Hermes 使用标准 cron 解析器，支持 `*/n`、`m-n/k`、`a,b,c` 列表。推荐用 `m-n/k` 显式指定偏移范围。
2. **每小时/每2小时任务也要错峰** — `0 */2` 与 `*/30` 在 `:30` 撞车。改为 `5,35 */2`。
3. **采集→分析管道要留时间差** — 采集 cron 在 `:02`，分析 cron 在 `:07`，确保数据落盘完成。
4. **修改 cron 后需验证 `next_run_at`** — 不是看表达式，要看实际下次触发时间。

---

# Telegram 投递审计双轨制清单

> 场景：用户问"我的任务有哪些推到 Telegram / 为什么不推 / 哪些推了"。**不能只看 cron 的 `deliver` 字段**，必须双轨并行审计。

## 双轨审计法

### 轨道 1：Cron 框架层 (`jobs.json`)

```bash
# 1. 拉取全量 cron
cronjob(action='list')

# 2. 筛选 deliver=telegram 的任务
jq '.jobs[] | select(.deliver=="telegram") | {id,name,script,schedule,deliver,origin}'
```

**局限**：`deliver=local` ≠ 不推 Telegram。脚本内部可能直连 Bot API。

---

### 轨道 2：脚本源码层（直连扫描）

对每个 cron 的 `script` 字段，扫描以下特征：

| 特征 | 搜索命令 | 说明 |
|---|---|---|
| `send_telegram` | `grep -r "send_telegram" scripts/` | Hermes CLI 封装 |
| `api.telegram.org` | `grep -r "api.telegram.org" scripts/` | 直连 Bot API |
| `telegram_direct` | `grep -r "telegram_direct" scripts/` | `telegram_direct.py` 兼容层 |
| `telegram_reliable` | `grep -r "telegram_reliable" scripts/` | 可靠推送库 |
| `push_tg_rich` | `grep -r "push_tg_rich" scripts/` | RichMarkdown 真表格推送 |
| `TARGET = "telegram:` | `grep -r 'TARGET = "telegram:' scripts/` | 硬编码目标 |

**输出格式**：
```
脚本路径 | 直连方式 | 目标话题 | 触发条件 | 是否受 deliver 控制
```

---

### 常驻 Daemon 单独审计

Cron 之外，常驻后台进程同样会推 TG，**不在 `jobs.json` 中**：

| 进程 | 心跳文件 | 推送入口 | 目标话题 |
|---|---|---|---|
| `btc_daemon.py` | `.btc_daemon_heartbeat.json` | `push_tg()` → `send_telegram_direct` | 386 |
| `行情守望.py` | `monitor_heartbeat.json` | `push()` → `telegram_direct` | 385/386/416/846 |
| `watchdog.py` | `watchdog_heartbeat.json` (无) | `send_watchdog_alert()` | 416 |

**审计动作**：
1. `ps aux | grep -E "btc_daemon|行情守望|watchdog"` 确认存活
2. 读对应源码，确认推送路径与话题
3. 检查是否有 `HANGQING_NO_SEND=1` 抑制开关

---

### 手动/一次性脚本

搜索项目内所有 `.py` 的 `send_telegram`/`telegram_direct`/`push_tg_rich` 调用，排除上述 cron/daemon 已覆盖的，剩余即为手动/一次性推送入口。

---

## 审计报告模板

```markdown
## Telegram 投递全景审计报告

### Cron 框架层 (deliver=telegram)
| Job ID | 名称 | 脚本 | Schedule | Origin Thread | 受控 |
|---|---|---|---|---|---|
| abc123 | Orion雷达 | orion_screener_radar.py | 2 8,10... | 455 | ✅ |

### 脚本直连层 (绕过 deliver)
| 脚本 | 方式 | 目标 | 触发条件 | 受控 |
|---|---|---|---|---|
| btc_daemon.py | telegram_direct | 386 | 评分≥8 且 非冷却 | ❌ |
| 行情守望.py | telegram_direct | 385/386/416 | 警报/计划触发 | ❌ |
| data_freshness_watchdog.py | push_tg_rich | 846 | 有过期文件 | ❌ |
| btc_ref_levels_sync.py | push_tg_rich | 846 | 关键位更新 | ❌ |

### 常驻 Daemon
| 进程 | 心跳 | 目标话题 | 抑制开关 |
|---|---|---|---|
| btc_daemon.py | .btc_daemon_heartbeat.json | 386 | 无 |
| 行情守望.py | monitor_heartbeat.json | 385/386/416/846 | HANGQING_NO_SEND=1 |

### 结论与建议
- 共有 **N** 条投递路径，**M** 条受 cron `deliver` 控制，**K** 条直连
- 建议：将直连脚本的目标话题统一由 `alert_target_for(symbol)` / `report_target()` 路由
- 增加统一抑制开关 `TELEGRAM_SILENT=1` 供维护窗口使用
```

---

## 检查工具化

```bash
# 一键扫描所有脚本的 TG 直连调用
grep -r -E "send_telegram|telegram_direct|telegram_reliable|push_tg_rich|api\.telegram\.org" \
  --include="*.py" scripts/ | \
  grep -v "__pycache__" | \
  awk -F: '{print $1}' | sort -u
```

将输出逐个读源码确认目标话题与触发条件。