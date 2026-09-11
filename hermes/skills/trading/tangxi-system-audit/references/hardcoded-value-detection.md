# 硬编码值检测模式

这是棠溪系统最常见的隐蔽bug类别。以下是检测方法：

## 检测目标
在 `multi_model_engine.py` 的模型函数中查找裸数字（硬编码的VWAP/VAH/VAL/POC/EMA值）。

## 示例（错误）
```python
def model_vwap_bounce(data: dict) -> Tuple[str, float]:
    price = data.get("binance_spot", {}).get("price", 0)
    vwap_s = 66054  # ← 硬编码！永远不会更新
    atr = 287        # ← 硬编码！
```

## 修复后（正确）
```python
def model_vwap_bounce(data: dict) -> Tuple[str, float]:
    tv = load_tv_data(data)
    price = _sf(data.get("binance_spot", {}).get("price"))
    vwap_s = _sf(tv.get("vwap")) or _sf(tv.get("w_vwap")) or 0
    atr = _compute_dynamic_atr(data, tv)
```

## 修复清单（2026-06-22 session）
删除的硬编码值（错误 → 正确）：
- `vwap_s = 66054` → `_sf(tv.get("vwap"))`  → 差异 -1,852 ✓
- `val = 65601` → `_sf(tv.get("val"))` → 差异 -1,707 ✓
- `poc = 65847` → `_sf(tv.get("poc"))` → 差异 -1,616 ✓
- `vah = 66692` → `_sf(tv.get("vah"))` → 差异 -2,232 ✓
- `ema9 = 65153` → `_sf(tv.get("ema9"))` → 差异 -1,054 ✓
- `ema21 = 65457` → `_sf(tv.get("ema21"))` → 差异 -1,322 ✓
- `ema55 = 65601` → `_sf(tv.get("ema55"))` → 差异 -1,463 ✓
- `m_vwap = 64288` → `_sf(tv.get("m_vwap"))` → 差异 -79 ✓
- `atr = 287` → `_compute_dynamic_atr()` → 动态 ✓
- `balance = 67.52` → `engine_data.get("account_balance")` → 动态 ✓

## 检测命令
```bash
grep -nE '(= [0-9]{4,5}\b|atr = [0-9]+\b|balance.*=.*[0-9]+\.[0-9]+)' hermes/scripts/multi_model_engine.py hermes/scripts/auto_card.py
```
任何匹配行如果不是从 `data.get()` / `tv.get()` / `_sf()` / API获取的值，则为硬编码bug。
