# 为 OpenRouter 免费档选型：避免动态路由器落到小模型

## 问题

`model.default: openrouter/free` 时，OpenRouter 把 `/free` 当作**动态路由器**——每次请求它自己挑一个免费模型，不受你控制。实测它落到过 `liquid/lfm-2.5-2.6b:free`（**2.6B 级**）这类太小、指令遵循差、速度不稳的模型，导致交易分析"很久很久"且完全不按"看下/现在呢/分析"分档跑。prefill 注入能部分救回档位，但 **2.6B 撑不起复杂工具链（五周期 TV + Binance 全采集）**。

## 根治：绕过路由器，固定一个具体的免费模型 id

```bash
hermes config set model.default nvidia/nemotron-3-super-120b-a12b:free
```

- `provider` 保持 `openrouter` 不变。
- `model.default` 从 `openrouter/free`（路由器）改成**具体模型 id**，即不再随机落小模型。
- `delegation.model`（子代理）是独立路由，不受此改影响（本系统保持 deepseek）。

## 选型探测法（可重复）

对每个候选免费模型，跑三个独立探测，任一不过即排除：

1. **延迟**：最小请求 `Reply with exactly: OK`，测毫秒。免费端点在 1–3s 属正常。
2. **工具调用完整性**：给出 `read_file(path)` 的 tools schema，要它"用 read_file 读 /tmp/a.txt"。看返回值：
   - `COMPLETE` —— arguments 是合法 JSON 且含 `path`（可用）
   - `PARTIAL`/`BROKEN` —— arguments 被截断（如 `'{'`）或非法（不可用）
   - `NO_CALL` —— 压根不调用工具（不可用）
3. **档位记忆**：喂一条分档规则（看下=轻量/分析=完整），问"用户说「看下XAU」该走哪档"。要求短答。

排除信号：
- 响应里 `model: None` = 端点异常/不可用，直接排除（GLM-5.2、gemma-4-31b、inkling 都命中过）。
- `max_tokens` 设太小（如 30）会**截断输出导致误判为空**——判断内容时用 `>=120`。
- bash 前台不能用 `&` 并行；要么串行 for 循环，要么写 python subprocess harness。

## 实测结论（2026-08-29）

| 模型 id | 延迟 | 工具调用 | 档位记忆 | 结论 |
|---|---|---|---|---|
| `liquid/lfm-2.5-2.6b:free` | ~2.1s | COMPLETE | 需 prefill | 太小，避免 |
| `minimax/minimax-m3:free` | ~3.5s | PARTIAL `'{'` | 轻量 | 不稳 |
| `minimax/minimax-m2.7:free` | ~4-5s | COMPLETE | 空输出 | 输出不稳 |
| `z-ai/glm-5.2:free` | ~2.4s | — | — | model=None，不可用 |
| `google/gemma-4-31b-it:free` | ~1.1s | NO_CALL | '' | 无工具能力 |
| `thinkingmachines/inkling:free` | ~1.0s | NO_CALL | '' | 无工具能力 |
| `nvidia/nemotron-3-super-120b-a12b:free` | ~1.8-2.6s | COMPLETE | 轻量+完整（"看下XAU→轻量；分析BTC→完整"） | **胜出（120B）** |
| `poolside/laguna-s-2.1:free` | ~2.9-4.4s | COMPLETE | 轻量+完整 | 备用 |

**推荐：`nvidia/nemotron-3-super-120b-a12b:free`** —— 120B、~2.6s、三探测全过。这是"别路由到小模型"的最稳答案。

## 验证已落地

固定模型 + prefill 后在独立新会话 `hermes chat -q` 实测：模型自报 `nvidia/nemotron-3-super-120b-a12b:free`，且正确回答「看下XAU」= 轻量。说明**档位规则（prefill 注入 + 120B 自身记忆）双保险生效**。

## 图像能力先预筛，再探（2026-09-12）

`GET /models` 的三组字段可以先筛掉不可能用的候选，比盲探省事：

```python
free    = [m for m in d['data'] if float(m['pricing']['prompt'])==0 and float(m['pricing']['completion'])==0]
tool_ok = 'tools' in (m.get('supported_parameters') or [])
img_ok  = 'image' in ((m.get('architecture') or {}).get('input_modalities') or [])
```

但这只是**声明**：声明支持图像 ≠ 真能读图。必须发一张带外部真值的真实截图才算数（见 `model-routing-validation` 的「视觉夹具必须带外部真值」）。

## 免费池基本兜不住视觉（2026-09-12 实测签名）

对免费池发真实 base64 图片请求，文本强模型多半直接回：

`HTTP 404 {"error":{"message":"No endpoints found that support image input"}}`

命中 `nvidia/nemotron-3-super-120b-a12b:free`、`cohere/north-mini-code:free`、`inclusionai/ling-3.0-flash-fin:free`（另有 400 provider error / 429）。结论：

- **免费池只适合兜文本与工具调用，不能兜视觉**；视觉槽的兜底必须另找非免费通道（订阅或中转），且视觉槽要显式钉住、不留 `auto`。
- 免费池里偶有能读图的（`dots-studio/dots-3-note-preview:free` 在 2026-09-12 正确读出 BTCUSDT.P / 15m / 最后价，但耗时 13–20s）——延迟量级已不适合当兜底，仅作最后手段。
- `thinkingmachines/inkling*:free` → `HTTP 403 ... only available on agentic harnesses`；`poolside/laguna-s-2.1:free` → 上游 429 `temporarily rate-limited upstream`。这类是**服务端准入/限流**，不是本地配置问题，别写进记忆当永久结论。

## 2026-09-12 三探复跑（用当前池子，勿沿用旧表）

| 模型 | 延迟 | 工具 | 档位 | 读图 |
|---|---|---|---|---|
| `nvidia/nemotron-3-super-120b-a12b:free` | 1.2–3.5s | COMPLETE | 轻量 ✅ | 404 无图像端点 |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 4.4s | COMPLETE（与 2026-08-29「JSON 字符串」记录冲突，按现场为准） | — | ✗ |
| `inclusionai/ling-3.0-flash-fin:free` | 1.3–2.1s | COMPLETE | 轻量 ✅ | 404 |
| `cohere/north-mini-code:free` | 1.0–2.7s | COMPLETE | 轻量 ✅ | 404 |
| `nex-agi/nex-n2.5-mini:free` | 1.2–2.2s | COMPLETE | 轻量 ✅ | 400 provider error |
| `poolside/laguna-s-2.1:free` | 2.5–3.1s | COMPLETE | 上游 429 | — |
| `thinkingmachines/inkling-small:free` | 0.8s | ✗ | ✗ | 403 agentic harness only |

兜底三席建议（只做文本/工具兜底，按实测延迟排序）：`nemotron-3-super-120b-a12b:free` → `nemotron-3-ultra-550b-a55b:free`（1M ctx）→ `ling-3.0-flash-fin:free`（金融语料、档位正确）。把会话实测最慢的 `nemotron-3.5-lightning:free`（探针 7.1s / 会话均值 16.3s）从第一位挪走。
