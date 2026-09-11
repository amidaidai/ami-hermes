# TV DMI决策引擎实现模式 (v6.9.14-15)

## 新增函数

### `_parse_tv_dmi_table(tv_tables) → dict`
- 从 TV Pine table 解析 DMI 决策表
- 输入: `[{"rows": ["等级 | X", "处理 | 结构冲突", ...]}]`
- 输出: `{"等级": "X", "处理": "结构冲突", "CVD": "顺多确认", ...}`

### `_apply_tv_dmi_override(meta, engine_data, symbol, dmi_rows, tv_vals) → dict`
- TV DMI A/B/C/X → card status/direction
- A多/A空 → meta.status = "A做多/做空" · meta.priority_plan = "A"
- X → meta.status = "X禁做" · meta.direction = "wait"
- 同时注入 TV CVD/POC/VAH/VAL 到 engine_data

### `_tv_cvd_override(cvd_data, tv_vals) → dict`
- 用 TV CVD Value/Slope 替代 Binance Taker 代理 CVD
- slope > 50 = "买" · < -50 = "卖" · < 10 = "中性"
- 质量: |slope| > 500 = A · > 200 = B · else C
- source 标记 "TV真实CVD"

### `_asset_weight_bias(symbol, bias_cn, klines, cvd_data) → str`
- 加密: 放量+CVD方向加分
- 贵金属/外汇: 扫掠权重更高
- 股票: 放量确认方向
- 对齐 TV SVP 多市场评分逻辑

## TV信号监控管道 (v6.9.15)

### `tv_signal_monitor.py`
- 分级推送: A多/A空→必推 · B+关键位→推送 · C/X→跳过
- 防重复: 同等级30min内不重复 · 日上限 A6次/B3次
- 状态持久化: `data/tv_signal_state.json`

### cron agent 配置 (`hermes/cron/tv_signal_monitor.yaml`)
- 每5分钟: 读TV MCP → 判断等级 → A/B(关键位)推 · C/X静默
- 无机会不用推送: 只写心跳不浪费token

## Patch工具f-string转义异常·workaround

**问题**: `patch` 工具在 Python f-string 含双引号时产生转义异常(如 `\"` 变成 `\"`)
**解决**: 用 `execute_code` (Python) 直接操作文件: `read_file` + Python `str.replace` + `write_file`
