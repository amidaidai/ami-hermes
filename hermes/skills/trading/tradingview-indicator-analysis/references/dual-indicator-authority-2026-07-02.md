# 双指标权威协议（2026年7月2日）

> ⚠ **本文已作废（2026-09-11）**：这是当时（2026-07-02）的实况记录，**不是当前字段映射权威**。
> 文中 `svp_indicator.txt` / `haldro_indicator.txt`、v5/v6、3163/469 行、10 行行动格、
> `MCP CVD Value` / `OI Total` / `Estimated CVD Value` 等全部已失效。
> **现行权威**：`D:/Hermes agent/docs/tv-indicator-field-map.md`（v3.0）+
> 契约 `D:/Hermes agent/scripts/tv_indicator_contract.py`。
> 定版指标：主 `SVP_主指标_空格修正_20260911.pine`（3557 行·68a34fc3）/ 副 `AggVol_副指标_最终版_20260911.pine`（966 行·c4c563ef）。


## 适用场景

当用户要求更新、校准或分析棠溪 TradingView 驾驶舱指标时，本文件是当前双指标协议的会话级权威记录。目标是防止未来分析继续沿用旧指标假设污染数据。

## 当前生产指标

| 指标 | 生产文件 | 行数 | 权威含义 |
|---|---:|---:|---|
| 主指标 | `D:/Hermes agent/svp_indicator.txt` | 3163 | `SVP+ICT+VWAP+CVD`；含 EMA、FVG/HTF FVG、行动格 v2、MCP Data Window |
| 副指标 | `D:/Hermes agent/haldro_indicator.txt` | 469 | `Volume Aggregated Spot & Futures`；含覆盖率、Composite、OI/CVD Data Window |

## 已作废的旧假设

- “主指标没有显式 FVG 代码”作废：当前主指标已内置 `SHOW_FVG`、`SHOW_HTF_FVG`、CE 50%、位移过滤，并在行动格确认行输出 `FVG✓` / `FVG✓HTF` / `扫★HTF`。
- “主指标 Data Window 编码导出已移除”作废：当前主指标已恢复 `MCP Side Code`、`MCP Grade Code`、`MCP Setup Score`、`MCP Entry Price`、`MCP Stop Price`、`MCP Target Price`、`MCP CVD Value`、`MCP Quality Code`。
- “副指标有独立占比行”作废：当前副指标将合约占比并入“量能”行，新增“覆盖”行与覆盖率 Data Window。
- 不再用旧 `SVP+ICT+VWAP+EMA+CVD` / 旧 HALDRO 字段名覆盖用户新上传指标。

## 正式分析读取顺序

1. 先确认 TV 健康、品种、周期和价格数量级。
2. 加密分析五周期固定读取：1D、4h、1h、15m、5m。
3. 每周期优先读主指标行动格 v2：结论、方向、进场、止损、目标、确认、风险、磁吸↑、磁吸↓。
4. 读取主指标 MCP Data Window 兜底：Side/Grade/Score/Entry/Stop/Target/CVD/Quality。
5. 读取副指标行动格：信号、结论、风险、高周、持仓、流向、覆盖、量能、爆仓、操作。
6. 读取副指标 Data Window：OI Total、CVD Value、Volume Ratio、Coverage、Exchange Dominance、Confirm Score、Composite。
7. 读取 labels / lines / boxes；FVG 应优先从主指标 boxes 与确认行读取，只有 TV MCP 未返回 boxes 时才用 OHLCV 补算。
8. 外部交叉验证 Binance OI/Funding/Taker/多空比/Depth、情绪、事件。
9. 截图必须是 full，含价格轴、主行动格、副指标或 CVD/OI 窗格。
10. 输出完整驾驶舱表格：多周期定位、关键位矩阵、多源交叉验证、矛盾点、AB方案、评分、管线完成度。

## 代码与测试同步点

- `scripts/auto_card.py` 应解析当前 MCP Data Window 字段，并支持副指标 `风险` / `覆盖` 行。
- `scripts/render_tv_card.py` 应允许副指标 `coverage` / `risk` 替代旧 `share`。
- `tests/test_render_tv_card.py` 应覆盖当前 MCP DW 字段与副指标新行动格行。
- 提交前至少运行：`python -m pytest tests/test_render_tv_card.py tests/test_tv_action_panel_decode.py -q`。

## 关键 pitfall

如果未来读图结果与旧技能文档冲突，以用户最新上传源码、`docs/tv-indicator-field-map.md` 和本参考文件为准；不要从记忆里恢复旧指标判断。