# 2026 年 9 月 · 美国区 ~$20 档 AI 订阅实况（官网价核实）

核实时间：北京时间 2026年9月13日。用户把这五个方案当成「都是 20 美元」来对比，实际上只有两个成立——
**先用官网核对每个方案在该价位是否真的存在，再做排序**。

## 一、结论速查

| 方案 | 实付/月 | 额度 | 模型口径 | Hermes 接入 |
|---|---|---|---|---|
| OpenCode Go | $10 | 每模型独立月度额度（$15–$60/模型），5h=20%、周=50%、月=100% | 27 个开源模型 | OpenAI 兼容 `https://opencode.ai/zen/go/v1/chat/completions`，单 sk- key |
| Command Code Pro | $20 + $1.01 刷卡费 ≈ $21 | $80 credits 池化、不过期（Deal 期抵 $120）；5h 上限 $16、周上限 $40 | 45+，含 Claude / GPT / Gemini 等闭源 | 原生 OpenAI `https://api.commandcode.ai/provider/v1/chat/completions` + Anthropic `/v1/messages`，CLI 与 API 同一把 key |
| Ollama Cloud Pro | $20（年付 $16.67） | $60 credits/月，按各模型挂牌价扣；无 5h/周限；并发 3 | 全开源（glm-5.3、kimi-k3、minimax-m3、deepseek-v4-pro、qwen3.5:397b、gpt-oss:120b…） | `OLLAMA_API_KEY` + `https://ollama.com/v1` |
| b.ai | **无 $20 档** | 订阅只有 Plan Pro $200/月（50–500 条/12h）、Plan Max $2000/月；$20 只是充值 | GPT-6 / Claude Opus 5 / Gemini 3.1 / GLM / Kimi / DeepSeek | 已在用 `https://api.b.ai/v1` |
| DeepSeek 官方 | **无订阅** | 纯按量充值，无额度加成 | DeepSeek V4.1 Flash / V4 Pro | `https://api.deepseek.com` + `/anthropic` |

## 二、Command Code 档位（容易看错的地方）

- **Go $1/月**：$10 credits、约 15K 请求，**不含 API 权限**（`Every plan except the Go plan has API access`）。是拉新价，别当成能接 Hermes 的档。
- **GOAT $10/月**：$70 credits、约 75K 请求、含 API 权限。
- **Pro $20/月**：$80 credits、约 100K 请求、45+ 模型（GOAT + Claude/GPT/Gemini）。
- **Max $100 / $200**：$150 / $300 credits，10× / 20× Pro 用量，闭源与开源各有独立额度。
- **Provider $15/月 + $1.01 刷卡费**：纯按量 API 档，$15 真实额度、无加成、无上限、额度不过期。要「不被订阅上限卡住」时选它，要「额度倍数」时选 Pro。
- 官网所有档位都写 `+ processing fee` 而不给数字；Provider 页公示为 $1.01 刷卡费，其余档按同口径估算并明确标注。
- Deal 会叠在额度上：MiniMax M3 2× 用量、MiMo V2.5 最高 99% off、Laguna S 2.1 / LongCat 2.0 免费、DeepSeek V4.1 Flash 限时提额（GOAT $60 / Pro $70）。

## 三、OpenCode Go 的真实口径

- 官方 `/go` 页的「Monthly usage」是**每个模型各自的月度美元上限**，不是共享池：余量不能跨模型挪用。
- 示例额度：Kimi K3 $15、GPT 5.6 Luna $15、DeepSeek V4 Flash $30、MiMo-V2.5 / MiniMax M3 / Qwen3.7 Plus / GLM-5.3-Flash / Muse Spark 1.3 各 $60；DeepSeek V4.1 Flash 限时 4×（$60、26,000 请求/5h）。
- 官方要求客户端发 `x-opencode-session` 头（否则缓存命中与路由变差），并会监控滥用。
- `/go` 的 Validated Clients 表把 **Hermes** 列为已验证客户端，但注明需要含 **PR #101864** 的构建，该修复**合并于 v0.21.0 之后**——v0.21.0 本身不含。

## 四、DeepSeek 官方价格（$20 只能当充值）

峰谷定价，闲时是高峰的一半；高峰为北京时间周一至周五 09:00–12:00 与 14:00–18:00。

| 模型 | 输入(缓存未命中) | 输出 |
|---|---|---|
| deepseek-flash (V4.1 Flash) | 闲时 1 元/M，高峰 2 元/M | 闲时 4 元/M，高峰 8 元/M |
| deepseek-v4-pro | 闲时 4.5 元/M，高峰 9 元/M | 闲时 13.5 元/M，高峰 27 元/M |

缓存命中价低一个量级（Flash 闲时 0.02 元/M）。官方**没有**订阅/会员/编程套餐；第三方（如云厂商 Token Plan）转售才是套餐形态。

## 五、额度倍数换算（回答「哪个划算」用的口径）

统一基准：1 美元官方用量 = 1 美元额度。

- Command Code Pro：$80/$20 = **4×**，Deal 期约 **6×**；代价是 5h $16 / 周 $40 的上限，额度不能一次烧完。
- Ollama Cloud Pro：$60/$20 = **3×**；无 5h/周限、并发 3，但月度清零不结转、无闭源模型。
- OpenCode Go：$10 换多个模型各 $15–$60 的**独立**额度（名义倍数最高），但不可池化、只有开源模型。
- b.ai：标准价 1:1（`1 USD = 1,000,000 Credits`），折扣只来自活动赠送；充值赠送 Credits 30 天过期。
- DeepSeek 官方：1×，但自家模型单价最低，闲时下单再省一半。

## 六、直接结论（2026年9月13日）

- 只买一个 $20 订阅、且要闭源前沿（Claude/GPT/Gemini）→ **Command Code Pro**。
- 接受只用开源模型、按单位美元算力选 → **OpenCode Go $10**（但需先升级 Hermes 到含 PR #101864 的构建）。
- 要并发兜底、无 5h/周限、全开源 → **Ollama Cloud Pro**。
- b.ai 与 DeepSeek 官方在这个价位不是订阅选项，别把它们放进「$20 档」的比较表里。
