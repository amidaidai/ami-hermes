# 可用性审计：skill / MCP / API 三面清单（2026-09-13 建立）

> **本文件已按修复后状态更新（2026-09-13 晚，commit `498c4db`）。**
> 初次审计发现的 P0/P1 已全部处置，下方每节标了「现状」。
> 下次审计请直接重跑六个扫描器并与本节基线 diff，不要从头找问题。

触发：用户问「我们有哪些不可以用的」「哪些 skill/mcp/api 坏了」。

**核心纪律：三类资产各有一套「连上 ≠ 能用」的陷阱，必须逐层实测。**

| 资产 | 容易误判为「可用」的表象 | 真实判据 |
|---|---|---|
| MCP | `hermes mcp test` 报 `✓ Connected` + `Tools discovered: N` | **实际调一次代表工具**，看返回是数据还是 `error` |
| Skill | `hermes skills list` 显示 `enabled` | 扫**正文**引用的脚本/凭证是否存在（frontmatter 声明覆盖率极低） |
| API | HTTP 200 / 有响应 | 校验 **body 里的 code/msg**（`HTTP 200 + code 401 "Upgrade plan"` 是常见伪装） |

## 六个可重跑扫描器（`scripts/maintenance/`）

```bash
cd "D:/Hermes agent"
python scripts/maintenance/api_source_health_probe.py    # 22 个数据源逐条真实调用 + 落盘基线自动 diff
python scripts/maintenance/mcp_proxy_check.py             # MCP 代理两层守卫（配置层 + 运行层）
python scripts/maintenance/mcp_stale_proxy_reaper.py      # 清理「无代理环境」的 MCP 进程树
python scripts/maintenance/skill_dependency_audit.py      # frontmatter required_* 校验
python scripts/maintenance/skill_body_dependency_audit.py # 正文里的凭证/命令依赖
python scripts/maintenance/skill_broken_ref_audit.py      # 正文引用的本地文件是否存在（三桶分类）
python scripts/maintenance/annotate_missing_refs.py [--apply]  # 未落地参考文档就地标注（幂等）
```

配套测试：`tests/test_credential_placeholder_guard.py`、`tests/test_massive_rolling_window.py`。

## 2026-09-13 实测结论（基线，供下次 diff）

### MCP（9 个全部 enabled）

| 服务器 | 连接 | 功能实测 |
|---|---|---|
| binance | ✓ | ✓ `get_price`=76695 / `get_account_summary` 鉴权通过 |
| **financekit** | ✓ | ✅ **已修**（2026-09-13）：Yahoo 类工具曾全部 429/403，根因=运行进程缺 `HTTP_PROXY`（配置层已对）。经 `/api/hermes/mcp/reload` + 清理陈旧进程后，`stock_quote`=332.27、`market_overview`（4 指数 + VIX 15.84）均恢复 |
| jin10 | ✓ | ✓ 重连后 `get_quote`=XAU 4348 / `list_calendar` 正常（首调曾遇子进程 dead） |
| stock-api | ✓ | ✓ `get_stock` SH510500 返回腾讯源数据 |
| tradingview | ✓ | ✓ CDP 连通，图 `BINANCE:BTCUSDT.P` 15m |
| hermes-studio-api/use/browser/devices | ✓ | ✓ 工具发现正常 |

### API（22 项）—— 已建立基线，可用基线 diff 监测回归

- **live 18**：Binance 公开/私有、CoinGecko、CMC、Massive(股票日线)、AlphaVantage、TwelveData、FMP、Tushare(分接口)、Dune、Polymarket、Tavily、Brave、Exa、Firecrawl、Metaso、Jin10 端点、x_search
- **plan_or_auth 2**：Coinglass（`HTTP 200 + code 401 "Upgrade plan"`，且系统未使用）、Massive 期货快照（不再被截断成不可诊断的 JSON 尾巴）
- **unconfigured 1**：OANDA —— ✅ **已加根因守卫**：`credential_store` 识别说明性占位符并判为未配置，三处消费方统一委托（详见下节）
- **unavailable 2**：Felo（端点只剩 `{"Hello":"World"}` 占位）、AnySearch（DNS 不通 / SSL EOF）。**两者系统均未引用**，不删密钥、只备案

### Skill（343 个 SKILL.md，enabled 205 / disabled 124）—— ✅ 已全部处置

真·不可用（正文让你跑的文件不存在）：

| 技能 | 原缺失 | 处置 |
|---|---|---|
| `options-strategy-advisor` | 7 个文件全缺（含 `scripts/black_scholes.py`） | ✅ **已补齐三个脚本 + 方法论文档**，按 SKILL.md 承诺的 CLI 实测通过 |
| `backtesting-suite` | `scripts/walk_forward_v2.py` | ✅ 标注为设计稿，指向 `backtest_runner_v2.py` / `regime_backtest.py` / `_disabled/walk_forward.py` |
| `market-regime-classifier` | `scripts/regime_classifier_v2.py` | ✅ 标注 9 体制为设计稿，指向线上真实分类器 `decision_regime.py` |
| `trading-card-generation`、`crypto-multisource-analysis`、`tradingview-indicator-analysis` | `scripts/render_v8.py` | ✅ 全部改为 `render_v96.py` |

另：**37 处**「引用了但从未落地」的 `references/*.md` 已就地标注（不编造内容）。

环境依赖：`python3` 已补齐（venv 内 `python3.exe`）→ 解封 6 个技能；
`docker` 缺（`serving-llms-vllm`）、`jq` 缺（`claude-code`）仍存在，但与本系统主业无关。

### 附带发现的正确性问题（比「不可用」更危险）—— ✅ 已修

`massive_aggs()` 的日期曾经是**硬编码的**（`scripts/multi_source_collector.py` 写死
`from_="2026-06-17", to="2026-06-18"`），即无论何时调用都返回 2026-06-18 那根日线。
这类「有数据、格式合法、但日期陈旧」的源比报错的源危险得多 —— 看门狗和卡面都不会拦。

**现状**：已改滚动窗口（`MASSIVE_WINDOW_DAYS=14`）+ 载荷带 `as_of`/`stale_days`，
超 `MASSIVE_MAX_AGE_DAYS=5` 额外带 `_stale`。实测回到 2026-09-11（close 332.27，
与 financekit 实时报价一致）。回归锁在 `tests/test_massive_rolling_window.py`。

---

## financekit 代理问题（2026-09-13 完整因果链）

症状：`stock_quote('AAPL')` / `technical_analysis` / `market_overview` 全报
`Too Many Requests. Rate limited.`，而 `crypto_price`（CoinGecko）正常。

因果链（全部实测，非推测）：

1. 对照实验：同一个 Yahoo 请求，**直连 HTTP 403 封锁页 / 走代理 HTTP 200 AAPL=332.27 0.5s**
2. `mcp_proxy_check.py`：配置层 `config.yaml` 有代理 ✓，但**6 个运行中的 financekit 进程 env 里没有 HTTP_PROXY**
3. 结论：配置已改、**运行进程没重读**。
4. **实际施行的修法（比手工敲命令更可复现）**：
   · `POST /api/hermes/mcp/reload`（Hermes Studio Web UI 的 MCP 桥，端口 8748）→ 新生进程带上代理；
     也可经 `hermes_studio_api_request` 工具调用（curl 直调会 401，认证在 MCP 服务器侧）；
   · 再跑 `mcp_stale_proxy_reaper.py` 清掉 reload 前启动的陈旧进程树（客户端下次用时自动重连）。
   · 复测：`stock_quote('AAPL')`=332.27、`market_overview` 四指数 + VIX 15.84 均恢复。

附带观察：
- financekit 子进程启动时试图绑 **8748**，而该端口被 `Hermes Studio.exe` 占着（错误 10048）。不致命（stdio 仍工作），但知道就好
- 含 `financekit` 字样的进程一度达 **30 个** —— 多表面（CLI/网关/Studio）各自 spawn，属进程堆积

判据沉淀：**「服务里失败、手动却成功」时，第一步永远是比对两者的运行环境（代理/env/cwd/解释器），
不要先归因「进程内部状态陈旧」。**（同族见 SKILL.md 的「诊断环境错配」一节）

---

## 状态与数据不一致：两个新坑 (2026-09-13 · 卡面暴露)

跑一次真实卡面（`python scripts/auto_card.py BTCUSDT`）才发现的两类问题 ——
**单看数据源扫描器是发现不了的，必须看输出层。**

### 坑一：活数据被判 unavailable（timestamp 键名错配）

`cmc_quote` / `cmc_global` 返回的行情**完整且实时**，但时间戳键是 CMC 的 `last_updated`，
而契约 `TIMESTAMP_KEYS` 只认
`(updated_epoch, updated_at, timestamp, ts, time, updated)`
→ `payload_timestamp()` 返 None → 列入 `unavailable(missing_timestamp)`。

**后果**：一份活数据在多源验证表里常年显红 —— 这是另一种“静默”—— 降级噪声掩盖真降级。
**修法**：把同一个 `last_updated` 同时挂到契约认得的 `updated_at`。
实测（**要先踢掉 120s 缓存**）：两个采集器 `unavailable → live`。
**测试**：`tests/test_source_contract_timestamps.py` 锁死「接线进契约的采集器必须可被解析出时间」。

> 通用判据：接入任何新采集器时，先问一句「它的时间戳键在 `TIMESTAMP_KEYS` 里吗」。
> 不在就一定被判 unavailable，而且因为数据看着是好的，极难被发现。

### 坑二：卡片文案把「档位设计跳过」与「采集失败」混为一谈

旧输出里同一句「本轮未采到有效字段（来源未路由或失败）」同时覆盖两种截然不同的情形：
quick 档**按设计**不跑 macro/cg_pro 步，和采集真的挂了。读者无法区分。
“失败必须可见”不等于“让正常降级也看上去像故障” —— 噪声本身就是一种不可见。

**修法**：沿用系统已有的 `⏭️ … 当前档位跳过（需 xx 步）` 约定标记设计跳过，
仅在真失败时用 ⚠️ 并加「需查源」。已统一到恐慌贪婪 / CoinGecko Top10 /
Trending / 宏观四处。

**验收方式**：跑 `python scripts/auto_card.py BTCUSDT` 看输出行，并确认管线仍 N/N 完成。

### 附带确认（非缺陷）

- `risk_state.json` 断在 2026-07-15：生产者 `risk_state_reconcile.py` 要求**人工显式输入**
  真实余额/当日盈亏，不是自动采集器 → 需用户提供数字，不是坏了。
- `cg_quota` 熔断残留（2026-09-02）：熔断逻辑比较 `blocked_until > time.time()`，
  过期条目不会拦截，只是状态文件不干净。

---

## 【安全】终端会话快照明文泄露凭据 (2026-09-13 发现)

**现象**：`~/AppData/Local/hermes/cache/terminal/hermes-snap-*.sh` 里有明文密钥。
实测每个快照含 **13 个凭据值**（`BINANCE_SECRET_KEY`、`TWITTER_AUTH_TOKEN`、
`POLYMARKET_RELAYER_API_KEY`、`BRAVE_API_KEY`、`AUTH_TOKEN` …）。

**根因链（逐层实测，非推测）**：

| 层 | 事实 |
|---|---|
| 写出 | `hermes-agent/tools/environments/base.py:373` 执行 `export -p > hermes-snap-<sid>.sh`，把**整个登录 shell 环境**写盘，**此路径无任何脱敏** |
| 脱敏 | `HERMES_REDACT_SECRETS=true` 确实开着，但 `agent/redact.py` 只管**文本**脱敏（工具输出/日志），不覆盖 shell 快照 |
| 剥离 | `_sanitize_subprocess_env`（local.py:586）只挡两份名单：**LLM 供应商密钥**（`_HERMES_PROVIDER_ENV_BLOCKLIST`）+ **Hermes 自身密钥** |
| 缺口 | Telegram/Discord/Feishu bot token、BINANCE/GitHub/搜索/钱包 relayer —— 都是「**用户服务密钥**」，不在两份名单里 → 原样进终端环境 → 落盘 |
| 向量 | `~/.hermes/.env` → Hermes 进程 env → 终端登录 shell。**不是**技能声明的（扫了 351 个技能，0 个声明这些变量），也**不是**用户配置（`terminal.env_passthrough` 本就为空） |

**为何没有干净的配置开关**：唯一扩展点 `agent/terminal_env_registry.py` 要求注册一整个
`TerminalEnvironmentProvider`（自定义终端**后端**），拿它只为了剥几个 key 是滥用。
→ **正解在上游**（两个方向：给 `export -p` 路径加脱敏，或扩充内置剥离名单）。

**当前处置**：`scripts/maintenance/scrub_terminal_snapshots.py`

```bash
python scripts/maintenance/scrub_terminal_snapshots.py          # 预演
python scripts/maintenance/scrub_terminal_snapshots.py --apply  # 落盘
```

· 把 `declare -x NAME="值"` 改为 `declare -x NAME=""`（保变量名 → 快照仍可 source，**不打断会话**）
· 只报键名，**绝不打印值**
· 两个易错点已处理：**不能清 `HERMES_REDACT_SECRETS`**（清掉等于关掉脱敏，更糟）；
  `*_API_BASE`/`*_ADDRESS`/`HERMES_*` 属端点/地址/内部开关，不动

> ⚠️ **这是一次性清理**：每条新会话都会重建快照。发现后应定期重跑，
> 并把上游修复当作真正的收口。

### 附带结论（避免误判）

- 那些无代理 financekit 实例来自**启动于配置变更之前的宿主会话**：
  配置之后启动的宿主（如重启后的 gateway、新会话）都会带上代理 ——
  已验证：gateway 重启后新宿主 带代理✓。所以问题会自然收敛，不需无休止 reap。
- `hermes gateway restart` 是本系统里**唯一可安全重启的客户端**（官方命令，
  drained cleanly）。**Hermes Studio 不行** —— 本会话就跑在它的进程树里，
  杀掉等于自尽且报告送不回来。需要重启 Studio 时应交给用户执行。

---

## 凭据占位符：另一类「看起来配置了」 (2026-09-13)

事故：`hermes/secrets/oanda_token.txt` 实际是**说明性占位符**（注释 + `PLACEHOLDER_REPLACE_WITH_REAL_TOKEN`），
但 `trading_system.py::oanda_spot_price` 裸读后拿去拼 URL → `InvalidURL: URL can't contain control characters`
→ 被 `except Exception: return None` 静默吞掉。**表象是「OANDA 不可用」，真相是「从未配置」。**

修法（类级，不只修实例）：`scripts/credential_store.py` 新增统一守卫

| 判据 | 命中含义 |
|---|---|
| 逐行跳过注释（`#` `//` `;`）与空行后无剩余 | 整份就是说明文 |
| 首条有效行匹配 `PLACEHOLDER/TODO/CHANGEME/YOUR_/<...>/XXX` | 显式占位符 |
| 有效行含 CJK **且无** ≥8 位 ASCII 串 | 中文说明散文 |

配套两个易错点（已锁在测试里）：
1. **取值要剥注释** —— 把「注释 + 值」整份当 token 会污染 `Authorization` 头；
   正确行为是返回首条有效行（`.json` 等结构化格式除外）。
2. **防误杀优先** —— 中文注释 + 真 key、`.json` 结构化凭据都必须仍可用；
   当前的 24 个真密钥逐个复测全部仍可取到值（`oanda_token.txt` 是唯一命中项）。

消费方接线：`trading_system.oanda_spot_price`、`multi_source_collector._read_secret`、
`xau_ohlcv_source._read_secret` 统一委托（后两者走 `read_secret_file(SECRETS / name)`，
以保留各自目录变量**可被测试 monkeypatch** 的能力 —— 直接换成模块级 `read_secret`
会静默破坏 `tests/test_xau_ohlcv_source.py`，已踩过）。

> 注：`xau_ohlcv_source` 早先**自带**一套占位符告警，当时确实是对的——
> 审计中曾误以为它会被占位符骗过，逐行核实后才推翻。**逐条验证风险，不要靠模式识别断言。**
> 代价对比：修真实例只能治一个点，建统一守卫才能防下一个 `xxx_token.txt`。
