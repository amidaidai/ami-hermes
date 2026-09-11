# 孤儿脚本集成模式 v1.0

> 2026-06-30 审计修复 · 用于将独立/孤立脚本快速接入分析管线

## 问题

棠溪系统有大量已实现但未接入分析管线的"孤儿"脚本——它们功能完整、有公开API，但 auto_card.py 从不调用。审计发现6个孤儿脚本共2,000+行闲置代码。

## 方案

创建统一封装层 `orphan_integration.py`，提供 `run_orphan_checks()` 对外接口：

```
orphan_integration.run_orphan_checks(symbol, price, direction, klines=None) -> dict
```

每个孤儿脚本的调用封装为独立函数（try/except），单个失败不影响其他。

## 已集成的6个孤儿脚本

| 脚本 | 封装函数 | 产出 |
|------|---------|------|
| `meta_labeler.py` | `run_meta_label_gate()` | 执行门控闸门 |
| `orderflow_absorption.py` | `run_absorption()` | 订单流吸收/消耗检测 |
| `cvd_analyzer.py` | `run_cvd_confluence()` | CVD共振分级 |
| `fvg_detector.py` | `run_fvg_detection()` | ICT三烛FVG检测 |
| `order_block.py` | `run_ob_detection()` | 机构OB识别 |
| `correlation_matrix.py` | `run_correlation_multiplier()` | 多资产风险乘数 |

## 接入模式

```python
# auto_card.py render_card_locked() 中 ⑦段
from orphan_integration import run_orphan_checks
orphan_results = run_orphan_checks(symbol=symbol, price=price, direction=direction)
# 写入分析卡
lines.append(f"- **FVG缺口：{best.get('direction')}向·{best.get('low')}-{best.get('high')}**")
```

## 适用场景

- 已有独立脚本但未接入主管线
- 脚本有公开函数但无统一调用入口
- 需要试/except容错（不因任一副模块失败影响主流程）
- 需要统一数据落盘（写入 `data/orphan_signals_{symbol}.json`）

## 不被此模式覆盖的场景

- 需要双向数据回传（脚本修改主流程状态）→ 用装饰器/事件总线
- 脚本需要大量预热/初始化 → 用延迟加载
- 脚本有外部依赖（GPU/数据库）→ 用异步worker
