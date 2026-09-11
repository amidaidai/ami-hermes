# GPT-5.6 Luna 主模型现场验证（2026-09-02）

## 运行态证据

- Active profile：`default`；持久记忆、用户档案与memory工具均启用。
- 当时全局默认仍为 `gpt-5.6-sol / openai-codex`；Luna只是候选，未把“可探测”误报成“已路由”。
- `context_length_cache.yaml` 精确键 `gpt-5.6-luna@https://chatgpt.com/backend-api/codex` 为 `272000`。
- Luna真实工具探测：提示要求调用terminal执行固定回执，结果出现真实工具结果并最终返回 `LUNA_TOOL_OK`，证明达到 tool-capable。
- 档位探测：对“看下BTC”正确回答轻量档、15m主周期，证明prefill/规则可被读取。
- `--reasoning low` 的短回执探测成功；但不同提示的16秒、29秒、72秒总耗时不可直接算倍率，因为包含冷启动、工具往返与提示复杂度。

## 记忆继承口径

Hermes官方机制是按profile保存 `MEMORY.md` 与 `USER.md`，并在每个新会话启动时以冻结快照注入。由此：

- 同一profile换模型：持久记忆、用户档案、SOUL、prefill、skills、项目文件继续存在。
- 同一会话 `/model`：还保留当前聊天历史。
- 同一profile新会话：继承持久材料，但不自动复制全部临时对话；需要 `/resume` 或 session search 才能恢复临时细节。
- 换profile：默认隔离，不能承诺继承。
- 会话中刚写入的记忆已落盘，但冻结系统提示要到下一新会话才重新注入。

## 日常提速建议

- 主模型：普通 `gpt-5.6-luna`，不默认用 `-900k`。
- Quick/Inherit/标准：`reasoning=low`；完整/深度才升档。
- 保持streaming开启；`/focus`只减少显示，不减少模型工作量。
- 长会话明显变慢时用有边界的 `/compress here 2` 或开新会话；持久记忆不会因此丢失。
- `/fast fast --global` 使用Priority Processing；先披露潜在计费影响，再持久开启。
- 交易速度的主要固定成本还包括TV五周期切换和Pine重算等待；不要把全部延迟归因于LLM。
