# event_ban 硬编码修复

日期: 2026-06-18

## 致命Bug

`multi_model_engine.py` L443 曾硬编码：
```python
merged = merge_directions(results, event_ban=True)  # ← 永远True
```
所有引擎预测输出 `"事件禁做（X禁做）"`，无论实际有无事件。预测日志6条全部禁做，引擎形同虚设。

## 修复

新增 `check_event_ban(data, symbol)` 五重实际检查：

1. **极端波动**：BTC 24h>2% / XAU>1%
2. **数据C级**：自动降级半仓
3. **宏观risk_off**：恐慌情绪禁做
4. **日内涨跌>5%**：极端事件禁做
5. **跨市场价差>5%**：数据异常禁做

## 铁律

**永远不要硬编码 `event_ban=True`**。这是沉默致命bug。用实际数据检查替代。
