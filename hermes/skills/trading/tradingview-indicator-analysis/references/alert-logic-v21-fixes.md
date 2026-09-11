# 警报逻辑 v2.1 修复 (2026-06-18)

## push_allowed 三处间隙

### 1. INFO tier 完全沉默 → 新增高优先接近提醒
```python
if tier == "info":
    if high_priority and score >= 70:
        return True  # 新增：高优先级接近不静默
```

### 2. WARNING 无 breach 但有高位信 → 明确不推
```python
# 旧：high_priority and (breached_like or score>=70) → 非 breach 高位信可能漏进
# 新：high_priority and breached_like → 必须同时满足触发
```

### 3. INVALID 低分高优先 → 放宽门槛
```python
# 旧：high_priority and score>=60 → OK
# 新：不变，保持。位信不足时正确降噪
```

## Discord 推送重试
```python
# 旧：try once → pass on fail
# 新：3次重试，间隔2s，与 Telegram 对齐
```

## 警报预算按品种拆分
```python
# 旧：全局 ALERT_BUDGET_GLOBAL=12 → BTC紧急用完→XAU被吞
# 新：提取 key 中的 symbol，按品种独立计数
symbol_counts = {}
for x in history:
    for key in x.get("keys", []):
        sym = key.split(":")[0] if ":" in key else "global"
        symbol_counts[sym] = symbol_counts.get(sym, 0) + 1
```

## CVD 双语标签
```python
# 旧：cvd == "买" → 仅支持中文标签
# 新：cvd in {"买","buy","BUY"} → 中英文双支持
```

## risk_gate cvd_quality
```python
def risk_gate(..., cvd_quality: str = "C"):
    if cvd_q == "C":
        max_risk = min(max_risk, max_risk * 0.5)  # CVD C级→半仓
```
