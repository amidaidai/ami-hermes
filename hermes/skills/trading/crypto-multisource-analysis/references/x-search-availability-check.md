# x_search 可用性排查指南

## 背景

x_search 是 Hermes 内建工具（非 MCP 工具），通过 xAI OAuth 调用 Grok 模型搜索 X/Twitter。它在 `config.yaml` 中独立配置：

```yaml
x_search:
  model: grok-4.20-non-reasoning
  timeout_seconds: 90
  retries: 2
```

## 排查协议（5层）

### 第1层：tool_search 注册检查

```python
tool_search('x_search')
# 若返回包含名称为 x_search 的 tool → 已注册
# 若为空 → 跳到第2层
```

### 第2层：config 存在性

检查 `config.yaml` 是否有 `x_search:` 段：
```bash
grep 'x_search:' ~/AppData/Local/hermes/config.yaml
```

若不存在 → 用户未配置该工具，回退 web_search 并标注。

### 第3层：platform_toolsets 挂载检查（最常见根因）

x_search 是一个 **toolset**（工具集），需要在 `config.yaml` 的 `platform_toolsets` 中为当前平台启用。例如 Telegram 平台可能只包含：

```yaml
platform_toolsets:
  # ...
  telegram:
    - browser
    - file
    - web
    # ... 但不包含 x_search
```

检查方法：在 config.yaml 中找到 `platform_toolsets` 段，查看当前会话平台（telegram/cli/home/discord）是否包含 `x_search`。

**常见根因**：x_search 在 Telegram 平台工具集中未启用，仅在 `home` 或 `cli` 平台启用。

**修复**（需要修改 config.yaml）：
```yaml
platform_toolsets:
  telegram:
    - x_search   # 添加此行
```

### 第4层：delegate_task 代理调用

若当前平台没挂载但配置存在，可尝试将 x_search 调用派到有 x_search 的平台：

```python
delegate_task(
    goal="用 x_search 工具搜索 X/Twitter 情绪",
    context="查询关键词...",
    toolsets=['x_search', 'web', 'terminal']
)
```

注意：subagent 继承父会话的平台工具集限制。如果 subagent 也报 x_search 不可用，说明其运行环境同样受限。

### 第5层：web_search 降级

最后手段：
```python
web_search(query='...')  # 标注「web源·非X实时」
```

## 排查输出示例

```
x_sent ⚠ 三层检查：①tool_search搜不到→②config有x_search→③platform_toolsets.telegram无x_search
→ delegate_task(CLI工具集)也失败（subagent同样受限）→ web_search替代
用户有Grok但当前平台为Telegram未挂载该工具集。若需x_search直连，请在平台配置中启用。
```

## 注意事项

- x_search 不是 MCP 工具，不通过 `tool_call(name='x_search')` 调用，而是直接作为 Hermes 内建函数调用
- x_search 在 Telegram 群组中可能不可用，但在 CLI 模式中可能可用
- 用户说「我有 Grok」意味着 x_search 的底层 API 可用，但当前会话平台可能没挂载对应工具集
- 工具集级别的限制不受模型能力影响 — 即使 Gpt-5 也不代表 x_search 在当前平台可用
- **工具集变更后必须发 `/reset` 重启会话**：修改 config.yaml 的 platform_toolsets 后，当前正在运行的会话不会自动加载新工具
- **不要用 `hermes config set` 写数组**：`hermes config set platform_toolsets.telegram [...]` 会写出 YAML 字符串字面量而非数组，破坏配置。需用 Python + PyYAML 或直接编辑。详见 `hermes-config-yaml-array-pitfall.md`
