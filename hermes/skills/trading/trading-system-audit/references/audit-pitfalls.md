# 审计陷阱速查（常犯的假阳性模式）

## JSON 字段名验证铁律

**在标记任何字段为"空/缺失/broken"之前，必须先打印 keys 列表。**

```python
# ✅ 正确
print(list(entry.keys()))
# 然后才用真实 key 名查询

# ❌ 错误 — 直接猜测 key 名
print(entry.get('win'))        # 实际是 was_correct
print(entry.get('reason'))     # 实际是 reasons
print(entry.get('data_quality')) # 实际是嵌套 dict
```

## git-bash 下进程/JSON 探查陷阱（2026-06-19 反复踩坑）

**审计在 Windows git-bash 跑，三类命令会静默坑你 — 用 read_file 或临时脚本替代，别硬刚 shell 引号。**

| 命令 | 坑 | 替代方案 |
|------|-----|---------|
| `python -c "import json; d=json.load(open('f.json',encoding='utf-8'))..."` | 嵌套单/双引号被 bash 吞掉 → 内层引号消失 → `SyntaxError: invalid syntax`（变量名当语法读）| 用 `read_file` 读 JSON 再在 execute_code 里 `json.loads`；或写 `.py` 临时脚本跑 |
| `wmic process where ...` | Win11 已弃用 wmic，常返回**空输出**（不报错），统计全为 0 | 用 `tasklist //FI "IMAGENAME eq python.exe" //V //FO CSV` 导出 |
| `powershell -Command "...D:\Hermes agent..."` | 路径含空格 → PowerShell 把 `D:\Hermes` 当 cmdlet 名 → `CommandNotFoundException`；且中文输出 GBK 乱码 | 避免 powershell；用 tasklist/netstat；必须用时路径加引号且 `chcp 65001` |

**read_file 读 JSON 去行号技巧**（read_file 输出带 `行号|` 前缀）：
```python
content = read_file("data/source_snapshot_BTCUSDT.json")["content"]
clean = "\n".join(l.split("|",1)[1] if "|" in l else l for l in content.splitlines())
d = json.loads(clean)
```

**进程构成判读**：`tasklist //V //FO CSV` 中，常驻 ~3.8M 内存 + CPU `0:00:00` 的 python 进程 = Hermes 重启遗留的孤儿子进程（P2，占内存不影响功能）；大内存进程（桌面运行时 ~330M、行情守望 ~60M、各 MCP server ~30-40M）是正常工作进程。

## 技能文件完整性已自动护栏（2026-06-19 接入）

**分析卡"其他渠道生成不了/读不到格式" → 先怀疑 SKILL.md 被行号污染，不是记忆没写。**

根因详见 `tradingview-indicator-analysis` 技能 Pitfalls。诊断：`skills_list` 看某技能 description 是否显示成乱码 `"1|---"`；`read_file` 看 SKILL.md 首行是否为 `1|---` 而非 `---`。修复：Python 逐行剥 `^\d+\|`（只剥行首第一个，不动表格 `|`），备份 `.corrupted.bak` 后写回，`skills_list` 验证 description 恢复。

**已自动化**：`scripts/清理守护.py` 的 `check_skill_integrity()` 每 6 小时（清理守护 cron，no-agent 零 token）扫全部 SKILL.md + references/*.md，检测行号污染 + frontmatter 损坏（首行非 `---` / 150 行内无结束边界），只在发现问题时报警到 Telegram 846。审计时不必再手动全库扫描，但仍应确认该 cron last_run 正常。注意：no-agent cron 从 `%LOCALAPPDATA%/hermes/scripts/` 执行，改了 repo 的 `清理守护.py` 必须同步 AppData 副本才生效。

## 已知字段名陷阱

| 文件 | ❌ 错误 key | ✅ 正确 key | 说明 |
|------|------------|------------|------|
| `prediction_log.jsonl` | `win` | `was_correct` | prediction_tracker 用此命名 |
| `structure_refresh_requests.jsonl` | `reason` | `reasons` | maybe_request_refresh 用复数 |
| `source_snapshot_BTCUSDT.json` | `data_quality` | `quality` / `prices.primary` | 嵌套结构 |
| `source_snapshot_XAUUSD.json` | `spread_pct` | `price_spread_pct` | 不同命名风格 |
| `monitor_levels.json` | `levels` (顶层) | `symbols.BTCUSDT.levels` | 多品种嵌套 |

## 数量陷阱

| 文件 | 陷阱 | 真实含义 |
|------|------|---------|
| `trade_reviews.jsonl` | 1条记录 ≠ 1笔真实交易 | 可能是 `test: true, taken: false` |
| `trade_plans.jsonl` | 48条计划 ≠ 48个待执行 | 多数是 `B等待` 且 `entry: null`（结构刷新） |
| `prediction_log.jsonl` | verified=True, win=None ≠ 追踪断裂 | win 字段根本不存在 |

## Source Snapshot 结构差异

**Per-symbol 文件** (`source_snapshot_BTCUSDT.json`):
```json
{
  "time": "...", "symbol": "BTCUSDT",
  "prices": {"primary": 63900, "primary_source": "Binance", "sources": [...]},
  "quality": "A", "confidence": 88, "confidence_label": "两源一致",
  "price_spread_pct": 0.11
}
```

**Unified 文件** (`source_snapshot.json`):
```json
{
  "time": "...", "symbol": "XAUUSD",
  "price": null,  // ⚠ 可能为 null，价格在 prices dict 里
  "prices": {...}
}
```

**XAU A-级正确形态**（2026-06-19 验证健康）：`quality: A-`, `confidence: 88`, `confidence_label: 金十+gold-api现货双源一致；Yahoo期货basis仅作参考`。这是正确的 spot/basis 分离，不要误判为"价差过大"——`price_spread_pct ~0.46` 是 GC/MGC 期货 basis 偏离造成，现货双源其实一致。

## OANDA Token 占位符检测

```python
with open('hermes/secrets/oanda_token.txt') as f:
    content = f.read()
if 'PLACEHOLDER' in content or content.startswith('# OANDA'):
    # → XAUUSD 质量上限 B(78%)
    # Fix A: get real OANDA token → A(92%)
    # Fix B: integrate gold-api.com (free, no auth) as third source → A(88-92%)
    #   - add gold_api_price() to trading_system.py
    #   - add probe to price_consensus()
    #   - add quality tier: 金十+gold-api+Yahoo → A(88-92)
    #   - reference: see trading-system-v95-plus-evolution skill
```

## 进程重启验证

修复代码后不要假设生效：
```bash
# 1. 查修复前 PID
cat data/monitor_heartbeat.json | jq .pid  # → 8236
# 2. 修代码
patch 行情守望.py ...
# 3. ⚠ 删 .pyc 缓存 — Python 可能用旧缓存跳过新代码
rm -f scripts/__pycache__/trading_system.cpython-311.pyc
rm -f scripts/__pycache__/行情守望.cpython-311.pyc
# 4. 杀旧进程（或等 watchdog 90s 超时自动重启）
taskkill //F //PID 8236
# 5. 等 40s 让 watchdog 重启（检查间隔 30s + 启动冷启动）
sleep 40
# 6. 验证新 PID
cat data/monitor_heartbeat.json | jq .pid  # → 24436 ≠ 8236 ✅
# 7. 验证错误消失
tail data/monitor.log  # 不再有 model_dir_text UnboundLocalError
# 8. 验证新功能生效（如 gold-api 集成）
python -c "import json; d=json.load(open('data/source_snapshot_XAUUSD.json')); print(d['quality'], d['confidence_label'])"
# → A 金十+gold-api+Yahoo三源验证 ✅
```

### .pyc 缓存陷阱

Python 模块首次导入时生成 `.pyc`，后续导入直接用缓存，**即使源文件已修改**（如果 .pyc 时间戳比源文件旧才会重编译，但 CI/编辑器行为不一致）。

对于常驻进程（行情守望/monitor）：
- 编辑 `trading_system.py` 后 → 先删 `__pycache__/trading_system.cpython-311.pyc`
- 再杀进程让 watchdog 重启 → 新进程会重新编译源文件
- 不删缓存 → 进程可能继续用旧逻辑（如 gold-api 探头不生效）

## watchdog 频繁重启判读（2026-06-19 观察）

`watchdog.log` 反复出现以下模式时的根因区分：
- `心跳停滞 Ns · 存活=True · 强制重启`，N 在 90-200s → 主循环**串行网络请求累积超时**（非崩溃）。常见元凶：某个推送通道超时空耗（如 Discord `hermes_cli timeout` 每轮 10s×3重试=30s）拖垮单轮心跳。
- `存活=False` 且 N>200 → 进程真崩溃。
- `重启速率限制：N次/小时已达上限` 反复出现 → 进入冷却但根因未除，应视为 P1（除非已发推送告警）。
**联动诊断**：先查 `monitor.log` 有无某通道反复 timeout，修通/摘除该通道后再观察心跳是否转稳——推送空耗与心跳停滞常同源。

## 模型覆盖率审计陷阱

When auditing model coverage, distinguish three sources:
- **五模型** (`five_model_matcher.py`): VWAP反抽, VAH回收, VAL回收, POC拒绝, 扫流动性回收, 突破接受 (6)
- **12引擎** (`multi_model_engine.py` ALL_MODELS): 五模型子集 + EMA趋势, 费率极端反转, 多空拥挤反转, Taker背离, OI背离, M_VWAP磁吸, 关联套利 (12)
- **治理** (`strategy_governance.json` rules): 交叉覆盖 (12)

Coverage checks:
```python
# ALWAYS print ALL_MODELS to verify what the engine actually registers
from multi_model_engine import ALL_MODELS
print([name for name, _ in ALL_MODELS])
# → ['VWAP反抽', 'VAL回收', 'POC拒绝', '扫流动性回收', '突破接受', 
#    'EMA趋势', '费率极端反转', '多空拥挤反转', 'Taker背离', 
#    'OI背离', 'M_VWAP磁吸', '关联套利']
# Note: VAH回收 is in 五模型 but NOT in ALL_MODELS
```

Common causes for 0-trade models:
- `conf < 0.5` threshold too high (engine models)
- Missing data: `oi_change_pct=0`, `funding_rate=0` (费率极端反转/OI背离 never fire)
- Model conditions favor specific market states not present in backtest window

## 引擎模型数据格式陷阱（静默失败 · 2026-06-18 发现）

**12引擎模型期望嵌套dict，传入平键会静默返回0笔交易——不报错不告警。**

```python
# ❌ 静默失败 — 引擎读不到嵌套key
data = {"taker_ratio": 1.05, "oi_change_pct": 0.5}

# ✅ 正确 — 匹配引擎内部 data.get("taker_futures",{}).get("ratio")
data = {
    "taker_futures": {"ratio": 1.05, "direction": "buy"},
    "binance_spot": {"24h_change_pct": -2.5},
    "long_short": {"top_long_pct": 64.5},
    "oi": {"btc": 105000, "change_pct": 0.5},
}
```

**诊断**：在 `run_engine_models_for_backtest()` 中 `print(name, conf)`。全部0=格式问题。
**根因**：查阅 `multi_model_engine.py` 每个模型的 `data.get()` 调用，构建匹配结构。
**效果**：覆盖率从31%→69%。

## GitHub API for Community Comparison

When web_search/Firecrawl is down (frequent), use GitHub REST API directly:
```bash
curl -s "https://api.github.com/search/repositories?q=<URL_ENCODED_QUERY>&sort=stars&per_page=5" \
  -H "Accept: application/vnd.github.v3+json" -H "User-Agent: TangXi"
```

Key fields to extract: `full_name`, `stargazers_count`, `forks_count`, `pushed_at`, `description`, `open_issues_count`.

Do NOT rely on web_search for GitHub repos — Firecrawl quota exhaustion is the default state.

## 核心脚本路径陷阱（2026-06-18 发现）

**Memory 和旧审计记录引用 `hermes/scripts/行情守望.py` 等路径 — 全部错误。**

实际路径：核心交易脚本在项目根 `scripts/` 目录，`hermes/scripts/` 下仅有 `multi_model_engine.py` 等引擎模块。

| ❌ 错误路径（memory/旧记录） | ✅ 正确路径 |
|---|---|
| `hermes/scripts/行情守望.py` | `scripts/行情守望.py` |
| `hermes/scripts/watchdog.py` | `scripts/watchdog.py` |
| `hermes/scripts/auto_card.py` | `scripts/auto_card.py` |
| `hermes/scripts/trading_system.py` | `scripts/trading_system.py` |
| `hermes/scripts/scoring_engine.py` | `scripts/scoring_engine.py` |
| `hermes/scripts/risk_constitution.py` | `scripts/risk_constitution.py` |
| `scripts/multi_model_engine.py` | `hermes/scripts/multi_model_engine.py` |

**审计前必须验证**：
```bash
ls scripts/行情守望.py scripts/watchdog.py scripts/auto_card.py
# 如果不存在，用 search_files 查真实位置
```

**根因**：`scripts/` 存在但放的是 repo-maintenance 脚本，交易系统脚本在项目根 `scripts/` 下。

## 代码质量审计指标速查

批量审计核心模块时，提取以下指标：
```python
import re
code = open(f, encoding="utf-8", errors="ignore").read()
lines = code.count("\n")
try_blocks = code.count("try:")
except_blocks = code.count("except")
bare_except = len(re.findall(r'except\s*:', code))       # bare except = 危险
broad_except = len(re.findall(r'except\s+Exception', code))  # broad = 吞异常
has_logging = bool(re.search(r'import logging|logging\.getLogger', code))
print_calls = code.count("print(")
has_typehints = len(re.findall(r'->\s*\w+', code))
```

**红旗指标**：
- `broad_except / except_blocks > 80%` → 异常吞噬严重（行情守望 25/28=89%）
- `has_logging = False` 且 `print_calls > 5` → 无结构化日志
- `bare_except > 0` → 最危险的异常处理（gold_monitor.py 有2处）

## 联网社区调研工具可用性（2026-06-18 验证）

### 搜索API（凭据存 `hermes/secrets/search_apis.json`）

| API | 状态 | 额度 | 用途 |
|-----|------|------|------|
| Brave Search | ✅ 可用 | 2000/月 | 主力搜索：Reddit帖子+技术文章+实时结果 |
| Exa Search | ✅ 可用 | 1000/月 | 语义搜索：深度技术文章、walk-forward/overfitting |
| Tavily | ✅ 可用 | 免费层 | **2026-09-13 复测恢复正常**（此前记 401） |
| Metaso | ✅ 可用 | 免费层 | **2026-09-13 复测返回结果**（此前记 SSL 错） |
| Felo | ✗ 不通 | 端点失效 | 端点只剩 `{"Hello":"World"}` 占位；系统未引用 |
| Firecrawl | ✅ 可用 | 免费层 | **2026-09-13 复测 `scrape` 成功**（此前记欠费 402） |
| AnySearch | ✗ 不通 | DNS/SSL | 直连 DNS 失败、代理下 SSL EOF；系统未引用 |
| DDGS (web_search内置) | ⚠ 不稳定 | 免费 | 兜底使用 |

### 网页爬取工具

| 工具 | 用途 | 仓库 |
|------|------|------|
| crawl4ai | JS渲染爬取，绕反爬 | https://github.com/unclecode/crawl4ai |
| Scrapling | 反爬专用 | https://github.com/D4Vinci/Scrapling |

### 其他工具

| 工具 | 状态 | 用途 |
|------|------|------|
| `web_extract` 官方文档 | ✅ 稳定 | Freqtrade/NautilusTrader/3Commas/Bookmap 文档 |
| GitHub REST API via curl | ✅ 稳定 | 搜索仓库、获取 star/fork 数据 |
| awesome-quant README | ✅ 可拉 | 26.8k star 资源索引 |
| Reddit r/algotrading | ⚠ 需cookie | 浏览器直接访问被反爬，可用cookie或crawl4ai |
| Google 搜索 | ⚠ 需clash代理 | 直接访问触发CAPTCHA，走代理可避 |

### Brave Search 调用示例

```python
import requests
r = requests.get(
    "https://api.search.brave.com/res/v1/web/search",
    headers={"X-Subscription-Token": "<KEY>", "Accept": "application/json"},
    params={"q": "site:reddit.com r/algotrading backtest overfitting 2025", "count": 10},
    timeout=15,
)
results = r.json().get("web", {}).get("results", [])
```

### 有效社区调研路径

1. Brave API 搜索 Reddit/X/技术文章（主搜索源）
2. Exa API 语义搜索深度技术文章（补充）
3. web_extract 拉取官方文档全文（Freqtrade/NautilusTrader/3Commas/Bookmap）
4. GitHub REST API 搜索仓库
5. awesome-quant curated list
6. 既有 `references/community-recommendations-*.md` 档案
7. DDGS 兜底
