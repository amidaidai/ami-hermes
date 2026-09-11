# TV 证据与指标参与核验清单

## 切图证据闸门

1. 调用 `chart_set_symbol` / `chart_set_timeframe`。
2. 主指标切换后等待约 15–30 秒；仅读图表状态或 OHLCV 至少等待 2–3 秒。
3. 回读 `chart_get_state`，逐项核对 symbol、exchange、timeframe/resolution。
4. 只有完全匹配，才读取 Pine tables、study values、labels、lines 并截图。
5. 若回读仍为旧图：不得把 MCP 成功响应当作生效；重试切换，必要时重建 TV/CDP。
6. 截图必须是最终状态、`region=full`，并检查文件存在、尺寸有效、已复制到可渲染上传目录。

## SVP ICT 参与链

审计不能只证明 ICT 画线存在，必须追踪：

`f_sweep_scan()` → sweep/reclaim/reject → `bullStructureRaw` / `bearStructureRaw` → `sweepOrAcceptLong/Short` 与 MSS 许可 → A级闸门 → action path / invalidation → Python `FinalVerdict`。

若链路在行动格或 Python 层断开，应标为“指标存在但未完整消费”，不得称 ICT 已参与裁决。

## AggVol LSR 契约

- 适用范围：仅 crypto。
- 必须记录：source、freshness、available、ratio、crowding_state、`risk_only=true`。
- `ratio > 1.3` 且价格/方向同向：多头拥挤风险；`ratio < 0.8` 且价格/方向同向：空头拥挤风险。
- LSR 用于不追、降级或风险码，不加入 CVD/OI/量能/HTF 方向票，也不能独立授权执行。
- 缺失、过期或源不可用必须显示为缺失/降级；不能当作中性确认，不能用旧值冒充实时。
- 外部多空比回退时必须标明回退源，不能伪装成 TV LSR。

## 最小证据包

`chart_get_state` 回读 + 行动格/Data Window 解析 + 源状态/新鲜度 + 最终全屏截图。任何一项缺失都降低审计结论等级；身份不符时直接 fail closed。
