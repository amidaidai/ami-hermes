# Hermes MoA 推理默认值与继承验证

## 通用结论

- `reasoning_effort` 省略或设为 YAML `null` 是受支持的：Hermes 解析为没有显式 `reasoning_config`，由对应 Provider/模型使用自己的默认策略。
- `auto` 不是 Hermes 的正式推理档位。当前解析器会把它解析为空配置，但配置解析路径可能记录 unknown-value 警告；不要把它当成“按任务难度自适应”的开关。
- 合法显式档位为 `none`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max`、`ultra`；`none` 明确关闭推理。
- MoA 参考模型只读取自身 slot 上的 `reasoning_effort`。参考 slot 未设置时，不继承全局 `agent.reasoning_effort`。
- MoA 汇总模型是实际执行模型。其推理优先级为：汇总 slot 的 `reasoning_effort` > `agent.reasoning_overrides` 中的模型覆盖 > 全局 `agent.reasoning_effort`。三者都没有时才交给 Provider 默认值。
- `temperature` 与 `reasoning_effort` 独立；若也要让 Provider 决定采样参数，应删除或设为 `null` 的 `reference_temperature` / `aggregator_temperature`。

## 审计判定

看到一个 preset 时，分别回答：

1. 参考模型是否在 slot 上显式设置推理强度？
2. 汇总模型是否被全局 `agent.reasoning_effort` 间接设置？
3. 是否写了非规范的 `auto`？
4. preset 是否 `enabled: true`？
5. 它是否只是被 `hermes moa list` 列出，还是实际被 `/model <preset> --provider moa` 或顶层 `model.provider: moa` 选中？

若目标是“所有模型使用 Provider 默认值”，应同时省略全局 `agent.reasoning_effort`、所有参考 slot 的 `reasoning_effort` 和汇总 slot 的 `reasoning_effort`。若只省略参考 slot 而保留全局值，通常是“参考模型默认、汇总模型固定全局档位”。

## 现场验证记录（2026-09-02，Hermes Agent v0.20.6）

- 当前配置识别到命名 preset `AMI`，且 `AMI.enabled: true`。
- `AMI` 的参考模型为 `openrouter:minimax/minimax-m3:free` 和 `openrouter:nvidia/nemotron-3.5-lightning:free`，汇总模型为 `openai-codex:gpt-5.6-luna`。
- AMI 参考 slot 没有 `reasoning_effort`；全局仍有 `agent.reasoning_effort: medium`，所以当前 AMI 的参考模型走各自默认，Luna 汇总器有效档位为 `medium`。
- 删除全局推理字段后的纯函数解析结果为 `None`，证明“完全交给 Provider 默认”在当前版本受支持。
- `parse_reasoning_effort("auto")` 也返回 `None`，但这不是规范值，不能据此宣称 Hermes 提供了智能自适应推理。
- `hermes chat -q ... --provider moa --model AMI -Q` 的真实 AMI 入口测试返回 `AMI_MOA_OK`，约 127 秒完成；这证明 preset 入口和汇总链路可用，但不等于每个 Provider 都会采用相同的内部推理策略。
- `hermes moa list` 显示 `default` 仍是 Default/Active；AMI 虽已启用但不是默认 preset。使用时应精确写 `/model AMI --provider moa`（名称大小写按配置保持）。
