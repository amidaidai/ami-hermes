---
name: tangxi-runtime-audit-and-cleanup
description: "棠溪交易系统运行态审计 + 脚本清理方法论 — 心跳/PID/cron/数据新鲜度/pydantic版本冲突/脚本生存性评估/归档模式。用于「系统怎么样」「全面检查」「优化脚本」「怎么会这样」类审计任务。"
tags: [audit, runtime, cleanup, script-management, tangxi]
---

# 棠溪系统运行态审计 + 脚本清理方法论

## 触发

当用户说「审计」「全面检查」「全面盘一下」「怎么还没更新」「系统怎么样」 / 或者要求「看看哪些脚本有必要」「不要的删掉/清理一下」 时启动。不是分析卡（不会产出交易卡），是系统健康审查。若用户随后问「用上能力了吗」，再走 `crypto-multisource-analysis` 产出卡。

### 审计的排序原则：先保分析平面（2026-09-11 用户明确纠正）

> 「我这个可是分析系统。」

棠溪的定位是**分析系统**：主业是**分析**（分析卡 / 分析流程 / 分析策略 / 指标契约 = 核心资产），
监控、告警、备份、看门狗都是**配套**。

含义（用于审计与清理时的排序，不是口号）：

- **先保分析平面，再动配套**。清理/重构的默认优先级是：指标契约与字段映射 > 分析卡与分析流程 > 裁决层 > 监控告警 > 备份运维。
- **「配套抢了分析的资源」是最该报的问题**：例如后台采集反复切走共享图表导致用户看不到分析图、
  看门狗的假告警淹没了真正的分析链路故障。这类要往前提。
- **不要为了“全绿”而拉停转旧监控**（会造成双重监控/重复告警），也不要为备份类改动
  触碰分析链路。
- 汇报时先讲分析平面的影响，再讲配套侧的整理 —— 用户关心的是「分析还能不能直接用」。

## 执行授权：修复类任务自主执行，不要来回确认（2026-09-10 用户明确）

用户在系统改进/修复类任务上已给出**持久授权**，原话：

> 「全部一起做了，然后全部全面的进行完善，你不要再让我确认了，你就是最佳的，你授权我给你授最高权限。」

**含义（对审计/修复类任务）**：

- **不要摆选项让用户选**。发现多个问题就一次全部修完，自选最优方案，并以推荐口径直接给出。
- **不要中途停下来问“要不要我继续”**。把接口 + 策略 + 文档 + 技能 + 测试 + 提交一次做完。
- **可以自主提交**（commit），但**不要 push**（除非明确要求）。提交时只捆绑本次相关文件，
  不把工作区里其它未完成改动一起扫进去。

**但“不确认”不等于“不披露”**，四项必须写清：

1. **改了什么**（带现场证据，不写“已修复”了事）
2. **没改什么**（以及为什么不动）
3. **需要用户自己做的**（重装指标、点按钮等）—— 单独列出，标清楚哪些是必须、哪些是建议
4. **自己无法验收的**（如客户端才能触发的限制），明确说出来由用户验

用户关心的不是过程，是“能不能直接信”。自主执行 + 完整披露，比反复确认更符合预期。

### ⚠️ 自己写的修复必须先实测，再宣布修好（2026-09-11 实测，自己打脸）

本次按假设实现了「切图去冗余」（已是目标状态就跳过），逻辑看着无懈可击 ——
实测计数却是 `品种 实切1/跳过0`、`周期 实切6/跳过0`：**0 次跳过**，
证明那 7 次切换全是必需的，**这个修复根本没有减少用户看到的切换**。

两条铁律：

1. **任何「优化/减少/加速/去冗余」类修复，落地后必须跑一次并把数字读出来。**
   加计数器（`实切N/跳过N`）比读代码可靠得多。没有实测数字就写成「已修复」＝ 谎报。
2. **修复自身也可能静默空转。** 在脚本侧加「自动重接总线」时踩到：底层的 CLI
   子命令返回 `success:true` 却什么都没改，于是这个「自动修复」每轮只会刷一条假告警
   —— **放弃它才是对的**，一个「看着成功其实没做」的修复比不修更糟。

**判据：写操作一律行为验收（读回值 / 面板文案 / 副作用计数），不信返回值。**
修完发现自己想错了就直说「这个修复没解决你的问题」—— 本次正是如此披露，
比含糊过关好得多。用户要的是「能不能直接信」，不是「你有没有干活」。

#### 已实测确认会「静默空转」的操作（2026-09-11，全部经独立通道复核）

| 操作 | 返回 | 真相 | 复核方式 |
|---|---|---|---|
| **CLI** `tv indicator set <id> -i '{...}'` | `success:true` | `updated_inputs:{}` —— **什么都没改** | 改完读面板文案（S-code 是否一致） |
| **CLI** `tv indicator get <id>` | `success:true` | `inputs: []` —— 元数据未加载，读不到 | 不要用它做读回校验 |
| **MCP** `tab_new` | `success:true, action:new_tab_opened` | **一个页都没开**（它发完 Ctrl+T 不校验） | `curl 127.0.0.1:9222/json/list` 数 page 数 |
| `pine_list_scripts` / `pine_open` 行数 | 有值 | 有缓存 / 不证明内容 | 用 `pine_get_source` 做 sha 逐字节比对 |

**对照：MCP 那条 `indicator_set_inputs` 是好的**（返回 `updated_inputs:{"in_164":"sQC3ma$49"}`
且行为可验）。同一功能走 CLI 和走 MCP 结果不同 —— **判断某操作能不能用时，
要按具体通道分别验，不能一杆子扫一类。**

**推论**：脚本侧想做「自动修复」时，先确认底层写操作真的有写入能力；
否则宁可**不写**那个自愈逻辑，把检查放到 Agent 侧（每次分析前用 MCP 做）。

### 交付约定：交付物是“文件”时，最终消息必须直接给可点链接

实测教训：用户问「文件呢？」—— 报告.md 写了但只放在交付目录里、正文没给可点链接，
用户等于没拿到东西。**判断标准：任务的产出物是什么，最终消息里那东西就必须是
可直接点开的链接（带绝对路径 + sha），而不是“详见 XX 目录”。**

指标类任务的交付格式（本次变体：用户要“最终版我下载”）：

```
**主指标** → [XXX.pine](<C:/Users/.../XXX.pine>)
　3449 行 · f35aefb149dccd19bd9b210c
**副指标** → [YYY.pine](<C:/Users/.../YYY.pine>)
　928 行 · c398a902675ece4c134e3d88
```

并且必须**逐字节核过**、写清哪份正在图表上跑、哪份更新但未装、装上去需要补什么步骤：

| | TV 账号上正在跑的 | 你下载到的 | |
|---|---|---|---|
| 副指标 | 928 行 · `c398a9…` | 928 行 · `c398a9…` | **完全一致** ✓ |
| 主指标 | 3445 行 · `98d633…`（v13） | 3449 行 · `f35aef…`（v15） | 差一处 |

核验方法：`pine_open(name)` 只返回行数、`pine_list_scripts` 有缓存、**都不能当源码凭证**；
要用 `pine_open` 打开后 `pine_get_source` 读编辑器内容，做 sha 逐字节比对。
（详见 `tradingview-pine-indicators` 的 `references/pine-na-aggregate-poisoning-20260910.md`
与 `tradingview-indicator-analysis` 的 `references/pine-install-via-mcp-20260910.md`。）

## 审计 8 步（Runtime）

| 步 | 动作 | 关键文件/命令 | P0 信号 |
|---|------|---------------|---------|
| 0 | 心跳检查 | `data/*_heartbeat.json` / 看门狗 | `status=stopped` / >5min 过期 |
| 0.5 | **Python 依赖完整性** | `python -c "import pydantic,pydantic_core"` | `SystemError: incompatible pydantic-core` → 立即 P0 (2026-08-29 新增) |
| 1 | 进程扫描 | `psutil` 枚举 `python.exe` daemons | 同脚本 >1 实例 |
| 2 | Cron扫描 | `cat ~/Local/hermes/cron/jobs.json` | 关键任务 `enabled: false` |
| 3 | 数据新鲜度 | 7类关键 data/ 文件 (下文详述) | btc_ref_levels >1h / protections >3d |
| 4 | TV MCP 连通 | `http://127.0.0.1:9222/json/version` | 9222 关 |
| 5 | API 可达性 | `curl -m3 https://fapi.binance.com/fapi/v1/ping` | 403/超时 |
| 6 | 实跾管线 | `timeout 90 python scripts/auto_card.py BTCUSDT` | exit≠0 / 缺GO/NO-GO |
| 7 | 脚本清理 | 生存性评估 → 归档/删除 | 83 个可删除 (2026-08-29) |

---

## Step 0.5：Python 依赖兼容性检查 (2026-08-29 新增)

**这是全系统级断路器**。MCP client SDK (`mcp.client.stdio`) 依赖 pydantic/pydantic-core，这俩如果版本不兼容，整个 TV 链接链条立刻崩。

```bash
python -c "import pydantic, pydantic_core; print(pydantic.__version__, pydantic_core.__version__)"
```
- 正确 → `2.13.4 2.46.4` (或兼容版本)
- 冲突 → `SystemError: The installed pydantic-core version (2.48.0) is incompatible... requires 2.46.4` → **P0**，立即修：

```bash
pip install 'pydantic-core==2.46.4' --force-reinstall
# 或升级 pydantic
pip install 'pydantic==2.13.4' --force-reinstall
```

**2026-09-02 扩展：双 Python 解释器陷阱。** 上面的 `python -c ...` 用的是 shell 里 `python` 解析到的解释器（hermes venv），但 `auto_card.py:4806` 与 cron `script` runner 实际用的是 uv 管理的 `cpython-3.11-windows-x86_64-none\python.exe`（Windows 短名路径）。如果 `python` 能 import pydantic 而 `auto_card` 跑 quick 仍 `ModuleNotFoundError`，**用错了解释器**。详细诊断 + `--break-system-packages` 装包 recipe 见 `hermes-windows-maintenance` skill 的 `references/uv-cpython-3-11-short-name-2026-09-02.md`。铁律：Step 0.5 必须用 cron 实际调用的解释器（不是 shell 里的 `python`）测试，审计完必跑一次 `auto_card BTCUSDT --quick` 用**同一解释器**确认 `ModuleNotFoundError` 彻底消除。

## Step 1：心跳 + 守护进程存活 (P0)

先做**生产权威发现**，再判断心跳：读取兼容层脚本头部、Cron `paused_reason`、当前活动任务和下游读取路径，确认哪个守护链才是现役权威。旧 `monitor_heartbeat.json` / `.btc_daemon_heartbeat.json` 即使过期，只要对应脚本已明确退役且现役 `keylevel_guard` 链完整，就不是 P0；禁止为追求“全绿”重新拉起旧守护造成双重监控。

当前关键位生产链必须成对：`keylevel_guard.py` 进程 + `.keylevel_guard_heartbeat.json` 心跳 + `btc_keylevel_guard_watchdog.py` Cron；到价消费链另查 `keylevel_read_trigger.py` Cron。审计时仍可读取所有历史心跳，但必须按“现役/兼容/退役”分类。

```bash
# 批量取证，不直接据此判死活
cat data/monitor_heartbeat.json 2>/dev/null          # 旧行情守望（先核是否退役）
cat data/.btc_daemon_heartbeat.json 2>/dev/null      # 旧BTC daemon（先核是否退役）
cat data/.keylevel_guard_heartbeat.json 2>/dev/null   # 现役关键位守护
cat data/.keylevel_guard_health.json 2>/dev/null      # 业务健康：有效批准位数量
```

### 守护进程实例数（psutil 过滤）

```python
import psutil, os, sys
DAEMON_PATH = "D:\\Hermes agent\\scripts\\btc_daemon.py"  # 示例
me = psutil.Process(os.getpid())
real_pids = []
for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
    except (KeyError, TypeError):
        continue
    if str(DAEMON_PATH) in cmd and 'bash' not in cmd and '-c import psutil' not in cmd and p.info['pid'] != me.pid:
        real_pids.append(p.info['pid'])
print(f"真实守护进程数: {len(real_pids)}")
assert len(real_pids) <= 2, f"多实例 P0: {real_pids}"
```

### 多实例复发修复铁律

1. `psutil` 列出所有 cmdline 含 `xxx_daemon.py` 的进程全部 `terminate()` → `kill()`
2. 删除 `.xxx.pid` + `.xxx.lock`
3. **不手动启动** → 等看门狗 cron 下次触发自动拉起
4. `psutil` 验证新进程 PID 写入 back，等待 2 个 cron 周期确认单实例

## Step 2：关键 cron 停用扫描 (2026-08-29 新增 P0)

不要把“暂停数量”直接等同于 P0。逐个核对 `enabled`、`state`、`paused_reason`、脚本是否存在、最近运行结果和替代守护链；迁移后由新守护接管的旧任务可以是有意归档设计。只有关键能力没有任何活动替代、或 enabled/state 矛盾导致调度器自动禁用时，才升级为 P0。

对每个关键任务先做“能力唯一性”检查，再做状态修复：确认当前生产权威、脚本入口和数据输出，避免重新启用旧监控/旧推送控制器造成双重拉起、重复告警或越权外发。

```bash
# 白名单 (来自 references/critical-cron-whitelist.md)
python -m hermes_cli.main cron list | grep -E "BTC|XAU|TV|守护|看门狗|同步|推送"
```

关键白名单：
- BTC关键位同步 (btc_ref_levels_sync.py)
- XAU TV现场同步 (xau_tv_sync.py)
- BTC关键位守护看门狗
- BTC关键位到价分析推送
- liq_listener_btcusdt

→ **缺一个 P0**。本次审计发现 BTC守护看门狗、行情守望看门狗、TV Desktop保活 停用 → 数据过期 49 天。

修复：编辑 `jobs.json` → `enabled: true`, `state: "scheduled"`。

## Step 2.5：业务健康不等于进程健康

心跳/PID 只说明进程存活，不说明业务配置可用。关键位守护还必须统计唯一批准源中“显式启用且未过期”的有效位数量；数量为 0 时写入 degraded 健康状态并阻断基于旧位的触发，不要机械延长有效期。TV/快照也要同时检查品种身份、根时间戳、嵌套子源时间戳和内容完整性。

### 批准关键位过期的安全恢复闭环

1. 先运行 `keylevels_collect.py`，完成 TV 五周期切换、20秒指标重算和品种/周期门禁，生成新的 `keylevels_candidates.json`；采集失败或候选为空时保留旧候选池。
2. 候选池只是候选，**不得自动升格**。人工复核后，把选中的名称/价格、候选时间戳和新的 `valid_until` 写入唯一批准源 `keylevels_config.json`；旧“现位/路径”若新池已不存在，应以新的稳定结构位替换，不能只续旧价格。
3. 手动执行 `btc_keylevel_guard_watchdog.py`，预期 exit 0，并读回 `.keylevel_guard_health.json` 确认 `active_approved_levels>0`。
4. 触发或等待一次看门狗 Cron，读回精确任务确认 `last_status=ok`；同时检查 `keylevel_read_trigger.py` Cron 为 ok。
5. 最后运行 `audit_preflight.py` 与关键位契约测试；只有 `active=configured>0`、守护心跳新鲜、两个活动 Cron 均 ok 才算恢复。

**不要**通过删除 `valid_until`、“无条件延长旧位”或自动批准整个候选池来消除 degraded；那会把安全停机改成旧数据静默运行。完整实测案例见 `references/keylevel-expiry-recovery-2026-09-02.md`。

### TV 五周期续航与共享图表恢复契约

五周期缓存 TTL 很短时，不能只靠用户发起分析刷新，也不能把批准位续期误当成 TV 数据续航。独立 no-agent 续航任务应在严格 TTL 到期前检查，只有 stale 才采集；任务必须 `deliver=local`、与 XAU 错峰、持有跨进程 TV 锁，并以“新时间戳＋五层完整＋候选非空”判成功。

后台采集的原子顺序固定为：**记录进入状态 → 切目标品种/周期 → 等待指标重算 → 采集五层 → 切主执行周期并等待 → 刷新行动格 → 校验配对缓存 → 原子发布 → 恢复进入状态 → 等待重算 → 读回 symbol/timeframe/studies**。禁止在行动格刷新前先恢复图表；否则后续刷新会再次切回采集品种，出现“日志称已恢复、最终状态却被覆盖”的竞态。

### ⚠️ “恢复进入时状态”会形成永久棘轮（2026-09-10 实测，用户报「图表怎么总是在黄金5分钟」）

共享图表上的后台任务，最常见的写法是「记录进入时看到的品种/周期 → 切走采集 → 采完恢复」——
逻辑看着对，但它有一个致命性质：**它把「进入时看到什么」当成真理**。

```
某次运行被 cron 超时杀掉 / 恢复失败
  → 图表停在采集品种（如 OANDA:XAUUSD 5m）
  → 下次运行记录的 previous 就是 XAU 5m
  → 它尽职地把图表「恢复」成 XAU 5m
  → 从此永久锁死，用户怎么切都没用
```

**这不是偶发失败，是自持稳态。** 排查时不要去找「谁切走了图表」——
要去看那个**恢复目标怎么算出来的**。

**修法：加一个「图表归属」状态文件，把“用户的图表”与“待归还目标”持久化。**

| 进入时看到 | 处理 |
|---|---|
| 非本任务品种（用户的图） | 记为用户图表 + 写入待归还目标 |
| 本任务品种 + **存在待归还记录** | **上次没还 → 用记录修回来**（打断棘轮） |
| 本任务品种 + 无待归还记录 | 用户真的在看这个品种 → 不动 |

成功归还后**清掉待归还标记**。于是：一次失败最多多留一个采集周期，下次运行自动修回。

```python
# 判据核心：只在“看到非本任务品种”时才更新用户图表记录
def resolve_restore_target(cur_symbol, cur_tf):
    state = load_owner()
    if cur_symbol and cur_symbol.upper() != OUR_SYMBOL.upper():
        state['pending_restore'] = {'symbol': cur_symbol, 'resolution': cur_tf}
        save_owner(state); return state['pending_restore']
    pending = state.get('pending_restore') or {}
    if pending.get('symbol'):
        return pending          # ← 打断棘轮的关键分支
    return {'symbol': cur_symbol, 'resolution': cur_tf}
```

**验收必须覆盖 5 例**（不能只测正常路径）：正常路径 / 残留修复 / 连续残留不漂移 /
用户真在看采集品种时不干扰 / 空状态安全。实测 6/6。

**实盘验证信号**：状态文件里同时有 `captured_at` 与 `restored_at` 两个时间戳，
且 `pending_restore` 已被清空 —— 这就是「采完确实还给用户了」的直接证据。
（本次现场：`captured_at 22:46:32` → `restored_at 22:48:33`。）

**同类风险清单**：任何“先切换共享资源再恢复”的脚本都要过一遍这个模型 ——
TV 图表品种/周期、浏览器标签、剪贴板、共享锁文件。判据：
**恢复目标是从「当前状态」推出来的，还是从「一份被持久化的、能区分自己与用户的记录」推出来的？**
前者就会形成棘轮。

### 批准的快速续期分支（existing_levels_only，2026-09-03 实测）

上面是**严格恢复路径**（重采集＋人工复核＋替换候选）。但存在一种合法的**快速续期**：**不重采集、只对唯一批准源里已经用户批准的位刷新 `valid_until`**（即 config 里的 `approval_renewal.mode: existing_levels_only`）。合法前提：
- 这些位**已在 `keylevels_config.json` 中且经用户批准**（不是候选池自动升格）；
- 各位仍在当前价格的可接受波段内（用于“仅价格事件监控”，不承载方向判断）；
- 用户明确授权自动续期（如“自动完成/续期用现有批准位”），而非要求重采集。

```python
CFG='data/keylevels_config.json'; TZ=timezone(timedelta(hours=8)); now=datetime.now(TZ)
shutil.copy2(CFG, CFG+'.bak.renew_'+now.strftime('%Y%m%d_%H%M%S'))
d=json.load(open(CFG))
new_until=(now+timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M:%S+08:00')  # 与“6小时有效”契约一致
for lv in d['symbols']['BTCUSDT']['levels']:
    if lv.get('enabled'): lv['valid_until']=new_until
d['updated_at']=now.strftime('%Y-%m-%dT%H:%M:%S+08:00')
d['approval_renewal']={'mode':'existing_levels_only','renewed_at':now.strftime('%Y-%m-%dT%H:%M:%S+08:00'),'valid_until':new_until,'source':'自动续期(现有批准位)'}
json.dump(d, open(CFG+'.tmp','w',encoding='utf-8'), ensure_ascii=False, indent=2); os.replace(CFG+'.tmp', CFG)
```

**验证**：直接跑 `python scripts/btc_keylevel_guard_watchdog.py`（成功应 exit 0 + “guard alive”），再读回 cron 任务确认 `last_status=ok`（本会话 `deacfc57ffd6` 由 `failed/DEGRADED` 转 `ok`）。快速续期只解**过期降级**，不解位本身失效——若位已明显偏离现价，仍应走严格路径重采集替换。

### ⚠️ 上一节的快速续期**有一个致命缺口**（2026-09-10 实战，漏了停摆 5 天）

上面只刷 `valid_until`，但 `active_approved_level_count()` 要求**两个**条件同时成立：

```
1. structure_review_is_current(config)   ← auto_approval_policy.max_structure_age_hours 内有人复核过结构
2. 每个位 level_is_active()             ← enabled + valid_until 未过期
```

只刷 `valid_until` 只解决第 2 条。第 1 条靠的是 `auto_approval_policy.structure_reviewed_at`，而
**这个字段此前只有手工能写、没有任何脚本或 cron 会写它** —— 于是任何一次人工复核之后
最多 24 小时监控必然停摆。实测：`structure_reviewed_at` 停在 09-04，`valid_until` 09-05 16:14
过期，此后看门狗持续 `DEGRADED: keylevels_config 当前无有效批准关键位`，守护进程心跳停了 3.5 天。

症状识别：`AUTO-RENEW skipped error=structure_review_required`。

**不要盲目回写 `structure_reviewed_at`** —— 那道闸的存在意义就是“有人真的看过结构”。
正确修法是**给它真的补一个生产者**（`scripts/keylevels_structure_review.py`）：

1. 读当前 SVP 价值区读数（用 **已有 cron 在刷的缓存**，不要为复核再占一次 TV 图表）
2. 逐位与**同名的当前读数**比对：漂移须 ≤ 2.5%（无同名读数的位走 ±10% 价格带）
3. **全数通过才盖 `structure_reviewed_at`**；任一失效即不盖，并列出待重新批准的位
4. 接在看门狗里，跑在 `auto_renew_existing_approved_levels()` **之前**

严格口径的理由：盖章会让看门狗把这批位**整体**续期（含已失效那个）→ 监控一个假价 → 发假警报。
宁可让闸落下、要求人工重新批准，也不放行已知失效的位。另加最小盖章间隔（如 30 分钟），
避免看门狗每 2 分钟写一次盘。

实测恢复：复核 8/8 通过 → 盖章 → 续期 8 位 → 看门狗重启死掉的守护进程 → `status: ok, active_approved_levels: 8`。
完整取证与验收清单见 `references/unsatisfiable-safety-gate-recovery-20260910.md`。

### ⚠️ 通用审计项：TTL 安全闸的输入字段没有生产者

这类隐蔽停摆会反复出现，把它当成一个固定的审计步骤：

```bash
# 对每个 auto_*/policy_* 闸，找出它读的每个字段，再问「谁会写这个字段」
grep -rn "structure_reviewed_at\|max_structure_age\|valid_until" --include=*.py scripts/ | grep -v tests
# 只有读、没有写 → 该闸永不可满足 → 功能会周期性静默死亡
```

判据：**一个只在读取处出现、写入处只出现在测试或手工里的字段，就是定时炸弹**。
它不会报错，只会让某个能力在 TTL 到点后安静地失效，而看门狗进程本身看着还活着。


### ⚠️ 通用审计项：监控器「报警疲劳」（2026-09-10 新增，比缺监控更常见）

一个**存在但在报警**的监控器，和没有监控器一样危险 —— 而且更坏，因为它让你以为有监控。

```bash
# 试跑每个看门狗，看它报多少条。报 10+ 条的看门狗 = 已被忽略的看门狗
python scripts/data_freshness_watchdog.py
```

**实测案例**：`data_freshness_watchdog.py` 盯着 **10 个采集器已停用**的产出
（x_sentiment / dune / qlib / stablecoin / oi_snapshot / deribit / orion /
 liquidation_pressure / polymarket…），每次运行必报 16 条过期 → 被 auto-disabled
→ 真正的 5 天停摆（BTC 到价监控）反而没人看见。

**修法（对齐活跃源 + 补监控链自身生命体征）**：

1. **只盯生产者还活着的文件** —— 对照 cron 的 `enabled+scheduled` 名单，逐个问「这文件谁在写」
2. **补上监控链自身的生命体征**：守护心跳 / 健康文件 / 唯一批准源 / 复核结果文件。
   后者才是「监控还活着吗」的直接证据，也是这类事故唯一能提前发现的位置。
3. **显式记录不监控的源**（`PAUSED_SOURCES` 字典 + 原因），让「为什么没报」有据可查，
   而不是让它们继续制造噪声。恢复某能力时，先恢复 cron，再把文件加回清单。
4. 交付标准：**健康时零输出**。报一条就是真事故。

本次实测：16 条 → 0 条；cron 从 auto-disabled 恢复 scheduled。

**变体：看门狗的阈值比它监控的那个生产者的实际契约更紧 → 自造噪声。**
本次实测：`btc_tv_refresh.source_snapshot_status()` 用 `max_age_hours=0.75`（丢到 45 分钟才去刷），
而看门狗却写 `threshold: 0.5`（30 分钟就报）→ 每个周期白报 15 分钟。
这类阈值不能拍脑袋定，**必须从生产者的代码里读出它自己的契约再对齐**：

```bash
# 对每个被监控文件，找到它的生产者与生产者自己的新鲜度阈值
grep -rn "max_age_hours\|max_age_minutes\|threshold" scripts/<producer>.py
# 看门狗阈值必须 ≥ 生产者阈值 + 一个调度间隔，否则必然周期性误报
grep -n "<file>\.json" scripts/data_freshness_watchdog.py
```

### ⚠️ 通用审计项：共享图表上的「切周期确认」重试强度不一致（2026-09-10）

同一个收集器常有两套实现（stdio 长连接 / CLI 单次调用），**确认强度会不一致**。
`keylevels_collect.py` 实测：stdio 路径重试 1 次，CLI 路径**完全不重试** ——
而 `btc_tv_refresh` 走的正是 CLI 路径，于是失败 54 次、五周期 age 达 2254s。

```bash
# 找出所有切周期后的确认点，比较它们的重试次数
grep -n "timeframe mismatch\|retry_set\|set_timeframe" scripts/keylevels_collect.py
# 只有一次 get_chart_state 就 raise 的，就是薄弱点
```

TV 会在图表**真正切过去之前** ACK timeframe；共享图表上还有别的任务和用户看盘在抢周期。
**判据：切周期后的确认必须是有界重试循环（4 次 / 5-10-15s 递增），不能在单次确认后 raise。**
重试耗尽后照旧抛错，不放过周期错配的数据。

#### ⚠️ 这个缺陷会重复出现在多个文件 —— 必须全库扫，不能改一处（2026-09-11）

上一版只点名了 `keylevels_collect.py`。**2026-09-11 实测发现同一个缺陷存在于三个地方**，
前一处的修复完全没有传播出去：

| 位置 | 写法 | 后果 |
|---|---|---|
| `keylevels_collect.py` 切周期确认 | 原为单次 | 已修（上文） |
| `xau_tv_sync._prepare_xau_main_chart` | `sleep(20)` + 单次检查 | XAU 同步**失败率约 1/3**；OHLCV 五周期明明全采到，却被整轮丢掉 |
| `xau_tv_sync._restore_chart` | 同一个写法 | 归还时**品种回去了、周期没回去** |

**症状指纹（很隐蔽）**：`_restore_chart` 失败时**品种已经切回**（`_tv_command("symbol")` 立即生效），
只有**周期**滞后 → 用户看到「图是我的币，但周期不对」（现场：归属记录 `user_timeframe=15`，图停在 `5m`）。
**出现“品种对、周期不对”就直接去看那个确认是不是单次检查。**

```bash
# 审计动作：列出所有“切换共享图表 → 等一会 → 检查”的确认点
grep -n "time.sleep(" scripts/xau_tv_sync.py scripts/keylevels_collect.py \
  scripts/btc_tv_refresh.py scripts/tv_screenshot.py 2>/dev/null
# 每个 sleep 后面只有一次 _chart_state()/_cli("state") 的，就是薄弱点
```

**教训的形态**：这是「同一根因、多处理器、只修了一处」的典型。学到一条修复模式后，
必须回头把同类调用点全部扫一遍再交付，否则用户下次会在另一个场景撞到同一个错。
有界重试的正确形状（6 次 × 5s，上限 30s，耗尽才判失败并打印当时实际状态）：

```python
for attempt in range(1, ATTEMPTS + 1):
    time.sleep(WAIT)
    actual = _chart_state()
    if <期望的 品种/周期/研究 全部就位>:
        return True
    last = f"symbol={...} tf={...}"      # 记住最后一次观测，失败时打出来
print(f"  ✗ 确认失败，最后观测: {last}")   # 失败也要有现场，否则无从定位
return False
```

配套验收（必须两例都有，只测正常路径不算）：**慢图能恢复**（前两次读到旧状态、第三次到位）
与 **一直不就位时有界退出**（不能无限等）。

### ⚠️ 通用审计项：不要自己重算守护的健康，读它自己的健康文件（2026-09-11 实测假 P0）

本次审计我犯了一个错：自己读 `keylevels_config.json` 的 `levels[]`、发现没有 `active` 字段，
就报了「有效=0，到价监控失效」的 P0 —— **误报**。真相在守护自己写的健康文件里：

```bash
# ✅ 权威：守护自己产出的健康文件（注意是【点文件】）
cat data/.keylevel_guard_health.json   # {"status":"ok","active_approved_levels":8,...}
cat data/.keylevel_guard_heartbeat.json
```

两个教训：

1. **“有效位”是由守护的 `active_approved_level_count()` 算出来的**（它还要叠加
   `structure_review_is_current()`），不是 config 里某个现成字段。自己按字段名猜
   （`.get("active")`）必然猜错 → 假 P0。
2. **这些健康文件是点文件**（`.keylevel_guard_*.json`）。写自己的审计脚本时
   按 `keylevel_guard_health.json` 找会报「缺失」，又是假 P0。

**铁律：审计时先找“这个能力自己的健康输出”，再决定要不要自己重算。**
重算只用于「健康文件本身也缺失/不新鲜」的交叉验证，不作为首选判据。
报给用户的每条 P0 都必须能追到权威产出位置，否则先自证再上报。

### ⚠️ 通用审计项：报告文件只在 `main()` 里落盘 → 被监视时会永远“过期”（2026-09-11 实测）

症状：某个健康/报告文件看起来停更好几小时，但它对应的能力其实**每几分钟都在跑**。

```
structure_reviewed_at = 今天 11:14   ← 复核一直在跑 ✓
keylevels_structure_review.json 停在 12.6 小时前   ← 但它被数据新鲜度看门狗监视着 ✗
```

**根因**：报告写盘写在 `main()` 里，而真正的调用方是**另一个模块 import 后直接调函数**：

```python
# 看门狗里：
from keylevels_structure_review import review, apply_review
return apply_review(result=review())      # ← 从不走 main()
```

于是 `main()` 里那段写盘永远不会执行。**判据：文件停更 ≠ 能力停摆；先看这个文件是谁写的。**

```bash
# 审计动作：对每个被监视的文件，找它的写入点在哪
grep -rn "<report_file>\.json\|REVIEW_OUT" --include=*.py scripts/
# 若只在 def main() 里 → 检查调用方是走 main() 还是 import 后直接调函数
```

**修法**：把写盘从 `main()` 抽成一个 `_write_report()`，放进**共用函数**里，
并覆盖**所有返回路径** —— 通过 / 跳过写盘 / 执行失败。

- 「跳过写盘」（如未到盖章间隔）也必须留痕：不然文件看上去就是死的
- 「执行失败」更必须留痕：那是安全闸的现场证据
- 函数定义要放在调用方之前（Python 运行期解析，靠前才安全）

**为什么这比没监控更糟**：它让看门狗持续报一条**假的**过期告警 → 掉进报警疲劳
（见上文「监控器报警疲劳」）→ 真正的停摆反而被淹没。
**验收：修完该文件 mtime 应回到分钟级**（本次 747 分钟 → 0.4 分钟）。

**同类风险清单**：任何「只有 `__main__` 会写、但实际被 import 调用」的产物 ——
报告 JSON、状态文件、缓存、健康标记。判据：
**这个文件的制造者是谁？如果是 `main()`，而调用方是 import，那它就是死文件。**

### ⚠️ 通用审计项：防御性 raise 要带诊断，否则等于没写

`keylevels_collect.py` 的 `RuntimeError("empty candidate pool")` 是**正确的防御**
（禁止用空池覆盖旧池）。但它只报一句话，无法区分「图被别的任务切走了」
还是「指标没渲染完」还是「解析规则不匹配」。
**判据：任何“拒绝发布”的 raise，失败时都要打出能定位的分项事实**
（本例：逐周期 symbol / price / levels 数 / keys）。
拒绝是对的，拒绝得没法查是错的。

### ⚠️ 通用审计项：共享图表被「频繁切走」（与「回不去」是两件事）

用户报「TV 图表总是自己切品种和周期」时，先分清两种成因：

| 成因 | 症状 | 去处 |
|---|---|---|
| 图表**回不到**原位 | 切走后就停在采集品种/周期 | 见上文「切周期确认重试强度不一致」+「棘轮」两节 |
| 图表**频繁切走** | 定位/品种/周期被反复改写 | 本节 |

本次两条都命中。**只修前者，用户依然会觉得「它总在切」。**

**第一步永远是先量化**，不要凭直觉认定主犯：

```bash
# 谁在切图
grep -rn 'set_symbol\|set_timeframe' scripts/*.py | head -40
# 频率 + 【有没有条件短路】—— 漏了后者会把 40 分钟才跑一次的任务当成主犯
#   对照 cron jobs.json 的 script/schedule，再读该任务的 main() 有没有 "if fresh: return 0"
```

本次真凶只有一个：**XAU 同步每 15 分切 7 次（品种+5周期+归还）**；
BTC 续航看似每 20 分，实际有条件短路，约 40 分才跑一次。

**第二步：先在共用工具层埋切换计数器**，再动手优化。
这一行的价值常超过修复本身 —— 它把「图表为什么在切」从不可观测变成可观测。
实测正是它打脸了我一个想当然的修复（`实切1/跳过0` → 0 次跳过，7 次全必需）。

**第三步：审计每个逐周期循环「到底读了什么」** —— 这一刀最值钱：

- 只读 `get_chart_state` + `get_ohlcv` → **它不需要占用用户的图表**，K 线可走 API
- 读 `study_values` / `pine_lines` / `pine_labels` / `pine_boxes` → **周期特有，切图切不掉**，不要试图优化掉

本次 XAU 的五周期循环只读 OHLCV，于是把 5 次周期切换换成一次 API 调用，
只保留 1 次「切到 5m 读指标面板」+ 归还。**切换 7 次 → ~3 次。**

完整 recipe（选源顺序 / 密钥占位符处理 / 跨源 K 线口径陷阱 / 旁路-对账-阈值-回退形状 /
429 熔断 / 实测记录 / 「第二标签页」隔离为何要先验证）见
`references/chart-switch-reduction-and-ohlcv-offload-20260911.md`。

两个最容易踩的坑先记在这里：

1. **跨源的「正在形成 / 已闭合」K 线不是同一根。** TV 取 `last_5_bars[-2]`（已闭合），
   TwelveData 的 `values[0]` 是**正在形成**的那根，必须取 `values[1]`。
   不改口径 → 卡片高/低随盘口跳动、与用户图上对不上。
   **更阴的是它曾经「校核通过」**（刚开盘 2 分钟，forming bar 恰好落在上一根范围内）——
   一次低差异的通过可能是巧合。
2. **换源一律「旁路 + 对账 + 阈值 + 回退」**，绝不直接换掉。旧路径保留成独立函数，
   新源校核超阈值或失败/熔断时回退到它（fail-safe，行为与改前一致）。

## Step 3：数据新鲜度审计 (7 类关键文件)

```bash
cd "D:/Hermes agent"
for f in data/btc_ref_levels.json data/monitor_levels.json data/keylevels_config.json data/source_snapshot_BTCUSDT.json data/source_snapshot_XAUUSD.json data/protections_state.json data/strategy_governance.json; do
  age=$(( ($(date +%s) - $(stat -c %Y "$f" 2>/dev/null || echo 0)) / 3600 ))
  echo "$f: ${age}h ago"
  [ $age -gt 24 ] && echo "  ❌ EXPIRED" || echo "  ✅ OK"
done
```

| 文件 | 阈值 | 状态 |
|------|------|------|
| btc_ref_levels.json | < 4h | 🔴 48.8d (过期) |
| monitor_levels.json | < 4h | 🔴 49.0d |
| source_snapshot_*.json | < 1h | ✅ 0.8h |
| protections_state.json | < 3d | 🟡 待查 |

## Step 4：TV MCP 连通性

```bash
python -c "import socket; s=socket.socket(); print('9222 OPEN' if s.connect_ex(('127.0.0.1',9222))==0 else 'CLOSED')"
curl -s --noproxy '*' -m 3 http://127.0.0.1:9222/json/version
```

- 9222 OPEN + version JSON → TV Desktop 正常
- CLOSED → `python scripts/tv_keepalive.py` 拉起 (需 `env -u ELECTRON_RUN_AS_NODE`)

## Step 5：脚本生存性评估 + 归档 (2026-08-29 落地)

145 个脚本 → 83 个无引用+>30 天 → 归档而非删除。

```python
# 算法：
for each .py script s:
    referenced = (
        import_map[s]  // 被其它本地脚本导入
        OR cron_ref[s]  // 被 cron jobs.json 引用
        OR s in auto_card_refs  // 被 auto_card.py 导入
        OR has_data_output_within_30d(s)  // 曾产出 data/*.json <30d
    )
    if referenced: KEEP
    elif age_days > 30: DELETE_CANDIDATE
    else: REVIEW
```

### 归档命令

```bash
mkdir -p scripts/_disabled_20260829
# 移动 83 个候选脚本至 _disabled_20260829/
# 然后清理 pyc
find scripts -name "*.pyc" -path "*/_disabled*" -delete
# 或直接删除（如果用户坚决删除）
# for f in $(ls _disabled_20260829/*.py); do rm $f; done
```

### 重要：不能直接删除的脚本 (有隐藏依赖)

| 脚本 | 原因 | 决策 |
|------|------|------|
| auto_card | 主入口 | 保留 |
| keylevel_guard | 守护中 | 保留 |
| btc_ref_levels_sync | XAU TV 同步 | 保留 |
| btc_daemon | 守护 | 保留 |
| fetch_tv_mcp | 所有 TV 调用 | 保留 |
| pipeline_router | 驾驶舱路由 | 保留 |
| render_v96 | 渲染 | 保留 |
| system_data_bridge | enrich engine_data | 保留 |
| data_gatherer | 采集 Binance | 保留 |
| telegram_reliable | TG 推送 | 保留 |

## Step 6：实测管线 (P0)

```bash
timeout 90 python scripts/auto_card.py BTCUSDT 2>&1 | grep -iE "GO/NO-GO|VWAP/EMA|exit"
timeout 90 python scripts/auto_card.py XAUUSD 2>&1 | grep -iE "GO/NO-GO|VWAP/EMA|exit"
```

## 修复优先级排序

P0（立即，2小时）：
1. pydantic-core 版本冲突
2. 启用 5 个关键 cron
3. 刷新 3 个过期数据 (btc_ref_levels / monitor_levels / daemon_heartbeat)
4. 清 P0 脚本

P1（2-4小时）：
5. 修复 XAU TV MCP stdio 路径
6. data_gatherer.py 禁用非 Binance (已完成)

P2（1天）：
7. 补 btc_daemon_watchdog (缺脚本)
8. 补行情守望看门狗 (缺脚本)
9. 补 TV Desktop 保活 (缺脚本)

## Pitfalls

- **心跳 staled ≠ daemon 死** (2026-08-29) — `.btc_daemon_heartbeat.json` 44d staled，但 `keylevel_guard` heartbeat 新鲜；判定必须查看对应文件名
- **脚本生存性评估必须过滤审计命令自身** (psutil 会把 `python -c "import psutil..."` 算成守护进程)
- **不能光看 "cron 跑过" 判断** — BTC关键位同步的 cron 跑过但其引用的 fetch_tv_mcp.py 崩 → `script failed` 静默
- **76 个「无引用+旧文件」中，signal_confluence / tv_data_bridge / cot_collector 等虽然无直接 import，但 data_freshness_watchdog 用它们产出的数据 → 要人工复核后归档**
- **删除脚本前必备份** — 即使是废弃脚本也可能被 cron 用到，删前 `grep jobs.json` 确认
- **git 工作树里「已删除但仍被 active 脚本 import」的模块，`git add -A` 会静默打挂导入方（2026-09-03 实测）** — `git status` 出现 54 个 `D <script>.py`，其中 `alert_dedup`←`orion_screener_radar.py`、`btc_card_gen`/`dmi_decision`/`tv_levels_collector`←`btc_daemon.py`、`five_model_matcher`←`backtest_runner.py`、`orion_radar_card`←`orion_screener_radar.py` 仍被 active 脚本 import。无脑 `git add -A scripts/` 提交会把删除一起落地 → 活跃脚本 ImportError（不是 run 时报错，是 import 时静默崩），且用户可能隔天才发现。**提交前必做删除安全检查**：对每个 `D` 文件取 basename，`grep -rlE "import <base>\b|from <base>\b" scripts/ --include='*.py'`（排除 _archive/_disabled），命中即把该删除**摘出单独审查**（恢复 / 补引用 / 确认引用方也已退役），再决定是否提交。**铁律：大量 `D` 删除 + 有活跃 import 命中 = 独立清理工程，不是批处理；先专项列出会打挂的引用交用户确认，不要 `git add -A`。** 与 `_disabled/` 归档扫描（搬家到 _disabled_YYYYMMDD）不同，这是「git 已跟踪但工作树删除、且引用方还活着」的直接破坏面。完整 recipe 见 `references/git-deletion-safety-check-2026-09-03.md`。
- **归档 ≠ 删除（2026-08-29 用户明确偏好）** — 用户说「不要的就删掉」时，实际选择是**归档到 `scripts/_disabled_YYYYMMDD/` 而非直接删除**。理由：①将来可能需要回滚 ②被其他 cron 静默引用时删了会导致脚本静默失败 ③用户偏好可见性优于不可逆操作。**铁律：用户说「删掉」时，仍默认归档，除非用户明确说「直接删/不要备份」。**
- **非 Binance URL 禁用模式（2026-08-29）** — 把 `safe_fetch("https://<non-binance-domain>...")` 整段替换为 `var = None  # TANGXI-DISABLED-NON-BINANCE 2026-08-29: <domain> (was ...)`,保留所有 snap[...] 字段解析但返回 None。不要用整行注释（会破坏 Python 缩进）。**必须先备份原文件**，再用 `py_compile` 验证语法。改完后所有依赖该字段的下游逻辑自动拿到 None，无需改业务代码。
- **bash heredoc / `python -c` 里的正则反斜杠会被 shell 吃掉（2026-09-11 实测，同一会话撞 4 次）** — 在 `python - <<'PY' ... PY` 或 `python -c "..."` 里写 `re.findall(r'"(?:[^"\\]|\\.)*"')` 这类带字符集的模式，实际到达 Python 的是 `[^"\]` → `re.error: unterminated character set`。同会话还发生「用 heredoc 改自己的修复脚本」时锚点不匹配（字节与预期不符）→ `AssertionError`。
  **铁律：凡是带【正则】、【反斜杠】、【中文】或【多行缩进】的临时脚本，一律 `write_file` 落成 `outputs/.../xxx.py` 再 `python xxx.py` 跑；不要走 heredoc / `python -c`。**
  好处额外有三：可重跑、失败时错误行号准确、可随交付物一起归档。省下的调试时间远超那一次 write_file。
  （同族问题：`patch` 工具对 CRLF/多行缩进不稳 → 批量改源码用「Python 行替换脚本 + `assert count==N`」。）
- **patch 工具对多行中文/缩进块会重排缩进（2026-08-31 实测）** — 对含前导缩进+中文注释的多行 Python 块做 patch 时，fuzzy 匹配可能把 old 块整体加/减缩进 → `IndentationError: unexpected indent` 反复报错（本会话 decision_loop.py/render_tv_card.py 各中招 2-3 次，包括"没引入新错误但文件仍坏"的假性成功）。**workaround：含前导缩进或中文注释的多行替换一律改用 Python 原子替换**（read → assert old in s → replace → write 回 `newline='\r\n'`），不要用 patch 工具；短单行/无缩进锚点才用 patch。示例：
```python
p = 'scripts/xxx.py'
s = open(p, encoding='utf-8').read()
old = '''    if hard:
        state = "NO-GO"'''  # 必须带与文件一致的前导缩进
new = '''    if hard:
        state = "NO-GO-2"'''
assert old in s, 'old block not found'  # 先断言再替换，防静默不匹配
s = s.replace(old, new)
open(p, 'w', encoding='utf-8', newline='\r\n').write(s)
```
- **data_gatherer.py 改造陷阱（2026-08-29 实测）** — 直接 `#` 整行注释会报 `IndentationError: unexpected indent`，因为下一行是 `headers={...}` 延续。正确做法：**找括号配平的整段赋值，替换为 `<var> = None` 单行**，保留缩进不变。

## cron auto-disabled 自相矛盾修复模式（2026-08-31 实测 P0 隐藏根因）

`paused_reason: "auto-disabled: enabled+paused contradiction"` 是 Hermes cron 调度器的状态机产物——`enabled=true` + `state=paused` 同时存在时被自动标 disabled。**标准修法（4 步顺序不可错）**：

```python
import json, time, shutil
p = r'C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json'
d = json.load(open(p))
for j in d['jobs']:
    if j.get('id') == 'b78741992dfd':  # 目标 cron id
        # 1. 改状态
        j['enabled'] = True
        j['state'] = 'scheduled'
        # 2. 删 paused 元数据
        j.pop('paused_at', None)
        j.pop('paused_reason', None)
        # 3. 让 scheduler 重新计算 next_run_at
        j['next_run_at'] = None
        j['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S+08:00')
        break
# 4. 写回前必备份
shutil.copy2(p, p + '.bak.' + time.strftime('%Y%m%d%H%M%S'))
json.dump(d, open(p, 'w'), ensure_ascii=False, indent=2)
```

**触发原因通常是 cron `script` 字段指向的文件被归档/删除**——常见根因是 8/29 binance-only 迁移把脚本移入 `scripts/_disabled_YYYYMMDD/`。**修法顺序铁律：① 把脚本从 `_disabled/` 复制回 `scripts/` → ② `py_compile` 验证 → ③ 改 cron 状态**。顺序反了（先改 cron 状态再恢复脚本）会立即再被 `auto-disabled`。

**验证命令**：读回 jobs.json 确认 `enabled=True, state=scheduled, paused_at=None, paused_reason=None`；然后 dry-run 脚本（`timeout 8 python scripts/tv_keepalive.py`）确认 exit=0 静默退出（端口已开时设计就是静默）。

## _disabled 归档区 P0 扫描（2026-08-31 新增铁律）

**scripts/_disabled_20260829/ 是 8/29 binance-only 迁移归档区，存 81 个脚本。** 任何 live `scripts/*.py` 缺且被其它 live 脚本/auto_card/trading_system/cron 引用者 = **真 P0**（cron 报"Script not found"、auto_card 出 ImportError、trading_system.source_snapshot 直接崩）。

**3 步扫描方法**：

```bash
# 1. 列出 _disabled 里所有被 live scripts 引用过的模块名
for f in scripts/_disabled_20260829/*.py; do
  base=$(basename "$f" .py)
  refs=$(grep -rln "\\b$base\\b" scripts/ --include="*.py" 2>/dev/null \
    | grep -v _disabled | grep -v _archive | wc -l)
  [ $refs -gt 0 ] && echo "🔴 $base.py: $refs live references"
done

# 2. 重点核 trading_system.py / auto_card.py / orphan_integration.py
grep -n "^from \\|^import " scripts/trading_system.py scripts/auto_card.py \
  scripts/orphan_integration.py 2>/dev/null | grep -E "_disabled|credential|cvd"

# 3. 验证恢复：恢复后必须 import 成功 + 跑一次依赖它的 quick 路径
python -c "import sys; sys.path.insert(0,'scripts'); from cvd_analyzer import check_cvd_confluence; print('OK')"
```

**已知 case（2026-08-31 实测）**：
- `cvd_analyzer.py`（orphan_integration.py:230/234 import）→ 恢复
- `credential_store.py`（trading_system.py:294 import）→ 恢复后 CG_KEY=`CG-tkua...` 有效
- `ws_liquidation_daemon.py`（liq_listener_btcusdt cron 引用）→ 配 0 0 * * * 必 3600s timeout
- `macro_poly_refresh.py`（"宏观Poly刷新" cron 引用）→ DXY missing 7/15 报错

**恢复铁律**：从 `_disabled_20260829/<name>.py` 直接 `cp` 到 `scripts/<name>.py` → `py_compile` 验证 → 改引用方 jobs.json / auto_card 路径。**不动 live 已工作的逻辑**，恢复后跑一次 quick 模式 auto_card 验证链路全通。

## 用户报告交叉验证（2026-08-31 防错信铁律）

**当用户提交审计报告/事件总结时，必须用 `grep/sed/ls` 三件套验证每条结论再写进审计卡**。错信/编造字段会让修复方案走错方向。

**三类典型错信**：

| 类型 | 案例 | 验证命令 |
|------|------|---------|
| **行号巧合** | 用户报"auto_card.py:4806 引用 cvd_analyzer" → 实际是该行 `_mode` 路由逻辑 | `sed -n '4800,4815p' scripts/auto_card.py` |
| **编造字段** | 用户报"`text_push_status: failed_or_missing`" → 三个日志位置全空 | `ls data/keylevel_triggers/ data/keylevel_analysis/ cron/output/keylevel_read_trigger.md` |
| **过时口径** | 用户说"6 孤儿其余 5 个在 scripts/" → 已对；但 6 概念本身可能是老图谱 | `ls scripts/{meta_labeler,orderflow_absorption,fvg_detector,order_block,correlation_matrix,cvd_analyzer}.py` |

**3 步验证流程**：
1. **找原文位置**：`grep -n "<claim-string>" scripts/<file>` 看真实匹配
2. **看上下文**：`sed -n 'N-5,N+5p' file` 排除巧合匹配（注释/字符串/无关逻辑）
3. **跑相关逻辑**：触发它看实际行为（`python -c "from X import Y"` / `python scripts/X.py`）

**判定**：
- 验证通过 → 写进审计卡
- 验证失败 → **不写进审计卡也不发 TG**；用证据反问用户出处（"你给 text_push_status 的具体文件路径+行号"）；不直接归类"用户撒谎"——可能用户记错/二手转述/口径过时

### ⚠️ 通用审计项：清理「文档/技能里的旧事实」——先实测再落笔，三态不能混（2026-09-11 自己打脸·第二次）

上文说的是「自己写的**修复**必须先实测」。这条是同一个毛病的**文档变体**，危害更大：
本轮给 6 个技能 + 1 个技能参考文件写了「下列脚本**已不存在/已删除**」，收尾核实时发现**是错的** ——
`btc_keylevel_ws_guard` / `btc_keylevel_sentinel` / `btc_keylevel_rest_guard` /
`btc_price_arrival_sentinel` **文件仍在 `scripts/`**，只是不在 cron、不在任何进程里。
已移入 `scripts/_archive/` 的只有 `btc_alert_watch_v3` / `btc_push_cron` /
`btc_collector` / `btc_fast_daemon`。上述为历史记录，错误的断言已经写进了**未来会话会直接读取的技能**里 ——
比不写更糟，且必须再花一轮提交去更正。

**脚本状态只有三态，写之前每条都要有命令证据**：

| 态 | 判据 | 该怎么表述 |
|---|---|---|
| ① 已归档 | `ls scripts/<n>.py` 不存在，且 `find scripts/_archive scripts/_disabled* -name` 命中 | 「已移入 `scripts/_archive/`」 |
| ② 仍在但停用 | 文件在 `scripts/`，不在 `jobs.json`，不在进程列表 | 「文件仍在，但不在 cron/进程中运行」 |
| ③ 现行 | 文件在，且在 cron 或进程里 | 「现行链路」 |

```bash
# 一条命令出三态，不要靠记忆和印象
for f in <候选脚本名...>; do
  [ -f "scripts/$f.py" ] && p=在根 || p="不在根"
  find scripts/_archive scripts/_disabled_20260829 -name "$f.py" 2>/dev/null | grep -q . && a=已归档 || a=-
  grep -q "$f.py" "$LOCALAPPDATA/hermes/cron/jobs.json" && c=cron引用 || c=-
  echo "$f: $p $a $c"
done
```

**同一类错误在子代理结论里也会出现**：本轮子代理为一条审计项给出的「现行脚本」建议，
把已归档的写成了现存。**子代理的事实性结论（尤其「文件存在/不存在」「已删除」
「这行代码在哪」）一律当未验证输入，落地前自己 `ls`/`find`/`git grep` 复核一遍。**
它的价值在「帮你定位和列线索」，不在「替你做事实判定」。

#### 清根目录/技能目录前：先读 `.gitignore`，它可能是有意为之

`Run` / `restart_gateway.*` / `restart_gw.*` / `annualof.txt` / `FinComYY.txt` 看着像垃圾，
实则 **`.gitignore` 里明确归入「本机工具/临时启动器」**，或技能明确记录过
「CFTC 持仓数据（annualof/FinComYY）是真实资产、审计见到 `M annualof.txt` 不要当脏文件删」。
**动手前两步：`grep -n "<file>" .gitignore` + 查技能是否点名该文件**；命中任一即保留，
并在归档说明里写下「为什么不能动」。

#### 清技能/文档：不改写带日期的历史记录，只加作废横幅

`references/*-2026-07-02.md` 这类**带日期的历史文档**记录的是「当时是什么样」。
逐行改写成现值 = **伪造历史**，而且会毁掉「当时踩过什么坑」的取证价值。
正确做法：**在文件顶部加一条作废横幅**----「本文已作废（YYYY-MM-DD），是当时实况记录，
不是当前权威；现行权威在 <绝对路径>」——正文一字不动。

只有 **SKILL.md 正文里的「活指令」**（下次会话真会照做的）才逐行改成现行值。

**判据：这段文字是「接下来该怎么做」还是「当时发生了什么」？** 前者改，后者只加横幅。
自检：如果一条历史记录被你改得「看不出它曾经是错的」，你就改过头了。

#### 换代的脚本名会在技能里成批残留 —— 配一个可重跑的扫描器，别靠人眼

「某个脚本被取代」这件事会散落在十几个技能的正文与 references 里。做法：

1. 写一个可重跑的漂移扫描器（本轮落地：`scripts/maintenance/skill_drift_scan.py`），
   扫旧版本号/旧行数/已废止字段名/不存在的脚本名，输出 `文件:行号 + 原文`。
2. **分级必须有**：`LIVE`（SKILL.md 正文 + 无日期参考，真会被人读）/ `HISTORICAL`
   （文件名或文头日期早于定版，只报不改）。否则历史记录会把真问题淹没。
3. **抑制规则必须有**：行内出现「已废止/已移入/已归档/退役/示意名/历史记录」=
   已显式声明，不算漂移；已带文件级退役横幅的文件的「脚本名」类不再逐行报
   （但字段/行名类仍要报 —— 横幅没覆盖它们）；索引文件整体跳过。
4. **配套一个单一对照表**（本轮：`realtime-trading-pipeline/references/dead-script-index.md`），
   写明「已废止 → 现行替代」；所有技能只指向它，不在各处再抄一份。

本轮效果：LIVE 漂移 129 → 31，剩下的全在历史 references 里而且**就不该改**。
完整 recipe（含根目录分类算法、模块遮蔽排查、抑制规则实现）见
`references/doc-and-skill-drift-cleanup-20260911.md`。

#### ⚠️ 同级陷阱：根目录的同名副本会**遮蔽**模块（静默 ImportError）

清根目录时发现一个真 bug：根目录有一份 113 行的 `fetch_tv_mcp.py`（**没有任何 `get_*` 函数**），
而真模块是 `scripts/fetch_tv_mcp.py`（251 行，技能写的是
`from fetch_tv_mcp import get_ohlcv, get_study_values, get_pine_tables, get_pine_boxes`）。
在仓库根目录跑 `python -c` 时 **CWD 在 `sys.path` 里优先** → 命中旧副本 → ImportError。

```bash
# 排查：仓根与 scripts/ 有没有同名 .py，内容是否一致
for f in *.py; do [ -f "scripts/$f" ] && echo "$f  root=$(sha256sum "$f"|cut -c1-12) scripts=$(sha256sum "scripts/$f"|cut -c1-12)"; done
# 确认真模块身份：它必须真的含有被 import 的函数名
grep -c "^async def get_\|^def get_" scripts/fetch_tv_mcp.py
```

**判据：同一模块名同时存在于仓根和 `scripts/`，且内容不同 = 定时炸弹。**
按「谁是技能/代码真正 import 的那份」保留，另一份归档并写清原因。

#### ⚠️ 维护工具不要放进被 gitignore 的目录

本轮把三个体检工具先放在 `tools/`，随后发现 **`tools/` 在 `.gitignore` 里**
（标记为「本机工具/外部仓库」）—— 放进去等于**不备份**，重装即丢。
维护/审计类脚本一律放 `scripts/maintenance/`（`scripts/` 已跟踪）。
**目录选择前先 `git check-ignore -v <path>` 确认它会不会被提交。**

## 仓库级维护：备份、受护栏的自动推送、脚本化批改（2026-09-11 建立）

### 技能目录的备份链路（唯一一条）

`~/AppData/Local/hermes/skills` 是**真实目录、不在仓库内** → 无版本、重装即丢。
现行链路是**单向镜像**（源唯一可写、快照只读）：

```
~/AppData/Local/hermes/skills ──(skills_snapshot.py 单向镜像)──▶ 仓库 hermes/skills ──git──▶ GitHub 远端
```

- cron `948f28dfaf76`（`技能快照备份`，每日 04:20，`no_agent=true`，`deliver=local`）
- **fail-closed**：源文件数塌到上次 60% 以下或 <100 个 → 拒绝镜像并报错，**绝不擦备份**
  （备份脚本最贵的错误是「把备份擦成空」，宁可拒绝跑）
- **只提交该路径**：`git commit -- hermes/skills`，不把工作区里其它在途改动一起扫进去
- 四条必知 / 日常用法 / 备份洞自检见 `references/skills-backup-mechanism-20260911.md`

### 自动推送的护栏（任何「自动发到外部」的脚本都适用）

自动 push（同族：自动发消息、自动开 PR）= **替用户发布**，必须加闸 ——
只推「本次任务自己产生」的提交，一旦混入别的提交就整体不推并说明：

```python
PREFIX = "chore(skills): 技能快照"
ahead = git("log", "--format=%s", "origin/main..HEAD").splitlines()
if ahead and not all(s.startswith(PREFIX) for s in ahead):
    print(f"⚠ 未推送：待推提交里有 {len(ahead)} 条非本任务提交 —— 为免替你发布，本次不自动推送")
    return
```

两条配套约定，缺一个就会长期出错：

1. **推送判定要放在「本次有变化」的判断之外**。放在里面 → 上一次推送失败（断网）后，
   下一轮没变化就永远不会补推 → 备份链**静默断掉**。
2. **「无 upstream / 未配置」要静默，真失败才出声**。no_agent cron 的约定是
   **健康即零输出**；把配置状态当事件报，就是给用户每天刷一行噪声
   （同族问题见上文「监控器报警疲劳」）。

### ⚠️ 脚本化批改文件时，不要相信自己的成功打印（2026-09-11 自己打脸·第三次）

用 `execute_code` / Python 脚本做批量替换时，写了 `t = t.replace(old,new); print("OK 已加…")`
—— 那个 `print` 是**无条件**的，于是替换没生效我也以为成功了。后续又只加了函数体、
没加调用点，结果 `--no-push` 被定义两次 → `argument --no-push: conflicting option string`
→ 脚本直接崩、cron 报 `script failed`。**同一个错误在同一轮里埋了三个坑。**

```python
# ❌ 自欺：成功打印与替换是否真的发生无关
t = t.replace(old, new); print("OK 已替换")

# ✅ 每一步都断言，并在写完后从磁盘读回复核
assert t.count(old) == 1, "锚点不唯一，先看清楚"
t = t.replace(old, new)
assert new in t
p.write_text(t, encoding="utf-8")
assert new in p.read_text(encoding="utf-8")   # 回读，不信内存
```

**判据：脚本里任何「宣布成功」的输出都必须依赖一个自己算出来的断言，
不能依赖「我这段代码跑到了」。** 写完还要**回读落盘内容** —— 本轮正是靠回读
才发现 `mod.REPO = tmp_dest.parent` 那条根本没进文件，白排查了一轮假失败。
（同族铁律见上文 heredoc 那条 pitfall：批量改源码用「Python 行替换脚本 + `assert count==N`」。）

### ⚠️ 测试沙箱必须隔离**全部**模块级常量，否则测试会打到真实环境

给「会读写真实仓库」的脚本写测试时，只覆盖一部分模块常量的后果是**测试打到真环境**：

```python
# 测试夹具只改了 SOURCE / DEST，忘了 REPO
mod.SOURCE = tmp_root; mod.DEST = tmp_dest
# → 内部 git 操作的 cwd 落在真仓库 → 读到真实的待推提交、打印真实警告
# → 「无漂移应静默」用例假失败，看起来像被测脚本有 bug
```

**修法**：把**每个**指向真实世界的常量都换成沙盒，并加一条断言自证隔离：

```python
mod.REPO = tmp_dest.parent
assert mod.REPO != Path("D:/Hermes agent"), "测试绝不能指向真仓库"
```

### 顺手记下的 git 坑（两个都会造成错判）

| 坑 | 症状 | 正解 |
|---|---|---|
| `.gitignore` **不支持行尾注释** | `!hermes/skills/**/*token*  # 说明` 永不匹配（`#` 后的说明也成了 pattern 的一部分） | 注释**独占一行**；改完 `git check-ignore -v <path>` 逐条验证 |
| `git ls-files` **默认转义非 ASCII 文件名** | 名字带中文时输出 `\346\226\207…`，集合比对虚报「上千个文件缺失」 | 加 `-c core.quotepath=false` |

### 结构性防呆：静默的失败比报错更贵

同轮在路由层发现三个同型缺陷 —— **未知输入不报错，而是安静地退化**：

| 位置 | 退化形态 | 修法 |
|---|---|---|
| `route_pipeline` 未知品种 | 返回**空管线**（不分析，不报错） | 补类别 + `assert steps` |
| `analysis_mode_spec` 未知档位 | **静默回落** quick | 返回 `mode_error` + `requested_mode` |
| 契约缺失时的 stub | 静默出**空卡** | 置 `DEGRADED=True`，卡面必须说出「契约缺失」 |

**判据：任何「查不到 → 走默认值」的分支都要问一句：用户能从输出里看出这是降级态吗？**
看不出就是在埋静默失败。修法是**显式标记 + 断言**，不是把默认值调好一点。
（完整 recipe 见 `references/repo-hygiene-and-guarded-push-20260911.md`。）

## 参考文件

- `references/pydantic-version-compatibility.md` — pydantic 版本冲突完整修复记录
- `references/script-lifecycle-management-20260829.md` — 2026-08-29 脚本评估清单（保留/归档/删除）
- `references/disabled-archive-p0-scan-2026-08-31.md` — 8/29 迁移归档区 P0 扫描方法+已知 case 全表
- `references/user-report-cross-validation-2026-08-31.md` — 错信 3 类+3 步验证流程+反问模板
- `references/keylevel-expiry-recovery-2026-09-02.md` — TV五周期刷新、人工续批、看门狗/Cron回读的完整恢复证据链
- `references/git-deletion-safety-check-2026-09-03.md` — 大量 `D` 删除 + 活跃 import 命中的提交前安全检查
- `references/unsatisfiable-safety-gate-recovery-20260910.md` — **不可满足的安全闸**（`structure_reviewed_at` 无生产者）取证链、真复核生产者代码骨架、全数通过才盖章的阈值设计教训+验收清单
- `references/chart-switch-reduction-and-ohlcv-offload-20260911.md` — **共享图表被频繁切走**：量化谁在切/频率/条件短路、切换计数器、逐周期循环「读指标还是只读K线」的判据、把 OHLCV 采集移出图表的完整 recipe（选源顺序、密钥占位符、跨源 K 线口径陷阱、旁路-对账-阈值-回退、429 熔断、实测记录）、「第二标签页隔离」落地前必须先验能力、以及「还原正确但错偏好被永久传承」这个变体
- `references/doc-and-skill-drift-cleanup-20260911.md` — **文档/技能漂移清理 + 根目录收口**：脚本三态分类（已归档/仍在但停用/现行）与实测命令、子代理事实性结论的复核规则、根目录分类算法（`.gitignore` 与技能点名要先查、引用计数要排除 `.gitignore`、归档 README 三要素）、漂移扫描器的三级+三类抑制设计、行数类正则的误报教训、模块遮蔽（仓根同名副本盖掉真模块）排查、维护工具不能放 gitignore 目录，以及「技能目录不在仓库内=无备份」这个结构缺口
- `references/skills-backup-mechanism-20260911.md` — **技能目录的唯一备份路径**：单向镜像机制、四条必知、日常 `--status` 用法、fail-closed 阈值、备份洞自检命令
- `references/repo-hygiene-and-guarded-push-20260911.md` — **仓库卫生与受护栏自动化**：自动推送护栏完整实现、fail-closed 快照阈值、内容级密钥扫描 vs 文件名级屏蔽、argparse 重复选项守卫、脚本化批改的自证与回读、测试沙箱隔离、git 坑、静默/出声约定
