# SVP 指标 Data Window 编码字段解码（历史参考）

## ⚠ 此文档仅适用于旧版本

**当前版本的主指标（v10, 2026-06-30 后）Data Window 编码导出已彻底移除。**
- Pine 源码第3058-3059行明确标注：「Data Window 编码导出已移除（无外部系统读取），以释放 TradingView 64 绘图配额」
- 所有9个编码plot（Magnet+ICT+Score, Scores, ICT Count, Risk, CVD Session, Replay Side+Grade, SMT Div, Eff Params, ADR Proj）均不再存在于 `study_values` 中
- 副指标（Volume Aggregated）新增4个简单`display=display.data_window` plot 供 TV MCP study_values 读取

## 当前数据获取路径（2026-06-30 后）

| 数据来源 | TV MCP 工具 | 数据内容 |
|---------|------------|---------|
| **行动格（主）** | `data_get_pine_tables` | 结论/方向/进场/止损/目标/核对/磁吸↑/磁吸↓ |
| **行动格（副）** | `data_get_pine_tables` | 信号/结论/高周/持仓/流向/量能/爆仓/操作 |
| **study_values（主）** | `data_get_study_values` | S VWAP/±1σ/±2σ, EMA9/21/34/55, POC/VAH/VAL/nPOC/WVWAP/MVWAP/DO |
| **study_values（副）** | `data_get_study_values` | OI Total, CVD Value, Volume Ratio, Composite（新增）|
| **pine_labels** | `data_get_pine_labels` | ICT会话高低、POC/VAH/VAL标签、上周/前日高低 |
| **pine_lines** | `data_get_pine_lines` | 支撑/阻力水平价位 |
| **pine_boxes** | `data_get_pine_boxes` | FVG缺口区上下边界 |

## 如果希望恢复编码导出

在恢复到主指标前需评估：

```pine
// 在 Pine 文件末尾（line 3138之后）添加，配额评估：
plot(magnetEncoded, "Magnet+ICT+Score", display=display.data_window)
plot(scoresEncoded, "Scores (Loc*100+Cfm*10+Ext)", display=display.data_window)
plot(gradeEncoded, "Replay Side+Grade (Side*10+Grade)", display=display.data_window)
// 上述3个plot会消耗3/64绘图配额，可捕获磁吸、评分、等级核心数据
```

## 更新历史

- 2026-06-26：初始创建（v10优化版，编码活跃）
- 2026-06-30：Data Window 编码完全移除，改为表格 + 副指标DV plot路径
