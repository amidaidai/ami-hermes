# 多模型引擎 v2.0 HHI 加权修复

日期: 2026-06-18

## 问题

`EMA趋势` 模型 quality=0.9，其他模型 quality=0.8。当 EMA趋势方向与多数模型相反时，单一高置信模型可压倒 4个同向模型。

**实测案例 (XAUUSD):**
- 4个多头模型 (扫流动性+VAL回收+M_VWAP+VWAP反抽) × 1个空头模型 (EMA趋势)
- 旧加权: 空0.900 vs 多0.373 → 偏空 (错误)
- DMI判X · Grok判偏多 → 引擎孤立偏空

## 修复 (v2.0)

### 1. HHI多样性惩罚
```python
hhi = sum(c²) / (sum(c))²  # 1.0=单模型垄断, ~0=多模型均衡
diversity_bonus = (1.0 - hhi) * 0.12
```
单模型垄断→diversity_bonus=0·多模型均衡→+0.085

### 2. 单模型上限
```python
capped = [min(c, 0.65) for c in confs]  # 最高单模型贡献0.65
```

### 3. 修复后结果
- 空: capped 0.65·HHI=1.0·bonus=0 → 0.650
- 多: 4模型均衡·HHI≈0.29·bonus=0.085·base≈0.373 → 0.458
- diff: -0.191 < threshold(动态0.35) → **方向不明/震荡** ✅

## v2.1 增强

- bias阈值动态：模型数比=4→threshold=0.35 (vs 固定0.2)
- 置信映射标准：0.5→3, 0.7→4, 0.85→5
- Grok分歧→强制action=B等待·confidence_5≤3
