# 模型路由决策框架：质量、延迟与套餐用量

## 适用场景

用户需要在主模型、fallback、delegation、compression、vision 与 MoA 之间分配模型，尤其是 Ollama Pro（GPU 时间计量）与外部按量 GPT 混合使用时。

## 先收集事实，再推荐

1. 读取活跃 `config.yaml`，列出所有自动调用入口：主模型、fallback、delegation、compression、vision、MoA reference/aggregator。
2. 读取模型目录，按能力筛选：context、tools、reasoning、image input、退役状态。
3. 查官方模型页的 Usage 等级；不要用参数量或 token 数代替实际套餐消耗。
4. 明确用户目标的优先级：延迟、质量、Ollama套餐压力、外部API费用、是否常驻MoA。
5. 只给一个主推架构；用户确认后再写配置并实测。

## Ollama Pro + 按量GPT的稳定基线

当用户重视速度、质量和节省Ollama套餐，而GPT按量费用可接受：

- 主模型：`ollama-cloud:deepseek-v4-flash`（Medium Usage、1M上下文）
- fallback：GPT → GLM 5.2 → Kimi K2.6
- delegation：GPT（避免3个高耗Ollama子Agent占满并发槽）
- compression：V4 Flash
- vision：通过真实交易图/OCR测试且未临近退役的Ollama多模态模型
- V4 Pro：Extra High，只放显式Deep或手动终审，不进入日常自动路径

若用户暂时停用MoA：只切换 `model` 为单主模型，保留已验证的MoA presets供手动调用，不删除。

## MoA设计

### 常驻平衡型

- References：V4 Flash + GLM 5.2
- Aggregator：GPT
- 理由：Flash提供速度，GLM 5.2提供近1M上下文和长任务审计，GPT提供异构聚合；不常驻V4 Pro。

### Deep复核型

- References：V4 Pro + GLM 5.2 + Kimi K2.6
- Aggregator：GPT
- 正好占用Ollama Pro三个云并发槽；只用于高风险、事件、严重证据冲突或核心系统修改。

## 交易场景权限边界

模型负责读取证据、提出候选计划、反方审查和解释冲突；Python风控闸门负责唯一的 GO/WAIT/NO-GO、仓位和杠杆裁决。多模型一致不等于概率，也不能覆盖数据新鲜度、R:R、事件窗口、回撤和组合暴露硬闸门。

## 验证清单

- `hermes config check`
- `hermes moa list`
- 单模型真实请求，不只解析配置
- Default/Deep各跑一次真实MoA
- 聚合者跑一次“工具调用→工具结果→最终答复”闭环
- 视觉模型用已知答案图片验证关键字段
- 断言退役模型不在任何自动入口
- 断言V4 Pro只出现在预期的Deep/手动入口
- 重启Gateway并确认运行状态
- 写入备份路径

## 常见误区

- fallback只处理调用失败，不能按任务复杂度自动升级。
- “订阅内”不等于“无限”；Ollama按GPU时间和模型难度计量。
- MoA每次工具迭代可能重新扇出参考模型，延迟和消耗会放大。
- 不要因为用户依赖模型辅助交易，就把最高耗模型放进所有自动入口。
- 不要连续提出互相矛盾的架构；每次修订必须说明是哪条新事实改变了裁决。
- GLM 5.2应作为长上下文/证据审计核心候选，而不是只当普通末位备用。
