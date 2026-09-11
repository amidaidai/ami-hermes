# 完整模型体系 v2.0

> 31类交易模型，8大类别。注册表源码：`scripts/trading_system.py` → `ALL_MODELS`

## 成交量/市场画像 (Volume Profile) — 6类

| ID | 中文名 | type_tag | 权重 |
|----|--------|----------|------|
| vwap_reclaim | VWAP反抽回收 | vwap_reclaim_filter | 1.0 |
| vah_val_reclaim | VAH/VAL回收 | vah_val_reclaim | 0.9 |
| poc_rejection | POC拒绝/支撑 | poc_rejection | 1.0 |
| naked_vpoc | 裸POC（裸价值区） | naked_vpoc | 0.8 |
| volume_node_transition | 成交量节点迁移 | volume_node_transition | 0.7 |
| lvn_breakout | 低量节点(LVN)突破 | lvn_breakout | 0.7 |

## ICT/SMC 机构订单流 — 8类

| ID | 中文名 | type_tag | 权重 |
|----|--------|----------|------|
| order_block | 订单块(OB)供需区 | order_block | 1.0 |
| breaker_block | 破坏块(Breaker)反转 | breaker_block | 0.9 |
| mitigation_block | 缓解块(Mitigation) | mitigation_block | 0.8 |
| fair_value_gap | 公允价值缺口(FVG) | fair_value_gap | 0.9 |
| inversion_fvg | 反转型FVG | inversion_fvg | 0.85 |
| liquidity_sweep | 扫流动性回收 | sweep_reclaim | 1.0 |
| liquidity_void | 流动性真空区 | liquidity_void | 0.7 |
| rejection_block | 拒绝块(Rejection) | rejection_block | 0.8 |

## 市场结构 — 4类

| ID | 中文名 | type_tag | 权重 |
|----|--------|----------|------|
| bos | 结构突破(BOS) | bos | 0.9 |
| choch | 性质转变(CHoCH) | choch | 0.95 |
| structure_flip | 结构翻转(S/R Flip) | structure_flip | 0.85 |
| breakout_accept | 突破接受确认 | breakout_accept | 1.0 |

## Wyckoff 方法论 — 4类

| ID | 中文名 | type_tag | 权重 |
|----|--------|----------|------|
| wyckoff_spring | Wyckoff弹簧(Spring) | wyckoff_spring | 0.8 |
| wyckoff_upthrust | Wyckoff上冲(UT) | wyckoff_upthrust | 0.8 |
| wyckoff_sos | Wyckoff强信号(SOS) | wyckoff_sos | 0.75 |
| wyckoff_sow | Wyckoff弱信号(SOW) | wyckoff_sow | 0.75 |

## 斐波那契/谐波 — 3类

| ID | 中文名 | type_tag | 权重 |
|----|--------|----------|------|
| fib_retrace | 斐波那契回撤位 | fib_retrace | 0.85 |
| harmonic_pattern | 谐波形态 | harmonic_pattern | 0.7 |
| abcd_pattern | AB=CD形态 | abcd_pattern | 0.75 |

## 缺口理论 — 2类

| ID | 中文名 | type_tag | 权重 |
|----|--------|----------|------|
| gap_fill | 缺口回补 | gap_fill | 0.7 |
| breakaway_gap | 突破缺口 | breakaway_gap | 0.65 |

## 经典价格形态 — 3类

| ID | 中文名 | type_tag | 权重 |
|----|--------|----------|------|
| double_top_bottom | 双顶/双底 | double_top_bottom | 0.8 |
| head_shoulders | 头肩顶/底 | head_shoulders | 0.75 |
| trendline_retest | 趋势线破位回收 | trendline_retest | 0.85 |

## CVD/订单流 — 1类

| ID | 中文名 | type_tag | 权重 |
|----|--------|----------|------|
| cvd_divergence | CVD背离确认 | cvd_divergence | 0.9 |

## 查询接口

```python
import trading_system as ts

ts.model_by_id('order_block')        # → {name_zh, category, type_tag, score_weight}
ts.model_by_type_tag('breakout_accept')  # 根据监控位 type 反查
ts.list_models_by_category('ict_smc')    # 按类别列出
```
