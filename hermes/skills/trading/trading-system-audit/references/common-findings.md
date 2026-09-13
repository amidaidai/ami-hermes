# Common Audit Findings

Catalog of previously observed issues. Update after each audit session.

## P0 Recurring

### 行情守望进程静默死亡
- **Symptom**: heartbeat file shows "running" but PID not in process list
- **Root cause**: Python crash unhandled, watchdog stale heartbeat check
- **Check**: `ps aux | grep <PID from heartbeat>` — if empty, process dead
- **Fix**: restart after fixing crash cause; improve watchdog pid_alive() for Windows

### model_dir_text 变量未初始化（v6.8+ 已修复 ✅）
- **Symptom**: monitor.log floods with `cannot access local variable 'model_dir_text'`
- **Root cause**: variable referenced before assignment in model direction display within `process_block()`
- **Impact**: 30s polling loop crashes, watchdog restarts, repeat
- **Fix**: initialize `model_dir_text = ""` at function start (L847 of `行情守望.py`)
- **Verification**: After code fix, **必须重启进程**才能生效。检查 monitor.log 13:00后无新错误即确认修复

### pid_alive Windows MSYS 不可靠（v6.3.4 已修复）
- **Symptom**: PID in heartbeat but not in process list; watchdog doesn't detect death
- **Root cause**: `powershell.exe Get-Process` in MSYS/git-bash has path/encoding issues, returns empty → evaluated as True
- **Check**: `tasklist /FI "PID eq <pid>" /NH` — look for PID in output AND "No tasks" not in output
- **Fix**: both `watchdog.py` and `行情守望.py` — replace powershell with `tasklist /FI`
- **Lesson**: MSYS calling powershell is unreliable; `tasklist` is Windows native and stable

### Binance recvWindow Timestamp Error
- **Symptom**: `HTTP 400: Timestamp for this request is outside of the recvWindow`
- **Root cause**: server clock drift >1000ms from Binance servers
- **Check**: `mcp_binance_get_account_summary()` — spot returns error. Note: simple price endpoints (`get_price`) have looser tolerance and may still work even when account endpoints fail. Don't assume API is healthy just because price queries succeed.
- **Fix**: sync NTP: `w32tm /resync` (Windows, must run from **cmd/PowerShell**, NOT git-bash — encoding garbles output). Linux: `ntpd -gq`.
- **Verification**: `powershell.exe -NoProfile -Command "w32tm /query /status"` → check '上次成功同步时间' is recent (<1 min ideally)
- **Pitfall**: git-bash/MSYS garbles `w32tm` output due to GBK encoding. Always run NTP commands via PowerShell or cmd.

### Hermes Cron vs jobs.json Drift
- **Symptom**: `hermes cron list` shows fewer jobs than `hermes/cron/jobs.json`
- **Root cause**: jobs.json is a config file; jobs must be registered via `hermes cron add`
- **Impact**: scheduled tasks silently never run
- **Fix**: re-register missing jobs with `hermes cron add` or verify registration

## P1 Recurring

### 全部交易计划 B等待 / 零执行
- **Symptom**: 40+ trade plans in `trade_plans.jsonl` all `state: "B等待"`, zero entries executed
- **⚠ NOT ALWAYS A BUG** — distinguish two plan types:
  1. **分析型计划** (model: "智能结构更新", `entry: null, stop: null, targets: []`) — 这些是监控位刷新计划，目的是更新 `monitor_levels.json`，不是交易计划。状态"B等待"是设计如此。
  2. **可执行计划** (model: "EMA趋势+VWAP拒绝"等, 有实际 entry/stop/targets) — 状态"待触发"表示计划已就绪但市场未达入场条件
- **关键检查**: 不要只看 `trade_plans.jsonl`，也要读 `monitor_levels.json`。可执行计划可能只存在于 monitor_levels.json 中（由分析卡流程直接写入）。
- **Root cause 候选**:
  - 如果 `monitor_levels.json` 中有可执行计划但未触发 → 市场未达条件（正常）
  - 如果 `monitor_levels.json` 中也没有可执行计划 → 分析卡管道未运行，需调用 `auto_card.py`
  - 如果 `trade_plans.jsonl` 大量 B等待但全是智能结构更新 → 正常行为
- **Impact**: 需区分"系统健康但市场不配合" vs "系统真的零计划"

### 推送降噪过度（v6.9 位信阈值已调优）
- **Symptom**: `push_sent: false` on most events; push_reasons: "未达到强确认", "降噪"
- **Root cause**: threshold too high — warning events with 位信<70% or medium-priority breaches get suppressed
- **Impact**: Telegram channel silent despite active market events
- **Fix pattern**: add third condition in `push_allowed` for medium-priority breaches with B+ data:
  ```python
  if breached_like and score >= 68 and data_q in ("A", "B"):
      return True
  ```
- **Verification**: check `trade_events.jsonl` push_sent distribution by tier. warning tier >50% blocked = threshold still too aggressive
- **REMEMBER**: after patching push_allowed, **must restart monitor** (watchdog auto-restarts on stale heartbeat >90s, or manual taskkill)

### CVD 持续 C 级
- **Symptom**: all trade_events show `cvd_quality: "C级"`
- **Root cause**: CVD data from TradingView indicator not reliably feeding into event system
- **Impact**: automatic half-position, reduced confidence, triggers noise suppression cascade

### Discord 未集成到 push()（v6.3.4 已修复 ✅）
- **Symptom**: Discord bot configured (server/channel known) but monitoring push() only sends Telegram
- **Fix**: `行情守望.py` push() now dual-sends: Telegram (3 retries) + Discord (1 attempt, non-blocking)
- **Discord target**: `discord:1474072925199143167` (安禾 bot)

## P2 Recurring

### XAUUSD 金十 vs Yahoo 价差（v6.9 已改善 → gold-api.com）
- **Symptom**: persistent 0.3-0.55% spread between 金十 Quote and Yahoo GC=F
- **Root cause**: different price sources (spot vs futures proxy), not a bug but quality degradation
- **Impact**: XAUUSD price quality was B(78%) without OANDA
- **Fix**: integrate gold-api.com (free, no auth, `https://api.gold-api.com/price/XAU`) as third source → 金十+gold-api+Yahoo → A(88-92%). Add `gold_api_price()` to `trading_system.py`, probe in `price_consensus()`, new quality tier. Root cause: OANDA Practice API requires real account; gold-api.com is a zero-friction alternative.

### XAUUSD Binance 400 无效查询循环浪费（2026-06-19 发现）
- **Symptom**: `monitor.log` 反复出现 `价格错误 XAUUSD: 400 Client Error: Bad Request for url: https://api.binance.com/api/v3/ticker/price?symbol=XAUUSD`
- **Root cause**: XAUUSD 是外汇对，不在 Binance 现货/合约交易对列表中。监控主循环每轮仍尝试 Binance `ticker/price` 端点查询 XAUUSD
- **Impact**: 每次无效 HTTP 请求浪费 ~200ms；日志噪音；触发 "价格源不可用→使用分析价兜底" 降级路径
- **Fix**: 在数据源路由器中标记 XAUUSD 为"非Binance品种"，跳过 Binance 查询，直走 gold-api.com + 金十 + Yahoo 管线
- **Lesson**: 多品种监控的数据源路由必须有 "品种×数据源" 兼容矩阵，不能所有品种走同一查询路径

### Dashboard 8766 "假活"模式（2026-06-19 发现）
- **Symptom**: `netstat -ano` 显示 8766 端口 LISTENING（PID 7672），但 `curl http://127.0.0.1:8766` 返回 "Remote end closed connection without response"
- **Root cause**: 进程存活但 HTTP 服务未正确初始化或崩溃后未清理端口绑定
- **Diagnosis**: 端口监听 ≠ 服务可用。必须做 HTTP 探测（curl/urllib），不能只查 netstat
- **Fix**: `taskkill //F //PID 7672` 后重启 dashboard 服务
- **Lesson**: 端口健康检查必须三层验证：netstat 监听 → HTTP 响应 → 业务数据正确

### CoinGecko Intermittent Null
- **Symptom**: BTC data points show CoinGecko returning null, degrading "三源一致" to "两源"
- **Impact**: minor confidence reduction

### watchdog.log 无日期（v6.3.4 已修复 ✅）
- **Symptom**: log entries show `[HH:MM:SS]` only, no date
- **Fix**: changed to `[YYYY-MM-DD HH:MM:SS]` format in watchdog.py

### GitHub 融合模块 · 花架子陷阱（v6.9 新增）

- **Symptom**: 模块 `import` 成功、demo 数据跑通、逻辑正确，但宣称"已接入"
- **Root cause**: 五个验证级别的巨大鸿沟：代码存在 ≠ 逻辑正确 ≠ 实弹跑通 ≠ 已接入管线 ≠ 产生信号
- **Check**: 五级验证矩阵（代码→逻辑→实弹→管线→信号）。L4 "已接入管线" 需要修改调用方代码（`行情守望.py`/`auto_card.py`/`智能更新结构.py`）。
- **Fix**: 修改调用方代码导入+调用新模块，`py_compile` 验证调用方语法，全管线串联测试。
- **2026-06-18 案例**: 8个融合模块中 4 个处于 L1-L3 但 L4 失败 → 全未接入现有管线。

### SMC smart-money-concept 库 · pandas 2.x 不兼容

- **Symptom**: `assignment destination is read-only` 异常
- **Root cause**: pandas 2.x 返回 `writeable=False` 的 DataFrame，SMC 库的 monkey-patch 赋值失败
- **Impact**: 5根K线时0输出，200根时仍崩溃。库本身 1348 行，yfinance 依赖。
- **Fix**: 不修复 → 用 `structure_detector.py` 纯 Python 摆动点检测替代。
- **Lesson**: GitHub 库有星 ≠ 可运行。先跑最小验证（5行代码 + 真数据）再写适配层。

### GitHub 搜索策略 · 精确查询陷阱

- **Symptom**: `browser_navigate(github.com/search?q=精确中文词)` 返回 0 结果
- **Root cause**: GitHub 搜索框对中文+组合精确词匹配极严
- **Fix**: 用 `web_extract(github.com/topics/<topic>?l=python)` 按标签浏览；或直查已知仓库 README
- **有效路径**: `github.com/topics/market-structure?l=python` → 20 repos; `github.com/topics/risk-management?l=python+trading` → 20 repos
- **Symptom**: "真实复盘样本不足：1/20"
- **Root cause**: zero executed trades means zero reviews
- **Impact**: cannot evaluate model effectiveness

## P0 New (2026-06-18 Audit)

### GitHub融合·未接入管线
- **Symptom**: 新模块 import 成功、demo 跑通，但 `行情守望.py`/`auto_card.py` 仍用旧逻辑
- **Root cause**: 融合只做到"代码存在+逻辑正确"，未改管线代码调用新模块
- **Impact**: 评分引擎/风险宪法/五模型匹配 逻辑正确但零收益
- **Fix**: 逐项改管线入口：`scoring_engine.score_setup()` → auto_card · `risk_constitution.check_constitution()` → 行情守望 · `five_model_matcher.generate_all_setups()` → 智能更新结构

### SMC库 Pandas只读视图bug
- **Symptom**: `assignment destination is read-only` when injecting Binance DF
- **Root cause**: pandas returns read-only views in certain index operations
- **Fix**: `df = df.copy()` before feeding to SmartMoneyConcepts
- **Data requirement**: ≥50 bars for structure detection (5-bar test always 0 results)

### Firecrawl 搜索欠费（**已恢复，2026-09-13 复测**）

> ⚠ 本节记录的是 2026-06 的状态。**2026-09-13 复测 Firecrawl `scrape` 返回 `success:true`，
> 已恢复可用**。下方「修复方案（用 Brave/Exa 替代）」仅在它再次失效时才需要。

- **Symptom**: `web_search` returns "Payment Required: Insufficient credits"
- **Root cause**: Firecrawl API credits exhausted (新key也欠费)
- **Impact**: web_search 内置 Firecrawl 后端不可用
- **Fix**: 使用 `hermes/secrets/search_apis.json` 中的 Brave/Exa API 替代
- **2026-06-18 更新**: 全面测试7个搜索API，结果：
  - ✅ Brave Search (2000/月) — 主力，搜Reddit+技术文章
  - ✅ Exa Search (1000/月) — 语义搜索，深度文章
  - ✗ Tavily 401 · Metaso SSL · Felo 405 · Firecrawl 402 · AnySearch 待测
  - 爬取工具：crawl4ai (JS渲染) + Scrapling (反爬)
  - Reddit需cookie · Google需clash代理
  - 详见 `references/audit-pitfalls.md` 联网工具表

### 看门狗日志停滞（v6.9 重新出现）
- **Symptom**: `watchdog.log` 最后条目为昨日 22:58，无今日记录
- **Check**: `tail -5 data/watchdog.log` → 对比当前时间
- **Root cause**: 看门狗进程可能静默死亡或日志写入路径异常
- **Impact**: 失去对行情守望的自动守护功能
- **Fix**: 验证 watchdog 进程存活（`tasklist | grep watchdog`），若不存活需重启

### 行情守望串行请求导致心跳超时·watchdog反复重启（2026-06-18 发现）
  `心跳停滞 95s · PID=xxx · 存活=True · 状态=running`
  `进程存活但心跳超时 · 可能卡死 · 强制重启`
  随后 `重启速率限制：3次/小时已达上限` 阻止进一步重启
- **Root cause**: `scripts/行情守望.py` L1032 `while True` 主循环内串行执行多个网络请求：
  - Binance API `requests.get(timeout=10)` × 3
  - subprocess `timeout=15` × 2
  - tasklist `timeout=5` × 1
  单轮累积可达 60-90s，接近/超过 watchdog 的 STALE_SECONDS=90 阈值
  watchdog 误判为"卡死"→ taskkill → 重启 → 新进程也可能再次卡住 → 速率限制触发
- **诊断**: 看 watchdog.log 中"心跳停滞 Ns"的 N 值
  - N=90-200 且 存活=True → 串行阻塞（本条）
  - N>200 且 存活=False → 进程崩溃（见上方"行情守望进程静默死亡"）
- **Fix**: (1) 心跳写入移到循环顶部，每轮开始立即 write_heartbeat("running")
  (2) 网络请求并行化（concurrent.futures.ThreadPoolExecutor 或 asyncio）
  (3) 或将大循环拆分为子轮次，每子轮次后更新心跳
- **Impact**: 监控盲区、推送中断、计划失效

### Memory 测试计数与实际不符（2026-06-18 发现）
- **Symptom**: memory 记录"31 test"或"24项pytest"，但 `find scripts/ tests/ -name "test_*.py"` 返回 0 结果
- **Root cause**: sandbox/ 目录下的 test 文件（feedgrab/feishu-streaming-card等）被误计入交易系统
- **Check**: 排除 sandbox/ 后查找 test 文件；检查 pytest.ini/pyproject.toml 是否存在
- **Fix**: 更新 memory 为实际计数；建立 `tests/test_core.py` 覆盖核心逻辑
- **Lesson**: memory 中的数字声明必须定期用实际命令验证，不能盲信
