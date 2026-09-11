# 硬编码价位审计模式（2026-06-22 实案）

## 场景

棠溪要求「全面审计系统」，发现 `multi_model_engine.py`（756 行）中所有模型关键位均为硬编码静态值。

## 发现详情

**文件**: `D:/Hermes agent/hermes/scripts/multi_model_engine.py`

| 变量 | 硬编码值 | 当前实际值(TV) | 偏差 |
|------|---------|----------------|------|
| `vwap_s` | 66,054 | 64,204 | +1,850 |
| `val` | 65,601 | 63,894 | +1,707 |
| `poc` | 65,847 | 64,231 | +1,616 |
| `vah` | 66,692 | 64,460 | +2,232 |
| `ema9` | 65,153 | 64,099 | +1,054 |
| `ema21` | 65,457 | 64,135 | +1,322 |
| `ema55` | 65,601 | 64,138 | +1,463 |
| `m_vwap` | 64,288 | 64,209 | +79 |

## 检测命令

```bash
# 1. 全量搜数字字面量赋值
grep -rn '\b[0-9]\{5,6\}\s*#' --include="*.py" hermes/scripts/ scripts/
# 2. 搜特定模式变量
grep -rn '\(vwap_s\|val\s*=\|vah\s*=\|poc\s*=\|ema9\|ema21\|ema55\|m_vwap\)\s*=' --include="*.py" hermes/scripts/ scripts/
# 3. 交叉验证：比对硬编码值与 TV 数据桥输出
cat "$LOCALAPPDATA/hermes/data/btc_tv_data.json" | python -c "import json,sys; d=json.load(sys.stdin); print('TV VWAP:', d.get('vwap')); print('TV VAH:', d.get('vah')); print('TV VAL:', d.get('val')); print('TV POC:', d.get('poc'))"
```

## 修法模式

1. **短期**: 从 TV 数据桥缓存 `btc_tv_data.json` 读取实时值替代硬编码
2. **长期**: 模型初始化时从统一入口（system_data_bridge / TV MCP）动态拉取，或改 register 模式：

```python
# ✅ 改前（硬编码）
vwap_s = 66054

# ✅ 改后（从data字典动态读）
vwap_s = data.get("vwap") or data.get("tv_data", {}).get("vwap") or 0
```

3. **验证**: 修改后实测 `python hermes/scripts/multi_model_engine.py <real_snapshot.json>`，对比输出值与 TV 实际值是否匹配。

## 根源分析

硬编码出现在多次迭代中无人发现的原因：
- 静态编译通过（无语法错误）
- pytest 用 mock 数据，mock 值正好匹配硬编码
- 管线跑起来 exit=0，所有 downstream 看起来正常
- 只有交叉验证（TV 值 vs 引擎输出）才能暴露

这就是审计铁律「静态扫描之后必须实测跑管线」的实案。
