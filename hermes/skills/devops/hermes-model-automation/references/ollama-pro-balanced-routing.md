# Ollama Pro：质量、速度与套餐消耗的平衡路由

## 官方计量事实（2026-07）

- Ollama Cloud 不是固定 token 计费；usage 主要反映云端 GPU 时间，取决于模型运行难度、请求持续时间和缓存命中。
- 短请求、共享缓存上下文的请求消耗更少。
- Pro：Free 的 50 倍云用量；最多同时运行 3 个云模型。
- 会话额度每 5 小时重置，周额度每 7 天重置。
- 用户的实际余额只能在已登录的 `https://ollama.com/settings` 查看；未登录时不得声称看到了个人剩余额度。

来源：Ollama Pricing 与 Cloud 官方文档。

## 已核实模型消耗档位

| 模型 | 官方 Usage | 上下文 | 推荐角色 |
|---|---:|---:|---|
| `deepseek-v4-flash:cloud` | Medium | 1M | 主模型、压缩、日常工具执行 |
| `deepseek-v4-pro:cloud` | Extra High（Level 4） | 1M | 仅显式 Deep / 重大终审 |
| `kimi-k2.6:cloud` | High | 256K | 中文与异构参考 |
| `glm-5.2:cloud` | High | 976K | 长上下文参考 |
| `minimax-m3:cloud` | High | 512K | 代码、Agent、多模态参考 |
| `qwen3.5:397b:cloud` | 以模型页当前标示为准 | 256K | 视觉/OCR（已实图验证） |

不要把上下文长度、参数量或 token 数当作套餐消耗的直接代理；优先读取每个 Ollama 模型页的 `Usage` 等级。

## 当外部 GPT 按量计费且用户不怕费用时

最佳平衡不是把 Ollama 的最强模型放满所有自动槽位，而是保护 Pro 的 5 小时/周额度：

```text
主模型：Ollama V4 Flash
自动强兜底：GPT
Ollama异构兜底：Kimi → GLM → Qwen
委派：GPT
压缩：V4 Flash
视觉：经实图验证且未临近退役的 Ollama 多模态模型
V4 Pro：只进入显式 Deep MoA
```

推荐 fallback：

```yaml
fallback_providers:
  - provider: api.aijws.com
    model: gpt-5.6-sol
  - provider: ollama-cloud
    model: kimi-k2.6:cloud
  - provider: ollama-cloud
    model: glm-5.2:cloud
  - provider: ollama-cloud
    model: qwen3.5:397b:cloud
```

V4 Pro 不进入自动 fallback、全局 delegation 或默认 MoA；临时网络错误不值得触发 Extra High 使用。

## MoA 并发设计

Pro 同时最多运行 3 个 Ollama 云模型。参考层若放 4 个 Ollama 模型，第 4 个可能排队，速度反而下降。

日常交叉验证：

```text
Kimi + GPT → V4 Flash
```

建议：参考 1000 tokens，聚合 4096 tokens。普通对话不要默认永久挂 MoA，直接使用 V4 Flash；需要碰撞时显式调用。

重大任务 Deep：

```text
V4 Pro + GLM + Kimi → GPT
```

恰好占用 3 个 Ollama 并发槽，GPT 聚合不占 Ollama 槽。建议参考 1500 tokens、聚合 8192 tokens。

## 配置与验证顺序

1. 从官方模型页核实每个候选的 Usage 等级、上下文、工具和图像能力。
2. 查看当前套餐与并发限制；查看个人剩余额度必须登录 settings。
3. 先设计角色，后写配置；避免同一 Extra High 模型同时占主模型、fallback、delegation 和 MoA。
4. 写入前备份 `config.yaml`。
5. `hermes config check`。
6. 分别做候选文本连通测试。
7. MoA 必须真实运行 default/deep；GPT 聚合者还要做一次工具调用测试。
8. 视觉模型必须使用真实交易图和中文密集表格探针。
9. 检查官方退役表，临近退役模型不得进入新配置。

## 退役处理

Ollama Cloud 会定期退役模型。2026-07-15 `gemini-3-flash-preview` 退役，官方建议 `minimax-m3`；棠溪视觉路由则应从仍可用候选中实图比较后选择，不能仅照官方替代名盲切。