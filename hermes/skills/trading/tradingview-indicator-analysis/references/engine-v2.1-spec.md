# 多模型引擎 v2.1 参数卡 (2026-06-18 锁定)

## HHI加权 (weighted_conf)

```python
def weighted_conf(models):
    confs = [m["confidence"] for m in models]
    sum_c = sum(confs)
    sum_c2 = sum(c*c for c in confs)
    
    # HHI: 1.0=单模型垄断, ~0=多模型均衡
    hhi = sum_c2 / (sum_c * sum_c) if sum_c > 0 else 1.0
    diversity_bonus = (1.0 - hhi) * 0.12  # 系数需50+笔校准
    
    # 单模型贡献上限
    capped = [min(c, 0.65) for c in confs]
    base = sum(c*c for c in capped) / sum(capped) if sum(capped) > 0 else 0
    
    return min(base + diversity_bonus, 1.0)
```

## 动态bias阈值 (v2.1)

```python
n_long = len(long_models)
n_short = len(short_models)
if n_long > 0 and n_short > 0:
    ratio = n_long / n_short if n_long > n_short else n_short / n_long
    threshold = 0.15 + ratio * 0.05  # 模型比越大→阈值越宽→"方向不明"
else:
    threshold = 0.2
```

4长1空→ratio=4→threshold=0.35

## 置信映射

| engine global_conf | n/5 |
|--------------------|-----|
| ≥ 0.85 | 5 |
| ≥ 0.70 | 4 |
| ≥ 0.50 | 3 |
| ≥ 0.40 | 2 |
| < 0.40 | 1 |

## Grok降级 (v2.1)

- agree=False + action非"不交易"/"禁做" → `"⚠Grok分歧→B等待"`
- confidence_5 上限 3

## event_ban (v2.1)

| 资产 | 24h波动阈值 |
|------|-------------|
| BTC/ETH | 5% |
| XAUUSD | 1% |

## 12模型注册

1. VWAP反抽 2. VAL回收 3. POC拒绝 4. 扫流动性回收 5. 突破接受
6. EMA趋势 7. 费率极端反转 8. 多空拥挤反转 9. Taker背离
10. OI背离 11. M_VWAP磁吸 12. 关联套利

前5个=五类固定模型(与模板直接对应)。后7个=辅助确认/否决信号。
