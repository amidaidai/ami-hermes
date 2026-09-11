# 常驻 MoA：GLM 5.2 核心路由（2026-07-11）

## 适用条件

- 用户明确要求所有主会话长期使用 MoA。
- Ollama 为 Pro：云使用量按GPU时间/模型难度计量，5小时会话额度、7天周额度、3个云模型并发。
- 外部 GPT 为API按量计费，用户费用不敏感。
- 系统用于交易分析辅助，但最终执行仍受Python硬闸门与风控宪法约束。

## 已核实模型事实

| 模型 | Ollama Usage | Context | 输入 | 推荐职责 |
|---|---|---:|---|---|
| DeepSeek V4 Flash | Medium | 1M | Text | 快速主分析、压缩 |
| GLM 5.2 | High | 976K | Text | 常驻证据审计、长上下文一致性 |
| Kimi K2.6 | High | 256K | Text/Image | Deep中文语境与独立视角 |
| DeepSeek V4 Pro | Extra High | 1M | Text | 仅显式Deep参考 |
| Qwen3.5 397B | 页面等级未明确 | 256K | Text/Image | 主视觉（实图夹具已通过） |
| MiniMax M3 | High | 512K | Text/Image/Video | 视觉/研究备用 |
| GPT 5.6 Sol | 外部API | 400K配置值 | Text+tools已验证 | 聚合、委派、fallback |

GLM 5.2官方优势证据集中于长上下文、Agent和编码：976K上下文；Terminal-Bench 2.1为81.0、SWE-bench Pro为62.1（厂商报告）。这些证据支持其担任长任务/证据审计角色，**不支持直接声称其短线交易胜率更高**。

## 推荐配置骨架

```yaml
model:
  default: default
  provider: moa

fallback_providers:
  - provider: api.aijws.com
    model: gpt-5.6-sol
  - provider: ollama-cloud
    model: deepseek-v4-flash:cloud
  - provider: ollama-cloud
    model: glm-5.2:cloud
  - provider: ollama-cloud
    model: kimi-k2.6:cloud

moa:
  default_preset: default
  active_preset: default
  presets:
    default:
      reference_models:
        - provider: ollama-cloud
          model: deepseek-v4-flash:cloud
        - provider: ollama-cloud
          model: glm-5.2:cloud
      aggregator:
        provider: api.aijws.com
        model: gpt-5.6-sol
      reference_max_tokens: 1000
      max_tokens: 5000
      enabled: true
      reference_temperature: 0.35
      aggregator_temperature: 0.15

    deep:
      reference_models:
        - provider: ollama-cloud
          model: deepseek-v4-pro:cloud
        - provider: ollama-cloud
          model: glm-5.2:cloud
        - provider: ollama-cloud
          model: kimi-k2.6:cloud
      aggregator:
        provider: api.aijws.com
        model: gpt-5.6-sol
      reference_max_tokens: 1200
      max_tokens: 6500
      enabled: true
      reference_temperature: 0.30
      aggregator_temperature: 0.10

delegation:
  provider: api.aijws.com
  model: gpt-5.6-sol

auxiliary:
  compression:
    provider: ollama-cloud
    model: deepseek-v4-flash:cloud
  vision:
    provider: ollama-cloud
    model: qwen3.5:397b:cloud
```

## 角色提示原则

- Flash：快速建立主结构与候选计划。
- GLM：只审计数据完整性、时间一致性、结构矛盾、遗漏证据，不与Flash互相附和。
- GPT聚合：明确列出支持/反对证据、缺失数据、候选计划；不得把模型一致度写成概率。
- Deep中的V4 Pro：寻找常规模型遗漏的尾部风险与反例。
- Python闸门：唯一输出GO-A/GO-B/WAIT/NO-GO、仓位与杠杆。

## 验证清单

1. `hermes moa list`确认default/deep模型与配置一致。
2. 验证`model.provider=moa`且`model.default=default`。
3. 扫描自动路径：V4 Pro只能出现在`moa.presets.deep.reference_models`或手动模型目录。
4. Default和Deep分别跑真实工具链：参考→GPT工具调用→工具结果→最终回复。
5. GPT delegation单独跑一次含文件/网页读取的真实子Agent任务。
6. 视觉使用真实TradingView图和中文密集表格夹具，不接受纯文本OK测试。
7. 影子对比：Default vs Deep在同一Point-in-Time快照、同一硬闸门下比较样本外期望值、回撤、WAIT质量和延迟；没有显著价值则不增加第三档Trade。

## 退役与缓存陷阱

模型缓存可能仍列出已退役型号。任何路由设计都要先对照Ollama Cloud官方退役列表；缓存可见不等于运行时可用。收到退役通知后，应在72小时前完成替换、真实探针和运行时解析验证。