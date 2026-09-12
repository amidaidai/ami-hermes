# 成本分层与订阅窗口选型（用户偏好，2026-09-12 实证）

## 用户明确过的两条方向

1. **「中转（bai）要用免费和打折的型号」** —— 日常吞吐走中转里的低价快档；高价档只在深度复核、冲突裁决、关键位事件时用。
2. **「codex 是这个月订阅的」** —— 订阅通道在订阅期内要保留在轮换里（别浪费），但**不当唯一主力**：额度一打满（429）会把整条链连同视觉一起拖垮。

配套风格要求：用户要的是**结论式推荐**（先给答案 + 排好槽位 + 一句话理由），不是罗列选项让他挑。

## 推荐模板（本轮实际采用的形状）

| 槽位 | 选谁 | 判据 |
|---|---|---|
| 主模型 | 中转里的低价快档（本轮 `deepseek-v4.1-flash`） | 会话实测延迟最低、工具+视觉双通、不吃订阅额度 |
| 视觉槽 | 显式钉中转强档（本轮 `gpt-5.6-luna`） | 过真实图夹具；**禁 auto**（auto 会跟随主模型配额） |
| 第一兜底 | 订阅通道（本月 Codex `gpt-5.6-luna`） | 唯一非中转、可做独立交叉验证；额度用完即降级 |
| 免费池 3 席 | 按现场三探排序 | 只兜文本/工具，**不兜视觉** |
| 高价档（opus/gemini/kimi 等） | 仅深度复核 | 单价高、实测 10–60s |

## 中转的价目与身份都不能程序化获取 —— 别编价格

对 b.ai 这类中转的实测：

- 线上 api 节点只放行推理路径：`/pricing`、`/v1/pricing`、`/api/pricing`、根路径全部 `403 HTTP node only allows access to inference API paths (/v1/chat/completions, /v1/messages, /v1/responses, /v1/models, /v1/images/*)`；官网是 SPA，价目在需登录的后台。
- `GET /v1/models` 只回 `id` / `object` / `created` / `owned_by` / `supported_endpoint_types`，**没有价格字段**；`?detail=1`、`?include_pricing=1` 也不加。
- `POST /v1/chat/completions` 响应**不含成本字段**（只有 `usage` token 数；`usage.completion_tokens_details.reasoning_tokens` 会吃掉 `max_tokens`）。
- 单模型 `GET /v1/models/<id>` 可能对**能用别名**回 `model_not_found`（实测 `deepseek-v4.1-flash`）→ 不要用单模型端点判定存在性。

所以：**「哪几个免费/打折」只能向用户要后台价目页**（截图或粘贴），拿到后再按真实单价重排；在此之前只给「贵/便宜」分层，并明确写清这是**分层假设、不是价目事实**。官方定价页（如 DeepSeek）可作单次成本锚点，用于估算而不是替代中转价目。

## 可复用的三探形状（中转 / 任意 OpenAI 兼容端点）

```python
# 1) 工具调用 shape：不给工具就跑文本，给 read_file schema 要它调用
TOOLS=[{"type":"function","function":{"name":"get_time","description":"获取当前北京时间",
        "parameters":{"type":"object","properties":{"tz":{"type":"string"}},"required":["tz"]}}}]
# shape = COMPLETE(arguments 是合法 JSON) / PARTIAL / NO_CALL
# 2) 档位记忆：把 prefill 规则原文塞进 messages，问「用户说『看下XAU』走哪档」，只答档位名
# 3) 读图：data:image/png;base64 发真实截图，要求品种/周期/最后价/可见低，四项逐行
```

要点：`max_tokens` 太小会把 reasoning 模型截成空 content（用 ≥1200 判内容）；响应里的 `model` 字段在中转上只是**回显请求名**，不能当身份证据。

## 本轮落地结果（2026-09-12）

- 视觉槽：`hermes config set auxiliary.vision.provider custom:b.ai` + `.model gpt-5.6-luna`；三层验证通过（`resolve_vision_provider_client()` → `(provider, client, model)` 返回 `b.ai / gpt-5.6-luna`；真图四项全对；本会话 `vision_analyze` 6.62s、无 429）。
- 兜底链：改为 `nemotron-3-super-120b-a12b:free` → `nemotron-3-ultra-550b-a55b:free` → `ling-3.0-flash-fin:free`；`hermes config set fallback_providers '[{...}]'` 写入后读回 `type list / len 3` 正常（本版本对 list-of-dict 写入没有踩到字符串陷阱，但仍必须读回类型）。
- 主模型切换（config 仍是 `openai-codex/gpt-5.6-luna`，会话跑 `custom:b.ai/deepseek-v4.1-flash`）属用户偏好决策，已给推荐并等回话；切换时必须同步 `prefill_trading_rules.json` 里写死的「默认使用当前单模型 GPT-5.6 Luna」文案与 cron 里的旧模型名。
