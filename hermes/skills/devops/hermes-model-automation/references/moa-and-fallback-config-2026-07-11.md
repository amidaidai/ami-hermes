# MoA + Fallback + Delegation 配置实战（2026-07-11）

本会话的实际配置过程记录，供未来参考。

## 起始状态问题

用户的 config.yaml 有三条失效的 fallback 链 + 错误的 delegation 模型 + MoA 完全关闭：

| 配置项 | 问题 |
|--------|------|
| fallback 1: `deepseek:deepseek-v4-flash` | 无 DEEPSEEK_API_KEY |
| fallback 2: `openrouter/owl-alpha` | OpenRouter 上无此模型 |
| fallback 3: `xai-oauth:grok-4.20-0309-non-reasoning` | 模型名旧 |
| delegation: `openrouter:nvidia/nemotron-3-ultra-550b-a55b:free` | 550B 太慢，3并发容易限流 |
| MoA: `enabled: false` | 完全关闭 |
| MoA ref: `opencode-go:deepseek-v4-flash` | 无此 provider 凭证 |
| MoA aggregator: `auto:gpt-5.5` | auto 不可靠，gpt-5.5 无明确 provider 映射 |

## 最终配置（Ollama Pro 优先策略）

用户明确要求"优先使用ollama的账号"。最终配置将主模型、兜底链前两级、子任务委派、MoA 参考模型 + 聚合者全部放在 ollama-cloud（Pro 额度内），仅保留 api.aijws.com 作为最终兜底、1个 openrouter 免费模型作为 deep 预设的外部视角补充。

### 主模型 + 兜底链

```yaml
model:
  default: deepseek-v4-flash
  provider: ollama-cloud

fallback_providers:
- model: deepseek-v4-pro:cloud
  provider: ollama-cloud         # 同家升级，推理更强
- model: kimi-k2.6:cloud
  provider: ollama-cloud         # 换厂商，256K长上下文
- model: gpt-5.6-sol
  provider: api.aijws.com        # Ollama全线挂了才用付费GPT
```

### Delegation

```yaml
delegation:
  model: deepseek-v4-flash:cloud
  provider: ollama-cloud
```

### MoA default 预设（日常分析，全 Ollama，3次/轮）

三个完全不同的中国厂商架构（Kimi / GLM / DeepSeek）→ 真正多元碰撞，全在 Pro 额度内，零额外成本。

```yaml
moa:
  presets:
    default:
      reference_models:
        - provider: ollama-cloud
          model: kimi-k2.6:cloud       # Kimi 月之暗面，256K长上下文
        - provider: ollama-cloud
          model: glm-5.2:cloud         # 智谱GLM，逻辑推理
      aggregator:
        provider: ollama-cloud
        model: deepseek-v4-flash:cloud  # DeepSeek，综合+工具调用
      reference_max_tokens: 1000
      max_tokens: 4096
      enabled: true
      reference_temperature: 0.6
      aggregator_temperature: 0.4
```

### MoA deep 预设（深度分析，4次/轮）

保留 1 个腾讯 Hy3 免费外部视角（金融反幻觉），其余全 Ollama Pro。

```yaml
moa:
  presets:
    deep:
      reference_models:
        - provider: ollama-cloud
          model: deepseek-v4-pro:cloud    # 深度推理
        - provider: ollama-cloud
          model: kimi-k2.6:cloud          # 长上下文
        - provider: openrouter
          model: tencent/hy3:free         # 腾讯295B金融视角（免费外部补充）
      aggregator:
        provider: ollama-cloud
        model: deepseek-v4-flash:cloud
      reference_max_tokens: 1500
      max_tokens: 4096
      enabled: true
      reference_temperature: 0.7
      aggregator_temperature: 0.3
```

## 成本结构（每轮）

| 预设 | Ollama Pro | OpenRouter免费 | 付费GPT |
|------|-----------|---------------|---------|
| default | 3次 | 0 | 0 |
| deep | 3次 | 1次 | 0 |
| 兜底（正常不用） | 0 | 0 | 0 |

日常分析 100% 在 Ollama Pro 额度内完成，零额外支出。

## Ollama-cloud 模型验证工作流（关键技巧）

### OLLAMA_API_KEY 不在 .env 里

`hermes auth list` 显示 ollama-cloud 凭证存在，但 `echo $OLLAMA_API_KEY` 在终端里为空。key 由 Hermes 桌面运行时注入，不在 `~/.hermes/.env` 中。

**后果**：用 `curl https://ollama.com/v1/chat/completions -H "Authorization: Bearer $OLLAMA_API_KEY"` 测试会得到 403 Unauthorized（空 key）。不能用 curl 直测 ollama-cloud。

### 正确验证方式：通过 hermes chat -q

```bash
# 1. 连通性测试
hermes chat -q "Say OK" --model "deepseek-v4-flash:cloud" --provider ollama-cloud -Q
# 输出含 "OK" = 正常

# 2. 批量连通性测试
for model in "deepseek-v4-flash:cloud" "deepseek-v4-pro:cloud" "glm-5.2:cloud" \
  "kimi-k2.6:cloud" "kimi-k2.7-code:cloud" "minimax-m3:cloud" "gemma4:31b-cloud"; do
  echo -n "$model: "
  hermes chat -q "Say OK" --model "$model" --provider ollama-cloud -Q 2>&1 \
    | grep -E "OK|error|Error|refused" | head -1
done

# 3. 工具调用测试（确认模型支持 tool calling）
hermes chat -q "What time is it? Use the terminal tool to run 'date' and tell me." \
  --model "kimi-k2.6:cloud" --provider ollama-cloud -Q --yolo 2>&1 | tail -5
# 能正确调用 terminal 工具并返回时间 = 工具调用正常
```

### 2026-07-11 实测结果

全部 7 个 ollama-cloud cloud 模型连通性 + 工具调用均通过：
- `deepseek-v4-flash:cloud` ✅
- `deepseek-v4-pro:cloud` ✅
- `glm-5.2:cloud` ✅
- `kimi-k2.6:cloud` ✅
- `kimi-k2.7-code:cloud` ✅
- `minimax-m3:cloud` ✅
- `gemma4:31b-cloud` ✅

## 可用 Provider 模型清单（2026-07-11）

### ollama-cloud（Pro 账号，全模型支持工具调用）

```
deepseek-v4-flash:cloud    deepseek-v4-pro:cloud    deepseek-v3.2:cloud
glm-5.2:cloud              glm-5.1:cloud            glm-4.7:cloud
kimi-k2.6:cloud            kimi-k2.7-code:cloud
minimax-m3:cloud           minimax-m2.7:cloud      minimax-m2.5:cloud
gemma4:31b-cloud           gemma4:26b
qwen3.6:27b                qwen3.5:4b               qwen3.5:2b
```

### OpenRouter 免费模型（支持工具调用，金融相关优先）

```
tencent/hy3:free                           295B MoE/21B active  ctx=256K  ← 金融强
nvidia/nemotron-3-ultra-550b-a55b:free     550B MoE/55B active  ctx=1M
nvidia/nemotron-3-super-120b-a12b:free     120B MoE/12B active  ctx=1M    ← deep预设用
qwen/qwen3-next-80b-a3b-instruct:free      80B MoE/3B active   ctx=256K
openai/gpt-oss-120b:free                   117B MoE/5.1B active ctx=131K
google/gemma-4-31b-it:free                 31B dense            ctx=262K  ← vision
```

## 关键教训

1. **用户偏好：Ollama Pro 优先** — 当用户有 Ollama Pro 账号时，主模型、兜底前级、子任务、MoA 参考 + 聚合者尽量全放 ollama-cloud，Pro 额度内零额外支出。外部模型（openrouter 免费、付费 GPT）只作最终兜底或视角补充。
2. **`hermes config set` 不能追加列表元素** — `reference_models.1.provider` 会 IndexError。用 Python yaml 直写整个段。
3. **`patch` 工具对 config.yaml 有写保护** — 必须 `hermes config set` 或 Python yaml 直写。
4. **`hermes moa configure` 交互向导控制有限** — 无法设 reference_max_tokens，复杂配置直接 Python yaml。非交互运行时会丢失多参考配置并自动选聚合者。
5. **聚合者不能用 codex_responses 模式模型** — gpt-5.6-sol 做 aggregator 可能工具调用不兼容。
6. **fallback 必须与实际凭证对齐** — 清理 auth 后同步更新 fallback，否则死链。
7. **deep 预设用 nemotron-3-super 而非 ultra** — 3个参考模型时 550B ultra 太慢，120B super 快一倍且 1M 上下文够用。
8. **MoA 成本 = 参考数 + 1** — default=3次/轮，deep=4次/轮，免费参考越多成本越低但延迟线性增长。
9. **OLLAMA_API_KEY 不在 .env** — 桌面运行时注入，curl 直测无效，必须 `hermes chat -q` 验证 ollama-cloud 模型。
10. **子任务模型选 deepseek-v4-flash 而非 hy3** — 当优先 ollama 时，delegation 用同厂商同模型（deepseek-v4-flash:cloud），不抢免费额度，3并发延迟一致。
11. **切换 delegation provider 必须清空旧覆盖字段** — 只改 `model/provider` 会遗留旧 `api_key/base_url`，形成“显示 Ollama、实际携带旧 OpenRouter 配置”的错路由。切换后设 `api_key: ''`、`base_url: ''`，验证时只断言为空，禁止打印密钥。
12. **Freerouter 与 Ollama Priority 必须职责隔离** — Freerouter 只维护 OpenRouter 模型发现、健康检查和 Web UI 可见性；主模型、fallback 前级、视觉、压缩、delegation、MoA 由 Ollama 路由管理。`OLLAMA_PRIORITY=true` 时 `patch_config()` 必须跳过配置修改。
13. **防定时任务反向覆盖要做哈希测试** — 调用 Freerouter `patch_config()` 前后计算 `config.yaml` SHA-256，哈希必须一致；这能抓出“当前配置正确、次日运维又改回去”的漂移。