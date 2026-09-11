---
name: tangxi-system-audit
description: 棠溪交易系统全面审计流程 — 静态扫描、社区对标、TV数据校验、管线实测、内存优化、git commit。每次大版本更新后执行。
---

# 棠溪系统审计流程

> ⚠ 2026-09-11 校正（**已实测核实**）：本文件部分段落把下列脚本当现行工具，实际状态是——
> ① `btc_alert_watch_v3` / `btc_push_cron` / `btc_collector` / `btc_fast_daemon` **已移入**
>    `scripts/_archive/`（`scripts/` 根下已无此文件）；
> ② `btc_keylevel_ws_guard` / `btc_keylevel_sentinel` / `btc_keylevel_rest_guard` /
>    `btc_price_arrival_sentinel` **文件仍在 `scripts/`，但既不在 cron 也不在任何进程中运行**
>    —— 属历史代际，不要拿它们当现行链路。
> **现行监控链只有一条**：`keylevel_guard.py`（常驻·亚秒 REST·多品种多顶点·每位 30min 冷却）
> + `btc_keylevel_guard_watchdog.py`（cron `*/2` 拉起）+ `keylevel_read_trigger.py`（事件本地分析）
> + `btc_tv_refresh.py`（五周期快照续航）。对照表：
> `trading/realtime-trading-pipeline/references/dead-script-index.md`；
> 系统全貌：`D:/Hermes agent/docs/系统总览.md`；指标字段/行名：`D:/Hermes agent/docs/tv-indicator-field-map.md`。

## 触发条件
- 大版本升级后（引擎、管线、cron结构变更）
- 用户说"审计"或"全面检查"、"全方位盘点"、"全方位优化"
- 每两周例行

## 审计深度
- **Level 1 快速健康检查**（触发词："审计看看"）：Step 1-6，15分钟
- **Level 2 深度战略审计**（触发词："全面审计"、"全方位审计"、"对标社区"）：Step 1-12，60分钟
- 用户说"全方位优化"时 = Level 2 + 自动实施所有P0/P1修复

---

### 监控心跳审计（P0 · 每次审计第一步 · v9.1 升级）

**心跳停了 = 全系统瞎了。** 不仅要查 cron，更要查守护进程。两个守护进程独立运行：

| 守护进程 | 心跳文件 | 脚本 | 责任 |
|---------|---------|------|------|
| 行情守望 | `data/monitor_heartbeat.json` | `scripts/行情守望.py` | 多品种实时价格+关键位突破 |
| BTC守护 | `data/.btc_daemon_heartbeat.json` | `scripts/btc_daemon.py` | BTC多因子评分+TG推送 |

```bash
# 并行检查两个心跳
cat data/monitor_heartbeat.json 2>/dev/null | python -c "import sys,json; d=json.load(sys.stdin); print(f'行情守望: {d[\"status\"]} ts={d[\"time\"][:19]}')"
cat data/.btc_daemon_heartbeat.json 2>/dev/null | python -c "import sys,json; d=json.load(sys.stdin); print(f'BTC守护: ts={d[\"ts\"][:19]} score={d[\"score\"]}')"
```

**恢复命令**（任一心跳 stopped/丢失时执行）：
```bash
# 行情守望恢复
cd "D:/Hermes agent"
rm -f data/monitor.lock
python scripts/行情守望.py -s BTCUSDT XAUUSD

# BTC守护恢复
rm -f data/.btc_daemon.pid data/.btc_daemon.lock
python scripts/btc_daemon.py
```

### 守护进程看门狗覆盖审计（P0 · 2026-07-07 教训 · 2026-07-11 实例验证）
**光查心跳新鲜度不够——必须查每个守护进程有没有看门狗 cron 兜底。**
实案：行情守望守护进程于 17:41 心跳停跳、进程已死，但全系统 4 小时无人发现、无人拉起。
原因：cron 里只有 `BTC守护看门狗`（每5分检测 `.btc_daemon_heartbeat.json`），**行情守望没有任何看门狗 cron**。
BTC守护有看门狗是因为历史上它崩过；行情守望是同样的单点故障却漏配。

**审计必查项（并入架构完整性检查 D 系列）**：
```
W1: 行情守望守护 → 心跳 monitor_heartbeat.json + 是否有看门狗 cron（cron list 搜 monitor/watchdog/守望）
W2: BTC守护    → 心跳 .btc_daemon_heartbeat.json + 看门狗 cron 存在 ✓
```
- 任一对「心跳 + 看门狗」不完整 → 标 P0（架构单点故障）。
- 行情守望看门狗补建模式（照搬 BTC守护看门狗）：
  - 每 5 分 cron，脚本检测 `data/monitor_heartbeat.json`：status≠running 或 time>5min → `rm -f data/monitor.lock && python scripts/行情守望.py -s BTCUSDT XAUUSD`（background 启动）+ 推 TG:846 告警。
  - 参考 `scripts/btc_watchdog.py` 的 emergency/限速逻辑（MAX_RESTARTS_PER_HOUR=20, MAX_RESTARTS_EMERGENCY=30）移植。

**铁律**：守护进程必须成对出现（进程 + 看门狗）。审计发现孤儿子进程（有进程无看门狗）即 P0，不等它死。

铁律：**用 Hermes background 模式启动守护进程**（`terminal(background=true)`），不用 shell `&`。

**2026-07-11 实测**：手动 background 启动 btc_daemon 后，看门狗 cron 仍会在下一周期尝试确保单实例；若此时审计者再次手动启动，则 2 实例并存。修复后唯一权威是 cron 看门狗——杀旧、清锁、等 cron 自动拉起，不再手动启动。

```bash
cat data/monitor_heartbeat.json 2>/dev/null | python -c "import sys,json; d=json.load(sys.stdin); print(d['status'], d['time'][:19])"
# 期望: status="running", time < 5分钟前
# P0: status="stopped" → 守护进程已死
# P0: 文件不存在 → 守护从未启动过
```

### 数据新鲜度审计（P0 · 2026-06-28教训）
```bash
ls -lt data/source_snapshot_*.json 2>/dev/null | head -5
# 期望: 修改时间 < 1小时内
### 守护进程存活检查（P0 · 每次审计第一步 · 2026-06-29教训）

**守护进程：**
- `行情守望.py` — 实时多品种推送 → heartbeat: `data/monitor_heartbeat.json`
- `btc_daemon.py` — BTC 零 token 多因子评分 (≥8推TG:386) → heartbeat: `data/.btc_daemon_heartbeat.json`

```bash
cat data/monitor_heartbeat.json 2>/dev/null
# 期望: status="running", time < 5分钟前

cat data/.btc_daemon_heartbeat.json 2>/dev/null
# 期望: ts < 5分钟前

# 两者都必须 running。停了=全盲
```

**2026-06-29 教训**：心跳从 6/28 15:06 停至 6/29 00:38 — 14h未被发现。LLM cron BTC高频分析仍在烧 $33/月。零 token 守护进程 `btc_daemon.py` 早已存在但停止。

**恢复命令**（心跳 stopped 时立即执行）：
```bash
cd "D:/Hermes agent"
# 行情守望
rm -f data/monitor.lock
python scripts/行情守望.py -s BTCUSDT XAUUSD &
sleep 5 && cat data/monitor_heartbeat.json

# BTC daemon
rm -f data/.btc_daemon.pid data/.btc_daemon.lock
python scripts/btc_daemon.py &
sleep 30 && cat data/.btc_daemon_heartbeat.json
```

**资源消耗审计**（P2 · 每次审计附带 · LLM token + API 调用）：
参考 `references/resource-consumption-audit.md`。月 token 预算 ≤ $5。LLM cron ≤ 每2min → 建议转 no_agent。
**TV MCP CDP 恢复**（data_get_study_values 返回 "CDP connection failed" 时执行）：
```bash
# CDP断连=Chrome DevTools Protocol到TradingView Desktop的管道断
# Node MCP进程还在但CDP tunnel挂了。修复步骤:
mcp_tradingview_tv_launch()   # 自动检测+启动TV Desktop，端口9222
sleep 8                       # 等TV Desktop完全加载+指标初始化
mcp_tradingview_tv_health_check()  # 验证: cdp_connected=true, chart_symbol存在
# 然后按需要切品种: mcp_tradingview_chart_set_symbol("OANDA:XAUUSD")
# 数据采集: data_get_pine_tables + data_get_study_values + data_get_pine_lines
```
详见 `references/tv-mcp-cdp-recovery.md`（完整恢复流程 + 检查清单 + Pitfalls）

**数据新鲜度**（快照过期=分析卡数据垃圾 · v9.1 扩展为全量检查）：

```bash
# 批量检查所有关键数据文件新鲜度
cd "D:/Hermes agent"
for f in data/btc_signal.json data/protections_state.json data/strategy_governance.json data/strategy_model_stats.json data/xau_macro_context.json data/tv_dmi_cache.json; do
  if [ -f "$f" ]; then
    age=$(( ($(date +%s) - $(stat -c %Y "$f" 2>/dev/null || echo 0)) / 3600 ))
    [ $age -gt 24 ] && echo "❌ EXPIRED ($age h): $f" || echo "  OK ($age h): $f"
  else
    echo "⚠️ MISSING: $f"
  fi
done
```

**铁律**：超过 24h 的数据文件标记 P0，需立即刷新。`protections_state.json` 控制真实风控，过期意味着止损冷却可能失效。刷新命令：`python scripts/macro_poly_refresh.py` + `python scripts/黄金宏观.py`（网络慢时可能需要多次重试）。
```bash
ls -lt data/source_snapshot_{BTCUSDT,XAUUSD}.json 2>/dev/null
# 期望: 修改时间 < 1小时内
# P0: XAU 超 1 天过期 → XAU 卡数据不可信
```

**Web 搜索连通性**（社区对标依赖 · 详见 `references/web-search-provider-testing.md`）：
```bash
# 逐个测试 provider，详见 references/web-search-provider-testing.md
curl -s --noproxy '*' "https://api.firecrawl.dev/v1/search" \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -d '{"query":"BTC test","limit":1}'
```
- 至少 1 个 provider 返回 `"success":true` → 搜索可用
- 全部失败 → P0：搜索链断裂，社区对标、X情绪、新闻搜索全不可用
- 代理干扰（`HTTPS_PROXY=http://127.0.0.1:7897`）→ 加 `--noproxy '*'` 绕过测试
- **配置修复**：当 provider 本身可用但 Hermes 配错了 backend（如 `ddgs` 不可用但 `firecrawl` 可用）：
  ```bash
  hermes config set web.search_backend firecrawl   # 切换可用 backend
  hermes config set web.extract_backend firecrawl  # 同步抽取后端
  ```

## Step 0.5：Pine 指标静态扫描

```bash
cd "D:/Hermes agent"
python scripts/pine_static_scan.py \
  "C:/Users/Administrator/.hermes-web-ui/upload/default/<主指标.txt>" \
  "C:/Users/Administrator/.hermes-web-ui/upload/default/<副指标.txt>"
```
检查：request.security 配额（上限40）、plot（上限64）、重绘信号、def-before-use 违例。
注意：def-before-use 扫描器对函数内局部变量（`i`、`j`、`v`、`dow`、`dayName` 等）
会误报——只要最终变量在引用前定义就没事。

## Step 1：静态语法扫描
```bash
cd "D:/Hermes agent"
for f in hermes/scripts/multi_model_engine.py hermes/scripts/auto_card.py hermes/scripts/data_gatherer.py hermes/scripts/session_strategy.py hermes/scripts/triple_confirm.py hermes/scripts/event_ban_live.py hermes/scripts/macro_filter.py; do
  python -c "import py_compile; py_compile.compile('$f', doraise=True); print('✅ $f')" 2>&1
done
```

## Step 2：硬编码值检测（P0 模式）
**这是高频出错点** — 检查以下特征：
- `multi_model_engine.py` 中各模型函数内是否有裸数字（如 `vwap_s = 66054`）而非 `data.get("tv",{}).get("vwap")`
- `auto_card.py` 中风控余额是否有硬编码（如 `67.52`）而非 `engine_data.get("account_balance")`
- 所有应从 TV 获取的价位（VWAP/VAH/VAL/POC/EMA/ATR）必须走 `load_tv_data()`

## Step 3：脚本目录双重去重检查

### 3a：跨目录重复（项目 `scripts/` vs AppData `~/AppData/Local/hermes/scripts/`）
- 执行 `diff -q` 比较同名文件
- 若完全重复 → 确认所有 cron 已设 `workdir: D:\Hermes agent`
- 若不一致 → 以项目目录 `scripts/` 为 canonical

### 3b：项目内目录重复（`scripts/` vs `hermes/scripts/`）
**2026-06-29 发现**：23 个脚本同时在 `scripts/` 和 `hermes/scripts/` 存在且版本已发散。

```bash
cd "D:/Hermes agent"
for f in $(find scripts hermes/scripts -name "*.py" -exec basename {} \; | sort -u); do
  c=$(find scripts hermes/scripts -name "$f" 2>/dev/null | wc -l)
  [ "$c" -gt 1 ] && echo "DUPLICATE: $f"
done
```

对 DUPLICATE 项执行 `diff -q`：
- IDENTICAL → 删 `hermes/scripts/` 副本（`scripts/` 为 canonical）
- DIFFERENT → 标记 P1 人工裁决

**P0 铁律**：`auto_card.py`、`multi_model_engine.py`、`data_gatherer.py`、`session_strategy.py` 四个引擎脚本必须版本一致。不一致时标记 P0。

### Step 4：告警层 gap 分析（重点 · v9.0+）
检查模型是否同时存在于 engine 层和 cron 自主层：
- 引擎层（auto_card.py/multi_model_engine.py）有的模型 → 是否注入 cron？
- Session策略 / Silver Bullet / 三层确认 / 宏观过滤 / CVD趋势线破 是否在 cron 自主告警链路中？
- 若仅在引擎层 → **✗ 告警 gap**（用户不主动触发时不推送）

### 架构完整性检查（v9.0 · 2026-06-29）

守护进程优先于 cron。必查项：
```
D1: 行情守望守护     → cat data/monitor_heartbeat.json → status=running?
D2: BTC daemon守护   → cat data/.btc_daemon_heartbeat.json → ts <5min?
C1: BTC守护看门狗    → cron BTC守护看门狗 → last_status=ok?
C2: BTC关键位同步    → cron BTC关键位同步 → last_status=ok?
C3: Orion全市场雷达  → cron Orion全市场雷达 → last_status=ok? (优化后5候选)
C4: XAU监控         → cron XAUUSD监控 → last_status=ok?
C5: 新采集器验证     → ETF/Dune/Deribit/COT cron → last_status=ok?
```

**常见缺失**: 守护进程停了但无人知晓。审计时必须先查守护进程，再查 cron。

### 看门狗限速与单一控制权审计（P0）

行情守望的生产重启权威只能有一个：Hermes cron `scripts/monitor/market_watchdog.py`。历史常驻 `scripts/watchdog.py` 必须默认退役；若两者同时运行，会互删锁、重复拉起并耗尽重启桶。

看到“重启速率限制[卡死/环境未就绪]：20次/小时”时，**禁止先调高上限或只清guard**，按顺序检查：
1. 查所有命令行含`行情守望.py`的进程，必须恰好1个；心跳新鲜也不能证明无重复实例。
2. 查是否仍有旧`scripts/watchdog.py`常驻进程/启动项；生产只留cron看门狗。
3. Windows 11进程发现使用`psutil`，不要依赖可能缺失的`wmic`。
4. 重启顺序必须是“杀旧进程→等待退出→删monitor.lock→直接Popen新进程”；先删锁会制造竞态。
5. 根因修复并清理重复实例后，才允许清空`restart_times`/`restart_times_emergency`。
6. 验证新PID与锁、心跳一致，再手动触发一次cron；健康时应静默成功且不新增实例。

完整诊断、实现和验证清单见 `references/market-watchdog-pattern.md`。

### Protections 状态检查（v3.2 新增）
- 文件: `data/protections_state.json`
- 必须字段: `stoploss_guard.count` · `cooldown.count` · `max_drawdown.daily` · `risk_multiplier`
- 缺失 → P1：风控保护未激活，真实交易无止损后冷却

## Step 5：TV 数据桥校验

确认输出文件存在且新鲜（<5分钟）：
- `data/tv_live.json` (agent上下文直连TV MCP — 优先级最高)
- `data/tv_dmi_cache.json` (cron tv_data_bridge — 回退)
- `data/btc_tv_data.json` (BINANCE:BTCUSDT.P · 旧路径)
- `data/XAUUSD_tv_data.json` (OANDA:XAUUSD · 旧路径)
- 字段完整性：poc/vah/val/action_grid

**v9.6 双缓存架构**：详见 `references/tv-live-dual-cache-architecture.md`。
tv_live.json 优先于 tv_dmi_cache.json。两文件都不含 `poc` 字段时，auto_card D 周期显示"待刷新"。
## Step 6：实测管线

**注意脚本路径**：canonical 路径是 `scripts/auto_card.py`，不是 `hermes/scripts/auto_card.py`。

```bash
cd "D:/Hermes agent"
timeout 90 python scripts/auto_card.py BTCUSDT 2>&1
```
- **超时设为 ≥90s**（实测 60s 只能出 partial output，错过 GO/NO-GO 行）
- **不要用 grep 过滤**：完整输出才能看到 exit_code 和所有检查点
- 确认 exit_code=0 且输出含六项检查点：
  `① 数据采集` → `② 引擎运算` → `④ 市场热点/⑤ 社区情绪` → `⑥ 市场体制` → `⑦ 渲染锁定卡片` → `🚦 GO/NO-GO`
- GO/NO-GO 闸门验证：`✗ NO-GO` 带红灯列表 ≠ 系统错误，是闸门正常拦截。确认红灯原因合理即可。

**v9.6 GO/NO-GO 闸门验证**（Step 6 附带）：
- 确认输出包含 `GO/NO-GO:` 行——闸门已成功接入 auto_card
- GO 状态 = 绿灯的 `verdict` 以 `✅ GO` 开头
- NO-GO 状态 = `✗ NO-GO` + 红灯门列表
- 若提示 `GO/NO-GO跳过`：检查 `scripts/go_nogo_gate.py` 是否存在、`check_gate()` 是否有 NoneType 错误
- 闸门红灯绝不意味着系统错误——恰恰相反：这是正确拦截的表现。只需确认红灯原因是否合理。

**Audit Closure: Before/After Comparison Run**（用户说"执行"或"再跑一次...对比前后"或"按照建议来"时强制执行）：
1. 捕获 BEFORE：`hermes doctor` + `hermes status --all` + `git status --short --branch` + `ls -lt data/source_snapshot*.json data/tv*.json data/*_heartbeat.json` + `cat` 关键 heartbeats。
2. 批量执行刷新（collectors + TV bridge + daemons + fixes）：`python scripts/data_gatherer.py`、`multi_source_collector.py`、`dune_collector.py`、`deribit_options.py`、`黄金宏观.py`、`macro_poly_refresh.py`、`tv_data_bridge.py`；`hermes doctor --fix`；背景启动守护（必须 `terminal(background=true)`，绝对不用 `&`）；`git add -A scripts/ *.txt` + commit。
3. 实跑验证 bundle（不可跳）：`python scripts/pine_static_scan.py svp...` + `python scripts/pipeline_router.py BTCUSDT XAUUSD` + `timeout 90 python scripts/auto_card.py BTCUSDT`（必须看完整 gates 表 + 预案表 + 总结） + XAU 版本 + `hermes mcp test tradingview` + `python scripts/repo-maintenance/daily_system_audit.py`。
4. 捕获 AFTER + 仅报告 deltas（时间戳、tv_dmi 刷新到 15:25+、心跳 15:26 running、git push 成功、auto_card 真实表格输出）。
完整可复用模式见 `references/audit-execution-before-after-comparison-pattern.md` 和本会话实测（collectors 列表、背景 daemon poll、90s 卡 gates 验证、git push 锁定）。 

**铁律强化**：daemon 重启必须 background=true 并 poll 验证 heartbeat；auto_card 必须 90s+ 拿完整 GO/NO-GO 和表格；执行后必 git push 锁定；TV MCP test + tv_data_bridge 刷新必须包含在 closure 中。

## Step 7：Cron 健康检查
```bash
hermes cron list
```
- 所有 job `ok`（非 `error`）
- 所有带 `script` 的 job 都必须能解析到项目 canonical 路径 `D:\Hermes agent\scripts\...`。如果 job 缺 `workdir`，Hermes 默认可能跑 `~/AppData/Local/hermes/scripts/` 旧副本；用 `cronjob update` 或 CLI edit 补 `workdir: D:\Hermes agent`，尤其是 OpenRouter/Orion 这类历史 job。
- 无双目录脚本散落
- **hermes cron CLI 命令对照**：`edit` 改配置（非 `update`）、`remove` 删任务、`pause`/`resume` 启停。`update` 不是有效子命令。
- **排期冲突检查**：按分钟分组 cron 的 schedule，同分钟 ≥3 个 cron 即标记 P2，需错峰分散。具体方法与推荐错峰间距见 `system-ops` 的「Cron 排期冲突检测与错峰分散」。

## Step 7.5：LLM cron 预算审计（P0 · v9.6 新增）

月 token 预算 ≤ $5。LLM cron（带 skills 或 prompt 的非 no_agent 任务）每次调用 ~$0.02-0.05。必查项：

```bash
hermes cron list | grep -v 'Mode:      no-agent' | grep '\[active\]'
# 列出所有 LLM 模式 active cron
```

**判断标准**：
| 频率 | 日调用 | 月成本估算 | 判定 |
|---|---|---|---|
| */30m × 24h | 48 | ~$43-72 | P0 立即删除 |
| */30m 9-23 | 28 | ~$25-42 | P0 立即删除 |
| 2×/天 | 2 | ~$1.8-3 | 可保留 |
| 1×/天 | 1 | ~$0.9-1.5 | 可保留 |
| 1×/周 | 0.14 | ~$0.13 | 可保留 |

**常见浪费模式**：采集脚本早已用 no_agent 落盘数据（如 `orion_screener_radar.py`、`qlib_factors.py`、`liquidation_collector.py`），但另外挂了 LLM cron 对同一数据做"解读"→ 纯重复烧钱。原始数据直接推 TG 即可，LLM 解读价值为 0。

**⚠️ 2026-06-29 教训**：`Orion雷达分析` 每日 28 次调用（~$33/月），用户明确要求保留（管线模式：no_agent 采集 → LLM 解读推 TG）。对此类被用户保留的 LLM cron：
- 在审计报告中如实标注成本（如"超预算 6.7x"）
- **不自动删除**，列到 P2 优化建议中让用户决策
- 删除前必须用 `clarify` 工具确认，不要假设 LLM 解读"价值为 0"

删除命令：
```bash
python -m hermes_cli.main cron remove <job_id>
```

2026-06-29 实例：3 个 LLM cron（Orion雷达分析/QLib因子解读/清算压力推演）各 48 次/天 → 月烧 ~$129。删除后无功能损失，回到 $5 预算内。

## Step 8：内存精炼
- 移除过时条目（SkillSpector 旧版本号、Session outcome、commit SHA）
- 合并同类项（多条BTC管线→一条带XAU支持）
- 目标：< 80%

## Step 9：技能矩阵审计（Level 2）
- `trading` category: 27 skills → 检查哪些被 cron/管线引用。用 `ls ~/AppData/Local/hermes/skills/trading/` 获取完整列表
- 闲置 skill 名单 + 推荐接入方案
- `polymarket` / `multi-symbol-screener` / `agentless-monitoring` 使用状态

## Step 10：MCP 利用度（Level 2）
8 个 MCP 服务器利用率：
- TradingView ✓ / Binance ✓ / Jin10(仅quote, 缺calendar/search_flash) / FinanceKit ✗ / StockAPI ✗ / Hermes Studio(仅管理, 缺LAN) / 其余 ✗
- 输出利用率% + 推荐接入模块

## Step 11：TV 指标策略深度（Level 2 · v3.3 增强）
- 当前图表指标 vs 社区标准：Session CVD三通道 / KillZone白银时刻 / SMT跨品种背离 / 入场核对清单 / 对象计数
- Pine Script 质量（版本 v5/v6、`request.security_lower_tf()` CVD精度、polyline性能、对象上限）
- Session高低点、发展区(DO Price)字段是否被引擎使用
- **新增审计维度（2026-06-24）**：
  - Session CVD三通道（亚/伦/纽）：是否拆分为独立子通道？Data Window是否输出？
  - KillZone白银时刻：伦敦07-09:30+纽约08:20-11:30是否标记？
  - SMT跨品种背离：BTC/ETH、XAU/DXY是否启用？
  - 入场核对清单：HTF✓/EMA✓/CVD✓/RR✓/位✓ 是否显示？
  - 对象计数：是否监控TradingView对象上限？
  - CVD精度警告：Data Window是否标注LTF近似 vs tick级？
  - Alert等级覆盖：是否仅A级？B/C/Z级是否也有alertcondition？
  - 性能模式：轻量模式是否跳过polyline等高开销绘制？
  - RR底线：是否≥1.5社区标准？

## Step 12：社区对标（Level 2 · v3.3 增强）
- 提取社区共识清单（三层确认模型、Session策略差异化、Confluence评分）
- **v3.3新增对标清单**：
  - Session CVD三通道(亚/伦/纽) vs 社区Session CVD Divergence
  - KillZone白银时刻 vs ICT KillZone黄金窗口
  - SMT跨品种背离 vs ICT SMT Divergence
  - CVD精度(LTF近似 vs tick级) vs 官方 `ta.requestVolumeDelta()`
  - 入场核对清单 vs Tradeciety 5项核对
  - RR底线1.5 vs 社区标准≥1:2
  - Alert分级覆盖(A/B/C/X/SMT) vs 仅A级
- 逐项对照：🟢已有 / 🟡部分 / 🔴缺失
- 差距分析 → P0/P1/P2 分级
- **用户已知偏好**：FVG/OB不列入缺失项（用户明确拒绝）

## 审计与交易分析的边界

用户说"分析我的系统"或"审计"时，先明确交付物类型；完成审计后若用户追问"分析流程/用上能力了吗"，必须主动补一张棠溪交易分析卡。

| 场景 | 关键词 | 首要交付 | 补充动作 |
|:---|:---|:---|:---|
| 系统健康审计 | "系统怎么样"、"审计"、"全面检查" | 健康/运行态/P0P1P2报告 | 完成后若用户追问流程，补交易卡 |
| 交易分析 | "分析BTC"、"分析XAU"、"出卡" | 棠溪交易卡（6段式） | 系统健康有P0时先修再出卡 |
| 混合场景 | "分析我的系统，审计" | 先做审计 → 再补交易卡 | 不可让用户重复提醒才补 |

**补卡触发语**（任一即执行）：
- "有没有使用我们的分析流程？"
- "用上我们的能力了吗？"
- "这个不是分析卡？"
- "按棠溪格式出卡"

**补卡格式**（必须走 `crypto-multisource-analysis` / `tradingview-execution-card` 管线）：
1. MEDIA 全屏 TV 截图首行（含价格轴 + CVD 窗格）
2. 首屏"现在在哪 + 现在怎么做"
3. ①当前结构 ②多周期定位 ③关键位矩阵 ④多源交叉验证 ⑤执行方案 ⑥最终裁决
4. 结论用 ↑/↓/○/× + 品种 + 价格 + 关键位 + 时间
5. 主推只给一个 ⭐，备选仅作失效路径
6. 必须标明硬闸门（regime_model / R:R<2 / 数据过期等）

## 输出

**格式铁律（2026-07-08 棠溪两次纠正 · 报告必须全表格化）**：
- 审计报告、任务盘点、能力矩阵、任何总结性交付 —— **一律用真 Markdown 管道表**，禁止退化成段落散文。`| 列 | 列 |` + `|:--|` 分隔行必备；文字只做极短衔接，不写大段解释。
- 表格数量按需，不强行压 3 张（3 张限制是交易卡/情绪简报场景）；但每表必须有表头+分隔行，是真实管道表不是空格对齐假表。
- 审计报告审美优化（2026-07-11 纠正）：顶部放一张大状态卡（总体健康/核心结论），修复前后/运行态/数据新鲜度/交易决策分块，每块一个小标题+短表格，截图引用放在交易决策块上方。不要连续铺多个宽表。
- **推 Telegram 必须经 RichMarkdown 真表格通道，禁止 `hermes send` / cron no_agent stdout**：`hermes send` 与 cron no_agent 投递都经 agent 侧 `send_message_tool` 走 `sendMessage` + `parse_mode=MarkdownV2`，**Telegram MarkdownV2 不渲染管道表格**，表格退化为裸 `|` 竖线文本——这是「看不到真表格」的底层根因，与 token/topic 无关。正确通道：
  ```python
  import sys; sys.path.insert(0, "scripts")
  from telegram_reliable import send_telegram_reliable
  send_telegram_reliable("telegram:-1003733144325:846", report_text, parse_mode="RichMarkdown")
  # 回执 "rich_sent" = 走 Bot API 10.1 sendRichMessage 渲染真表格；自动检测表格并路由
  ```
  表格前不要紧贴 standalone `表1 · xxx` 标题行（RichMarkdown 会降级成文字），脚本 `_normalize_rich_markdown_tables` 已自动剥离。若 `rich_sent` 失败或用户反馈仍是裸 `|`，退回**图片表兜底**：写深色 HTML → `browser_navigate` 加载 → `browser_vision` 截图 PNG → 走 `telegram_reliable.send_telegram_photo()` 发图（详见 `xau-analysis-format` §⑬）。对话内回复同步用同一份纯 Markdown 管道表，两端一致。
- **7 个推 TG 的 cron 必须统一改 RichMarkdown self-send（2026-07-08 棠溪二次纠正·最高格式优先级）**：用户确认「这个才对，其他的任务报告，也是这种的格式才对」。当前 Orion雷达/每日复盘提醒/X情绪LLM/每日运维聚合 是 no_agent stdout 投递（退化成裸 `|`）；BTC关键位同步/BTC守护看门狗/行情守望看门狗 走 subprocess 调旧发送器（未必 RichMarkdown）。修复：no_agent 类改为**脚本内 self-send** `telegram_reliable.send_telegram_reliable(parse_mode="RichMarkdown")` 且 cron `deliver` 改 `local`（避免 cron 再发退化版）；subprocess 类统一换 `telegram_reliable` RichMarkdown。7 cron 清单与转换模板见 `references/tg-report-richmarkdown-consistency.md`。审计 Step 7 检查推 TG 任务时，若仍为 `deliver: telegram` + no_agent 脚本无 self-send 调用，标记 P1 整改。
- 审计报告（P0/P1/P2/P3 分级，全表格）
- 能力矩阵对比表（之前 vs 之后，全表格）
- 内存占用审计前后对比（全表格）
- 任务盘点表（编号/名称/频率/投递/实测状态）—— 范例见 `references/audit-report-table-format.md`
## Pitfalls

- **守护进程多实例是审计高频 P0（2026-07-11 实测复发）** — 看门狗拉起守护时旧进程未被完全杀死，或手动启动与 cron 看门狗同时运行，导致 3 个 `btc_daemon` + 3 个 `行情守望` 实例并存。审计 Step P0 心跳检查时必须用 `psutil` 逐个列出 `python.exe` 守护进程的 PID + 年龄 + cmdline，发现同一脚本 >1 实例即标 P0。修复：杀旧→清锁→保留最新单实例→验证看门狗下一周期不重复拉起。详细模式见 `references/market-watchdog-pattern.md`。
- **MCP SDK 缺失导致 `hermes mcp test` 全失败（2026-07-11 实测）** — `hermes mcp test tradingview/binance` 报 "requires the 'mcp' Python SDK, but it is not installed"。修复：`pip install 'hermes-agent[mcp]'`。审计 Step 5 TV 桥校验时如 `mcp test` 失败但 `tv_live.json`/`tv_dmi_cache.json` 数据新鲜且无品种污染，说明 TV MCP CDP 通道虽不通但缓存链正常，标 P1 而非 P0。
- **`hermes` CLI uv trampoline 故障须用 `python -m hermes_cli.main` 替代（2026-07-11 实测）** — 直接调 `hermes cron list` 报 `uv trampoline failed to canonicalize script path`，但 `python -m hermes_cli.main cron list` 正常。审计及运维脚本中所有 `subprocess.run(["hermes", ...])` 调用须改为 `[sys.executable, "-m", "hermes_cli.main", ...]`。此问题已在旧 Pitfall 中记录（daily_system_audit/daily_skill_mcp_update 已修），但需扩展到审计流程本身：审计命令也必须用 `python -m hermes_cli.main` 路径。
- **`hermes send` CLI 超时但 `telegram_reliable` 脚本直发可用（2026-07-11 实测）** — `hermes send --json -t telegram:...` 返回 `Timed out`，但同环境中 `from telegram_reliable import send_telegram_reliable; send_telegram_reliable(..., parse_mode="RichMarkdown")` 返回 `(True, 'rich_sent')`。审计 TG 推送链路时不能只用 CLI 测试判定"推送不可用"；必须双路径测试（CLI + 脚本直发），以脚本直发结果为准。
- **auto_card 截图子进程卡住导致管线超时（2026-07-11 实测 XAU）** — `tv_screenshot` 子进程 `Connection closed` 后管线不降级而是卡住，XAU 卡 120s 超时无法输出 GO/NO-GO 段。BTC 卡因截图返回空而能继续。修复方向：截图子进程加独立 timeout（如 15s）+ 失败降级 `⚠️ 截图不可用` 而非阻塞主流程。审计 Step 6 实跑 XAU 时如超时，grep 前半段确认 VWAP/EMA 和 TV 注入正常即可，不因截图卡住而判管线全挂。
- **不要跳过实测跑管线** — 静态检查发现不了 import 错误和运行时崩溃
- **杀 LLM cron 前必须先确认用户（2026-06-29 教训）** — 用户明确说保留的 cron（如 Orion雷达分析）不可擅自删除。审计 Step 7.5 的"常见浪费模式"只适用于采集脚本已有 no_agent 落盘且用户从未要求保留 LLM 解读的情况。删除前用 `clarify` 工具确认，不要假设 LLM 解读"价值为 0"。
- **治理数据文件过期 ≠ 数据失效（2026-06-29 v9.6 修正）** — `btc_signal.json`（仅交易触发写入）、`protections_state.json`（无交易无保护变更）、`strategy_governance.json`（月度更新周期）这三类文件的 mtime 老旧是正常现象，不代表数据损坏。判断标准改为：①内容是否含有效字段（如 protections_state 的 stoploss_guard 结构完整）②是否有新交易需要这些数据生效。仅当文件结构损坏 + 有新交易时才标 P0。source_snapshot 类（BTC/XAU 快照）仍保持 <1h 的 P0 铁律。
- **Protections状态必须是结构化JSON对象（2026-07-01审计实测）** — `data/protections_state.json` 不能落成 JSON 字符串如 `"Protections(stoploss_guard={}, ...)"`。审计时用 `json.load` 后检查类型必须为 `dict`，且至少含 `stoploss_guard`、`cooldown`、`max_drawdown`、`risk_multiplier` 或等价结构化字段；若为字符串/缺字段，标P0/P1并修 `risk_constitution.save/load` 为标准对象落盘，同时兼容读取旧字符串。
- **Git 提交 dirty 文件时先判性质（2026-07-07 教训）** — `git status` 出现 `M FinComYY.txt` / `M annualof.txt` 这类修改，不要默认「清理/删除」。实测它们是 `cot_collector.py` 产生的公开 CFTC 持仓数据（外汇+农产品），属项目真实资产、无敏感信息。正确做法：`git add <file> && git commit` 锁定，而非 `rm`。审计发现 unexpected modified 文件时先 `head -3` 看内容性质，确认非密钥/非临时日志再决定提交还是忽略，绝不直接删。
- **Git 114 dirty files → 批量提交是标准解法（2026-06-29）** — 大量 `M scripts/` + `?? scripts/` 是跨会话累积。解法：`git add scripts/ hermes/scripts/` → `git commit -m 'sync: archive accumulated script changes batch v{N}'`。不要逐个审查，不要 stash，不要 cherry-pick。一次大 batch 提交后 dirty count 从 114→0 是正常结果。
- **硬编码值是最隐蔽的 bug** — 必须逐行检查模型函数中的裸数字。`gold_monitor.py:18-21` BUY_ZONE 硬编码为 P1 例行检查项
- **XAU TV SVP v10 行动格/Composite/CVD 不可用，但基础 OHLCV 可现场读（2026-07-07 修正旧 Pitfall）** — 旧 Pitfall 误写「SVP v10 在 OANDA:XAUUSD 不返回 Pine 数据，TV 只能作 BTC 专用」。实测：`chart_get_state` + `data_get_ohlcv` 通过 TV MCP(CDP→TV Desktop) 能返回 OANDA:XAUUSD 真实五层 OHLCV（不依赖 SVP 的加密 Funding/OI 字段）。SVP 的 *行动格/Composite/CVD* 在 XAU 确实不可用（依赖加密独有字段），但 *基础 K线结构* 可 TV 现场读取。正确做法：`scripts/xau_tv_sync.py` 现场切 OANDA:XAUUSD 五层写 `data/xau_tv_state.json`，`auto_card.py` XAU 分支优先读之覆盖占位推算；无则 gold-api 占位但标 `⚠️非TV现场`+状态降B。审计 Step 5 对 XAU 不再「跳过 TV 校验」，改为「优先 TV 现场 OHLCV，缺失才 gold-api 兜底」。
- **XAU/BTC TV缓存交叉污染是P0（2026-07-01首报 · 2026-07-08复发）** — 根因在**数据写入端** `tv_data_bridge.py`：symbol 字段**硬编码 `BINANCE:BTCUSDT.P`** 且 `fresh: True` 自标，但它读取的是 TV 当前图表（可能停在 OANDA:XAUUSD）的 POC/VAH/VAL。`tv_live_dump.py` 包 `collect_and_cache()` 同病。于是 XAU 的 4122 被写进 `tv_dmi_cache.json` 且谎称 BTCUSDT → auto_card 旧 `_tv_cache_status` 只校验 symbol 字符串匹配+年龄，两文件都谎称 BTCUSDT → 误判 usable → **BTC 卡被 XAU 价位污染**（POC 4122 而非 62669）。`行情守望.py` 的 `_check_tv_grade_change` 也读此缓存 → 等级告警误报。2026-07-08 完整根因+两段式修复 recipe 见 `references/2026-07-08-tv-cache-pollution-recurrence.md`。**审计必查命令**：`python -c "import json;d=json.load(open('data/tv_dmi_cache.json'));print(d.get('symbol'),d.get('poc'))"` —— 若 `symbol=BINANCE:BTCUSDT.P` 但 `poc<10000` 即污染铁证；再 `timeout 150 python scripts/auto_card.py BTCUSDT 2>&1 | grep -iE 'POC41|TV实时注入|污染|未采用'`，BTC 卡出现 POC4122/VAH4132 立即标 P0。**两段式修复（已落地验证）**：① 写入端根治 —— `tv_data_bridge.py` 新增 `read_state_symbol()` 调 `_tv_json("state")`（CLI 命令是 `state`，**非** MCP 的 `chart_get_state`）读真实图表 symbol 如实标；`collect_and_cache(expect_symbol=...)` 增加期望品种参数，真实 symbol 不符则拒绝写入+回退旧缓存；`tv_live_dump.py` 传 `expect_symbol="BINANCE:BTCUSDT.P"`。② 读取端第二道防线 —— `auto_card._tv_cache_status` 增加**价位区间合理性校验**：BTC POC 应 >10000、XAU POC 应 <10000，落错区间即判污染拒绝。验证：BTC 卡 POC 4122→62669；`_tv_cache_status` 双拒 `tv_live.json: 价位污染 POC=4122 疑似XAU数据` + `tv_dmi_cache.json: 品种不匹配 OANDA:XAUUSD`。回归断言必须覆盖 `XAU拒绝BTC TV缓存` 与 `BTC接受BTC TV缓存`；旧污染缓存标 `stale` 防误用。
- **修复后必须补回归脚本（2026-07-01修复闭环）** — 全面修复类任务不能只改业务代码，应新增/更新轻量回归脚本（如 `scripts/regression_system_audit.py`）并覆盖：①TV缓存品种门禁 ②Protections旧字符串兼容读取+结构化落盘 ③驾驶舱"矛盾点"表存在 ④Markdown表格列数一致。最终验证命令至少包含 `python -m py_compile ...`、`python scripts/regression_system_audit.py`、BTC/XAU双品种 `auto_card` 实跑、cron错误列表检查。
- **修复后复审必须重跑完整证据链（2026-07-01复审闭环）** — 用户要求"再来一次齐全的全方位审计和检查"时，不要只复述修复报告。必须重新采集运行态/MCP/cron/心跳/数据新鲜度，实跑 BTC+XAU auto_card，保存证据目录并生成新的 `REPORT.md`。复审模式详见 `references/2026-07-01-full-audit-closure-pattern.md`。
- **XAU TV同步无三级降级会拖垮 cron（2026-07-08 实测 P1）** — `scripts/xau_tv_sync.py` 原 `__main__` 直接 `raise SystemExit(asyncio.run(_run()))`，TV CDP 偶断（图表切换/断连）即 exit 1 → cron `XAU TV现场同步` 报 `error: Script exited with code 1`。含铁律（见 `references/2026-07-07-system-optimization-patterns.md` 第四节「cron采集类不得因单源偶断 exit 1」）三级降级修复：①try/except 包住；②若旧 `xau_tv_state.json` 15min 内则保留旧数据 exit 0；③无旧数据则写 `{"stale":true,"error":...}` 占位 exit 0。**审计必查**：`hermes cron list` 中采集类 cron 若 `last run: error: Script exited with code 1`，先查脚本是否含裸 `raise SystemExit` / `sys.exit(1)` 无兜底，是则 P1 补三级降级。**注意**：`xau_tv_sync.py` 顶部需 `import time`（降级逻辑用 `time.time()/strftime`），仅 `import os` 会 NameError。
- **TV缓存桥闭环修复模式（2026-07-01实测）** — `tv_data_bridge.py` 不能再按旧文本格式解析 TradingView CLI；CLI `values/data lines/data tables` 实际返回 JSON。POC/VAH/VAL 优先从 `studies[].values` 的 `POC Price/VAH Price/VAL Price` 读取；行动格从 `studies[].tables[].rows` 解析；`auto_card.py` 读 `tv_live.json`/`tv_dmi_cache.json` 时必须逐个执行 `_tv_cache_status(cache, symbol)`，旧live过期或错品种时继续fallback到新cache，不能提前break；`tv_live_dump.py` 只能作为真实 `collect_and_cache()` wrapper，禁止写硬编码TV关键位；写入端 symbol **必须读真实图表**（见上条 2026-07-08 复发）。完整模式见 `references/2026-07-01-tv-cache-bridge-closure.md` + `references/2026-07-08-tv-cache-pollution-recurrence.md`。
- **双指标能力运行态利用率审计（2026-07-03实测）** — 当用户要求"检查流程/驾驶舱/策略/skill有没有真正用上我的两个指标"时，不能只看源码字段存在；必须验证 `auto_card` 实跑是否实际吃到 SVP MCP Data Window 与 HALDRO Composite/CVD/OI。TV缓存过期/错品种时管线完成度必须标 ⚠️ 并写原因，不能假 ✅；B等待/C等待/X禁做或 R:R<1:2 时不得把当前价渲染成可执行入场。完整检查与修复模式见 `references/dual-indicator-runtime-usage-audit-2026-07-03.md`。
- **auto_card VWAP/EMA 引擎饿死诊断与看门狗 CLI 实战** — 见 `references/auto-card-klines-starvation-2026-07-07.md`（症状/根因/诊断 grep/修复模式/看门狗 cron 正确写法/Windows GBK 坑）。
- **双指标驾驶舱落地模式（2026-07-04实测）** — 当用户同意"可以的/落地/按建议改"后，优先把双指标从"展示字段"升级为"裁决层"：`auto_card.py` 生成 `_dual_indicator_verdict`，`render_v8.py` 在多周期前新增"### 双指标裁决"表，`go_nogo_gate.py` 从7闸门升级8闸门并新增 `dual_indicator` 红/黄/绿灯。非加密品种必须明确 HALDRO 不适用且不因缺失降级；加密主副强冲突必须红灯禁止A级执行。保留 `pytest.ini` 原配置并追加 `pythonpath=scripts`，新增/维护双指标闸门测试。详细落地 runbook 见 `references/dual-indicator-cockpit-implementation-2026-07-04.md`。
- **双指标驾驶舱落地模式（2026-07-04实测）** — 当用户同意"可以的/落地/按建议改"后，优先把双指标从"展示字段"升级为"裁决层"：`auto_card.py` 生成 `_dual_indicator_verdict`，`render_v8.py` 在多周期前新增"### 双指标裁决"表，`go_nogo_gate.py` 从7闸门升级8闸门并新增 `dual_indicator` 红/黄/绿灯。非加密品种必须明确 HALDRO 不适用且不因缺失降级；加密主副强冲突必须红灯禁止A级执行。保留 `pytest.ini` 原配置并追加 `pythonpath=scripts`，新增/维护双指标闸门测试。详细落地 runbook 见 `references/dual-indicator-cockpit-implementation-2026-07-04.md`。
- **TV运行态恢复 + 驾驶舱完整卡闭环（2026-07-03实测）** — 用户要求"按优化建议恢复"时，必须按 BEFORE→守护心跳→TV CDP→study_values/pine_tables/screenshot→`tv_data_bridge.py`→P0数据刷新→BTC/XAU实跑→提交推送→TG报告的顺序闭环。full card 文件本身必须追加"管线完成度审计"表；GO/NO-GO 的 `tv_live` 闸门必须认可 `_tv_main`/`_tv_override`/新鲜 `_tv_cache_status`，不能只认 `_tv_pine`。XAU 拒绝 BTC TV 缓存并显示 7/8 是正确门禁。完整 runbook 见 `references/tv-runtime-recovery-and-card-closure-2026-07-03.md`。
- **监控心跳审计是 P0 第一步** — 本会话发现 heartbeat status="stopped" 持续 14 小时未被任何 cron 检测到
- **守护进程看门狗覆盖必须成对审计（2026-07-07 教训）** — 光查心跳新鲜度会漏掉「孤儿子进程」：行情守望进程存在但无任何看门狗 cron，死亡后全盲 4 小时无人拉起、无告警。审计架构完整性检查必须逐项核对「心跳文件 + 对应看门狗 cron」双存在，缺看门狗即 P0。补建照搬 BTC守护看门狗（`btc_watchdog.py` 每5分 + emergency 限速 20/30）。cron 显示 `last_run=ok` 只代表采集脚本跑过，不代表实时守护活着——两者必须分开查。看门狗脚本模板 + cron 正确写法 + 验证命令见 `references/market-watchdog-pattern.md`。
- **幽灵模块引用检测必须验证文件真实存在（2026-07-07 教训 · 修正旧 Pitfall）** — 旧 Pitfall 曾误写「`auto_card.py` 引用 `system_data_bridge.py`（不存在）」，实测该文件**真实存在**于 `scripts/system_data_bridge.py`（`enrich_engine_data` / `asset_macro_enrich` 均可用）。审计时不能只 grep import 就标 ghost——必须 `find . -name "xxx.py"` 确认文件确实缺失才算幽灵模块。误报会让健康系统被标 P0。当前状态（2026-09-11 实测）：`system_data_bridge.py` **仍在** `scripts/`；`btc_alert_watch_v3` / `btc_push_cron` / `btc_collector` / `btc_fast_daemon` **已移入 `scripts/_archive/`**（`scripts/` 根下已无）。另注意 `btc_keylevel_ws_guard` / `btc_keylevel_sentinel` / `btc_keylevel_rest_guard` / `btc_price_arrival_sentinel` **文件仍在但不在 cron、不在进程中运行** —— 判定幽灵模块时要区分「真缺失 / 已归档 / 仍存在但停用」三态，见 `trading/realtime-trading-pipeline/references/dead-script-index.md`。
- **auto_card VWAP/EMA 引擎饿死是隐藏 P1（2026-07-07 实测根因）** — 实跑 BTC 时打印「⏭ VWAP/EMA引擎：无K线数据，跳过」不等于偶发网络失败。真因：主流程 crypto 分支只拉 CMC/Binance ticker 价格，从未调用 `_collect_binance_data(engine_data, symbol)` 填充 `engine_data["klines"]`。后果：第 3014 行 VWAP/EMA 引擎读 `engine_data.get("futures_klines", [])`（永为空）→ 跳过；第 821 行 `vwap_ema_cvd_summary` 兜底读 `engine_data["_raw_klines_multi"]`（虽有数据但路径未接通）。诊断铁律：遇到「无K线数据」必须 grep 确认主流程是否真的填了 klines（搜 `_collect_binance_data` + `engine_data["klines"]=` + `futures_klines`），而非只查网络。修复模式：crypto 分支 quality=A 后置插入 `try: _collect_binance_data(engine_data, symbol) except Exception: pass`；3014/829 行改读 `_raw_klines_multi["15m"]` 重组 OHLCV；Binance klines 拉取加多源回退（fapi→api.binance.com→data-api.binance.vision）。修复后 BTC 卡从 NO-GO 转 GO 绿灯 6/8。
- **XAU VWAP/EMA 引擎同样会饿死（2026-07-07 R2 修复）** — 原 `_collect_binance_data` 对 XAU/GOLD 直接 return，导致 metal 分支 klines 永空、3014 行 VWAP/EMA 引擎跳过。修复：XAU 不再早退，改拉 Binance XAUUSDT public K线填 klines+_raw_klines_multi（不覆盖 gold-api 共识价，双源并行无冲突）；metal 分支补调 `_collect_binance_data(engine_data, symbol)`。修复后 XAU 实跑 VWAP/EMA 引擎吃到 K线（快线4164·慢线4149）。审计时必须 BTC+XAU 双品种都实跑并 grep VWAP/EMA引擎，两个品种都要出现 `✅ VWAP/EMA引擎：快线...` 而非 `⏭ ...跳过`。
- **Step 6 实跑必须 grep 引擎饿死信号（2026-07-07 新增）** — `timeout 90 python scripts/auto_card.py BTCUSDT 2>&1 | grep -iE "VWAP/EMA引擎|无K线"`：若出现 `⏭ VWAP/EMA引擎：无K线数据，跳过` = 引擎未吃到 K线 = P1（按上条诊断）。BTC 期望 `✅ VWAP/EMA引擎：快线X·慢线Y·CVD方向Z`；XAU 同理（gold-api 价格保留，K线来自 XAUUSDT）。TV五层 `⚠️` 对 XAU 是已知架构限制（SVP v10 加密字段），不算 P1。
- **cron create 实战坑（2026-07-07 实测）** — ①`hermes cron create` 的 `--mode no-agent` 是**无效参数**（报错 `unrecognized arguments: --mode no-agent`）；正确写法是用标志 `--no-agent`（无值）。②script 路径**必须带子目录前缀**，否则解析失败且 cron 运行报 `failed`：例 `monitor/market_watchdog.py` 而非 `market_watchdog.py`（Hermes 把 script 当 `D:/Hermes agent/scripts/` 下相对路径解析，无前缀则找不到）。正确示例：`hermes cron create "3 */1 * * *" --script monitor/market_watchdog.py --no-agent --workdir "D:/Hermes agent" --deliver telegram:-1003733144325:846`。
- **cron script 路径双前缀陷阱（2026-07-09 审计 P0 发现）** — `hermes cron create` 或 `cron edit` 传 `--script` 参数时，Hermes 会把 workdir 下的 `scripts/` 子目录自动拼到路径前。如果脚本本身传了 `scripts/黄金宏观.py`，实际解析成 `D:\Hermes agent\scripts\scripts\黄金宏观.py` → 404 `Script not found`。**铁律：`--script` 参数只传文件名（如 `黄金宏观.py`），不传 `scripts/` 前缀**。子目录脚本传 `monitor/market_watchdog.py`（一级子目录前缀保留，`scripts/` 不传）。审计 Step 7 检查 cron 时，若 `Last run: error: Script not found` 且路径含 `scripts/scripts/`，立即 `hermes cron edit <id> --script "<basename only>"` 修复。实测修复：`黄金宏观刷新`(f171ce3a818a) 和 `TV Desktop保活`(b78741992dfd) 两 cron 均为此 bug。

- **cron 排期语法陷阱：`*/3 *` ≠ `3 */3`（2026-07-09 实测 P0 故障）** — 把看门狗从「每分钟」降频时误写 `3 */3`（分钟=3，小时=`*/3`=每3小时第3分），本意是「每3分钟」应写 `*/3 * * * *`。后果：行情守望看门狗每3小时才检查一次，中间守护进程崩溃（pid 死）23分钟无人拉起、心跳停摆。修复：改回 `*/3 * * * *` 后看门狗立刻在下一触发点拉起守护。**铁律：审计查 watchdogs 时，必须核对看门狗 cron 本身的 schedule 是否真按预期频率触发（用 `hermes cron list` 的 Next run 推算），不能只看 `Last run: ok`——看门狗自己的 schedule 写错 = 单点故障源头。** 通配符位置对照：`*/3 * * * *`=每3分、`3 */3 * * *`=每3小时第3分、`*/3 8-22 * * *`=8-22时段每3分。
- **孤儿数据文件 = 缺 cron 接线（2026-07-09 审计 P0 发现）** — `data_freshness_watchdog` 报某文件过期时，不能只刷它或加白名单。必须先追溯**产出脚本** + 确认**有 cron 驱动该脚本**。实案：`xau_macro_context.json` 由 `黄金宏观.py` 产出，但 hermes cron 里**根本没有挂这个脚本** → 文件永久停在 37h 前（看门狗一直误报）。同样 `source_snapshot_XAUUSD.json` 由 `行情守望.py` 守护每5分节流刷新，守护死后也陈旧。修复：给 `黄金宏观.py` 加 cron（每2h `20 */2`），守护恢复后自动补刷。**审计标准动作（并入数据新鲜度审计）**：对每个被看门狗标记过期的文件，执行 `grep -rl "<filename>" scripts/` 找产出脚本 → `hermes cron list | grep -i <脚本名>` 确认有 cron；无 cron 即 P0（数据永旧），补建 cron 而非删文件/加白名单。
- **高频推送脚本必须加 per-script dedup 限频（2026-07-09 审计发现）** — 审计 TG 推送频率时，`orion_screener_radar.py` 与 `deribit_options.py` 每30分跑且**无条件 `push_tg_rich` 直推**（Orion 有 `if report:` 即推，但 report 只要置信≥4候选就生成，几乎每次都有 → 30条/天）。这俩占全天推送 60 条/天，是轰炸源头。修复：在推送前包 `from alert_dedup import should_send; if should_send("job", content, force_every_seconds=3600): push(...)` —— 内容变化才推，同内容每1h 强制最多1条。`alert_dedup.should_send(job, content, force_every_seconds=3600)` 接口：内容变化或超强制间隔返回 True，否则 False；加 `ImportError` 退化直接推（宁滥勿丢报告）。QLib/X情绪已用同类 dedup（1h/2h）。**审计推送频率时必查**：每30分/每小时跑的脚本若 `push_tg_rich` 前无 `should_send`/`dedup_wrapper` 包裹且无信号 gate，标 P1 补限频（参考已修的 Orion/Deribit）。
- **TV Desktop 无自动保活是架构弱点（2026-07-09 审计修复）** — TV Desktop 依赖人工在桌面 GUI 启动，无自动保活机制。一旦关闭，所有依赖 TV MCP 的管线（`tf_alignment_tv` 周期一致性、`btc_ref_levels_sync` 结构位、`xau_tv_sync`）静默降级 REST/Binance 直取——这是设计内优雅降级，**审计报告必须标注「TV Desktop 当前未运行，管线走 REST 降级」，不能误判为 bug**。修复：新增 `scripts/tv_keepalive.py` 看门狗 + cron「TV Desktop保活」（`*/10 * * * *`，脚本 `scripts/tv_keepalive.py`）：每10分探 9222，未开则调 `tools/tradingview-mcp/scripts/launch_tv_debug.bat` 拉起，拉起失败（无头 session 拒绝访问/路径缺失）静默降级 REST 并记 30 分冷却不刷屏。**铁律：审计 TV 依赖管线前，先确认 9222 是 OPEN 还是被人工关了** —— `curl -s -m 3 http://127.0.0.1:9222/json/version` 或 `python -c "import socket; print(socket.socket().connect_ex(('127.0.0.1',9222))"`（`0`=开放，`10061`=拒绝=TV关）。若 TV 关着，作战室融合报告的周期一致性会显示 `[REST]` 而非 `[TV]`，属正常降级。可复现脚本见本 skill `scripts/tv_keepalive.py`。
- **TV Desktop 从 Hermes 终端启动必须清 ELECTRON_RUN_AS_NODE env（2026-07-09 攻克根因）** — 手动/keepalive 启动 TV 带 `--remote-debugging-port=9222` 时若报 `bad option: --remote-debugging-port` 或「拒绝访问」，根因是 **Hermes 终端默认注入 `ELECTRON_RUN_AS_NODE=1`**，让 TV（Electron 应用）以 node 模式启动并拒绝 Chromium flag。MCP 的 `tv_launch` 内部已 strip 该 env 所以能用，但手动启动/keepalive 脚本必须自己 strip。修法三选一（均实测可用）：①bash `env -u ELECTRON_RUN_AS_NODE -u ELECTRON_DISABLE_SANDBOX "TV.exe" --remote-debugging-port=9222`；②Python `child_env=os.environ.copy(); child_env.pop("ELECTRON_RUN_AS_NODE"); subprocess.Popen([tv_exe, f"--remote-debugging-port={PORT}"], env=child_env)`；③bat `set ELECTRON_RUN_AS_NODE=` 后 `start "" "%TV_EXE%" --remote-debugging-port=%PORT%`。**适用范围：任何从 Hermes 终端启动、需传 Chromium flag 的 Electron 应用都先清该 env。** 完整复现+验证见 `references/tv-desktop-launch-env-pollution.md`。`tv_keepalive.py` 回退路径与 `launch_tv_debug.bat` 已落地该修复，所以现在保活看门狗能真拉起 TV（之前因 env 污染拉不起，只能 REST 降级）。

- **Windows 看门狗脚本 wmic GBK 解码坑（2026-07-07 实测）** — 看门狗用 `subprocess.run(["wmic",...], capture_output=True, text=True)` 读取进程列表时，wmic 返回 GBK 编码，Python 线程解码抛 `UnicodeDecodeError: 'utf-8' codec can't decode byte` 导致 watchdog 异常退出（虽仍输出重启表但 stderr 噪音大）。修复：去掉 `text=True`，改 `stdout.decode("gbk", errors="replace")`。同理任何调用 wmic/tasklist 的脚本都要显式 gbk 解码。
- **复盘率不足已根治（2026-07-07 实测）** — 审计时 `wc -l data/trade_plans.jsonl data/trade_reviews.jsonl` 实测 441/372 = 复盘率 84%（远超 10% 门槛）。原 Pitfall 中「复盘率 3.5%」已失效，不再标记 P1。但**仍要查**（防止回退）：若 reviews/plans < 10% 才标 P1。
- **技能清单需与文件系统同步** — 本 SKILL.md 列出的 4 个脚本（btc_alert_watch_v3/btc_push_cron/btc_collector/btc_fast_daemon）实际不存在
- **脚本双目录散落** — 修改 AppData 的脚本，项目目录的旧版本还在运行。`scripts/` 和 `scripts/monitor/` 存在重复
- **告警 gap** — 模块在引擎层但不在 cron 自主层 = 用户等不来推送
- **多资产覆盖盲区** — 审计默认只查 BTC/XAU。外汇/股票/期货/期权需手动指定 asset_class 参数验证
- **管线实测超时不足（2026-06-29）** — `auto_card.py` 需要 ≥90s 才能输出完整结果（含 GO/NO-GO）。60s 仅能输出前半段（数据采集+引擎运算），错过闸门状态和 exit_code。审计 Step 6 必须设 `timeout 90`，不要用 60 或 120 以外的值。
- **脚本双目录版本发散（2026-06-29）** — `scripts/` 和 `hermes/scripts/` 下有 23 个同名脚本，除 `orion_screener_radar.py` 外全部版本不同。`auto_card.py` 通过 `sys.path.insert` 同时引用两个目录解决了 import，但 AI 按文档执行 `python scripts/xxx.py` 和 `python hermes/scripts/xxx.py` 可能调的是不同版本。审计 Step 3b 必须执行 `diff -q` 逐一比对。修复方案：统一到 `scripts/` canonical 后删除 `hermes/scripts/` 副本。
- **多数据目录并存（2026-06-29）** — 脚本输出可能散落在三个目录：`D:/Hermes agent/data/`（交易系统 canonical）、`~/AppData/Local/hermes/data/`（Hermes 默认）、`D:/Hermes agent/tail_logs/`（旧采集）。审计数据新鲜度时必须检查这三个目录。错判"文件不存在"会导致误报。排查顺序：①项目 data/ → ②AppData data/ → ③tail_logs/
- **Orion API 参数要求（2026-06-29 修复）** — `fetch_orion("")` 不传 exchange 参数时 Orion Terminal API 返回空数组。修复：`fetch_orion("binance")`。同时脚本内置代理回退（cron 环境无 HTTPS_PROXY）。
- **Cron stdout 编码（2026-06-29）** — emoji (⚠️📡🟢) 在 cron 存储层产生 mojibake（`鈿狅笍`），错误信息用纯 ASCII。
- **数据文件过期是静默 P0（2026-06-29）** — `protections_state.json` 9 天过期 → 真实风控失效。`btc_signal.json` 6 天过期 → 信号基于过期数据。审计 Step 0 全量检查 7 个关键文件的 mtime。
- **Skill 库精简审计（2026-06-29）** — 281 个 skill 全部 enabled 时增加每会话扫描开销。审计时 `hermes skills list | tail -3` 看总数。精简方法：在 `config.yaml` 的 `skills.disabled` 列表加入不相关领域的 skill 名。保留 trading(27)、Hermes 管理(11)、devops 核心(7)、GitHub(6)、安全(2)、数据分析(2)、内容创作(~30)、浏览器/搜索(~8)、文档(4)、编码(~15)、金融数据(~10)。可禁用：n8n(7)、HuggingFace(12)、crypto-web3 DeFi/NFT(10)、创业/PM(14)、无关社区/创意/DevOps(~56)。实测 281→183（-35%）无功能损失。
- **v9.0 分析流程社区对标（2026-06-29 联网审计）** — 当用户要求"联网社区全面看分析流程"时，对比以下 2026 年社区最佳实践：
  - 盘前 GO/NO-GO 闸门（EdgeFlo）：7 问硬检查，分析卡输出后、下单前执行
  - 交易执行质量评分（Trader's Second Brain）：入场后 A/B/C 评级，A级亏钱 > C级赚钱
  - 仓位公式 + 体制乘数（Quant Checklist）：仓位 = 账户风险% ÷ (ATR × 体制乘数)
  - 6 体制模型（Market Regimes）：方向(200MA) × 波动(ATR比值) = 6 类，你的 4 类缺方向维度
  - 相关性限制（Quant）：新仓位与持仓相关性 >0.7 → 减仓 50%
  - 加密 Kill Zone（ICT）：亚洲积累→伦敦扫荡→纽约派发
  - 亏损冷却（TQS）：亏损 >1.5% → 暂停 5 分钟；C 级连击 2 次 → 当日停止
  你的 v9.0 16 维管线在数据源覆盖上属社区顶级，但缺上述 6 个执行层环节。
- **驾驶舱策略/模板/任务稳定性总审计（2026-06-29 实测补充）** — 此类任务必须把"能力是否存在"和"运行态是否吃到能力"分开审计。新增参考 `references/2026-06-29-cockpit-strategy-audit-lessons.md`。关键新增检查：①cron绿灯不等于daemon健康（先查行情守望/BTC daemon心跳）②大量 modified/untracked = P0 未锁定 ③master-template 与用户表格偏好冲突 = P1 模板源头漂移 ④router 要实测6类资产，不能只看文档 ⑤auto_card 能跑但若 TV缓存过期/品种不匹配/风控0U/高低价异常，仍判不可信 ⑥复盘率 reviews/plans 低于10% = P1 策略治理断裂。
- **截图必须用 send_message** — MEDIA: 路径写在回复里不保证发到正确话题
- **Cron 超时是系统性问题不是偶发** — no_agent cron 默认 120s 超时对多源网络验证脚本不够用。Orion 全市场雷达（四层验证：Orion→HL→Binance→CoinGecko）和 SkillMCP 更新（MCP 测试+curator+升级检查）均会超时。审计 Step 7 检查 cron 健康时，对 `last run: error: Script timed out after 120s` 的任务标记 P1。修复优先级：①优化脚本减少候选数/增加 per-call timeout → ②增加 cron 超时阈值 → ③拆分为多个顺序 cron
- **脚本路径分裂（2026-06-29 深度审计发现）** — 21 个关键脚本只在 `hermes/scripts/` 目录下，不在 `scripts/`。SKILL.md 和用户文档中写的是 `python scripts/data_gatherer.py`，但实际路径是 `hermes/scripts/data_gatherer.py`。`auto_card.py` 通过 `sys.path.insert` 同时插入两个目录解决了 import 问题，但 AI 按 SKILL.md 指引直接执行 `python scripts/xxx.py` 会报 `No such file`。审计时检查：`ls scripts/data_gatherer.py hermes/scripts/data_gatherer.py 2>&1` — 如果只在 hermes/scripts/ 存在，标记 P1。受影响脚本：data_gatherer, multi_model_engine, model_checklist, coingecko_collector, position_sizer, prediction_tracker, multi_source_collector, sentiment_search, macro_filter, event_ban_live 等 21 个。
- **治理数据文件过期（2026-06-29 深度审计发现）** — 审计 Step 5 只检查 source_snapshot 新鲜度，但以下治理/风控文件同样需要新鲜度检查：`protections_state.json`（风控保护状态）、`strategy_governance.json`（策略治理）、`strategy_model_stats.json`（模型统计）、`xau_macro_context.json`（黄金宏观）、`btc_signal.json`（BTC信号）。实测 5 个文件过期 6-9 天，意味着风控系统在用过期的 protections 状态。审计时追加检查：`ls -lt data/protections_state.json data/strategy_governance.json data/strategy_model_stats.json data/xau_macro_context.json data/btc_signal.json` — 超过 3 天标 P0，超过 1 天标 P1。
- **复盘率严重不足（2026-06-29 深度审计发现）** — trade_plans.jsonl 有 342 条但 trade_reviews.jsonl 只有 12 条，复盘率 3.5%。strategy_model_stats 只有 1 笔交易记录，远低于 20 笔的模型升权门槛。审计时检查：`wc -l data/trade_plans.jsonl data/trade_reviews.jsonl` — 如果 reviews/plans < 10%，标记 P1。复盘闭环断裂意味着系统无法自我改进——分析再多也不知道对错。**注意**：`trade_events.jsonl` 是系统监控事件（位突破预警/信号失效/接近关键位等），不是交易计划。复盘率计算必须用 `trade_plans.jsonl`（真实交易计划），不要拿 `trade_events.jsonl` 来算——310条事件≠310笔交易，会误判为积压。
- **SOUL.md 未定制 persona（2026-06-29 深度审计发现）** — SOUL.md 仍是默认 Hermes Agent 提示词（513 字符），未包含"安禾"或"棠溪"或交易 persona 个性化内容。Memory 里写了 `SOUL persona=安禾`但实际文件未改。审计时检查：`grep -c "安禾\|棠溪\|交易" ~/AppData/Local/hermes/SOUL.md` — 返回 0 则标记 P1，persona 未生效。
- **Windows cron 脚本 UTF-8 编码修复模式（2026-06-29 修复）** — 输出中文/emoji 的 no_agent cron 脚本在 Windows GBK 环境下会产生乱码。修复模式：在脚本 import 后、任何 print 之前插入 `import io as _io; if hasattr(sys.stdout, "buffer"): sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")`。已修复 11 个脚本：orion_screener_radar, gold_monitor, btc_daemon, btc_zone_alert, etf_flow_collector, dune_collector, deribit_options, cot_collector, btc_card_gen, daily_skill_mcp_update, daily_private_repo_backup。审计时对新脚本检查：`head -20 scripts/xxx.py | grep TextIOWrapper` — 无则标记 P2。
- **hermes CLI uv trampoline 修复模式（2026-06-29 修复）** — cron 环境中 `hermes` 命令的 uv 包装器可能报 `uv trampoline failed to canonicalize script path`。修复：所有 subprocess 调用 hermes CLI 的地方用 `[sys.executable, "-m", "hermes_cli.main", ...]` 替代 `["hermes", ...]`。已修复 daily_system_audit.py 和 daily_skill_mcp_update.py。审计时检查：`grep -rn '"hermes"' scripts/repo-maintenance/*.py` — 如果有则标记 P2。
- **cron 合并审计模式（2026-07-07 新增）** — 用户说"cron太多/优化cron"时优先合并而非删除。可合并：①同数据「采集cron(local)」+「分析cron(tg)」→采集完直接渲染推TG，删独立分析cron（Orion实例）；②多低频维护cron同窗口→聚合脚本顺序调各main()拼接输出一次推TG（daily_ops_bundle实例）。不可合并：数据源不同（X情绪采集vsLLM）、监控对象/重启逻辑不同（3看门狗）、各自独立数据源频率不同。cron id 从 `C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json` 读（`hermes cron list` 不输出id）。cron 操作命令铁律见 `references/2026-07-07-system-optimization-patterns.md`。
- **社区 skill 联网发现+安装模式（2026-07-07 新增）** — 用户说"联网社区按最佳推荐"时：先 `hermes skills search <kw>` 再 `web_search` "skills.sh trending / Heurist Mesh TraderMonty / Binance Skills Hub"，GitHub 直链 kukapay/crypto-skills + tradermonty/claude-trading-skills 可 `hermes skills install <github raw SKILL.md url> --name X --yes` 直装（security scan SAFE/MEDIUM 均可）。注意：`hermes skills uninstall` 对 builtin/local 源报"not a hub-installed skill"无法卸载且不占负担→不强制清理 disabled skill。完整发现源/安装命令/本会话装的2个/不装的清单见 `references/2026-07-07-system-optimization-patterns.md`。
- **BTC关键位 cron 偶发失败必须降级（2026-07-07 新增）** — `btc_ref_levels_sync.py` 原 TV刷新失败直接 raise→exit 1。修复：`refresh_tv_cache()`失败转warning继续+新增`_pick_cache_relaxed()`放宽cache年龄到120min兜底。铁律：cron采集类任务不得因单一数据源(TV)偶断而exit 1，必须有次级源/Binance直取/放宽cache年龄三级降级。详见 `references/2026-07-07-system-optimization-patterns.md` 第四节。
- **系统全面对比是独立交付物（2026-07-07 新增）** — 用户说「全面检查/对比社区/我们的系统」时，产物不是单纯 P0/P1 清单，而是「自研 vs 内置tangxi skill vs 社区标杆」三维对比。核心认知：棠溪系统=Hermes内置`tangxi-*` skill规格的落地实现（100+脚本是工程落地）。对比方法四步法（一致性/社区对标/六市场地图/真实差距）+ 五维评分总评A-，见 `references/2026-07-07-system-comparison-and-rename.md`。铁律：区分「主动定位边界」(不开户/不碰美股/不碰DeFi)与「真实短板」(零真实成交校准)，边界不当短板。
- **disabled skill 无法卸载（2026-07-07 实测）** — `hermes skills uninstall <name>` 对 builtin/local 源报「not a hub-installed skill」，不可卸载且不占运行时负担。不要在此浪费时间；改为「自研脚本 vs Hermes内置trading套件整合」方向（options-trading-strategies/professional-finance-data/crypto-onchain-flow 已内置可整合）。
- **cron 跑的是内存里旧 .pyc，改源码后必须清 pyc 才生效（2026-07-08 实测）** — 给 `xau_tv_sync.py` 加了三级降级并 py_compile 通过，但随后 16:15 的 cron 仍 `error: Script exited with code 1`（跑的是修复前旧字节码）。手动 `python xau_tv_sync.py` 却 exit 0。根因：cron 调度进程持有编译后的 `.pyc`，源码改了但没重载。铁律：**审计中 patch 任何被 cron 引用的脚本后，必须 `find scripts -name "*.pyc" -delete` 清字节码缓存，再 `hermes cron run <id>` 验证修复真的在 cron 环境生效**，不能只手动跑脚本通过就以为修好了。
- **夜间静默门 + 盘中降频是 cron 优化的标准交付（2026-07-08 用户明确要求）** — 用户要求「23:00–次日08:00 不提示但后台运行，其他时段发TG」。正确做法不是逐个脚本加时段判断，而是**在统一推送入口 `telegram_reliable.push_tg_rich` 加一处时段 gate**（`now_h>=23 or now_h<8` → `return True,"silent_night"`），19 个推 TG 脚本全部自动生效；返回 True 而非 False 避免 cron 误判失败/堆积 pending。同时用 `hermes cron edit <id> --schedule "..."` 把盘中任务（Orion/Deribit/X情绪/清算/数据新鲜度/QLib/作战室/X情绪LLM/行情守望）加 `8-22` 时段窗口降频、行情守望 `*/1`→`*/3`；保活类（BTC守护看门狗/执行桥接/XAU TV同步/BTC关键位同步）保持常驻不降频。完整 gate 代码 + 降频清单 + 两个 cron error 任务修复 recipe 见 `references/cron-night-silent-and-downschedule.md`。审计 Step 7 检查「任务频繁/夜间打扰」诉求时，按此模式实施而非新建脚本。
- **cron 在跑 ≠ 推送成功（高价值陷阱 · 2026-07-07 首报 + 2026-07-08 重大修正）** — 用户说「7个推TG的cron一个都没在TG群收到」。⚠️ **2026-07-08 推翻旧单一归因**：旧 Pitfall 曾写「根因=TELEGRAM_BOT_TOKEN 未配置→Hermes静默丢弃」。本次实测证明该假设**不恒成立**——本机 token **已配置**，`hermes send --json` 返回 `message_id` 连续递增（5452→5456），投递链路真实可用，但用户仍说没收到。**「用户没见到」有五种独立原因，必须分离验证，不能只看 `Last run: ok` 或盲目 grep Roaming 路径的 .env**：
  1. **配置路径找错（误判来源）** — 别硬编码 `Roaming/hermes/.env` 去找 token；用 `hermes config env-path` 取真实 .env（`AppData/Local/hermes/.env`），`hermes config path` 取 config.yaml。`hermes send --list telegram` 能列 target = token 已生效。
  2. **bare `sent` 不是交付证明** — `hermes send "x"` 回 `sent` 仅 CLI 回显。必须 `--json` 拿真实回执：`success:true` + **`message_id` 连续递增**（如 5452→5453）才是服务端真实接收证据。连发3条看 message_id 是否递增。
  3. **cron 本身有无产出** — 查 `cat "$LOCALAPPDATA/hermes/cron/output/<job_id>/<latest>.md"`：`Status: silent (empty output)` = 脚本无 stdout 可推，与 token/topic 无关，是独立故障类（P2/P3）。
  4. **发错 topic** — `hermes send --list telegram` 列所有 forum topic（如 `阿弥黛黛 / topic 846` vs `topic 386`）。cron 配 `:846` 但用户实际看 `:386`（BTC信号源）→ 消息到了但用户没在看那个话题。改 cron `deliver` 到对应 thread_id 或重发验证。
  5. **表格退化成裸 `|`（2026-07-08 棠溪纠正真因之一）** — `hermes send` 与 cron no_agent stdout 投递都走 `sendMessage`+`MarkdownV2`，**不渲染管道表**，真表格在 TG 显示为 `| 列 | 列 |` 竖线文本。用户说「不是真表格」即此。根因不是没发，是发了但没渲染。修复：脚本内 self-send `telegram_reliable.send_telegram_reliable(parse_mode="RichMarkdown")` 走 `sendRichMessage` 渲染真表格（回执 `rich_sent`），cron `deliver` 改 `local`。7 个推 TG cron 必须统一，见 `references/tg-report-richmarkdown-consistency.md`。
  6. 排除前5项后让用户直接确认「去该话题看有没有 message_id XXXX」：有=投递通只是没注意或表格退化；无=回到 ①②③④。
  **铁律**：报「TG投递已验证」前必须 `--json` 拿 `message_id` 且用户确认可见（真表格非裸 `|`）；配置路径用 `hermes config env-path` 取不要猜 Roaming/Local；「用户没见到」≠「系统没发」。
  **完整诊断树见 `references/telegram-delivery-debugging-2026-07-08.md`**（旧版 `telegram-delivery-debugging.md` 归因部分已过时，以 2026-07-08 版为准）。
- **审计中修一个脚本会拖垮另一个 cron（2026-07-08 高价值教训）** — 审计修复 `tv_data_bridge.py` 加 `expect_symbol` 回退旧缓存逻辑后，BTC关键位同步（`btc_ref_levels_sync.py` 调 `tv_live_dump`→`collect_and_cache`）因图表停在 XAU 回退到错的旧缓存 → 每日4次的 BTC关键位同步全部 `script failed` → 用户「推送tg的都没见到报告」。**铁律：审计/修复改了被多个 cron 共享的底层模块（tv_data_bridge / tv_live_dump / auto_card 等）后，必须把依赖它的每一个 cron 都 `hermes cron run` 复跑一遍，不能只看「手动跑脚本通过」就收工。** 正确修法（已落地）见 `references/btc-key-level-sync-mcp-stdio-recipe.md`：BTC关键位同步改用 MCP stdio 路径独立切 BTC 读 SVP，不回退旧缓存、不依赖全局图表状态。
- **`expect_symbol` 回退旧缓存是错误修法（2026-07-08 修正旧 Pitfall）** — 旧 XAU/BTC 污染修复用 `collect_and_cache(expect_symbol)` 「品种不符则拒绝写入+回退旧缓存」。但回退到的旧缓存本身可能就是错品种（手动跑 bridge 时图表停 XAU 把 XAU 写进了缓存），于是把错数据继续传播。正确写入端：**独立 MCP stdio 路径切目标品种直读**（`references/btc-key-level-sync-mcp-stdio-recipe.md`），读取端第二道防线（价位区间合理性 BTC>10000/XAU<10000）保留。
- **TV MCP `--symbol` 直读对 SVP 主指标无效（2026-07-08 实测）** — `tv values/data tables/data lines --symbol BTC` 只返回 HALDRO 副指标（聚合、仅加密有效），SVP 主驾驶（POC/VAH/VAL/决策表）绑定图表当前品种，直读读不到。CLI `symbol set` 在 CDP 下极不稳定（反复切会卡 `CBOE_DLY:SET`）。唯一可靠路径：MCP stdio（`fetch_tv_mcp.set_symbol` + `get_study_values`/`get_pine_lines`）独立切品种读，读完回切原图表。
- **MCP 工具返回必须先 `parse_result` 再 `json.loads`（2026-07-08 实测）** — `fetch_tv_mcp` 的 `get_study_values`/`get_pine_lines`/`get_ohlcv` 返回 `CallToolResult`，含 `meta=None content=[TextContent(...)]` 包装。直接 `json.loads(str(raw))` 失败返回 `{}` → 解析函数返回 None → 静默降级。必须先 `from fetch_tv_mcp import parse_result; json.loads(parse_result(raw))`。另：调用 `get_chart_state`/`set_symbol` 等是 **async** 函数，必须 `await`，漏 `await` 会 `TaskGroup` 报错。
  1. **配置路径找错（误判来源）** — 别硬编码 `Roaming/hermes/.env` 去找 token；用 `hermes config env-path` 取真实 .env（`AppData/Local/hermes/.env`），`hermes config path` 取 config.yaml。`hermes send --list telegram` 能列 target = token 已生效。
  2. **bare `sent` 不是交付证明** — `hermes send "x"` 回 `sent` 仅 CLI 回显。必须 `--json` 拿真实回执：`success:true` + **`message_id` 连续递增**（如 5452→5453）才是服务端真实接收证据。连发3条看 message_id 是否递增。
  3. **cron 本身有无产出** — 查 `cat "$LOCALAPPDATA/hermes/cron/output/<job_id>/<latest>.md"`：`Status: silent (empty output)` = 脚本无 stdout 可推，与 token/topic 无关，是独立故障类（P2/P3）。
  4. **发错 topic** — `hermes send --list telegram` 列所有 forum topic（如 `阿弥黛黛 / topic 846` vs `topic 386`）。cron 配 `:846` 但用户实际看 `:386`（BTC信号源）→ 消息到了但用户没在看那个话题。改 cron `deliver` 到对应 thread_id 或重发验证。
  5. 排除前4项后让用户直接确认「去该话题看有没有 message_id XXXX」：有=投递通只是没注意；无=回到 ①②③④。
  **铁律**：报「TG投递已验证」前必须 `--json` 拿 `message_id` 且用户确认可见；配置路径用 `hermes config env-path` 取不要猜 Roaming/Local；「用户没见到」≠「系统没发」。
  **完整四因诊断树 + 各因验证命令见 `references/telegram-delivery-debugging-2026-07-08.md`**（旧版 `telegram-delivery-debugging.md` 仍保留 token 配置/forum thread/TOPIC_CLOSED/Markdown表格400 等写法，但归因部分已过时，以 2026-07-08 版为准）。
- **审计中修一个脚本会拖垮另一个 cron（2026-07-08 高价值教训）** — 审计修复 `tv_data_bridge.py` 加 `expect_symbol` 回退旧缓存逻辑后，BTC关键位同步（`btc_ref_levels_sync.py` 调 `tv_live_dump`→`collect_and_cache`）因图表停在 XAU 回退到错的旧缓存 → 每日4次的 BTC关键位同步全部 `script failed` → 用户「推送tg的都没见到报告」。**铁律：审计/修复改了被多个 cron 共享的底层模块（tv_data_bridge / tv_live_dump / auto_card 等）后，必须把依赖它的每一个 cron 都 `hermes cron run` 复跑一遍，不能只看「手动跑脚本通过」就收工。** 正确修法（已落地）见 `references/btc-key-level-sync-mcp-stdio-recipe.md`：BTC关键位同步改用 MCP stdio 路径独立切 BTC 读 SVP，不回退旧缓存、不依赖全局图表状态。
- **`expect_symbol` 回退旧缓存是错误修法（2026-07-08 修正旧 Pitfall）** — 旧 XAU/BTC 污染修复用 `collect_and_cache(expect_symbol)` 「品种不符则拒绝写入+回退旧缓存」。但回退到的旧缓存本身可能就是错品种（手动跑 bridge 时图表停 XAU 把 XAU 写进了缓存），于是把错数据继续传播。正确写入端：**独立 MCP stdio 路径切目标品种直读**（`references/btc-key-level-sync-mcp-stdio-recipe.md`），读取端第二道防线（价位区间合理性 BTC>10000/XAU<10000）保留。
- **TV MCP `--symbol` 直读对 SVP 主指标无效（2026-07-08 实测）** — `tv values/data tables/data lines --symbol BTC` 只返回 HALDRO 副指标（聚合、仅加密有效），SVP 主驾驶（POC/VAH/VAL/决策表）绑定图表当前品种，直读读不到。CLI `symbol set` 在 CDP 下极不稳定（反复切会卡 `CBOE_DLY:SET`）。唯一可靠路径：MCP stdio（`fetch_tv_mcp.set_symbol` + `get_study_values`/`get_pine_lines`）独立切品种读，读完回切原图表。
- **MCP 工具返回必须先 `parse_result` 再 `json.loads`（2026-07-08 实测）** — `fetch_tv_mcp` 的 `get_study_values`/`get_pine_lines`/`get_ohlcv` 返回 `CallToolResult`，含 `meta=None content=[TextContent(...)]` 包装。直接 `json.loads(str(raw))` 失败返回 `{}` → 解析函数返回 None → 静默降级。必须先 `from fetch_tv_mcp import parse_result; json.loads(parse_result(raw))`。另：调用 `get_chart_state`/`set_symbol` 等是 **async** 函数，必须 `await`，漏 `await` 会 `TaskGroup` 报错。

- **多市场运行态利用率 + TV前置顺序 + FinalVerdict渲染 + 逐代理节点验证（2026-07）** — 当用户问“全部能力是否用上/代理还是直连/全面优化驾驶舱”时，不能把Key存在、接口可调用或路由声明当作已接线。必须区分已配置→可调用→已接线→已裁决；只有后两级算用于分析。正式分析顺序固定为目标symbol复核→主周期→Data Window刷新→XAU五层同步→引擎/体制/风控→full截图。TV五层和cron_read完成度按真实周期覆盖、文件名、mtime和内容质量计算。FinalVerdict只允许GO-A/GO-B/WAIT/NO-GO，旧等级不得覆盖。代理必须逐节点测Spot/Futures/只读签名接口，测试后恢复原节点。详见 `references/multiasset-runtime-and-proxy-verification-2026-07.md`。
- **守护进程多实例复发 + 手动启动与看门狗冲突（2026-07-11 实测）** — 即使看门狗 cron 已配齐（行情守望每3分 + BTC守护每5分），手动 `terminal(background=true)` 启动守护进程后看门狗又拉起一个 → 立即 2-3 实例并存。根因：手动启动与看门狗拉起无互斥机制。**审计修复后铁律：杀所有实例 → 清所有锁 → 不手动启动 → 等看门狗 cron 下次触发自动拉起单实例。** 只有看门狗是生产重启权威。验证用 `psutil` 逐个列 PID+age+cmdline，同脚本 >1 即 P0。
- **MCP SDK 缺失导致 `mcp test` 全失败（2026-07-11 实测）** — `hermes mcp test tradingview/binance` 报 `requires the 'mcp' Python SDK, but it is not installed`。修复：`pip install 'hermes-agent[mcp]'`。修复后 TV 78 tools + Binance 15 tools 全部 Connected。**注意**：`execute_code` 环境的 `pip install` 可能不生效（PATH/解释器差异），需在 `terminal` 中跑。审计 Step 5 MCP 利用度检查时如 `mcp test` 失败但缓存数据新鲜且无品种污染，说明 TV MCP CDP 通道虽不通但缓存链正常，标 P1 而非 P0。
- **XAU auto_card 三段累积超时（2026-07-11 实测根因）** — XAU 管线 90s 超时卡死，根因不是单点而是三段累积：① `xau_tv_sync.py` subprocess timeout=30s ② `tv_live_dump.py` 紧接着再跑 45s（XAU 已由 xau_tv_sync 完成同步，重复等待）③ `_collect_binance_data` 对 XAUUSDT 拉 4 周期 klines × 6s = 最坏 24s。三段合计 75-99s。修复：① XAU 时 `xau_tv_sync` 降为 20s + `try/except TimeoutExpired` ② XAU 跳过 `tv_live_dump`（XAU 专用路径）③ XAU klines 限 2 周期 × 3s timeout。**审计铁律：管线超时必须逐段计时定位**（`price_consensus` 12s + `_collect_binance_data` 17s + TV前置 30s），不能假设单一阻塞点。完整修复模式见 `references/auto-card-klines-starvation-2026-07-07.md` 末尾「XAU auto_card 超时根因与三段式修复」。
- **截图超时双层保护模式（2026-07-11 实测）** — `auto_card.py` 调 `_tv_screenshot(symbol)` 时若 `tv_screenshot.py` 内部 MCP `Connection closed`，子进程虽返回 None 但可能耗时很长（原 timeout=180s）。修复：① `tv_screenshot.py` 子进程 timeout 180→60s ② `auto_card.py` 用 `threading.Thread(daemon=True).join(timeout=45)` 包裹截图调用，线程超时后打印降级信息继续出卡。**铁律：任何可能卡住的 subprocess 调用都应在线程级加超时保护，不能依赖子进程自身 timeout。**
- **管线审计段 klines NameError（2026-07-11 实测）** — `auto_card.py` 管线完成度审计段引用 `klines.get(tf)`，但 `klines` 是 `_collect_binance_data` 内部局部变量，在审计段作用域不可访问 → `NameError: cannot access free variable 'klines'`。修复：改用 `engine_data.get("klines", {}) or {}`。审计时若 XAU auto_card 输出 `Traceback...NameError: klines` 即此 bug。
- **`binance_public.py` 代理绕过导致全源返回None（2026-07-11 实测 P0）** — `_opener()` 原本强制 `urllib.request.ProxyHandler({})` direct连接，但 Hermes 桌面环境必须走 `HTTPS_PROXY=http://127.0.0.1:7897` 才能访问外网。结果 `fetch_spot()` / `fetch_futures()` 全部返回None，`auto_card` VWAP/EMA引擎因无K线而跳过。修复：检测 `HTTPS_PROXY`/`HTTP_PROXY` 环境变量存在时改用默认opener（自动继承系统代理），无代理时才direct。审计时若 `python -c "from binance_public import fetch_spot; print(fetch_spot('/api/v3/time'))"` 返回None但 `curl -x $HTTPS_PROXY https://api.binance.com/api/v3/time` 能通，即此问题。
- **XAU K线必须走 Binance U本位期货，现货无此symbol（2026-07-11 实测 P0）** — `XAUUSDT` 在 Binance 现货不存在（`/api/v3/klines` 返回 `-1121 Invalid symbol`），只有 U本位期货 `/fapi/v1/klines` 提供。`_collect_binance_data` 原对XAU仍调用 `fetch_spot('/api/v3/klines')` → 永远空K线 → VWAP/EMA引擎饿死。修复：XAU分支改走 `fetch_futures('/fapi/v1/klines')`。BTC等加密现货仍走spot。
- **BTC守护看门狗必须用 psutil 杀全部实例并Popen直起（2026-07-11 实测 P0复发）** — 旧 `btc_watchdog.py` 用 Windows `start /B python btc_daemon.py` shell拉起，PID文件追踪不可靠；手动启动与cron看门狗无互斥，导致2-7个 `btc_daemon` 实例并存。修复后看门狗铁律：①`psutil` 列出所有cmdline含 `btc_daemon.py` 的进程全部terminate/kill；②删除 `.btc_daemon.pid` + `.btc_daemon.lock`；③`subprocess.Popen([sys.executable, DAEMON])` 直接起；④sleep 2秒用psutil验证进程存在；⑤把PID写回文件；⑥启动后若心跳仍失联则推TG告警。不可用 `os.system('start /B ...')` 或 `subprocess.Popen('start /B ...', shell=True)`。
- **看门狗 resume 后必须再等 1-2 个触发周期才确认单实例（2026-07-11 实测）** — resume 看门狗时旧 watchdog.log/状态文件可能仍停在崩溃前时间点，不能单凭"无新日志"就判定看门狗没跑；应查 `hermes cron list` 的 `Last run` 和 `Next run`，并用 `psutil` 过滤虚警后统计真实守护进程数。新看门狗脚本应写独立日志（如 `data/.btc_watchdog.log`）或每次执行追加时间戳到状态文件，否则 `watchdog.log` 停止更新会误导审计。
- **psutil 进程发现会把审计命令自身算成守护进程（2026-07-11 实测）** — `psutil.process_iter()` 会把当前执行的 `python -c "import psutil..."` 子进程以及 bash `-c '...import psutil...'` 包装进程误列入守护进程清单，导致实例数虚高。审计命令必须过滤：排除 `cmdline` 含 `bash -c`、含 `-c import psutil`、以及当前 `os.getpid()` 自身。真实守护进程判断：`str(DAEMON_PATH) in cmd and 'bash' not in cmd and '-c import psutil' not in cmd`。
- **守护进程/看门狗脚本应写结构化运行时日志而不是静默成功（2026-07-11 实测）** — 修复后 `btc_watchdog.py` 运行成功时若 stdout 为空，`watchdog.log` 与 `watchdog_state.json` 均停留在崩溃前旧内容，审计无法区分"没跑"与"跑了且健康"。修复标准：看门狗每次执行写入 `data/.btc_watchdog_state.json`（含本次运行时间、发现实例数、采取措施、当前守护PID），守护进程每次循环心跳同时写 `data/.btc_daemon_state.json`（zone/price/alert_count）。审计 Step 0 心跳检查应直接读这些结构化文件而非只看原始心跳。
- **同一修复在 execute_code 和 terminal 环境表现可能不同（2026-07-11 实测）** — `execute_code` 子环境可能不继承 `HTTPS_PROXY`，而 `terminal()` 继承了；`requests.get` 能通不代表 `urllib.request`（binance_public）能通。验证修复时必须在**目标执行环境**（cron/terminal/execute_code）中分别测试，不能跨环境假设。

## 2026-07-11 审计二期 · 看门狗/可观测性/XAU同步/报告审美

### 看门狗运行时必须写结构化日志与状态文件（P1→可观测性）
修复 `btc_watchdog.py` 后若每次健康 tick 都静默 exit 0，`data/watchdog.log` 与 `data/watchdog_state.json` 会停留在崩溃前旧内容，审计无法区分「没跑」与「跑了且健康」。修复铁律：
- 每次 tick 追加一行到 `data/watchdog.log`：`[2026年07月11日20：10] tick age=1.8 instances=1 pids=[18348]`。
- 每次 tick 覆写 `data/watchdog_state.json`：schema=`btc_watchdog_state_v2`，含 `updated`、`status`（healthy/restarted/restart_failed）、当前 `daemon_pid`、detail（心跳年龄、发现实例数、采取措施）。
- 心跳新鲜时也要更新状态（`status: healthy, action: noop`），不能只退出。
- 状态文件需能被 `json.load` 直接读取，不要写成裸字符串或旧 schema。

### 守护进程实例计数必须过滤审计命令自身（P0→虚警）
用 `psutil.process_iter()` 统计 `btc_daemon.py` 实例时，当前执行的 `python -c "import psutil..."` 子进程以及 bash `-c '...import psutil...'` 包装进程会被误判为守护进程，导致实例数虚高。审计/看门狗脚本都必须过滤：
```python
cmd = ' '.join(p.info['cmdline'] or [])
if str(DAEMON_PATH) in cmd and 'bash' not in cmd and '-c import psutil' not in cmd:
    real_pids.append(p.info['pid'])
```
同样，`'-c import psutil'` 这种硬编码探测串要改成更鲁棒的判断，例如当前脚本自身的 `sys.executable` 路径或命令字符串匹配。

### resume 看门狗后必须验证多个触发周期（P0→复发验证）
修复/重写看门狗并 `hermes cron resume <id>` 后，至少要等 2 个触发周期（BTC守护看门狗每5分，则等10分）再确认实例数。判定标准：
1. `hermes cron list` 显示 `Last run` 已更新、`Next run` 正确。
2. `psutil` 过滤后真实守护进程数 = 1。
3. 心跳文件 `ts` 在 30 秒内。
4. `watchdog_state.json` 的 `status` = healthy，`daemon_pid` 与真实 PID 一致。
单周期通过可能是巧合，两个周期通过才说明互斥逻辑稳定。

### XAU TV同步 cron 加固模式（P1→偶发CDP抖动）
`xau_tv_sync.py` cron 偶发 TV CDP 断开导致 `xau_tv_state.json` 写 stale。加固：
1. `_run()` 外套 `_run_with_retry(max_attempts=3)`，每次失败 sleep 5 秒再试。
2. 旧数据保留阈值从 15 分钟放宽到 30 分钟（XAU 15 分钟同步一次，一次失败不应立刻降级）。
3. 旧文件可用时 exit 0 并打印保留信息，不让 cron 报 `error: Script exited with code 1`。
4. 多源快照刷新 `_refresh_source_snapshot_if_stale` 同步放宽到 30 分钟，与 TV 降级阈值对齐。
验证：手动跑成功后，等下一个 cron 触发，检查 `xau_tv_state.json` 不是 `{"stale":true}`。

### 报告审美优化信号（2026-07-11 用户纠正）
用户反馈「发到电报的报告审美好差」。审计报告优化方向：
- 顶部放一张大状态卡（总体健康 / 核心结论），不要一上来就是 7 列表格。
- 表格控制在 4-5 列，列宽易读；用 emoji 状态列代替纯文字。
- 修复前后对比、运行态、数据新鲜度、交易决策分块，每块一个小标题+短表格。
- 总体结论放在最前，数据支撑在后。
- 推 TG 仍必须走 `telegram_reliable.push_tg_rich`（RichMarkdown 真表格）。
- 截图引用放在报告首行或对应交易决策块上方。

### 代理感知的 public fetcher（P0→网络层）
`scripts/binance_public.py` 的 `_opener()` 若强制 `urllib.request.ProxyHandler({})` direct 连接，而 Hermes 环境又要求 `HTTPS_PROXY=http://127.0.0.1:7897`，则 `fetch_spot` / `fetch_futures` 全部返回 None。修复：
```python
import os
proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')
opener = urllib.request.build_opener() if proxy else urllib.request.build_opener(urllib.request.ProxyHandler({}))
```
审计验证：先 `curl -x $HTTPS_PROXY https://api.binance.com/api/v3/time` 通，再看 `fetch_spot('/api/v3/time')` 是否返回正常 JSON。

### 自动修复后的闭环动作顺序
当审计发现 P0/P1 并自动修复后，必须按顺序闭环：
1. 手动验证修复在目标环境生效（terminal / execute_code / cron）。
2. 等 2 个 cron 周期观察是否复发。
3. 刷新相关数据文件至新鲜。
4. 重新跑对应品种 `auto_card` 确认管线完成度。
5. 生成优化后的审计报告 v2 并推 TG:846。
6. `git add` + `git commit` + `git push`。
7. 最后再扫一次进程/心跳/数据新鲜度，确认没有引入新 P0。

## 模块清单（v9.6 · 2026-06-29审计更新 · canonical = scripts/）

```
scripts/                          # 一级目录（所有可执行入口）
├── auto_card.py                  # 主入口 (6类资产 + 智能路由)
├── pipeline_router.py            # ★ v9.0 智能路由 (按资产自动选步骤)
├── go_nogo_gate.py               # ★ v9.6 GO/NO-GO 下单七问硬闸门
├── render_v96.py                 # ★ v9.6 表格驾驶舱渲染器 (原 render_v8.py 重命名·2026-07-07·消除v8误导)
│
├── data_gatherer.py              # 多源采集 (Binance+Yahoo+CoinGecko+Jin10)
├── multi_source_collector.py     # CG Pro 全速
├── multi_model_engine.py         # 核心引擎 v2.1
├── model_checklist.py            # 模型核对清单
├── session_strategy.py           # Session 策略
├── triple_confirm.py             # 三层确认
├── macro_filter.py               # 宏观风险 (DXY/VIX/SPX/US10Y)
├── coingecko_collector.py        # CG 社区数据
├── polymarket_bridge.py          # Polymarket 事件概率
├── sentiment_search.py           # 情绪搜索
│
├── cot_collector.py              # ★ v9.0 CFTC COT 持仓
├── deribit_options.py            # ★ v9.0 Deribit 期权 OI
├── etf_flow_collector.py         # ★ v8.5 BTC ETF 日净流
├── dune_collector.py             # ★ v8.5 Dune 链上数据
├── orion_screener_radar.py       # ★ v9.0 Orion 全市场雷达 (5候选) · 采集完直接调 orion_radar_card.main() 渲染推TG(2026-07-07合并)
├── xau_tv_sync.py                # ★ XAU TV MCP现场五层同步 (2026-07-07·覆盖占位推算)
│
├── gold_monitor.py               # XAUUSD 监控
├── btc_monitor.py                # BTC 监控
├── btc_daemon.py                 # BTC 守护进程
├── btc_watchdog.py               # BTC 看门狗 (cron 每5分)
├── btc_zone_alert.py             # BTC 区间告警
├── btc_push_386.py               # BTC 推送至 TG:386
├── btc_card_gen.py               # BTC 分析卡生成
│
├── x_sentiment_collector.py      # X 情绪采集
├── liquidation_collector.py      # 清算压力
├── stablecoin_collector.py       # 稳定币供应
├── qlib_factors.py               # QLib 量化因子
├── trade_exec_bridge.py          # 交易执行桥接
├── data_freshness_watchdog.py    # 数据新鲜度看门狗
│
├── tv_data_bridge.py             # TV 数据桥
├── tv_levels_collector.py        # TV 水平位采集
├── tv_live_dump.py               # TV 实时转储
├── macro_poly_refresh.py         # 宏观+Poly 缓存
├── 黄金宏观.py                   # 黄金宏观背景
│
├── daily_review.py               # 每日复盘
├── daily_learn.py                # 每日学习
├── auto_review.py                # 自动复盘管线
│
├── freerouter.py                 # OpenRouter 模型同步
├── fallback_chain.py             # 回退链
├── alert_dedup.py                # 告警去重
├── engine_orchestrator.py        # 引擎编排
├── depth_wall.py                 # 深度墙
├── fvg_detector.py               # FVG 检测
├── cvd_analyzer.py               # CVD 分析
├── cvd_aggtrades.py              # CVD 聚合交易
├── correlation_matrix.py         # 相关性矩阵
├── dmi_decision.py               # DMI 决策
├── equity_tracker.py             # 权益跟踪
├── event_calendar.py             # 事件日历
├── event_ban_live.py             # 事件禁令
├── hard_stop.py                  # 硬止损
├── position_sizer.py             # 仓位计算器
├── prediction_tracker.py         # 预测跟踪
├── backtest_runner.py            # 回测运行器
├── bayesian_optimizer.py         # 贝叶斯优化
├── dryrun_progressive.py         # 渐进式模拟
├── five_model_matcher.py         # 五模型匹配
├── adversarial_analyst.py         # 对抗分析
│
├── repo-maintenance/             # 仓库维护
│   ├── daily_skill_mcp_update.py
│   ├── daily_system_audit.py
│   ├── daily_private_repo_backup.py
│   ├── daily_ops_bundle.py        # ★ 运维聚合 (2026-07-07·合并技能更新/审计/备份/模型同步4→1)
│   ├── daily_hermes_official_update.py
│   ├── patch_cron_utf8.py
│   ├── reset_remote.py
│   ├── reset_repo.py
│   └── skill_integrity_guard.py
│
└── monitor/                      # 守护进程
    ├── btc_watchdog.py
    ├── market_watchdog.py        # 行情守望看门狗 (2026-07-07 新建·每时:03 cron·心跳>300s拉起+TG:846)
    └── tv_levels_collector.py
```

### 模块清单审计备忘

- **canonical 目录为 `scripts/`**，`hermes/scripts/` 是旧版残留，23 个脚本与 `scripts/` 版本已发散。
- **`scripts/` vs `scripts/monitor/`** — `btc_watchdog.py`、`market_watchdog.py`、`tv_levels_collector.py` 在 `monitor/` 子目录；`hermes/scripts/` 下也有这两个文件的旧版本，被 cron 引用的 canonical 路径是 `monitor/xxx.py`。
- **行情守望看门狗已实体化（2026-07-07）** — `scripts/monitor/market_watchdog.py` 检测 `data/monitor_heartbeat.json`：status≠running 或 time>300s → 杀旧进程(start/B python 行情守望.py) + 重启 + 推 TG:846 三表告警。cron `行情守望看门狗`（job 020e260f5ac0，每时 :03，错峰 BTC守护看门狗 :00）。审计时确认该 cron 存在且静默（心跳 alive 时无 stdout）。
- **存活率检查**：`ls scripts/*.py | wc -l` + `ls scripts/monitor/*.py` + `ls scripts/repo-maintenance/*.py` = 实际可执行脚本数。对比 cron 引用的脚本列表。

## Confluence 评分体系 (v3.2)
- 14维信号加权求和 + CVD趋势线破(LEADING信号) → 5级评级 (A+/A/B/C/D)
- A+条件: 同方向≥2个A级 + 权重倾斜 >2:1
- 输出格式: 决策驾驶舱 (方向+评级+置信%+关键位)
- 自愈: btc_latest缺price→直连Binance API兜底
- 噪音控制: 15min同模型冷却 + 波动率门槛
- **6层架构蓝图**: `references/6-tier-architecture-blueprint.md`
- **2026 社区最佳实践对标**: `references/community-best-practices-2026.md`（盘前闸门/执行评分/仓位公式/6体制/相关性/Kill Zone/亏损冷却）
- **Windows cron 脚本维护模式**: `references/windows-cron-maintenance-patterns.md`（UTF-8 编码修复/uv trampoline 修复/ThreadPoolExecutor 并行化/备份 git add-A/GitHub Push Protection 密钥清理）
- **系统优化模式（cron合并/XAU TV现场/skill安装/工具限制）**: `references/2026-07-07-system-optimization-patterns.md`
- **Cron 夜间静默门 + 盘中降频模式（2026-07-08 落地）**: `references/cron-night-silent-and-downschedule.md` — 在 `push_tg_rich` 入口加 23:00–08:00 时段 gate 全局静默、hermes cron edit 降频 8-22 窗口、两个 cron error 任务修复 recipe。
- **Telegram 推送投递调试（token配置/forum thread/TOPIC_CLOSED/Markdown表格400）**: `references/telegram-delivery-debugging.md`
- **TV Desktop 启动 env 污染根因（ELECTRON_RUN_AS_NODE 导致 bad option / 拒绝访问）**: `references/tv-desktop-launch-env-pollution.md`
- **多源数据降级 + XAU Data Window + TV MCP多Monaco/中文界面/浏览器上下文编译**: `references/multisource-tv-mcp-resilience.md`
- **2026-09-02 全面审计定稿 8.5/10（5 个 P0 全清零 + 4 项留观边界 + 双 Python 解释器隐性炸弹 + P0-3 真实影响链路）**: `references/2026-09-02-comprehensive-audit-closure.md`
- **分析档位 v2 定稿（quick/inherit/full/monitor 4 档 + pipeline_router 路由 + source_snapshot 写盘不对称性 + XAU/crypto 前置差异）**: `references/2026-09-02-analysis-tiers-v2.md`
