# MCP 数据服务器：扫描 → 实测 → 安装 → 接入闭环

适用：用户问「某某 MCP 目录上有没有能增强我们系统的」「把这个 MCP 接进来」。
MCP 与 skill 的区别在于**它会改工具目录、吃外部配额、把数据带进决策链**，所以比装 skill 多四道闸（见 SKILL.md 的「装 MCP 数据服务器」节），本文给具体做法。

## 1. 目录扫描（以 mcp.so 为例）

mcp.so 无公开搜索 API，用浏览器驱动它的 ⌘K 搜索框：

1. 打开 `https://mcp.so/zh/servers`，点顶部「搜索 MCP 服务器、工具、集成…」弹出对话框。
2. 输入框 selector = `input[placeholder*='MCP']`，**必须用 React 原生 setter 写值**（直接 `fill_input` 在二次输入时找不到元素）：

```js
(v) => { const el=document.querySelector("input[placeholder*='MCP']");
  const d=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el),'value');
  d.set.call(el, v); el.dispatchEvent(new Event('input',{bubbles:true})); return el.value; }
```

3. 读结果：`document.querySelector('[role=dialog]').innerText`（每次输入后等 ~3.5s）。
   搜索框是**模糊语义搜索**，单关键词最好；长短语（"gold commodity"）会 0 结果。
4. 分类全量清单走分页 URL：`https://mcp.so/zh/servers?category=finance-commerce&sort=popular&page=N`
   （金融与商务 325 条 = 6 页 × 60）。`?q=` 参数**无效**，会被忽略返回热门榜。
5. 详情页 `https://mcp.so/zh/servers/<slug>` 用 web_extract 能拿到「连接信息 / 传输方式 / 认证方式」，
   但**工具列表经常抽不全**（README 没有 `## Tools` 标题就为空）→ 一律以端点 `tools/list` 实测为准。

## 2. 还原连接方式：唯一硬证据

对每个候选直接发 JSON-RPC：`initialize` → `tools/list` → **真调一个工具拿真实数字**。

- 传输：Streamable HTTP → `POST <url>`，body `{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}`。
- 响应可能是 SSE，需按 `data:` 行解析。
- **Requests 必须带浏览器 User-Agent**，否则 Cloudflare 直接 403。
  （注意：这只影响自写探针；Hermes 自家 MCP 客户端不受影响，别据 403 判定「接不进来」。）
- 配额、延迟档、行数上限通常在 `my_access` 这类自省工具里，必查。
- 工具参数用 `tools/list` 的 `inputSchema` 取，**不要照抄详情页文案猜参数名**。

## 3. 认证与时效实测（不信自述）

**端点常分两个，凭证往往只能走其中一个**，装错端点会得到 401 并误判「key 无效」：

| 端点 | 用途 | 带 API key |
|:--|:--|:--|
| `https://coinlobster.com/mcp` | key 或 keyless 都走这里 | ✅ `X-API-Key:` 与 `Authorization: Bearer` 均可 |
| `https://coinlobster.com/mcp/connector` | 只给 OAuth 登录（客户端 connect-and-sign-in） | ❌ 401，**报错文案还会误导你「or send an API key in X-API-Key」** |

REST 面另算（`/api/ai/v1/...` 只要 `Authorization: Bearer`；`/api/public/...` 是 keyless 公开面）。

**证明「真的实时」的两条独立手段**（档位字段说 0 延迟不算数）：

1. 从响应自身时间戳算年龄：`as_of` / `updated_at` / `generatedAt` / 序列最后一点的时间。> 5 分钟即非实时。
2. 与 Binance 1m K 线对表：取它给的价，在 `fapi/v1/klines?symbol=BTCUSDT&interval=1m&limit=120`
   里找最接近的收盘价，那个 bar 的时间就是真实数据年龄。

**测试前先断言凭证存在**：凭证丢了请求会**静默降级成匿名档**，量出来的是匿名档的延迟，
足以得出完全相反的结论。匿名档有显式指纹 —— 响应里出现 `delayed: {minutes: 30}` +   
`access_note: "... without an account"`；带有效凭证时这两个字段消失。

## 4. 装进 Hermes

`hermes mcp add` 是**交互式**的，直连会挂住等 stdin：

```bash
printf 'n\ny\ny\ny\n' | hermes mcp add <name> --url "<endpoint>" --connect-timeout 20
```

- 第 1 问 `Does this server require authentication?` → keyless 填 `n`；OAuth 类填 `Y` 并配 `--auth oauth`。
- 末问 `Enable all N tools?` → `y` 保存；填 `n` → `Cancelled — server not saved`
  （**只连不存**，可用来零成本试连、判断能否接进来而不落配置）。
- 端点直连可用的**不要加** `HTTP_PROXY` env；只有境外被墙/被限流的源才加。

**`--auth header` 的密钥提示读不进去**：`API key / Bearer token` 用 `password=True` 读 stdin，
管道和 pty 都拿不到值（pty 实测空值过去，最后存成无 token 的配置，表面还显示 Connected）。
正确做法是**先种 `.env` 再跑 add** —— `_configure_http_auth()` 会先查 `get_env_value("MCP_<NAME>_API_KEY")`，命中即跳过提示：

```python
# 用 hermes venv python 跑，与 CLI 共用同一套写入逻辑
import sys; sys.path.insert(0, r"C:/Users/<user>/AppData/Local/hermes/hermes-agent")
from hermes_cli.config import save_env_value
save_env_value("MCP_<NAME>_API_KEY", "<token>")
```

env key 命名规则：`MCP_` + 服务名大写（非字母数字转 `_`） + `_API_KEY`。写完再跑 add，
会看到 `MCP_<NAME>_API_KEY: already configured`，并落盘 `headers: {Authorization: Bearer ${MCP_<NAME>_API_KEY}}`。

**验三层，缺一层都不算装好**：

| 层 | 命令 |
|:--|:--|
| 配置层 | `hermes mcp list` 出现该 server 且 `✓ enabled` |
| 连接层 | `hermes mcp test <name>` → `✓ Connected` + 工具数 |
| 会话层 | `hermes chat -q "调用 <name> 的 <tool> 查 XXX"` → 真返回实时数字 |

新 CLI 会话启动即读新配置；**已在跑的网关会话**要 `/reload-mcp`。

**工具数是选型硬约束**：大工具集直接装会污染工具选择（参见本 skill 的 FinanceMCP 记录：
17 个工具 13 个死工具）。优先「工具数 ≤ 10 且稳定可用」的；大工具集必须**免费档就能跑通全部工具**
才装；装完用真实查询验一次，不通的工具要么禁用（`hermes mcp configure`）要么撤掉。

## 5. 接入管线：collector + 五态 + 配额预算

**不现场调工具，写成 collector**（本系统既有约定：一源一 collector，见 `scripts/stablecoin_collector.py` 范式）：

- `scripts/<source>_collector.py`，`from source_contract import write_source_artifact`
  → `~/AppData/Local/hermes/data/<source>_snapshot.json`，带 `_source_status` / `_source_timestamp` / `_source_cached` 信封。
- 凭证从 env 读，**缺失时回落 `~/AppData/Local/hermes/.env`**（cron 环境没有 env 变量）。
- 直连优先，失败回落本地代理；带浏览器 UA。
- 401/403/429 立即返回不重试（重试只会烧配额），其余网络异常可回落代理。
- 全失败：保留上一次 payload 并标 `unavailable` + `cached=true`，**绝不冒充实时**。
- 内置两个开关，供不同调用方：
  - `--profile core|full`：core 只采真正要接进管线的那几格（省额度），full 按需深采。
  - `--if-stale-minutes N`：工件未过期直接跳过并 exit 0，**不消耗额度** —— 分析入口按需调用的正确姿势。

**先算配额再定频率**（免费档实测 200 次/日）：

| 用法 | 算术 | 结论 |
|:--|:--|:--|
| full（6 次/轮）挂 `*/10`（照抄现有清算刷新频率） | 6 × 144 轮 | ❌ 超支 4.3 倍 |
| core（2 次/轮）挂 `9,29,49`（**避开** TV 租约任务的 `7,27,47`） | 2 × 72 轮 | ✅ 144 次/日，留余量 |
| 分析入口调 `--if-stale-minutes 10` | 一天 30 次分析 | ✅ ≤ 180 次/日 |

**已落地实例**（CoinLobster，2026-09-16）：`scripts/coinlobster_collector.py` +
`scripts/coinlobster_refresh.py`（no_agent 入口，默认 core + 8 分钟防重跑）；cron 任务 id `3cb9786b5494`，
`9,29,49 * * * *`，`--no-agent --deliver local --script coinlobster_refresh.py --workdir "D:/Hermes agent"`。

**额度必须提前入账（2026-09-16 实测教训）**：免费档 200 次/日被 cron（core 2 次/轮 = 96/日）
加按需深采（full 6 次/轮）吃满后，之后每一轮都 429，而旧实现按 exit 1 上报 →
**每 30 分钟铸一条 cron incident 并把 `audit_preflight` 的 Cron策略 拖红**，看起来像“源坏了”。
现在：429 带 daily 字样（`code -32029` / `Daily limit reached`）→ `quota_cooldown` +
`data/.coinlobster_quota_breaker.json` 冷却到次日 00:05 + **exit 0**；另有当日额度记账
（`COINLOBSTER_DAILY_BUDGET`），剩余不够一轮计划时按顺序保核心格，跳过项写进工件 `skipped_tools`。
**接入任何带日额度的 MCP 源时先把这件事做了**：估算“cron 频率 × 每轮调用”是否 < 额度，
否则第一天白天就会打满。

cron 装配坑：

- `--script` 写 `workdir/scripts/` 下的**裸文件名**；本机 `~/.hermes/scripts/` 与仓库 `scripts/`
  是**同一个目录**（inode 相同），脚本放仓库里即生效。
- **不要和 TV 租约敏感的 job 同分钟**。首建时挂在 `7,27,47`（与 btc_tv_refresh 同分钟），
  已错到 `9,29,49`；同分钟并发会拉紧 TV 刷新任务的时限。
- 验证要三层：job 落盘 → `hermes cron run <id>` 真跑一次 → 工件信封 `_source_status` +
  `_source_timestamp` 是刚写的。只看 `hermes cron list` 显 ok 不算验过。
- 降级不算故障：单工具失败仍 exit 0（写 `partial_errors` / `degraded_tools`），只有全部不可用才 exit 1；
  否则单源抖动会被 Cron 记成 incident 噪声。

**字段口径坑（同一源内部就会骗你）**：

- `lending_liquidations`（链上借贷清算）与 `perp_liquidations`（永续强平）是**两条车道，任何统计都不许相加**。
- `funding_matrix` 各所 `interval_h` 不同（1h/8h），**必须归一化到 8h 才能横向比较与排序**。
- 免费档 `whale_radar` 只给 BTC 全深度，其余币种仅方向且 `blurred=true` → 只能提示「存在异动」，**不许报数字**。
- `market_snapshot` 的 `stats_24h` 块会滞后（带 `stats_age_minutes` 与说明），价格实时 ≠ 24h 统计实时，引用时要分开口径。

**采集器自身的两个假绿陷阱（都踩过）**：

- **上游「调用成功但空数据」必须显式登记降级**。`funding_matrix` 会间歇性返回
  `{"pair":"BTC/USD", "available":false, "note":"No funding matrix for this pair right now."}` ——
  JSON-RPC 没错，但内容为空。只按「调用是否报错」判定会写出 `_source_status: live` 而字段是空的，
  **假绿**。做法：shape 阶段检查 `available is False` / 关键数组为空 → 写 `degraded_tools` 并打印，
  与「调用失败」分列。
- **未纳入本轮 profile 的工具必须整块跳过**：用 `raw.get(tool)` 而**不是** `raw.get(tool) or {}`，
  否则 core profile 会把「没采」误报成「采空」（whale_radar 会被假报 `empty_windows`）。

**读侧与采集侧是两个维度，不许混用**（这是接入最后一公里最容易错的地方）：

| 字段 | 谁写 | 含义 | 阈值 |
|:--|:--|:--|:--|
| `usable_as_live` | 采集时写死 | 采集当刻上游数据是否实时 | 上游延迟 ≤ 5 分钟 |
| `state` | 消费时判定 | 工件采集距今多久 | 新鲜 ≤ 25 分 / 陈旧 25–90 / 不可用 > 90 或缺失 |

- 读侧函数必须**纯文件读、不发网络请求**（渲染器里不能插网络 I/O）：
  `coinlobster_collector.read_state()` / `read_evidence(symbol)`。陈旧态照样给数，
  但**必须带读数年龄**（「工件 32 分前·仅背景」）；不可用返回空串不占位。
- 阈值要跟 cron 周期对齐：cron 20 分钟一轮 → 读侧新鲜线取 25 分钟。
  若拿采集侧的 5 分钟当读侧线，卡面会一半时间误报陈旧。
- 卡面落点：`render_v96` ③ 多源表新增一行（参 `_liquidation_line` 的三态写法），
  裁决列写「背景/反证·非执行授权」；**只服务该源真实覆盖的品种**，
  其它品种返回空串，绝不拿 BTC 的数据冒充 ETH/XAU。
- 路由与守护注册三处：`pipeline_router.CRON_SOURCES[资产]` + `CRON_SOURCE_FILES`
  （源名 ≠ 文件名时必加）+ `CRON_SOURCE_MAX_AGE`（与产物 TTL 对齐，否则完成度表每轮误报）。
- **只覆盖部分品种的源必须注册进按品种表（`CRON_SOURCES_BY_SYMBOL`），不能进资产类别通用清单** ——
  否则分析没被覆盖的标的时会显示「已消费该缓存」，等于拿 BTC 的数据冒充别的币。
  加进任何注册表前先 `grep -rn "CRON_SOURCE" tests/`：既有测试会精确断言这些清单，
  改注册表必然牵动它们 —— 红了先判是「测试该更新」还是「注册位置本身就错了」。
- 测试锁住三态：新鲜/陈旧（必须带年龄）/超龄不可用 + 缺失 + 信封非 live + 非目标品种不许冒充。

## 6. 合同分级与审计闭环

接入一个会进决策链的数据源，**必须落在合同里**，否则以后会被误用成执行信号：

1. `docs/指标驱动分析与策略合同.md` → 新增/更新「外部验证层」节：能做/不能做对照表 +
   四条口径（绝不现场调工具、延迟实测不信自述、口径隔离不许混算、降级可见）；
   同时在 §一 总原则表加一行、在档位表与验收清单各加一条，避免只写一节而入口没吃。
2. 跑两个审计，**都要过**：
   ```bash
   python scripts/indicator_source_audit.py   # 指标源码哈希 vs 合同
   python scripts/audit_preflight.py          # 运行态/数据身份/新鲜度/cron
   ```
3. 审计红了先**证明归属**再动手：`git status --short` 看工作区未提交改动 + 看目标文件 mtime。
   工作区里的未提交改动可能正被别人改，**不要覆盖**，如实报「既有问题 + 证据」交给对应链路。

## 7. 已实测候选（2026-09 复核，本机）

| 服务器 | 端点 | 认证 | 实测 | 判定 |
|:--|:--|:--|:--|:--|
| **Coinfuty** | `https://mcp.coinfuty.com/api/mcp` | 无 | 直连 0.6s，7 工具，实时（BTC 报价 vs Binance 差 0.05%） | ✅ 已装 |
| **CoinLobster** | `https://coinlobster.com/mcp` | 免费 key | 54 工具；**带免费 key = 实时 + 200 次/日 + 独享 60/min**，深度上限不变 | ✅ 已装 |
| Unquant（Streetbeat） | `https://unquant.ai/mcp` | 无（匿名免费档） | 28 工具：宏观日历/指标、新闻+影响评分、美股基本面、**美国国会议员交易披露**；延迟/EOD | ⏸ 备选 |
| CryptoQuant | `https://mcp.cryptoquant.com/mcp` | API key / OAuth | initialize 401 | ❌ 需付费 key |
| Swiss Whale Intelligence | `https://mcp.swisswhaleintelligence.com/mcp` | OAuth 2.1 | initialize 401；免费档 24 工具 / **10 次/日** | ❌ 配额太小 |
| ApexVol Options | pipx / remote | 付费 ApexVol 计划 | 43 工具（IV rank/VRP/GEX），美股期权 | ❌ 付费且非加密 |
| Depthy | `pip install depthy-mcp` | 免费 key（depthy.io） | Polymarket 聪明钱 + Hyperliquid 盘口深度/清算簇 | ⏸ 待评估 |

**明确不装**：Trading Economics 日历（与 jin10 日历重复）、各类 x402 微支付源（记账成本）、
DeFi/土狗/发币类、接非币安券商的下单 planner（用户手动交易）。

CoinLobster 付费档解锁点（决定要不要花钱时看这张表，别只看价格）：

| 档 | 价 | 真正解锁的 |
|:--|:--|:--|
| 免费 key | $0 | 实时 + 200 次/日 + 独享限速；**深度上限一行不放开** |
| Starter | $9/月 | 所有币种全深度、DEX 换手门槛归零、告警位 |
| Pro | $29/月 | `squeeze_score` 拥挤度、`liq_zones` 级联链、whale_flow 分所分钱包 |
| Alpha | $99/月 | 再加具名钱包名单 |
