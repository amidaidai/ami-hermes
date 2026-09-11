# 棠溪两个TV指标完整源码与分析指南

## 1. Cumulative Volume Delta (CVD)

跨低周期扫描买卖成交量差，以蜡烛形式绘制每根K的Delta。绿色=买方主导，红色=卖方主导。

**MCP读取**：`mcp_tradingview_data_get_study_values` → `"CVD"` 字段。

**信号判断**：正值+上升=买盘·负值+下降=卖盘·翻正=吸筹·斜率转正=出货尾部。

## 2. SVP+ICT+VWAP+EMA+CVD (2024行)

六大组件全可MCP读取：

| 组件 | MCP方式 |
|------|--------|
| SVP(POC/VAH/VAL/nPOC) | `get_study_values` |
| ICT(会话高低/扫掠) | `get_pine_lines` + `get_pine_labels` |
| VWAP(会话+周/月) | `get_study_values` |
| EMA(9/21/34/55+云) | `get_study_values` |
| CVD(值/斜率/背离) | `get_study_values` |
| DMI决策表(A/B/C/X) | `get_pine_tables` |

DMI决策表示例：`等级 | C等待` `CVD | 买盘回升` `执行 | 多:破VWAP xxx｜空:反抽VWAP xxx`
