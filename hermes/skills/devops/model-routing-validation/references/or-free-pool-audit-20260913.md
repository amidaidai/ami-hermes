# OpenRouter 免费池兜底选型（2026-09-13 13:05–13:50 BJT，含能力基准审计）

**核心结论：免费池兜底最优解 = `nvidia/nemotron-3-ultra-550b-a55b:free`。**
先前的“挑最快的小模型”思路是错的：兜底要接得住主模型的活，先看能力和幻觉率，再看延迟。

## 1. 为什么是 ultra-550b（能力硬数据）

Artificial Analysis / OpenRouter 官方基准，同一家 NVIDIA 出品的两个免费模型对照：

| 指标 | **ultra-550b-a55b** | super-120b-a12b | 意义 |
|---|---|---|---|
| 规模 / 上下文 | 550B 总·55B 活 / **1M** | 120B·12B / 262K | 1M 能装下 Hermes 长系统提示（实测会话 msgs=188 tokens≈157K） |
| AA Intelligence | **23.4** | 13.6 | 综合推理 |
| AA Agentic | **21.7** | **4.1** | agent 能力差 5 倍 |
| GPQA Diamond | **86.7%** | 80.0% | 研究生级推理 |
| IFBench（指令遵循） | **81.4%** | 71.5% | 本系统强依赖指令遵循 |
| τ²-Bench Telecom | **83.3%** | 67.8% | 对话式双控 agent |
| AA-LCR（长上下文推理） | **79.3%** | 65.7% | |
| Terminal-Bench Hard | **36.4%** | 28.8% | 终端/工具 |
| **AA 非幻觉率** | **70.3%** | **13.0%** | **交易场景命门：编造风险 1/5** |
| Tool Call Error Rate | **1.71%** | 3.97% | 免费池最低 |
| E2E Latency P50 | 60.7s | 10.3s | ultra 的代价 |
| Availability (3d) | 76.1% | 93.3% | ultra 的代价 |

代价与对策：ultra 慢且可用率低（上游过载 = 已知的 “HTTP 200 + body 里带 error”）。**链上配法 = ultra 打头 + super-120b 垫底**，别只放 one-shot。

## 2. 为什么不用 ling-3.0-flash-*（旧结论修正）

`ling-3.0-flash-fin/sante/vl` 是 **124B 总 / 5.1–5.5B 活** 的**窄域微调**（金融 / 医疗 / 视觉），不是通用模型。做兜底要接任意任务（TV MCP、terminal、文件、中文分析），窄域专精不占优。它们胜在快且稳（p50 0.6–1.9s、up 100%），适合当**快链尾**，不适合做唯一兜底。

## 3. inkling 的真相（免费池参数最大，但 API key 用不了）

- `thinkingmachines/inkling:free` = 975B 总 / 41B 活、**1M ctx、文本+图像+音频**、up 100%，参数上免费池第一。
- **但裸 API key 一律 403**：`only available on agentic harnesses`。**实测 9 种身份头组合全 403**（无头 / `HTTP-Referer=nousresearch.com` / `X-Title` / `X-OpenRouter-Title` / `+X-OpenRouter-Categories:cli-agent` / 换 referer / `User-Agent: hermes-agent`），同头对照组 `north-mini-code` 正常 200 → **gating 不是 HTTP 头，是 Ori 的 OAuth 通道**。
- OR 官方把 Hermes 列为受支持 harness（`ori hermes`，见 https://openrouter.ai/docs/guides/ori/harness），所以“harness 白名单”里 Hermes 是正式成员；要真用它得走 `ori hermes` + OAuth PKCE 登录，不能走 config.yaml 里的 API key provider。
- 即便走通也不比 ultra 强：GPQA 81.8–84.2% < ultra 86.7%，Tool Call Error 4.41% > ultra 1.71%。**不值得为它改架构。**
- 另有硬约束：免费端点条款明写**禁止上传机密/个人数据、prompt 与 output 会被记录用于改进模型**。

## 4. 其他淘汰项（重测后修正）

| 模型 | 旧判 | 修正后 | 依据 |
|---|---|---|---|
| `poolside/laguna-s-2.1:free` | 可用 | ❌ 淘汰 | **Tool Call Error Rate 9.88%（免费池最高）**，第三方 7 日仅 1/2 成功；另有“输入输出用于训练”条款 |
| `poolside/laguna-xs-2.1:free` | 不可用（429） | ❌ 淘汰 | 429 是上游瞬时限流（重试可通），真正短板是**空回复/拒答** |
| `dots-studio/dots-3-note-preview:free` | 视觉兜底备选 | ❌ 淘汰 | **2026-09-30 下架** |
| `nemotron-3.5-lightning:free` | 快 | ❌ 不进 | 纯文本 9.4 / 62.2 / 114.5s，官方 p90 63.4s、p99 112s |
| `google/gemma-4-31b/26b:free` | 429 | ❌ 不进 | 对本地 key 持续 429（Google AI Studio 上游） |
| `nex-agi/nex-n2.5-pro:free` | 可选 | ⚠️ 仅纯文本参考 | Structured Output Error **26.61%**、E2E P99 813s |
| `openrouter/free` | — | ❌ 不进兜底链 | 官方写明 **at random** 路由，结果不可复现 |
| `cohere/north-mini-code:free` | 快 | ✅ 可做快链尾 | p50 0.5s、tps 87、tool error 低 |

## 5. 配额与红线

- 免费模型 **20 RPM**；RPD = **50**（累计买 credits < 10）或 **1000**（累计≥ 10，一次性门槛）。本机 key `is_free_tier:false`、`total_credits:15` → 落 **1000/天**。
- **余额降到负数时连 `:free` 也返 402**。
- 429 大多来自 **上游 provider 饱和**（错误 body 带 `temporarily rate-limited upstream`），与自己的配额无关。
- NVIDIA 免费端点（super/ultra/nano-omni）条款：勿传机密/个人数据，使用会被记录用于改进 NVIDIA 产品。
- **判健康必须解析 body**：Nvidia 端点会返 `200 + {"error":{"message":"Upstream error from Nvidia: ResourceExhausted..."}}`，只看状态码会误判。

## 6. 推荐兜底链（写回 config.yaml 用的形状）

```yaml
fallback_providers:
  - provider: "openrouter"
    model: "nvidia/nemotron-3-ultra-550b-a55b:free"   # 能力最优，1M ctx，非幻觉 70.3%
  - provider: "openrouter"
    model: "nvidia/nemotron-3-super-120b-a12b:free"   # 快速垫底，Availability 93.3%
  - provider: "openrouter"
    model: "cohere/north-mini-code:free"              # 极快链尾，p50 0.5s
```

视觉槽不走免费池（免费真读图 ≥18s 且多为游标读数）：主通道 `custom:b.ai` 的视觉模型或订阅通道。

## 7. 可复跑命令

```bash
curl -s https://openrouter.ai/api/v1/models | jq '.data[]|select(.id|endswith(":free"))|.id'
curl -H "Authorization: Bearer $KEY" https://openrouter.ai/api/v1/models/nvidia/nemotron-3-ultra-550b-a55b:free/endpoints
curl -H "Authorization: Bearer $KEY" https://openrouter.ai/api/v1/key
```
参考第三方每日重测（结构化）：https://klymentiev.com/assets/data/openrouter-free-models.json
