# 模型路由清理与实测验收

用于清理 Hermes 中失效模型，同时避免误删“同名模型、不同提供商”的可用路由。

## 核心原则

- **按 `provider + model + base_url/api_mode` 识别路由**，不能只按模型名判断。相同模型名经不同提供商接入时，健康状态可以完全不同。
- 删除前逐条实测；一个提供商返回认证错误，不代表其他提供商上的同名模型不可用。
- 交易分析主链优先稳定和低延迟；未完成交易场景基准测试的可用模型先保留为手动复核，不要直接加入自动 fallback。

## 清理前的全槽位盘点

检查模型是否出现在：

1. `model` 主模型
2. `fallback_providers`
3. `delegation`
4. `auxiliary.vision`、`auxiliary.compression` 等辅助槽位
5. `moa.presets.*.reference_models`
6. `moa.presets.*.aggregator`
7. `custom_providers`

只删除已确认失效的具体路由。若某个 custom provider 未参与主路由且尚未实测，不要因模型同名连带删除。

## 最低实测标准

每条准备保留的分析模型至少做两类探针：

```bash
hermes chat -q '只回复OK' --provider <provider> --model <model> -Q
hermes chat -q '请使用terminal工具执行 date +%s，只回复工具返回的数字。' \
  --provider <provider> --model <model> -Q --yolo
```

- 第一条验证基本推理接口。
- 第二条验证 agent 工具调用，不允许只用 HTTP 200 或纯文本 `OK` 证明可承担自动分析。
- 视觉模型另做真实 TradingView 图探针，必须读出品种、明确价格和 CVD/指定窗格；文本探针不能证明视觉能力。

## 推荐清理动作

- 失效 fallback：从 `fallback_providers` 移除，不要留下必然失败的静默跳转。
- 失效 delegation：切回已验证主模型，避免子任务走坏路由。
- 失效 MoA：清空 reference/aggregator 并 `enabled: false`；不能只关主模型而遗漏手动 MoA 入口。
- 可用但未做交易基准的备用提供商：保留 custom provider，仅手动深度复核。

## 结构化配置陷阱

`hermes config set` 会正确解析布尔值和数字，但在部分版本中，传入 `'[]'`、`'{}'` 可能被保存成字符串，而非 YAML 列表/对象。写完必须重新解析并检查类型：

```python
import yaml
from pathlib import Path
p = Path.home() / 'AppData/Local/hermes/config.yaml'
d = yaml.safe_load(p.read_text(encoding='utf-8'))
assert isinstance(d.get('fallback_providers', []), list)
```

如果必须修正结构化节点，使用 Hermes 自己的安全 YAML 读写/原子写入机制，并在修改后运行：

```bash
hermes config check
```

不要直接输出或记录 `api_key`。

## 完成验收

- 配置可被 YAML 解析，列表/对象类型正确。
- 失效路由在所有自动槽位均不再出现。
- 主模型文本与工具调用均通过。
- 手动备用与自动 fallback 的角色明确。
- 新会话或 gateway 重载后再次确认实际解析的 provider/model。
