---
name: tangxi-analysis-audit-checklist
description: 棠溪分析系统审计清单 v1.0 — 分析策略流程、分析档位、API拉取能力、记忆读取、TV MCP集成、守护运行态五维全景扫描与优化建议。触发词：全面盘点、分析策略流程、分析档位、API拉取、记忆读取、全面扫描。
category: trading
---

# 棠溪分析系统全景扫描清单

> 触发词（任一即执行）：全面盘点、分析策略流程、分析档位、API拉取、记忆读取、全面扫描  
> 触发词（完整级）：审计、全面检查、全方位盘点、全方位优化  
> 包含：「分析策略流程」+「分析档位」+「API拉取链路」+「记忆读取机制」+「五维问题扫描」+「优化建议」

---

## 第一维：分析策略流程

### 1.1 策略管线路由（静态扫描）

读取以下文件，确认路由逻辑是否与用户配置一致：

| 检查项 | 文件 | 期望 |
|--------|------|------|
| pipeline_router.py 存在 | `D:/Hermes agent/scripts/pipeline_router.py` | 存在且含 `route_pipeline` |
| 路由步骤数 | `pipeline_router.py` 的 `route_pipeline()` 实测 | 以代码返回为唯一真相；当前加密 Full 实测15步、黄金8步、外汇7步 |
| 档位识别实码 | `resolve_analysis_mode` 函数 | 「分析/全面/深度/完整卡」=full / 「看下/看一眼/快速过一遍」=quick / 「现在呢/继续/接着看/更新」=standard（无上下文也不改档） |
| **档位代码化 hook（2026-08-31）** | `auto_card.py --mode-auto --message "<用户原话>"` | **对话层必走此入口**：档位由 `resolve_analysis_mode` 决定，模型不再自行判断；实测 分析/深度→full · 看下→quick · 现在呢→inherit(有上下文) · 裸品种→quick |
| 完整管线步骤 | `route_pipeline(mode="full")` | 步骤数量必须动态读取；禁止在技能或卡片中硬编码旧步数 |

```python
# 实测路由
import sys
sys.path.insert(0, "D:/Hermes agent/scripts")
from pipeline_router import route_pipeline
for sym in ["BTCUSDT", "XAUUSD", "EURUSD", "AAPL"]:
    steps = route_pipeline(sym, "full")
    print(f"{sym}: {len(steps)}步 {steps}")
```

### 1.2 分析档位与输出格式（动态验证）

| 档位 | 触发词 | 输出特征 |
|:--:|---------|---------|
| quick 轻量 | 「看下」「看一眼」 | 行动格+现价+截图+衍生品 |
| standard 标准 | 「现在呢」「继续」「接着看」「更新」 | quick + 相邻周期结论行；上下文可继承但无上下文也保持 standard，不升级 full |
| full 完整 | 「分析」「深度」「全面」 | 完整10步+手机三表速读 |

**必检项**：
- 含「分析」=完整模式硬开关，不因刚出过卡而降级
- CLI 使用 `--mode-auto --message "<用户原话>"` 时，品种解析必须读取 `--message`；不能把带自然语言的消息当作无位置参数而静默回退 BTC。跨资产入口须用 BTC/XAU 代表性消息做端到端冒烟验证。
- 表格前禁止 standalone 标题行（Telegram RichMarkdown 真表格降级根因）
- MEDIA 截图必须首行，每轮输出（含「现在呢」）必须带新截图
- 完整性备注：逐项读取 `route_pipeline()` 返回的实际步骤，标 ✅/⚠️/❌；缺项写原因，禁止沿用历史“10步”数字

### 1.3 输出格式铁律

| 场景 | 格式 |
|------|------|
| 完整卡 | MEDIA截图首行 → 一句话裁决 → ①方向速览 → ②关键位矩阵 → ③一句触发/裁决 |
| 轻量卡 | 行动格 + quote现价 + 一张截图 + [加密]衍生品 |
| 追踪更新 | <0.2%无变化→只报一句；0.2-0.5%→浓缩3表+新截图；≥0.5%→全量刷新 |

---

## 第二维：API拉取能力

### 2.1 Binance 数据链路

```bash
# 现货 API
curl -s "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=5"

# 合约 API
curl -s "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=BTCUSDT"

# OI 多空
curl -s "https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol=BTCUSDT&period=1h&limit=1"
```

| 端点 | 用途 | 需认证 |
|------|------|:---:|
| `/api/v3/*` | 现货行情 | 否 |
| `/fapi/v1/*` | 合约行情 | 否 |
| `/futures/data/*` | 机构级数据（HMAC签名） | 是 |

**降级路径**：
- fapi Cloudflare 403 → 改用 `api.binance.com` 现货
- get_price 对期货独占币失败 → 改用 TV OHLCV close
- XAUUSDT 现货不存在 → 走 `/fapi/v1/klines` U本位期货

### 2.2 其他免费 API

| 服务 | 端点 | 备注 |
|------|------|------|
| CoinGecko | `api.coingecko.com/api/v3/` | 免费，无需Key |
| 恐慌贪婪 | `api.alternative.me/fng/` | 免费无认证 |
| 金十快讯 | `api.jin10.com/quote/XAUUSD` | 需凭据或MCP |
| Yahoo Finance | `query1.finance.yahoo.com/v8/finance/chart/` | GC=F/MGC=F 黄金 |

### 2.3 X 情绪获取

```
x_search("$BTC crypto sentiment today bullish bearish")
  → 模型: grok-4.20-non-reasoning, 90s超时, 2次重试
降级: web_search + 标注「web源·非X实时」
```

**检查**：`tool_search('x_search')` 能搜到 → 在当前 platform toolsets 中 → 测试调用一次

### 2.4 TV MCP 实时数据

```bash
# 端口探测
python -c "import socket; s=socket.socket(); s.settimeout(2); r=s.connect_ex(('127.0.0.1',9222)); print('CDP开放' if r==0 else f'CDP关闭:{r}'); s.close()"

# 进程探测
tasklist //FI "IMAGENAME eq TradingView.exe" 2>/dev/null | grep TradingView && echo "TV运行中" || echo "TV未运行"
```

| 检查项 | 期望 | 不通时的降级 |
|--------|------|-------------|
| TV Desktop 进程 | 运行中 | REST Binance API |
| CDP 9222 端口 | 开放 | REST Binance API |
| 主指标行动格 `study_filter="SVP"` | 有数据 | 降B级 |
| 副指标行动格 `study_filter="Volume Aggregated"` | 有数据（加密）| 降B级 |

---

## 第三维：记忆读取机制

### 3.1 长期记忆（Memory）

| 文件 | 用途 | 写入时机 |
|------|------|---------|
| `memory` 工具 | 持久跨会话偏好 | 用户明确偏好、格式铁律、稳定规则 |
| `user profile` | 用户身份/偏好 | 会话开始时自动注入 |
| `SOUL.md` | AI persona | 手动编辑 |

**检查命令**：
```bash
# Memory 内容
grep -c "." ~/AppData/Local/hermes/memories/*.md

# SOUL.md 是否定制
grep -c "安禾\|棠溪\|交易" ~/AppData/Local/hermes/SOUL.md
```

### 3.2 短期状态（Data文件）

| 文件 | 内容 | 新鲜度阈值 |
|------|------|-----------|
| `data/source_snapshot_BTCUSDT.json` | BTC多源快照 | <1h |
| `data/source_snapshot_XAUUSD.json` | XAU多源快照 | <1h |
| `data/btc_ref_levels.json` | SVP参考位 | <24h |
| `data/keylevels_config.json` | 关键位配置 | <24h |
| `data/monitor_levels.json` | 监控位 | <24h |
| `data/tv_dmi_cache.json` | TV DMI缓存 | <2h |
| `data/tv_live.json` | TV实时缓存 | <2h |

### 3.3 会话历史（Session）

```python
session_search(query="BTC XAU 分析", limit=3)
  → 找回同品种历史分析上下文
```

---

## 第四维：TV MCP集成

### 4.1 MCP工具可用性

```bash
# 测试 MCP 连接
mcp_tradingview_tv_health_check()
  → 期望: cdp_connected=true, api_available=true

# 失败时恢复（两级）
# ① MCP 调用级：直调 mcp__tradingview__* 报 "does not exist" ≠ 工具下线
#    → tool_search 确认目录存在 → tool_describe 重载 schema → 走 tool_call 通道
# ② 进程级：tv_launch(kill_existing=true, port=9222) 等8-10s → tv_health_check() 重试
```

### 4.2 数据读取铁律

| 数据 | 工具 | study_filter |
|------|------|-------------|
| 主指标行动格 | `data_get_pine_tables` | `SVP+ICT+VWAP+CVD` |
| 副指标行动格 | `data_get_pine_tables` | `Volume Aggregated` |
| VWAP/EMA/POC/VAH/VAL | `data_get_study_values` | — |
| 水平线 | `data_get_pine_lines` | — |
| 标签 | `data_get_pine_labels` | — |
| FVG缺口 | `data_get_pine_boxes` | `SVP` |
| K线 | `data_get_ohlcv` | — |

**关键陷阱**：
- `study_filter` 必须明确指定，否则只返回副指标（Volume Aggregated）
- 切品种后必须 `chart_get_state` 确认 symbol，避免跨会话数据污染
- **图表会被并发 cron 切走（2026-08-30 实测）**：XAU TV现场同步等任务会切共享标签页到 OANDA:XAUUSD/5m——读行动格/截图前必须 `chart_get_state` 核对 symbol+resolution（BTC=BINANCE:BTCUSDT.P+15m）；发现被切走先 `chart_set_symbol` + `chart_set_timeframe` 切回主执行周期，`chart_ready=true` 后再读/截，否则会截到错品种（违反复核铁律，旧截图冒充更新同罪）
- `study_values` 大数被缩写(4.6K/1.1M) → 用 `pine_lines`/`pine_labels` 读精确价

### 4.3 完整图表证据审计（价格栏 + ICT + 视觉复核）

完整图表不是截图附件，而是独立证据层。每次BTC分析必须同时核对：

1. **价格栏**：现价、当前K线OHLC、日高/日低、价格轴；并定位其相对 VAH/VAL/POC/nPOC/VWAP 的层级。
2. **ICT主图**：FVG上/下沿与CE、OB/Breaker区间及质量、BOS/MSS/CHoCH方向与年龄、前日/前周及摆动高低点流动性、扫位/收回状态、溢价/折价。
3. **订单流窗格**：CVD、成交量、持仓/OI、主动买卖与数据覆盖；区分新仓推动和回补/平仓。
4. **视觉复核**：截图必须含价格轴、主图、行动格和底部窗格；视觉结论必须能与结构化字段、SVP行动格、Binance读数对应。

**证据状态必须显式化**：`chart_verified`（对象和字段均可对应）、`chart_partial`（部分对象缺失）、`chart_visual_only`（仅能看截图）、`chart_identity_mismatch`（品种/周期错）、`chart_stale`（过期）。`chart_partial`/`chart_visual_only`不得给GO-A；身份错或过期必须fail-closed且不得覆盖最后有效缓存。

**关键验证顺序**：`tv_health_check → chart_get_state → 必要时切回BTC/15m → 等待指标重算 → 读tables/values/lines/boxes/labels/OHLCV → 截图 → 再次核对symbol+resolution`。若截图视觉上有ICT对象但`lines/boxes/labels/tables`返回空，不能宣称ICT已被机器读取，应标记`chart_visual_only`或`chart_partial`，并只给人工观察路径。

**周期边界**：BTC的15m是主执行层，5m只做触发；D/4h/1h是背景。当前图表若为5m，不得把5m视觉结构直接当成15m主裁决。

---

## 第五维：守护运行态

### 5.1 守护进程心跳（P0 — 必须 <5min 且 status=running）

```bash
# 并行检查
cat data/monitor_heartbeat.json      # 行情守望
cat data/.btc_daemon_heartbeat.json   # BTC守护
cat data/.keylevel_guard_heartbeat.json  # 关键位守护（2026-08-29在线）

# Python 一键脚本（存为 scripts/audit_preflight.py）
python scripts/audit_preflight.py
```

| 守护进程 | 心跳文件 | 状态 | 最后运行 |
|---------|---------|:---:|---------|
| 行情守望 | `monitor_heartbeat.json` | ? | ? |
| BTC守护 | `.btc_daemon_heartbeat.json` | ? | ? |
| 关键位守护 | `.keylevel_guard_heartbeat.json` | ? | ? |

**心跳新鲜 ≠ 监控有效（2026-08-31 实测 P0）**：keylevel_guard 心跳 `status=running` 且 <1min 新鲜，但 `keylevels_config.json` 所有 level 的 `valid_until` 全部过期 → `level_is_active()` 返回 False → 守卫进程活着但**一个位都没在监控**，空转 24h+。保险丝：config 37h 未更新 + 全位 valid_until 早于当前时间。审计必查：
```bash
python -c "import json; [print(l['name'], l['price'], l.get('valid_until')) for l in json.load(open('data/keylevels_config.json'))['symbols']['BTCUSDT']['levels']]"
# 全部早于当前时间 = P0（守卫空转），不是心跳 bonus
```
修复：`python scripts/keylevels_collect.py` 重采集（若报「D 采集失败: timeframe mismatch: expected D, got 1D」→ 校验集需含 `{"D": "1D"}` 别名，2026-08-31 已修）→ 按候选重写 keylevels_config.json（valid_until=当日 23:59:59）。守卫每 0.5s 热读 config，无需重启。

### 5.2 Cron任务状态

```bash
# 直接解析 jobs.json（实测：`cron list --json` 输出非纯JSON，json.load 必失败）
python -c "
import json
jobs=json.load(open(r'C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json',encoding='utf-8')).get('jobs',[])
for j in jobs:
    en='active' if j.get('enabled') else 'paused'
    print(f\"[{en}] {j.get('name','')[:22]:24s} model={j.get('model')} provider={j.get('provider')} script={str(j.get('script'))[:28]}\")
"
# 人类可读视图：hermes cron list
```

**模型路由核验**：jobs.json 每项含 `model`/`provider` 字段——确认关键位到价分析推送仍钉在 `deepseek-v4-flash-vision-exp`/`deepseek`（切换对话模型不影响 cron 路由的铁律以此为准）。

**关键任务（当前 2026-08-31 实际 active 仅 4 个 — 8/29 binance-only 迁移后有意的精简）**：
- XAU TV现场同步（active）
- BTC关键位守护看门狗（active）
- BTC关键位到价分析推送（active，钉 deepseek-v4-flash-vision-exp）
- liq_listener_btcusdt（active 但 error，见下）
- 其余 21/25 暂停 = 迁移设计，**不是故障**（querylevels 替代 btc_ref_levels_sync、keylevel_guard 替代行情守望）；审计只核实暂停是否为有意迁移产物，勿当 P0 恢复

- **⚠️ 守护进程被误配成 cron（P1 · 2026-08-31 实测）**：`ws_liquidation_daemon.py`（while True websocket 常驻）被配成 cron `0 0 * * *` 每天跑一次 → 必然 `Script timed out after 3600s` 且完成数=1。铁律：**常驻 daemon 不该进 cron 每日调度**；确需 cron 触发则脚本必须支持 `--once`/单次模式，否则走守护+看门狗体系。审计时 `last_status=error + timed out` 先查脚本是否 while True 常驻。

- **⚠️ 审计因果错配三大类（2026-08-31 实测，必入审计方法论）**：本会话出现 3 类典型误判，每一类都会让审计报告失真。
  1. **grep 行号巧合命中非引用关系** — `grep -n "cvd_analyzer" scripts/auto_card.py` 在第 4806 行命中，但 sed 该行上下文是 `_mode = "quick"` 路由逻辑，非 import。`grep` 默认会把任意字符串匹配计入。铁律：grep 命中后必须 `sed -n 'N-5,N+5p'` 看上下文，**只有 `from X import` / `import X` 形态才算引用**。`auto_card.py` 实际不直接 import `cvd_analyzer`，引用只在 `scripts/orphan_integration.py:230,234`。
  2. **编造无源字段做证据** — 报告写 `text_push_status: failed_or_missing` 推导「所有关键位分析卡片推送失败」，但 `data/keylevel_triggers/` `data/keylevel_analysis/` `cron/output/` 三处全空，该字段无任何真实出处。铁律：报告中每个结论性字段必须能 `cat <path>` 或 `grep -rn` 找到原始行号；给不出路径 = 不能写进报告，按错信处理。
  3. **迁移设计边界误判 P1** — 报告把 8/29 迁移后的 21/25 cron paused 标 P1，把 `btc_ref_levels_sync.py` paused 标 P1。实际 `keylevel_guard` 已替代 `行情守望`，`querylevels` 已替代 `btc_ref_levels_sync`。铁律：审计 `enabled: false` 前先确认是否 8/29 binance-only 迁移设计产物——`keylevels_config.json` 在用 = `querylevels` 在用 = `btc_ref_levels_sync` 可不启用，**不是故障**。

  完整会话证据链（用户原报 vs 实测 vs 修订）见 `references/audit-cross-validation-2026-08-31.md`。

- **⚠️ 孤儿脚本 integration 模式是 P0 隐藏路径（2026-08-31 实测补漏）**：tangxi-system-audit 旧 Pitfall「幽灵模块引用」覆盖「文件不存在」一类，但**遗漏了「孤儿集成层 import 链」**：`orphan_integration.py` 集中 import 6 个孤儿脚本（meta_labeler/orderflow_absorption/cvd_analyzer/fvg_detector/order_block/correlation_matrix），主入口 `auto_card.py` 不直接 import 它们。审计步骤必须加：
  1. `grep -rn "from orphan_integration\|import orphan_integration" scripts/` 找孤儿集成层引用方
  2. 读 `orphan_integration.py` 第 10-50 行，列出全部孤儿脚本清单
  3. 对每个孤儿脚本 `ls scripts/<name>.py` + `ls scripts/_disabled_*/<name>.py` —— 仅在 `_disabled` 即真孤儿，恢复路径固定为 `cp scripts/_disabled_YYYYMMDD/<name>.py scripts/`
  4. 验证：`python -c "from cvd_analyzer import check_cvd_confluence"` 能 import 才算修复完成
  已知本次会话真孤儿：`scripts/cvd_analyzer.py`（仅 `scripts/_disabled_20260829/cvd_analyzer.py` 存在），其它 5 个在 `scripts/` 存在。

**⚠️ 脚本归档后 cron 引用悬空（P1 · 2026-08-31 实测）**：`tv_keepalive.py` 被 8/29 迁移移入 `scripts/_disabled_20260829/`，但 cron `TV Desktop保活` 仍引用 `scripts/tv_keepalive.py` → `Script not found`。审计 `Script not found` 错误时：先查 `scripts/_disabled_*/` 归档目录，确认脚本是被有意禁用（cron 应同步 pause）还是误删（需恢复）。

### 5.3 Python进程实例计数

```python
import psutil
for name in ["行情守望.py","btc_daemon.py","keylevel_guard.py","btc_watchdog.py","market_watchdog.py"]:
    pids = [p.info['pid'] for p in psutil.process_iter(['pid','cmdline'])
              if name in ' '.join(p.info['cmdline'] or []) 
              and 'bash' not in ' '.join(p.info['cmdline'] or [])]
    print(f"{name}: 实例数={len(pids)} PIDs={pids} {'✅' if len(pids)==1 else '❌多实例'}")
```

**⚠️ uv venv stub 双节点陷阱（2026-08-31 实测 P0 根因）**：Hermes venv 由 `uv venv` 创建，`venv/Scripts/python.exe` 是 redirector stub——用它启动脚本时会 spawn 真实 uv python 子进程跑同一脚本 → **同一逻辑实例有 2 个进程节点**（cmdline 完全相同、stub 父 + real 子）。看门狗 psutil 数到 2 → 永远判定 count≠1 → 每 2 分钟“杀 2 个起 1 个”死循环，心跳 PID 每 2 分钟漂移但 status=running（看似健康）。
- **诊断**：进程父子链中 venv python 节点是 uv python 节点的父进程 = stub 双节点；真多实例则各自独立父进程。
- **修复**：看门狗 Popen 重启守护时不 `sys.executable`，解析 `pyvenv.cfg` 的 `executable` 字段拿真实解释器；计数时跳过 stub（cmdline 首元素含 `hermes-agent\\venv\\Scripts\\python.exe` 且有同脚本子进程）。已落地 `btc_keylevel_guard_watchdog.py`（2026-08-31）。
- **铁律**：实例计数 >1 先排除 stub 双节点再定性真多实例；“多实例杀不掉每次杀完又变 2”=嫌疑点。

---

## 问题分类：P0/P1/P2 清单

### P0（致命 — 阻断分析）

| # | 问题 | 验证命令 | 修复方向 |
|:--:|------|---------|---------|
| 1 | TV Desktop 未运行 / CDP 端口关闭 | `socket.connect_ex((9222))!=0` | `tv_launch(kill_existing=true)` |
| 2 | 关键守护进程心跳停止（>5min或status≠running） | `cat monitor_heartbeat.json` | 重启对应守护进程 |
| 3 | 守护进程多实例（>1个同名进程） | `psutil` 实例计数 | 杀旧实例+等看门狗拉起 |
| 4 | source_snapshot_{BTC,XAU}.json 过期（>1h） | `ls -lt data/source_snapshot_*.json` | `python scripts/tv_live_dump.py` |
| 5 | BTC ref_levels.json 过期（>24h） | `ls -lt data/btc_ref_levels.json` | `python scripts/btc_ref_levels_sync.py` |
| 6 | cron 关键任务全部暂停 | `hermes cron list` | `hermes cron resume <id>` |
| 6b | keylevels_config 内 level 全过期（心跳新鲜但守卫空转） | `cat data/keylevels_config.json` 查 valid_until | `python scripts/keylevels_collect.py` 重采集→重写 config |

### P1（严重 — 影响质量）

| # | 问题 | 验证命令 | 修复方向 |
|:--:|------|---------|---------|
| 7 | Binance fapi Cloudflare 403 | `curl https://fapi.binance.com/fapi/v1/time` | 改用现货API或TV OHLCV |
| 8 | x_search 不可用 | `tool_search('x_search')` | 降级 web_search+标注 |
| 9 | CG Pro 返回None | `curl CoinGecko Pro API` | 改 FinanceKit MCP 或 curl免费端点 |
| 10 | TV study_values 品种污染（BTC图上出现XAU价位） | 检查VWAP数量级 | `chart_set_symbol` 重切+等刷新 |
| 11 | monitor_levels.json 过期（>24h） | `ls -lt data/monitor_levels.json` | 关键位守护自动刷新 |

### P2（次要 — 优化项）

| # | 问题 | 验证命令 | 修复方向 |
|:--:|------|---------|---------|
| 12 | SOUL.md 未定制棠溪persona | `grep "棠溪\|安禾" SOUL.md` | 手动编辑 SOUL.md |
| 13 | 脚本188个，存在孤岛/过时脚本 | `ls scripts/*.py | wc -l` | 归档旧脚本 |
| 14 | 21/25 cron 暂停（非关键任务） | `hermes cron list` | 按需启用或删除 |

---

## 优化建议优先级排序

### 🔴 立即执行（P0）

1. **修复TV连接**：任何分析前必须先 `tv_health_check`，失败则 `tv_launch`
2. **恢复关键守护**：monitor_heartbeat + BTC daemon 心跳必须新鲜
3. **刷新数据快照**：source_snapshot / btc_ref_levels 必须 < 阈值的才可信
4. **启用关键cron**：4个关键任务 enabled=True

### 🟠 短期执行（P1）

5. **修复API降级链路**：Binance fapi/现货/XAU期货三路必须有一路通
6. **X情绪降级**：x_search不可用时自动走 web_search+标注
7. **TV品种防污染**：每次 `chart_set_symbol` 后必须 `chart_get_state` 确认

### 🟡 持续优化（P2）

8. **SOUL.md persona 定制**
9. **脚本归档**：188个脚本去重，保留canonical版本
10. **cron 精简**：非关键任务按需启用

---

## ⚠️ 双 Python 解释器冲突 — quick 模式专属炸弹（2026-09-02 实测 P0-5）

`auto_card.py` 实际跑的解释器**不一定是 PATH 上的 `python`**。当前实测：
- `python`（默认）→ Hermes venv（`hermes-agent/venv/Scripts/python.exe`）✅ 已装 `requests 2.33`
- `auto_card.py:4806` 实际跑 → **uv cpython 3.11**（`/c/Users/Administrator/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe`）🔴 缺 6 个核心包（requests/pydantic/aiohttp/numpy/pandas/websockets）

**症状**：
- `auto_card BTCUSDT --quick` 在 `_collect_binance_data` 行 2550 报 `ModuleNotFoundError: No module named 'requests'`
- `auto_card BTCUSDT --full` 跑通（A 阶段已验证），因为 full 不走 `_collect_binance_data`
- 同台机器双解释器并存是设计（Hermes 用 venv，uv 用 cpython），但 `auto_card.py` 没钉死解释器

**审计验证**：
```python
import subprocess
for py in ['python', '/c/Users/Administrator/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe']:
    r = subprocess.run([py, '-c', 'import requests, pydantic, aiohttp, numpy, pandas, websockets'],
                       capture_output=True, text=True, timeout=5)
    print(f'{py}: {"✅" if r.returncode==0 else "🔴 " + r.stderr.split(chr(10))[-2]}')
```

**修复**（一行）：
```bash
uv pip install -p $(uv python find) requests pydantic aiohttp numpy pandas websockets
```

**铁律**：任何 `auto_card` 子命令的 P0 排查先验证解释器实际跑哪个；不要假设 `import` 失败是包没装。**P0 排错清单新增第 7 项：双解释器冲突**。

## ⚠️ Pine 行动格行数 vs table.new 次数不符（2026-09-02 实测 P0-6 · 记忆过期型）

主指标 13 行已定稿（2026-09-11）：位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位。**实测 `SVP_ICT_v2_20260810_fix.source.pine` 全文件只有 3 处 `table.new` 和 `table.cell`**。

**根因**：13 行不是 13 个 table cell，而是**单 cell 内用 `str.tostring()` 拼 13 行换行**。这是 Pine 渲染规范（`table.cell` 第一参数是位置，第二参数是 row 0，row 1，row 2；行数是表内不同 row 的 cell 数）。

**审计验证**：
```bash
grep -c "table.new\|table.cell" SVP_ICT_v2_*.source.pine
# 期望：个位数（≤5）。>10 则记忆过期。
```

**铁律**：审计 Pine 行动格行数时**先 grep `table.new`/`table.cell` 实际计数**，再核对记忆条目。**记忆 vs 源码不符 = 记忆过期，不是代码 bug**。

## 分析档位 v2 定稿（2026-09-02 pipeline_router.py 实测）

更新第一维 1.2 节的"档位"表格（详细步骤数 + 主周期）：

| 档位 | 步数 | 主周期 | 触发词 | 上下文继承 |
|:--:|:--:|:--:|---|:---:|
| **quick** | crypto 实测 **3 步**（tv/binance/card，cg_pro 不在 quick）· gold 2 步（tv/card） | BTC=15m / XAU=5m | "看下/看看/快速过一遍" | 否（零成本） |
| **inherit** | 同 quick | 同 quick | "现在呢/继续/接着/更新/继承" | 是（4h 内 `analysis_context_{symbol}.json`） |
| **full** | crypto 10 / gold 8 / forex 7 / stock 8 / futures 6 | 全 5 层 D/4h/1h/15m/5m | "分析/全面/全周期/深度/完整卡" | 否（重扫全源） |
| **monitor** | crypto 5 / gold 4 | 简 | cron 内部 | 否 |

**关键代码定位**（`scripts/auto_card.py:3182-3213` + `scripts/pipeline_router.py:153-206`）：
- inherit 升级 full 条件：`load_analysis_context` 返 None OR 加载异常
- XAU 路径：`subprocess.run xau_tv_sync.py` 20s 超时（跳 `tv_live_dump` 避免双倍等待）
- crypto 路径：`subprocess.run tv_live_dump.py --timeframe 15` 45s 超时
- **quick 模式不写 source_snapshot**（仅 full `render_card_locked` 后写盘）—— 这是设计，不是 bug

**审计验证**：
```python
import sys
sys.path.insert(0, 'D:/Hermes agent/scripts')
from pipeline_router import route_pipeline
for sym in ['BTCUSDT', 'XAUUSD', 'EURUSD', 'AAPL', 'ES']:
    for mode in ['quick', 'full']:
        steps = route_pipeline(sym, mode)
        print(f'{sym:8s} {mode:7s} {len(steps):2d} 步 → {steps}')
# 期望：BTC quick=4(full 4-step base, 含 binance) · BTC full=10
```

## 分析逻辑代码级审计（2026-08-31 五维扫描 · 3 个 P0 确证 + 复现技术）

**铁律：记忆/skill 里的纪律条文 ≠ 代码有闸门。** 用户铁律（B等待禁价、观望改A禁行、R:R≥1:2）必须 `grep`/`sed` 验证代码实现，未实现=审计必报 P0，不能当"已按纪律执行"。完整证据链见 `references/analysis-logic-code-audit-2026-08-31.md`。

✅ **三大 P0 已修复（2026-08-31 当晚闭环落地 + 8/8 决策矩阵断言通过）**，修复点位与验证见下节；下方 P0-1/2/3 条款保留作"修复前症状"参考。

### 修复落地点位（2026-08-31 已改）

| P0 | 代码修改 | 验证 |
|:--:|---|---|
| P0-1 B等待/C反执行权 | `decision_loop.py`：`elif wait or is_bc: state=WAIT/executable=False`（GO-B 取消）；`render_tv_card.py:142-155` 不可执行时不再注入执行价，保留 Pine 行动格候选价供人工判断；`_render_push/_render_full` B/C反 渲染 `🔵主推 等 | 触发描述 | 候选 X·人工判断`（无损/标） | 单元实测：B空→`⭐主推 空/损标` 消失、`候选 62,880·人工判断` 出现 |
| P0-2 观望改A兜底链 | `auto_card.py` 新增 `_conclusion_forces_c_wait()`（词表：观望/未收线/等解除/等收线/⚠冲突/⚠未收线/等待方向/待确认方向/C等待）；`_build_tv_main_data` 与 `_apply_tv_dmi_override` 在 MCP 数值兜底**之前**插入语义闸门；第二道闸门拦「等级行 A/B + 结论含硬 C 词」 | 8/31 事故三场景（观望·等解除 / ⚠未收线 / 等空 反抽 ⚠冲突）全部 → C等待；合法 B等待/A做多 不受误伤 |
| P0-3 R:R 底线放宽 | `decision_loop.py` `min_rr = 2.0`（删除 is_bc 的 1.5） | A多 rr1.5 → WAIT；B多 rr1.6 → WAIT |
| X禁做 硬化（顺手修复） | `decision_loop.py` `if grade.startswith("X"): hard.append("x_forbidden")` —— 旧逻辑 X 也会被 WAIT 覆盖成 C等待 | X → NO-GO/grade=X禁做 |
| tv_live_dump 死引用（顺真 P0） | `auto_card.py` crypto 前置刷新改为 `_tv_dump.exists()` 判断——脚本已在 `_disabled_20260829/`，缺失时跳过子进程改依赖 TV 实时缓存 | quick 回归无报错 |
| D 层缺失（P1） | `_collect_binance_data` 加密 K 线加 `("1d", 30)` → `klines["D"]` | klines keys 含 D · 渲染 TF 行 D🟢 |

**验证命令（回归）**：
```python
# 决策矩阵 8/8（A多副OK→GO-A · B/C反→WAIT · X→NO-GO · rr<2→WAIT · 主副冲突→NO-GO）
cd "D:/Hermes agent/scripts" && python - <<'EOF'
from decision_loop import resolve_final_verdict
good={'asset_is_crypto':True,'valid_code':3,'conflict':False,'aligned':True}
for g,d,rr,du in [('A多','long',2.5,good),('B多','long',2.0,good),('C反空','short',2.0,good),('X禁做','wait',3.0,good),('A多','long',1.5,good),('B空','short',1.6,good),('A多','long',2.5,{**good,'conflict':True})]:
    fv=resolve_final_verdict('BTCUSDT',{'grade':g,'direction':d,'entry':100,'stop':98,'target':104,'rr':rr,'data_grade':'A'},du)
    print(g,fv.state,fv.executable)
EOF
# 渲染复现实测
python -c "
from render_tv_card import render_tv_card
main={'grade':'B空','treatment':'等5m触碰VWAP回落+CVD转负→激活预案B','vwap':63342,'val':62558,'poc':62876,'entry':'62,880','stop':'63,380','target':'61,780','_final_verdict':{'grade':'B空','state':'WAIT','executable':False,'model_id':'vwap_pullback'},'_dual':{}}
assert '⭐主推 空' not in render_tv_card(main,{},'BTCUSDT',62880,'push')
print('B级无执行单 OK')
"
```

**修复后仍留 P1（2026-08-31 复核修正）**：核对行只读不判——**已过时**：v2 行动格（位置/结论/方向/路径/风控/现位/磁吸）已无"核对"行，核对语义由"协同/路径/现位"承担且已接入新闸门，无需修复；full/quick 同卡——**已工作**：render_card_locked 内部 `if not force_full and tv_main and tv_sub → render_tv_card(push速读)` / `force_full=True → render_v96_card(完整驾驶舱)`，Card A=full / Card B=push 双卡已分离；tv_dmi_cache 通用缓存过期——**已重建**（2026-08-31 现场数据，与 tv_live_BTCUSDT.json 同结构）。

### 修复前症状（保留作判断参考）

| 位置 | 作用 |
|---|---|
| `decision_loop.py:182-184` | `elif is_a or is_bc: state="GO-B"; executable=True` —— **B/C反 全部可执行** |
| `render_tv_card.py:150-155` | executable 时把 final 的 entry/stop/target 注入 main |
| `render_tv_card.py:217`（_render_push） | 渲染 `⭐主推 空 \| 62880 \| 空 损63380 标61780` |
| `render_v96_card:390` | GO-B 同样走"可执行"分支 |
| `auto_card.py:1359-1360` | status 直接用 `final_verdict.state`/`grade`，**旧 A/B/C/X 等级被 FinalVerdict 覆盖** |

**违反 8/29 用户铁律「B等待卡严禁给具体入场/止损/止盈价格」**（只给条件触发描述）。已单元级实测复现（合成 `_final_verdict={'executable':True,'state':'GO-B'}` 直调 `render_tv_card` → 秒出带价卡）。

### P0-2：等级兜底链可把「观望/未收线/等解除」改写为 A 级（8/31 事故代码根因仍在）

链：`_build_tv_main_data`（auto_card.py:958-961）与 `_apply_tv_dmi_override`（:980-981）——行动格"结论"行前缀匹配失败（⚠未收线/观望/等解除等非标准前缀）→ `_grade_from_mcp_values`（:881-884）用 MCP Side/Grade Code 数字兜底：`side=1 & grade_code=3 → "A多"`。**全程无「结论含 观望/等待/未收线/解除/收线/⚠ → 强制 C等待」语义闸门**。

记忆里的 8/31 纪律是输出层约束，代码层没有；只要 Pine 结论行非标准前缀 + Data Window Grade Code 恰好=3，事故可复现。修复方向：等级判定优先级 ①结论文本语义（含等待词=强制C等待）②等级行 ③MCP 数值兜底（仅当前两者无明确方向）。

### P0-3：R:R 硬底线被 B 级放宽到 1:1.5

`decision_loop.py:157` `min_rr = 2.0 if is_a else 1.5 if is_bc else 2.0` —— B 级 rr 1.5-2.0 照样 GO-B 放行，违反「GO/NO-GO 只看主线 R:R≥1:2」。注意 `_downgrade_low_rr_a_status`（auto_card.py:2461）只拦 A 级，B 级绕过。

### 审计技术：单元级渲染复现（秒级验证卡行为）

```python
cd "D:/Hermes agent/scripts" && python -c "
import sys; sys.path.insert(0, '.')
from render_tv_card import render_tv_card
main = {'grade':'B等待','treatment':'等5m反抽VWAP确认','vwap':63342,'val':62558,'poc':62876,
        '_final_verdict':{'grade':'B空','executable':True,'state':'GO-B','entry':62880,'stop':63380,'target':61780},
        '_dual':{'direction_verdict':'主副同向'}}
print(render_tv_card(main, {'signal':'偏空'}, 'BTCUSDT', 62880, 'push'))
# B等待→GO-B→输出带价 ⭐主推 空 = P0-1 复现
"
```
不必跑全管线，合成 FinalVerdict dict 直调渲染器即可验证"B是否带价/C是否可执行"。

### 实测快检卡发现（2026-08-31 quick 实测）

- **TV 数据注入失败时整卡退化**：D周期"待刷新"、五层"位置"列全 `—`、HALDRO `Composite 待刷新·副指标无效`——`data/tv_live.json` 过期（>2h）直接导致；管线审计自认 `TV五层 ⚠️ 周期覆盖 4/5`。审计必查 tv_live.json mtime。
- **核对行（8项✓）只读不判**：`main["check"]` 解析后无任何消费，skill 声称的「8/8→A、≤5/8→降级」未落地（`grep check 降级链` 零命中）→ P1。
- **full 与 quick 输出同一张卡**：`render_card_locked:1416-1419` 两分支都 return full，"三表速读 vs 完整8表"档位切换在代码层不存在 → P1。
- **档位关键词分歧**：实码 `resolve_analysis_mode` 只认「现在呢/继续/接着/更新/继承」为 inherit；skill 文档 L2 触发词「扫一下/状态」实码落 quick fallback → P2（文档-实码分歧以下表实码为准）。

### 本档位核查通过项（避免误报）

档位主链正确（分析/全面/深度=full 硬开关）✓ · inherit 无上下文自动升 full（auto_card.py:3200-3213）✓ · XAU 直调 xau_tv_sync 跳 tv_live_dump ✓ · 主副冲突裁决（valid_code/conflict/hard_conflict）✓ · A级 R:R<2 降级闸门 ✓（但被 P0-3 B级门槛绕过）· GO/NO-GO 七门接完整卡尾 ✓ · 管线审计表存在 ✓。

## 快速验证命令（可复制执行）

```bash
# 一键预检
cd "D:/Hermes agent"
python -c "
import json,os,socket
# TV/CDP
s=socket.socket(); s.settimeout(2)
r=s.connect_ex(('127.0.0.1',9222)); s.close()
print('TV CDP:', '开放✅' if r==0 else f'关闭❌:{r}')
# 心跳
for n,f in [('行情守望','data/monitor_heartbeat.json'),('BTC守护','data/.btc_daemon_heartbeat.json'),('关键位','data/.keylevel_guard_heartbeat.json')]:
    try:
        d=json.load(open(f))
        ts=d.get('ts') or d.get('time') or ''
        print(f'{n}: {d.get(\"status\",\"?\")} {ts[:19] if ts else \"无时间戳\"}')
    except: print(f'{n}: 文件缺失❌')
"
```

---

## ⚠️ 审计因果错配三大类铁律（2026-08-31 实测必入审计方法论）

本会话出现 3 类典型误判，每一类都会让审计报告失真。完整证据链见 `references/audit-cross-validation-2026-08-31.md`。

1. **grep 行号巧合命中非引用关系** — `grep -n "cvd_analyzer" scripts/auto_card.py` 在第 4806 行命中，但 `sed -n '4800,4815p'` 该行上下文是 `_mode = "quick"` 路由逻辑，不是 import。`grep` 默认会把任意字符串匹配计入。**铁律：grep 命中后必须 `sed -n 'N-5,N+5p'` 看上下文，只有 `from X import` / `import X` 形态才算引用**。`auto_card.py` 实际不直接 import `cvd_analyzer`，引用只在 `scripts/orphan_integration.py:230,234`。
2. **编造无源字段做证据** — 报告写 `text_push_status: failed_or_missing` 推导「所有关键位分析卡片推送失败」，但 `data/keylevel_triggers/` `data/keylevel_analysis/` `cron/output/` 三处全空，该字段无任何真实出处。**铁律：报告中每个结论性字段必须能 `cat <path>` 或 `grep -rn` 找到原始行号；给不出路径 = 不能写进报告，按错信处理**。
3. **迁移设计边界误判 P1** — 报告把 8/29 迁移后的 21/25 cron paused 标 P1，把 `btc_ref_levels_sync.py` paused 标 P1。实际 `keylevel_guard` 已替代 `行情守望`，`querylevels` 已替代 `btc_ref_levels_sync`。**铁律：审计 `enabled: false` 前先确认是否 8/29 binance-only 迁移设计产物——`keylevels_config.json` 在用 = `querylevels` 在用 = `btc_ref_levels_sync` 可不启用，不是故障**。

## ⚠️ 时间分层与当前工作树复核（2026-09-01）

用户提交的审计报告是**带时间戳的证据快照**，不是当前运行真相。复核时必须先记录当前时间、仓库根目录、`git status --short --branch`、有效 Hermes 配置路径和运行态，再逐条核对；不要把报告中的行号、退出码、缓存年龄或模型可用性直接沿用到当前版本。

**每条结论必须分层标注**：`历史实测`（当时成立）· `当前复现`（现在仍成立）· `已修未提交`（当前工作树已改但未锁定）· `未复现`（当前证据不成立）· `未验证`（缺少可重跑证据）。代码测试通过不等于运行态健康；必须把测试、静态检查、数据新鲜度、业务健康和外部投递分栏报告。先比对当前工作树与 `HEAD` 的 diff，再解释行号，避免把父版本缺陷误报成现行缺陷。

**裁决链复核不能只看函数签名**：必须追踪“生产者写入 → FinalVerdict 调用 → GO/NO-GO 渲染”的实际顺序。即使 `resolve_final_verdict(..., advanced=...)` 已存在，只要 `_advanced` 在 FinalVerdict 计算之后才生成，门控仍未接入；同理，后置写入 `meta` 不能证明最终闸门消费了它。

**数据闸门至少跑两组对照**：
- 已知 `status.usable=false` → 必须红灯/阻断；
- 缺失 `status`、只有非空旧数据 → 不能推断为实时可用，必须单独标记 unknown/fail-closed 风险。

**历史缺陷与当前修补要拆开报告**：例如 C反多/C反空方向、Meta-Labeling 默认拒绝、B/C等待无执行权等，若当前工作树已修复，应移入“已修未提交/已修复”表；若主流程调用顺序仍绕过修补，则只保留未闭环的根因，不重复旧行号叙述。

**按数据对象分别判新鲜度**：`xau_tv_state.json`、`source_snapshot_XAUUSD.json`、`tv_live_XAUUSD.json` 不是同一缓存；某个对象新鲜不能替代另一个对象的新鲜度。`fresh=true` 也不能覆盖由时间戳计算出的过期结论。

**审计工具/测试结果也要诚实分层**：没有 lockfile 时 `npm audit` 的 ENOLOCK 是“无法审计”，不是 0 漏洞；全量 collection error、定向测试失败、脚本 py_compile 通过必须分栏记录，不能合并为一个“测试通过”。完整取证模板见 `references/audit-report-reconciliation-2026-09-01.md`。

## ⚠️ 孤儿脚本 integration 模式是 P0 隐藏路径（2026-08-31 实测补漏）

旧 Pitfall「幽灵模块引用」覆盖「文件不存在」一类，但**遗漏了「孤儿集成层 import 链」**：`orphan_integration.py` 集中 import 6 个孤儿脚本（meta_labeler/orderflow_absorption/cvd_analyzer/fvg_detector/order_block/correlation_matrix），主入口 `auto_card.py` 不直接 import 它们。审计步骤必须加：

1. `grep -rn "from orphan_integration\|import orphan_integration" scripts/` 找孤儿集成层引用方
2. 读 `orphan_integration.py` 第 10-50 行，列出全部孤儿脚本清单
3. 对每个孤儿脚本 `ls scripts/<name>.py` + `ls scripts/_disabled_*/<name>.py` —— 仅在 `_disabled` 即真孤儿，恢复路径固定为 `cp scripts/_disabled_YYYYMMDD/<name>.py scripts/`
4. 验证：`python -c "from cvd_analyzer import check_cvd_confluence"` 能 import 才算修复完成

已知本次会话真孤儿：`scripts/cvd_analyzer.py`（仅 `scripts/_disabled_20260829/cvd_analyzer.py` 存在），其它 5 个在 `scripts/` 存在。

## ⚠️ 脚本归档后 cron 引用悬空（P1 · 2026-08-31 实测）

`tv_keepalive.py` 被 8/29 迁移移入 `scripts/_disabled_20260829/`，但 cron `TV Desktop保活` 仍引用 `scripts/tv_keepalive.py` → `Script not found`。**审计 `Script not found` 错误时：先查 `scripts/_disabled_*/` 归档目录，确认脚本是被有意禁用（cron 应同步 pause）还是误删（需恢复）**。

## ⚠️ 设计性退役的判断标准（2026-08-31 实测补漏 · 审计哲学）

下述 4 类文件陈旧**不一定是 P0**，必须用「内容是否含有效字段 + 是否有新业务需要它」双标准判断：

| 文件 | 设计性退役判断 | 留观而非重建 |
|---|---|---|
| `data/source_snapshot_*.json` | quick 模式不写盘（仅 `auto_card.py --full` 触发 `source_snapshot()`） | 下次 full 模式触发自动刷新 |
| `data/monitor_levels.json` | `_approved_monitor_levels()` 已改读 `keylevels_config.json`，仅历史兼容路径 | 改用 `keylevels_config.json` 为唯一批准源 |
| `data/protections_state.json` | `save_protections()` 在 live 区无调用方（仅 `_archive/行情守望.py` 调） | 用户偏好"手动控制开单"+"trade_events.jsonl 不活跃写" → 失活可接受 |
| `data/trade_events.jsonl` | 用户偏好"不需要自动交易" → 无活跃事件 | 写入链路已退役 |

**铁律**：4 个文件陈旧**不自动标 P0**。判断顺序：① 是否被新代码读（`grep`）；② 是否有 cron 驱动；③ 是否有用户偏好导致失活。**符合 ①②③任一即「设计性退役，留观」**，不要盲目 `python xxx.py` 重生。

## ⚠️ cron auto-disabled 自相矛盾修复模式（2026-08-31 实测 P0 隐藏根因）

`paused_reason: "auto-disabled: enabled+paused contradiction"` 是 Hermes cron 调度器的状态机产物——`enabled=true` + `state=paused` 同时存在时被自动标 disabled。修法：

```python
# 标准修法：j['enabled']=True, j['state']='scheduled', j.pop('paused_at',None), j.pop('paused_reason',None), j['next_run_at']=None
# 写回前必备份：shutil.copy2(jobs_path, jobs_path + '.bak.' + time.strftime('%Y%m%d%H%M%S'))
# 触发原因通常是 cron 引用的脚本被归档/删除 → 必须先恢复脚本再改 cron 状态（顺序反了会立即再被 auto-disabled）
```

**审计时若看到 `paused_reason: auto-disabled: enabled+paused contradiction`，先查 cron `script` 字段指向的文件是否存在**——常见根因是 `script` 引用的脚本被 8/29 迁移归档到 `scripts/_disabled_*/`。修法顺序：① 把脚本从 `_disabled/` 复制回 `scripts/` ② `py_compile` 验证 ③ 改 cron 状态。

## ⚠️ C 全套修复闭环（用户「全部修一遍」标准动作序列 · 2026-08-31 落地）

用户选 "C 全套" 时按以下顺序跑，每步**立即验证再进入下一步**，避免引入新 P0：

1. **真 P0 修复**（孤儿/断链）：从 `_disabled_*/` 复制脚本到 `scripts/` → `python -c "import xxx"` 验证 import 通
2. **守护 cron 修复**（自相矛盾）：恢复脚本 → 改 `enabled/state/paused_reason` → 备份 `jobs.json`
3. **关键位数据重生**：`python scripts/btc_ref_levels_sync.py` 同步 `btc_ref_levels.json` + `tv_live.json` + `tv_dmi_cache.json`（一个脚本同时刷三个）
4. **设计性退役判定**：4 类文件（source_snapshot/monitor_levels/protections_state/trade_events）按上面表格留观
5. **设计性错配 cron 暂停**：`liq_listener_btcusdt`（while True daemon 配每日 cron 必 timeout）/ `macro_poly_refresh.py`（脚本已归档 cron 引用断链）→ 改 `state=disabled` + `paused_reason` 写明断链原因
6. **端到端验证**：7 孤儿全部 import + 关键数据 mtime < 30min + 4 活跃 cron `last_status=ok` + 2 个本轮暂停 cron 留观文档完整
7. **评分前后对比**：修复前 7.2/10 → 修复后 8.5/10；扣分项全部为设计边界

**铁律**：不立即验证 = 制造新 P0 的高风险。**绝对不要一次性跑完全部步骤最后才 grep 错误**。

## TG 表格守卫 hook（2026-08-31 落地 · 防御层）

**问题**：模型把分析卡管道表直接写进 TG 回复时，TG 自动投递渲染成 bullet/列表而非真表格（用户 8/29 两次纠正"不是表格"的根因）；换模型后此行为可能复发。

**落地**：`~/.hermes/hooks/tg_table_guard/{HOOK.yaml, handler.py}`（Hermes 官方事件钩子机制）。

| 项 | 内容 |
|---|---|
| 事件 | `agent:end`（context: platform/chat_id/thread_id/session_id/model/response） |
| 检测 | platform=telegram + 回复前 500 字含 ≥3 行管道表 + 分析卡关键词（主推/结构位/周期/行动格/关键位/裁决） |
| 动作 | 写审计日志 `data/hooks_tg_table_guard.log` + 向同一话题发一条纠正提醒（不重发表格，防双发噪音） |
| 测试 | `TG_TABLE_GUARD_DRY=1` 环境变量 → 只写日志不发消息 |

**边界（诚实告知）**：agent:end 在消息发送**之后**触发且 response 截断 500 字——hook 无法拦截/改写已发送消息，定位为"记录+提醒+证据链"；真表格保证仍是代码管道（auto_card --push 直连 `send_telegram_reliable(parse_mode="RichMarkdown")`）。gateway 重启后自动加载。审计/排障时检查 hook 是否在 ~/.hermes/hooks/ 且日志有记录。

hook 机制参考：Hermes 源码 `gateway/hooks.py`（HOOK.yaml 声明 events，handler.py 提供 async handle，错误永不阻塞主管线；所有可用事件：gateway:startup/session:*/agent:start/step/end/command:*）。

## 多资产统一审计与X模型边界（2026-09-02新增）

棠溪不是单一加密系统。审计与优化必须先按资产画像路由：加密、黄金、外汇、股票、期货、期权分别定义主执行周期、适用数据源、禁用数据源和卡片字段。统一画像与模式契约见 `references/multi-asset-analysis-contract-20260902.md`。

- 加密：BTC/主流币15m；SVP主驾驶，AggVol仅确认/降级/否决；Binance Futures负责实时价格、OI、Funding、Taker、多空比和深度。
- 黄金：5m；SVP + 金十/DXY/US10Y/GLD-GDX-TIP/COT；不得混入AggVol、Binance Funding/Taker或BTC情绪缓存。
- 外汇：15m；SVP + 金十日历/DXY/央行/利差/相关货币对；事件前后单独门控。
- 股票：1h；SVP + FinanceKit/SEC/财报/板块轮动/期权链；必须考虑盘前盘后、跳空和财报窗口。
- 期货：15m；SVP + 期货行情/库存/经济日历/DXY/相关商品；区分连续合约、交割月和夜盘。
- 期权：先分析底层标的，再分析到期日、IV、Greeks、OI/PCR和MaxPain有效性；无效MaxPain不得进入结论。

档位固定为：`quick=execution_only`（看下/看一下）、`inherit=execution_plus_context`（现在呢/更新）、`full=all_sources`（分析/全面/深度）、`monitor=event_only`（只产生事件，不判方向）。含“分析”不得因刚出过卡而降级；每轮正式加密/黄金更新必须新截图，截图前核对symbol+resolution。

X/xAI模型是证据源，不是执行器：只提供情绪、新闻催化剂、叙事和盲点；不可修改FinalVerdict、主引擎置信度、Entry/Stop/Target或GO权限。X不可用时必须显示未授权/降级，不得拿旧缓存冒充实时。TV、Binance、API、X和卡片均不能绕过FinalVerdict；只有`GO-A`允许执行三件套，`WAIT/NO-GO`不得渲染执行价格。

共享TradingView图表存在并发风险：多个资产任务切图前必须取得跨进程锁，切换后和读取后各做一次symbol/timeframe校验；不完整、错品种、错周期或空候选池必须fail closed且不得覆盖旧缓存。缓存至少记录`identity_valid`、`action_table_complete`、`source_quality`和时间戳。

## 参考文件

- 技能主文档：`trading/tangxi-system-audit/SKILL.md`（完整审计Step 0-12）
- 看门狗模式：`trading/tangxi-system-audit/references/market-watchdog-pattern.md`
- uv venv stub 双节点 + 关键位空转（2026-08-31 实测）：`trading/tangxi-analysis-audit-checklist/references/uv-venv-stub-and-keylevels-empty-idle-2026-08-31.md`
- **审计因果错配证据链（2026-08-31 实测 · 3 类方法论失败 + 1 个真 P0 漏报）**：`trading/tangxi-analysis-audit-checklist/references/audit-cross-validation-2026-08-31.md`
- **C 全套修复闭环 Runbook（2026-08-31 落地 · 9 步标准动作 + 必查陷阱）**：`trading/tangxi-analysis-audit-checklist/references/audit-9-step-closure-runbook-2026-08-31.md`（用户选"全部修一遍/全部自动修复"时直接套用）
- **分析逻辑代码级审计证据链（2026-08-31 · 3 个 P0：B等待→GO-B带价 / 观望改A兜底链 / R:R B级1.5 + 单元级复现法）**：`trading/tangxi-analysis-audit-checklist/references/analysis-logic-code-audit-2026-08-31.md`
- TV缓存污染：`trading/tangxi-system-audit/references/2026-07-08-tv-cache-pollution-recurrence.md`
- **完整图表证据（价格栏/ICT/截图与结构化读取一致性）**：本技能 `4.3`；审计时优先按该节执行
- 预检脚本：`D:/Hermes agent/scripts/audit_preflight.py`
