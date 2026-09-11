# 额度敏感路由与模型退役切换

## 适用情形

- 旗舰模型订阅内可用，但单位任务额度消耗过高。
- provider 发出模型即将退役通知。
- 视觉、MoA、fallback 等自动槽位可能隐式调用高耗或退役模型。

## 审计矩阵

逐项检查：主模型、`fallback_providers`、`auxiliary.compression`、`auxiliary.vision`、`delegation`、MoA全部preset的reference与aggregator、cron脚本硬编码模型。

## 额度治理基线

- 高耗旗舰：仅手动终审，不进入任何自动链。
- 日常：Flash级主模型；压缩与委派也用稳定轻量模型。
- fallback：异构中档模型逐级降级，外部付费放最后。
- 默认MoA：2个异构参考，每个约800 tokens；Flash聚合约3072。
- deep MoA：2个异构参考，每个约1000 tokens；非旗舰强模型聚合约4096。

## 退役切换步骤

1. 收到通知后立即定位所有引用。
2. 同provider优先筛选替代模型。
3. 视觉候选必须通过已知答案的交易图和中文密集表双夹具。
4. 切换配置并验证运行时实际解析结果。
5. 验证旧模型不再出现在自动路由；保留手动入口需明确标注。
6. 重载gateway并做候选连通测试。

## 2026-07-11验证案例

- DeepSeek V4 Pro因额度消耗高，从fallback及deep MoA移除，仅保留手动终审。
- fallback改为 Kimi K2.6 → GLM 5.2 → Qwen3.5 397B → 外部GPT。
- deep MoA改为 Kimi K2.6 + MiniMax M3 → GLM 5.2。
- `gemini-3-flash-preview:cloud` 将于2026-07-15退役，主视觉提前切换到已通过双夹具的 `qwen3.5:397b:cloud`。

具体型号与日期属于案例，不应覆盖未来实时catalog和重新基准测试结果。