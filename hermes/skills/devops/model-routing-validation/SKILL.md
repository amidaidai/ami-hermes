---
name: model-routing-validation
description: "Use when choosing or auditing Hermes analysis models."
version: 1.0.0
---

# Model Routing Validation

Use this skill when the user asks which Hermes model is best, whether a fallback chain works, whether MoA is active, or whether a model is suitable for TradingView/market analysis.

## Core rule

Recommend from runtime evidence, not model names, parameter counts, catalog entries, or the presence of a config stanza. Maintain five distinct states:

1. **Configured** — model/provider appears in the active profile config.
2. **Credentialed** — a credential entry exists; this is not proof of successful authentication.
3. **Reachable** — a real request succeeds.
4. **Tool-capable** — a real request successfully invokes a required tool and consumes its result.
5. **Actually routed** — the live default, fallback, auxiliary, delegation, or MoA path selects it.

Only states 3–5 support a current operational recommendation. State 1 or 2 alone is a candidate, not a working model.

## Audit procedure

1. Load `hermes-agent` guidance when changing Hermes configuration. Read the active profile config path with `hermes config path`; never print secrets.
2. Inventory `model`, `fallback_providers`, `delegation`, `auxiliary.vision`, and `moa` sections. Explicitly determine whether the active main route is a direct provider or `moa:<preset>`.
3. Probe the primary and every fallback independently with a real short request. Record provider, model, success/failure, and whether fallback continued. Do not collapse authentication, protocol, timeout, and model-not-found into one generic unavailable label.
4. Probe the primary with a real tool call when the workload requires terminal, browser, TradingView MCP, or data tools. A text `OK` probe does not prove tool calling.
5. Enumerate what the user **actually has** per credential channel before comparing candidates: per-provider `/models` (DeepSeek `GET https://api.deepseek.com/models`; xAI `GET https://api.x.ai/v1/models` with the OAuth access token from `auth.json`; Codex from `~/.codex/models_cache.json`), plus `auth.json` → `credential_pool` (which providers even carry a credential) and `providers.<name>.last_auth_error` (`relogin_required: true` = that login is dead). A provider declared under `config.yaml providers:` with no usable credential is not a channel.
6. Prove **paid capacity separately from free capacity**: OpenRouter returns 403 on paid models while `:free` still works when the key's own spend limit is exhausted — check `GET /api/v1/key` (`limit`/`limit_remaining`) and `GET /api/v1/credits` (account balance) as two different facts.
7. For visual market analysis, use a real TradingView screenshot fixture with an **external ground truth** (recipe in 「同题横评与真实夹具」 below), and verify symbol, timeframe, last price, pane count/names, and visible high/low. A model name containing `vision` is not evidence of image quality, and a text-only `OK` probe proves nothing about image input.
8. When several candidates look equivalent, run the **same-task head-to-head**: identical evidence pack + house rules with a verdict trap, scored on compliance and fabrication (section below). One clean probe per model is not enough to pick a main model.
9. Recommend the fastest model that is both reachable and fit. Prefer a single validated model for frequent key-level triggers; reserve MoA/deep fan-out for major conflicts, event windows, or explicit deep analysis. Take latency from **real session logs** (`logs/agent.log` → `API call #n: model=… in=… out=… latency=…`), not from probes; probes only prove reachability.
10. Keep the final trading verdict outside the LLM: the Python `FinalVerdict`/hard gates remain the authority. Models produce evidence and candidate plans, not automatic orders.

## Trading-analysis quality gates

Before allowing model output to influence a card:

- Validate asset class through one shared contract; BTC must not be crypto in one module and non-crypto in another.
- Recompute cache freshness from timestamps at read time; do not trust a producer's `fresh: true` flag.
- Normalize missing-data states as `available`, `missing`, `stale`, `timeout`, `invalid`, or `not_applicable`.
- Apply quantity/order-of-magnitude and symbol checks to external fields. An implausible BTC options MaxPain or cross-asset value is `invalid` and must be excluded from direction scoring.
- In quick mode, report actual period coverage (for example, TV 1/5) rather than presenting a partial scan as a full scan.
- Unknown or conflicting evidence may produce WAIT/NO-GO; never fill unknown values with a neutral directional claim.

## 同题横评与真实夹具（2026-09-10 实证配方）

只测连通/工具能力不足以选主模型——**让所有候选答同一道题，再比合规与保真**。

**A. 决策卡同题横评**

- 同一份「证据包 + 房规」提示词跑遍候选（模板 `templates/model_evidence_fixture_prompt.txt`；批量跑 `scripts/head2head_probe.sh`）。
- 证据包必须内建**裁决陷阱**：例如 S3 源间冲突 + Python `FinalVerdict=WAIT(executable=false)`。评分 5 项：①是否出 WAIT/NO-GO ②三件套是否清空写「无」③是否只有一个 ⭐ 主推 ④是否引用证据包里不存在的数字（编造 = 一票否决）⑤是否点出数据缺口（ATR 缺失、周期行动格未收敛）。
- 统一条件：`hermes chat --query-file <fixture> --provider P --model M -t file --ignore-rules -Q --yolo`。`--ignore-rules` 让所有模型看到完全相同的上下文，横评的是模型而不是技能加载行为；分批后台跑并落盘，别把长输出堆进上下文。

**B. 视觉夹具必须带外部真值**

「模型说了话」不算通过。做法：取 `tools/tradingview-mcp/screenshots/` 已有截图 → 用文件名/mtime 定位北京时间 → 拉当时交易所 K 线当真值 → 比对读回值。

```python
import datetime, json, urllib.request
BJT = datetime.timezone(datetime.timedelta(hours=8))
t0 = datetime.datetime(2026, 9, 5, 2, 0, tzinfo=BJT)   # 截图拍摄时刻附近的整 15m
u = f'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&startTime={int(t0.timestamp()*1000)}&limit=3'
for r in json.loads(urllib.request.urlopen(u, timeout=30).read()):
    print(datetime.datetime.fromtimestamp(r[0]/1000, BJT), r[1], r[2], r[3], r[4])
```

提问要具体到可判分：品种代码、周期、图上最后价格、副窗格数量与名称、可见区间最高/最低。2026-09-10 实测：`deepseek-flash` 与 `gpt-5.6-luna` 在同一张图给出完全相同的品种/周期/价格（79,536.2，交易所真值 ≈79,530）——**读图能力可以用交易所真值直接判分，不需要人眼**。

**C. 延迟与成本取真实会话数据**

探针延迟只证明可达；真实延迟用 `logs/agent.log` 里带 `in=/out=/latency=` 的 `API call #n` 行按 provider/model 聚合（实测 2026-09-10：deepseek-v4-flash 45 次会话调用均值 5.1s / 71K 输入）。成本按真实 in/out 均值算，别用假设 token 数。

**D. 避免假阳性（这几条会把审计结论带偏）**

- cron 里 `no_agent: true` 的 job **从不解析** `provider`/`model` 字段——那里残留的死模型名或未定义 provider 名只是卫生问题，不是 P0 死链。
- 免费池 `:free` 会静默转付费（服务端 404 + "unavailable for free"），所以本 skill 里任何免费池表格都只是某天快照，**推荐前必须现场重探**。
- 单次「stream produced no SSE events / 零事件」失败先重跑一次再评分；MoA 参考层少一个成员不影响整体跑完。
- 免费视觉候选可能在**真实图片请求**上 429（文本/工具探针却通过），所以视觉槽必须走 B 的真实图夹具。

2026-09-10 完整横评结果、免费池重探清单、DeepSeek 价格与真实延迟表见 `references/model-head-to-head-and-vision-fixtures.md`。

## OpenRouter 免费池实测总表 (2026-08-29 全测18个)

`openrouter/free` 是服务端动态路由,不能控制"优先大模型";免费池共18个真实模型(去掉路由器)。实测结论:

**✅ 可用(工具调用完整+档位判断正确)**
- `nvidia/nemotron-3-super-120b-a12b:free` 262K/120B/2-4s **⭐最佳(但⚠️无真实工具结果时会编造占位截图/假数据→禁出实盘卡)**
- `nvidia/nemotron-3-ultra-550b-a55b:free` 1M/550B/22s(实测慢) · **⚠️工具调用返回JSON字符串而非tool_use块→NOT tool-capable→禁当主模型** · 仅深度复核
- `nvidia/nemotron-3.5-lightning:free` 1M/2.2s
- `nvidia/nemotron-3-nano-omni-30b:free` 256K/30B/2.8s
- `minimax/minimax-m3:free` 1M/3-6s (档位✅)
- `minimax/minimax-m2.7:free` 196K (档位输出偶不稳⚠)
- `poolside/laguna-s-2.1:free` 262K/工具✅/档位✅
- `poolside/laguna-xs-2.1:free` 262K/工具✅
- `cohere/north-mini-code:free` 256K/工具✅
- `dots-studio/dots-3-note-preview:free` 512K/工具✅/档位✅
- `liquid/lfm-2.5-2.6b:free` 65K/**仅2.6B小**/工具✅/档位靠prefill

**❌ 实测不可用/受限**
- `thinkingmachines/inkling:free`, `inkling-small:free` → HTTP 403 仅限 agentic harness(编码agent专用)
- `nvidia/nemotron-3.5-content-safety:free` → HTTP 404 不支持工具调用
- `google/gemma-4-26b:free`/`gemma-4-31b:free`/`z-ai/glm-5.2:free` → 反复429限速(服务商每日限流,代码层可用但额度紧)
- `inclusionai/ling-3.0-flash-fin:free` → 工具✅但档位ERR

**2026-09-10 重探（4 周后池子已大幅漂移，勿直接沿用上面结论）**

- ❌ `minimax/minimax-m3:free` → HTTP 404「This model is unavailable for free. The paid version is available now」= **已转付费**；还钉着它的 delegation / MoA 参考位会白等一轮（实测 MoA 一次全程就挂在这里）。
- ❌ `poolside/laguna-s-2.1:free` → 429；`thinkingmachines/inkling:free`、`inkling-small:free` → 403（agentic harness 专用，与上表一致）。
- ⚠️ `google/gemma-4-31b-it:free` 文本/工具探针通过，但**真实图片请求 429** → 免费视觉通道不可靠。
- ⚠️ `nvidia/nemotron-3-super-120b-a12b:free` 横评中输出了伪造的「看盘截图(MEDIA)」占位行（数字未编造）→ 印证「禁出实盘卡」，只能兜底/委派。
- ✅ 新进且可用（工具 COMPLETE + 无编造）：`nex-agi/nex-n2.5-mini:free`(1.4s) · `cohere/north-mini-code:free`(1.5s) · `inclusionai/ling-3.0-flash-sante:free`(1.6s) · `dots-studio/dots-3-note-preview:free`(2.0s) · `nex-agi/nex-n2.5-pro:free`(2.2s) · `nvidia/nemotron-3.5-lightning:free`(3.2s) · `inclusionai/ling-3.0-flash-fin:free`(3.3s，金融专精)。
- ⚠️ `openrouter/free` 动态路由本次落到 `inclusionai/ling-3.0-flash-sante:free`——不可控，别放进持久 MoA 预设。
- 真免费共 21 个（含 2 个 Lyria 音乐、1 个 content-safety，与交易无关）。

**选型建议**: 想要"大且稳"固定用 nemotron-3-super-120b;想要最大Context用 nemotron-3-ultra-550b(1M);接受动态路由用 /free 但需接受可能掉到小模型/踩坑模型(inkling/gemma/glm限速会白等)。

## Weak-model档位保真 (prefill注入, 2026-08-29 验证)

当主模型是弱/免费模型(如 `openrouter/free` 动态路由到 `liquid/lfm-2.5-2.6b:free` 等 2.6B 级小模型)时,它**靠 skill 加载记不住"看下=轻量/现在呢=标准/分析=完整"这类分档规则**——长 SKILL.md 弱模型读不动、也不遵守。这会导致分析"很久很久"且不按分档跑。

**根治:用 prefill 注入,而不是让模型去读 skill。**

- config 顶层 `prefill_messages_file` (canonical) = 指向一个 JSON 数组文件;`agent.prefill_messages_file` 是 legacy fallback。兼容 env `HERMES_PREFILL_MESSAGES_FILE`。
- 文件须为 `[{"role":"user","content":"..."}]` 格式。相对路径从 `~/.hermes/` 解析。
- 注入位置: `agent/conversation_loop.py` —— 每条 prefill 消息插入在 **system prompt 之后、对话历史之前**,每次 API 调用都注入。弱模型必读。
- prefill 内容要点: **极短、命令式、逐条硬命令**。一档一条,顺序编号,明确"只做对应步骤,禁止多跑少跑";输出首行必须是 MEDIA 截图;时间格式中文日期+全角冒号。不要长篇——26B 模型装不下。
- 落地路径: 写 `~/.hermes/prefill_trading_rules.json` → 设 config → 开新会话验证。

**验证方法 (实测有效)**: 用 `hermes chat -q "用户说「看下XAU」按规则走哪个档位?" --provider openrouter --model openrouter/free`,看模型能否答出"轻量档位+步骤"。26B 的 lfm-2.5 实测能正确识别档位并列出步骤。

**注意**: 换弱模型后,即使 prefill 到位,模型工具调用能力仍可能受限。`openrouter/free` 实测能正确发出 tool_calls(read_file 测试通过),但复杂工具链(五周期TV+Binance全采集)可能不稳,需单独实测。

**更进一步 (2026-08-29): 选固定大模型,别让路由器落下小模型。** `openrouter/free` 是**动态路由器**,每次请求自己挑模型,可落到 2.6B 级小模型(lfm-2.5-2.6b)撑不起交易工具链。**根治 = 绕过路由器,在 `model.default` 固定一个具体 `:free` 模型 id**(provider 仍 openrouter;delegation 独立不受影响)。选型三探测:①延迟(1-3s)②工具调用完整性(arguments 须为含 `path` 的合法 JSON = COMPLETE;`PARTIAL/BROKEN/NO_CALL` 排除;响应 `model:None` = 端点异常直接排除)③档位记忆(喂规则问「看下XAU」短答)。判定内容用 `max_tokens>=120`,否则被截断误判为"空"。**实测胜地 `nvidia/nemotron-3-super-120b-a12b:free`**(120B,~2.6s,三探测全过)。完整探测脚本见 `scripts/or_free_model_probe.py`,方法+逐模型结论见 `references/or-free-model-selection.md`。

## Cron LLM 死锁应急切换工作流 (2026-08-31 验证)

**场景**: 某个 LLM-cron (如 `keylevel_read_trigger.py` 每 2min 拉起 LLM 分析) 配置的 `provider/model` 出现 `HTTP 402: Insufficient Balance` 或持续 4xx,`cron list` 报 `N failures in a row`(实测 228 次连续失败占满 cron 失败计数)。**不要先充值,先恢复链路**——把 cron 模型切到 OpenRouter 免费池,避免信号堆积。

**四步恢复** (适用于 hermes cron, `~/AppData/Local/hermes/cron/jobs.json` 直接编辑):

```bash
# 1. 确认 cron 失败模式
hermes cron list | grep -A 3 "<cron_name>"
# 看 last_status: "error: RuntimeError: HTTP 402: Insufficient Balance (N failures in a row)"
# → provider/model 账户欠费

# 2. 选免费替代 (按本 skill 末尾"OpenRouter 免费池实测总表"挑可用+工具完整+档位稳)
#   推荐默认: nvidia/nemotron-3-super-120b-a12b:free (120B, 260K ctx, 工具✅档位✅)
#   视觉任务保留 openrouter/free (router);文本分析用具体 :free id 避免随机路由

# 3. 直接编辑 jobs.json (Python, 安全;不要 hermes config set 改 cron 字段)
python -c "
import json
p = r'C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json'
d = json.load(open(p, encoding='utf-8'))
for j in d.get('jobs', []):
    if j.get('name') == '<cron_name>':
        j['model'] = 'nvidia/nemotron-3-super-120b-a12b:free'
        j['provider'] = 'openrouter'
        j['provider_snapshot'] = {'provider':'openrouter','model':j['model']}
        j['model_snapshot'] = {'provider':'openrouter','model':j['model']}
        j['last_status'] = 'switched_to_or_free_<date>'
        j['last_run'] = None  # 清失败计数,让下次可跑
json.dump(d, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
print('OK')
"

# 4. 直连验证 (跳过 cron, 先 200 OK 再信任下次 tick)
python -c "
import re, json, urllib.request
env = open(r'C:/Users/Administrator/AppData/Local/hermes/.env', encoding='utf-8').read()
key = re.search(r'OPENROUTER_API_KEY=(sk-or-[a-z0-9_-]+)', env).group(1)
body = json.dumps({'model':'nvidia/nemotron-3-super-120b-a12b:free',
                   'messages':[{'role':'user','content':'回执OK就答一字:好。'}],
                   'max_tokens':20}).encode()
req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
    data=body, headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
r = urllib.request.urlopen(req, timeout=50)
resp = json.loads(r.read())
print('✅ 状态:', r.status, '| 模型:', resp.get('model','?'))
"

# 5. 手动跑一次上游脚本 (如 keylevel_read_trigger.py),确认不再是 402
python scripts/<upstream_script>.py
# 期望: exit 0 + "WAIT no-trigger" (无新事件静默,符合 cron 铁律)
```

**关键判断**: 切换后第一次跑通常输出 `WAIT no-trigger`——不要怀疑切错,这是设计(无新事件=静默);只有 `trigger_X.json` 实际 `triggered=true` 才出卡。

**同步刷新清单** (切完一并做):
- 切完后**第一时间手动消费堆积的 trigger**: 查 `data/trigger_*.json` 中 `triggered=true & handled=false` 的,直接 `python scripts/<upstream>.py` 跑一次可消。
- 已 `handled=true` 但 `text_push_status=failed_or_missing` 的 = **历史失败残留**,**不要重推**(易重复发卡);记录在 audit 报告等下次清理。
- 监控该 cron 下次 tick 是否仍 402;若仍失败查 OpenRouter 账户余额(`GET /api/v1/auth/key`)。

**陷阱**:
- 不要用 `hermes config set` 改 cron 字段(只改 model.* 不改 cron 任务级 model);直接改 `jobs.json`。
- 不要切到 `openrouter/free` (动态路由)——会落到限流小模型(glm-5.2/gemma-4/lfm-2.5 反复 429/空 content)。
- 不要删除 cron 重装——保留 cron id,只改 model/provider;否则 prompt/skills/schedule 全丢。
- 若 cron prompt 里强依赖视觉(如 chart_get_state + 截图),免费 nemotron 文本强但视觉弱,**改用 `openrouter/free` 路由**(动态选带 vision 的)而非固定 nemotron 文本模型。

## 模型质量劣化诊断（2026-08-31 实测 · 「感觉换了个模型很差劲」排查路径）

用户反馈"模型变差/变慢/格式乱"时，**先查配置变更时间线，不要猜模型本身**。本会话实测：用户体感"换了个很差劲的模型"，实际是当天 17:30 config.yaml 被改成 `minimax/minimax-m3:free` 免费池（会话中途 15:43 还是 nemotron-ultra-550b:free，一天被换两次）。

**诊断三步（全部只读，30 秒完成）**：

```bash
# 1. 当前生效主模型
head -4 ~/AppData/Local/hermes/config.yaml   # model.default + provider

# 2. 变更时间线（备份带时间戳）
ls -la ~/AppData/Local/hermes/config.yaml.bak* | awk '{print $6,$7,$8,$9}'
for f in ~/AppData/Local/hermes/config.yaml.bak*; do echo "-- $f"; grep -A2 "^model:" "$f" | head -3; done

# 3. 本会话实际路由（系统提示 Model/Provider 字段）+ cron 显式钉底模型
python -c "
import json
jobs=json.load(open(r'C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json',encoding='utf-8')).get('jobs',[])
for j in jobs:
    if j.get('enabled') and j.get('model'): print(j['name'], '→', j['model'])
"
```

**判定**：
- config 当前值与备份时间线差异 = 配置漂移（`hermes model` 手动切换 / 会话级 flags），不是模型退化。**本会话系统提示 Provider=opencode-go 而 config 是 openrouter = 会话级覆盖，两者可并存**。
- 免费 fallback 链是质量劣化放大器：主模型 4xx/限流 → 沿链掉到 minimax-m2.7 → nemotron-ultra-550b(22s) → poolside → glm-5.2（实测反复 429）→ openrouter/free 动态路由（可落 2.6B 小模型撑不起交易工具链）。"时好时坏+变慢"典型 = 正在 fallback。
- **记忆期望 vs 备份实际漂移**：记忆说"固定 DeepSeek vision-exp"但 8 月全部备份从未出现过该配置（实际是 opencode-go+deepseek-v4-flash）——**以备份/当前实测为准，记忆过期要更新记忆而不是修改配置**。
- 恢复命令参考：`hermes model set <model> --provider <provider>`；用户坚持"不恢复只记录"时，把真实模型状态写进记忆并主动提醒切回已验证配置。

## Effective context-window audit

When a user asks for the context size of the currently configured Hermes model, report the effective runtime route rather than a public catalog maximum.

1. Load `hermes-agent` if Hermes configuration is involved, then run `hermes config path` and inspect only non-secret `model.default` and `model.provider` fields. Never print `.env` or OAuth tokens.
2. Check the active profile's `context_length_cache.yaml`. For provider-backed routes, the cache key is commonly `<model>@<base_url>`; match the exact model slug and endpoint.
3. Distinguish model variants. For OpenAI Codex OAuth, ordinary `gpt-5.6-luna` is currently cached at `272000` tokens on `https://chatgpt.com/backend-api/codex`, while `gpt-5.6-luna-900k` is a separate large-context picker variant. Do not substitute an OpenRouter/Bedrock/catalog claim of ~1M for the active Codex OAuth route.
4. State whether the value is cached/detected or manually configured. If no exact runtime entry exists, label the context as unresolved instead of guessing from the model name. For Codex, inspect `~/.codex/models_cache.json` as non-secret runtime evidence: distinguish `context_window` (the ordinary active/default limit) from `max_context_window` (the larger entitlement/ceiling). A base slug such as `gpt-5.6-luna` uses the former; do not report the latter unless the large-context variant is explicitly selected and verified.
5. If compression behavior matters, report both the total window and the effective trigger. Hermes' Codex GPT-5.6 autoraise applies to the ordinary 272K family but explicitly excludes `-900k` variants; with `compression.codex_gpt55_autoraise: true`, the trigger is 85% (for 272K: 231,200 tokens), otherwise the global default is 50% (136,000 tokens). If `model.context_length` is unset, report the provider-detected value rather than recommending the public OpenAI API maximum.

Evidence to include: active config model/provider, exact cache key, detected context length, variant distinction, and any compression threshold. Keep credentials and secret-bearing files out of the evidence.

## Codex large-context picker verification

When a user cannot see a documented large-context alias in `/model`, do not infer that a `-pro` suffix is equivalent. For Hermes' Codex OAuth route, `gpt-5.6-luna-pro` is a distinct public/API-style slug and is not the large-context opt-in; it may be rejected by the ChatGPT Codex backend. The verified Hermes-side opt-in is `gpt-5.6-luna-900k` (likewise `sol-900k`, `terra-900k`, and `gpt-5.4-900k` where supported).

Verify picker availability against the installed runtime, not only web docs:

1. Run `hermes --version` and note update lag; then inspect the installed `hermes_cli/codex_models.py` and `agent/model_metadata.py` when necessary. The picker synthesizes `-900k` entries only for the eligible base slugs in `is_codex_900k_base()`.
2. If the source supports variants but `/model` does not show one, refresh the model picker cache with `hermes model --refresh` and reopen it. Treat a missing menu entry as a discovery/cache/version issue, not evidence that `-pro` provides a larger window.
3. If the alias still cannot be selected, report it as unavailable in that installed picker and do not claim the large window is active. A manual config value is only a candidate until a real request or runtime metadata confirms it.
4. Separate public API claims (for example, Luna's 1.05M catalog maximum) from the active Codex OAuth route: base `gpt-5.6-luna` is commonly managed as 272K, while the explicit Hermes `-900k` alias opts into the separately verified ~900K route.

## GPT-5.6 Luna 主模型切换与提速验证

对 Hermes `openai-codex` 路由，不要把“换模型”“记忆继承”“速度优化”混成一个问题：

1. **继承边界**：同一 profile 内切换模型或开新会话，`MEMORY.md`、`USER.md`、SOUL、prefill、skills 和仓库文件仍可用；新会话只重新注入持久快照，不自动复制全部临时聊天。换 profile 默认不继承。模型切换同会话则保留当前历史。
2. **先验收再设主模型**：至少做一次真实短请求、一次真实工具调用、一次档位规则复述；工具探测必须看到真正的 tool call 和结果，不能只看模型文本说“已调用”。
3. **速度主旋钮**：Quick/Inherit/标准分析优先 `reasoning=low`；Full/重大审计再临时升 `medium/high`。`/fast fast --global` 会写 `agent.service_tier=fast` 并请求 Priority Processing，可能影响计费，必须先说明成本再持久开启。
4. **上下文选择**：日常交易驾驶舱优先普通 `gpt-5.6-luna`；不要为了“更强”默认切 `-900k`。普通Codex OAuth路由的现场缓存为272K，足够承载规则且通常更利于日常延迟。
5. **区分冷启动与模型延迟**：`hermes chat -q` 的总耗时包含Hermes启动、规则/记忆注入和工具往返，不能直接当纯模型延迟；比较推理档位时要使用相同提示、相同工具和同一运行方式。

推荐切换序列（是否开启Priority必须由用户知情决定）：

```text
/model openai-codex:gpt-5.6-luna --global
/reasoning low --global
/fast fast --global
/reset now
```

完整现场证据与判读见 `references/luna-main-model-speed-and-memory-2026-09-02.md`。

## MoA with OpenRouter fixed-free references and Codex aggregators

For MoA designs that combine OpenRouter free models with `openai-codex` Luna/Sol:

- Distinguish `openrouter/free` (a server-side dynamic router) from fixed model IDs ending in `:free`. A dynamic router is not a stable advisor and should not be placed in a persistent MoA preset unless variability is intentional and revalidated.
- A preset has exactly one aggregator. To use both Luna and Sol, create two named presets rather than chaining two aggregators: a fast `default` with fixed, heterogeneous free advisors → `gpt-5.6-luna`, and a slower `deep` preset with a heavier advisor → `gpt-5.6-sol`.
- `moa.active_preset` only selects the configured preset; it does not activate MoA when the top-level route is still direct. Verify `model.provider: moa`, `model.default: <preset>`, and preset `enabled: true`. `enabled: false` means aggregator-only, with the reference fan-out disabled.
- For short-turn trading, explicitly use `fanout: user_turn` and bound advisor output with `reference_max_tokens` (roughly 600 for daily work and 1000 for deep review). Keep advisor roles distinct (lead structure vs. skeptic/auditor); model agreement is not a probability.
- Reference models never own execution. The aggregator must pass a real tool/result probe and is the only model that should fetch live data, call TradingView/Binance tools, or produce user-facing artifacts. Python hard gates remain the final trading authority.
- Validate each slot independently before promoting it. Record configured, credentialed, reachable, tool-capable, and actually-routed as separate states; report latency as end-to-end probe time, not pure model latency.
- When a preset needs multiple references, use the Desktop/GUI editor or an atomic whole-block YAML write. Do not try to append a new list element through indexed `hermes config set` paths.

Session-specific route evidence and the recommended two-preset skeleton are in `references/moa-codex-openrouter-routing-2026-09-02.md`.

## MoA reasoning defaults and inheritance

When auditing or designing a MoA preset, distinguish “unset” from an explicit effort and from Hermes-level adaptive routing:

- Omitting `reasoning_effort` (or setting it to YAML `null`) is supported. Hermes passes no explicit reasoning configuration and the selected Provider/model uses its own default. This is provider-default behavior, not a Hermes scheduler that dynamically chooses low/medium/high by task difficulty.
- `auto` is not a canonical Hermes effort. Do not write it as a policy switch: current parsing may treat it like an absent value while warning about an unknown setting.
- Reference advisors use only their slot-level `reasoning_effort`; an omitted reference slot does **not** inherit global `agent.reasoning_effort`.
- The aggregator is the acting model and resolves `aggregator slot > agent.reasoning_overrides > global agent.reasoning_effort > provider default`. Therefore a preset with unconfigured advisor slots but a global `agent.reasoning_effort: medium` still runs its aggregator at medium.
- If all MoA roles should use provider defaults, omit the global setting and every slot-level `reasoning_effort`. Keep `temperature` separate; remove/null `reference_temperature` and `aggregator_temperature` only if sampling should also use provider defaults.
- Verify this separately from reachability: run `hermes moa list`, inspect the redacted active config, then perform a real `hermes chat -q ... --provider moa --model <preset>` probe. A listed/enabled preset is not necessarily the active top-level route. The detailed AMI/default-inheritance evidence is in `references/moa-reasoning-defaults.md`.

## Routing recommendations

- **Default trading route:** use the validated single primary model for Quick, Monitor, Standard, and Inherit requests. This is the correct default for fast execution-oriented analysis because it minimizes latency, quota fan-out, and advisor noise.
- **Conditional MoA escalation:** recommend a manual `/moa` deep review only for a critical macro event (CPI/FOMC/NFP), a clear conflict between TradingView and Binance/other sources, a valid key support/resistance break, a data-contract or risk-control suspicion of hallucinated output, or a major position-size/stop-loss decision at or above 1.5× normal exposure. Do not silently switch the session to MoA.
- **Configuration distinction:** clearing `moa.active_preset` prevents a configured preset from being selected as an active session route, but it does not by itself change the top-level model. Verify the direct `model.provider`/`model.default` route separately; `/moa <prompt>` remains a one-shot manual escalation and restores the prior model afterward.
- **Execution boundary:** MoA references and aggregator are evidence/review layers only. Reference models provide structure checks, refutations, and blind spots; the aggregator may call tools and draft the response, but it never owns Entry/Stop/Target or final execution authority. Require data contracts, SVP main structure, risk hard gates, and `FinalVerdict`, followed by manual user confirmation and no automatic orders.
- **Full/deep:** use heterogeneous reviewers only after each provider is independently reachable; the aggregator must also pass a real tool/result test.
- **Fallback repair:** a configured 401/403 or protocol failure is a broken fallback, even if `hermes auth list` shows a credential. Repair and re-probe before promoting it.
- **Vision:** keep a separately validated vision route if the primary has not passed the TradingView image fixture.

## Evidence format

Report a compact table with: role, configured provider/model, credential state, live probe, tool probe, visual probe, actual route, and recommendation. Lead with one direct recommendation and clearly label unverified candidates.

## Pitfalls

- `moa.active_preset` does not activate MoA when `model.provider` is still a direct provider.
- A successful primary request can hide a dead fallback chain until the primary fails; probe every fallback explicitly.
- A model with a larger context or “Vision” suffix is not automatically better for short-term trading.
- A safe WAIT caused by incomplete data is a correct gate result, not proof that the data pipeline is healthy.
- Do not modify a protected existing audit/model skill; if it is user-owned, create or update a curator-managed umbrella and note the overlap to the user.
- **Distinguish credential failure from model failure BEFORE probing.** A stray/placeholder API key (e.g. a 12-byte `sk-or-xxxx` stub) returns HTTP 401 with `response.model:None` — that is a CREDENTIAL error, NOT 'model unreachable'. Do not collapse 401/403/404/429 into one 'unavailable' label — they are four different root causes. Sanity-check the key first: real OpenRouter keys are long `sk-or-v1-...`. If `grep KEY .env | cut -d= -f2- | xargs` yields a suspiciously short value, the probe result is meaningless — diagnose the credential (`.env`, `hermes auth list`) before reporting a candidate as down. Only `model:None` + HTTP 4xx with a VALID key means an endpoint/model problem. This prevents a false 'model is down' note from hardening into a permanent refusal.
- **Tool-capable ≠ recollects the rules.** A model can correctly REPLAY a tier/skill-loading instruction (proving the prefill enforcement layer works) yet still emit the tool call as a JSON-in-prose string instead of a real tool_use block. That model is NOT tool-capable even though it "knows" the flow. Always probe with an actual tool intent (screenshot/load-skill) and check the SHAPE of the tool emission, not just the text. Refer to state 4 (tool-capable) not state 3 (reachable).
- **Watch for fabricated artifacts when no real tool result.** Free models without a live tool result may INVENT placeholders — e.g. `![BTC 15m chart](https://example.com/...png)` for a screenshot, or plausible-looking prices. This is the P0 red line (TV不可用不得用旧截图/假图冒充). Bar any model that fabricates from producing live analysis cards; flag the fabrication when seen.
- **免费池表格是快照，不是事实。** 任何 `:free` 结论（含本 skill 里的表）在推荐前都要现场重探；`minimax-m3:free` 在 2026-09-10 已静默转付费。见「同题横评与真实夹具」。
- **付费 403 ≠ 账号没钱。** OpenRouter 的 `403 Forbidden` 常是**该 key 的 spend limit** 用满（`GET /api/v1/key` 的 `limit_remaining`），账户 `credits` 可能还有余额；两者分开报，别写成「账户欠费」。
- **`no_agent: true` 的 cron job 不解析 provider/model。** 这类记录里残留的死模型名/未定义 provider 名属卫生问题，不要当 P0 死链报出去（会稀释真正的发现）。
- **Probe CN/multiline prompts with Python urllib, not curl.** `curl -d` with a multi-line Chinese prefill returns HTTP 400 (shell-escaped quotes/newlines). Use `execute_code` + `urllib` so Python builds the JSON body; read the key from `~/.hermes/.env` (not the workspace `.env`, which may hold a short stub); use `max_tokens>=650` or reasoning-token truncation mangles the reply. Reproducible recipe: `references/free-model-probe-and-cross-model-rules.md`.

See `references/runtime-model-audit.md` for a reusable evidence template and the session-derived anomaly checks.
See `references/model-head-to-head-and-vision-fixtures.md` for the 2026-09-10 head-to-head results, free-pool re-audit, DeepSeek V4.1-Flash facts/pricing, and real-session latency tables.
Templates/scripts: `templates/model_evidence_fixture_prompt.txt` (same-task fixture prompt) and `scripts/head2head_probe.sh` (batch runner across provider/model pairs).
See `references/luna-main-model-speed-and-memory-2026-09-02.md` for Luna tool-call validation, persistent-memory boundaries, and speed-tuning evidence.
