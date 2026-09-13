# MCP 子进程环境变量白名单 与「诊断环境错配」陷阱（2026-09-13 取证）

> 这是一次**自己打脸**的完整取证链：上一轮把「长命进程 stale」当成根因并宣布已修复，
> 下一轮实测发现完全没修好。真正的根因是**诊断命令与目标进程的环境不同**。

## 1. 症状

`financekit` MCP 的 Yahoo 类工具（`stock_quote` / `market_overview` / `price_history`）
持续返回：

```
Failed to fetch quote for 'AAPL': Too Many Requests. Rate limited. Try after a while.
```

而 `crypto_price`（CoinGecko 腿）正常。
错误串来自 `yfinance/exceptions.py` 的 `YFRateLimitError` —— 但它**不代表 Yahoo 真的在限流你**。

## 2. 决定性对照实验

同一个调用，只改代理环境：

| 走法 | 命令 | 结果 |
|---|---|---|
| 直连 | `env -u HTTP_PROXY -u HTTPS_PROXY uvx --from financekit-mcp python -c "from financekit.providers.yahoo import get_quote; print(get_quote('AAPL'))"` | ❌ `Too Many Requests. Rate limited.` |
| 走代理 | `HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 uvx --from financekit-mcp python -c "…同上…"` | ✅ `332.27` |

同时排除了这些**看似合理但错误**的假设：

| 假设 | 实测 | 判定 |
|---|---|---|
| Yahoo 封了整个 IP | 裸 `curl` 到 `query1.finance.yahoo.com/v8/finance/chart/AAPL` 走代理 → `HTTP 200` + 正常 JSON | ✗ |
| yfinance 版本问题 | financekit 环境 1.7.0 / 本机 venv 1.4.1，两者在**有代理**时都成功 | ✗ |
| 代码路径问题 | 生产路径 `financekit.providers.yahoo.get_quote` 新进程成功 | ✗ |
| 进程 stale（**上一轮的结论**） | 杀光 6 个 financekit/uvx 进程 → 网关重新生成 → **仍然 429** | ✗ |

## 3. 真根因：子进程 env 被白名单过滤

`tools/mcp_tool.py::_build_safe_env()` 给 stdio MCP 子进程构造环境时**只放行白名单变量**：

```python
for key, value in os.environ.items():
    if (key in _SAFE_ENV_KEYS
        or key.upper() in _SAFE_ENV_KEYS_CASE_INSENSITIVE
        or key.startswith("XDG_")
        or (get_secret_source is not None and get_secret_source(key))):
        env[key] = value
if user_env:
    env.update(user_env)      # ← 只有该 server 的 env: 块能进来
```

设计意图是防密钥外泄，副作用是 **`HTTP_PROXY`/`HTTPS_PROXY` 这类网络变量也被挡掉**。
所以：网关（或终端）自己有的代理，永远进不了 MCP 子进程 —— 必须在
`mcp_servers.<name>.env` 里显式写（`env.update(user_env)` 在过滤之后，优先级最高）。

## 4. 上一轮为什么会得出错误结论

终端里跑诊断命令时，shell 自带 `HTTP_PROXY=http://127.0.0.1:7897`：

```
终端进程   → 有代理 → "uvx 直跑 yfinance 成功" ← 这个成功是代理给的，不是真相
MCP 子进程 → 无代理 → 一直 429，重启多少次都一样
```

于是形成「杀进程好像修好了 → 过一会又坏」的假象，真凶始终没被碰到，
而且把错误结论写进了技能和记忆（已更正）。

## 5. 通用判据

> **当「服务里失败、手动命令行却成功」时，第一件事是比对两者的运行环境**
> **（代理 / env / cwd / 解释器 / 工作目录），不要先归因「进程内部状态陈旧」。**

```python
# 比对本进程 env 与目标进程 env（psutil 可读同用户进程的 environ）
import psutil, os
KEYS = ('HTTP_PROXY','HTTPS_PROXY','NO_PROXY','ALL_PROXY','SSL_CERT_FILE')
print('本进程:', {k: os.environ.get(k) for k in KEYS if os.environ.get(k)})
for p in psutil.process_iter(['pid','name']):
    if 'financekit' in (p.info['name'] or '').lower():
        e = p.environ()
        print(p.info['pid'], {k: e.get(k) for k in KEYS if e.get(k)} or '⚠️ 无代理')
```

同族陷阱（都是「探针环境 ≠ 被测环境」）：

- 在 venv 里跑测试，而 cron/服务用的是另一个解释器（双 Python）。
- 在仓根跑 `python -c`，`sys.path` 命中仓根同名副本而非 `scripts/` 里的真模块（模块遮蔽）。
- 用 `bash` 跑脚本而生产用 `cmd`/PowerShell。

## 6. 修复（已落地并端到端验证）

```bash
# patch 工具拒绝写 ~/.hermes/config.yaml（安全护栏），只能用官方命令；点号路径支持嵌套
hermes config set mcp_servers.financekit.env.HTTP_PROXY  "http://127.0.0.1:7897"
hermes config set mcp_servers.financekit.env.HTTPS_PROXY "http://127.0.0.1:7897"
hermes config set mcp_servers.financekit.env.NO_PROXY    "localhost,127.0.0.1"
hermes config get mcp_servers.financekit.env      # 读回确认
```

**端到端验证**（不看配置文件，看真实调用）：

```bash
hermes chat -q "调用 financekit 的 stock_quote 查 AAPL，只回复一行：AAPL=<价格>"
# → AAPL=332.27 ✅（新进程读新配置，绕开网关的旧 env）
```

### 生效需要「重读配置」——这就是第二个陷阱

**「改了配置文件」≠「运行中的进程变了」。** 网关只在启动或显式 reload 时读配置：

| 层 | 验什么 | 做法 |
|---|---|---|
| 配置层 | `mcp_servers.<name>.env` 有代理 | `hermes config get mcp_servers.<name>.env` |
| 运行层 | **在跑的进程** env 真有代理 | `python scripts/maintenance/mcp_proxy_check.py` |

实测：改完配置后网关重新生成的 6 个 financekit 进程**依然没有代理** →
说明网关按启动时载入的配置生成子进程。

- 网关**没有** mcp_servers 自动重载 watcher（`cli.py` 有「config watcher → auto-reload MCP」，
  `gateway/run.py` 只有显式的 `/reload-mcp` 处理器）。
- 生效方式：**在网关会话里发 `/reload-mcp`**（比 `hermes gateway restart` 安全：
  重启网关会打断正在进行的会话，`/reload-mcp` 不会）。

## 7. 回归守卫

`scripts/maintenance/mcp_proxy_check.py`（2026-09-13 落地，**只读**，不改配置不重启进程）：

- ① **配置层**：`NEEDS_PROXY` 名单里的 server 是否配了 `HTTP_PROXY`/`HTTPS_PROXY`；
- ② **运行层**：名字匹配的**在跑进程** environ 里是否真有代理 ——
  报 `live_process_without_proxy` 就是「配置已改、网关没重读」。
- 无进程运行时报「不可验证」而**不报失败**（没跑 ≠ 配错）。
- 写 `data/maintenance/mcp_proxy_check.json`；退出码 0/2。
- 配 14 条测试（`tests/test_mcp_proxy_check_20260913.py`），含「对本机真实 config.yaml 的软检查」——
  本机若把 financekit 的代理删掉，测试直接红。

**推广判据**：凡是「配置驱动 + 长命进程」的组合（MCP server、cron 脚本、守护进程），
守卫都要**同时**查配置层和运行层；只查配置层的守卫会在「配置对了但没生效」时误报健康。

## 8. 边界：只有境外源需要

| server | 目标 | 需要代理 |
|---|---|---|
| `financekit` | Yahoo（行情/宏观/期权）+ CoinGecko | ✅ 需要 |
| `binance` / `jin10` / `stock-api` | 币安 / 金十 / 腾讯等国内可达源 | ✗ 直连即可 |
| `tradingview` / `hermes-studio-*` | 本机 CDP / localhost | ✗ 绝不要加 |

不要「顺手给所有 MCP 都加上代理」—— 本机回环目标走代理会引入无谓故障面。
