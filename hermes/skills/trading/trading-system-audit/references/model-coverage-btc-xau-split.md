# 13模型 · BTC vs XAU 适配度

棠溪系统共13个模型，天然分成三派。回测覆盖率低不一定是模型有问题——可能是品种不匹配。

## 模型分类

### BTC专属（需要Binance futures数据）

| 模型 | 依赖数据 | 不触发原因 | 修复方向 |
|------|---------|-----------|---------|
| 费率极端反转 | funding_rate + rate_change | 回测中funding_rate=0 | 拉Binance funding rate历史 |
| 多空拥挤反转 | LS ratio极端值 | long_pct=64%不会<40% | 降LS阈值40%→55% |
| Taker背离 | taker_futures嵌套结构 | 数据格式不匹配 | 参考本skill §数据桥 |
| OI背离 | oi.btc + oi.change_pct | conf<0.15 | 降阈值或放大OI权重 |

### XAU专属（黄金特性更适配）

| 模型 | 为什么适合黄金 | 为什么不适合BTC |
|------|--------------|----------------|
| 突破接受 | 黄金突破干净，回踩确认率高 | BTC假突破多 |
| M_VWAP磁吸 | 黄金频繁回归VWAP | BTC趋势性强·磁吸弱 |
| 关联套利 | XAU vs DXY天然负相关 | BTC需ETH/SOL做关联 |

### 共用（两边都行）

VWAP反抽·VAH回收·VAL回收·POC拒绝·扫流动性回收·EMA趋势

## 引擎模型数据桥

12引擎模型期望的数据结构是**嵌套dict**，不是平键：

```python
# ❌ 错误（平键）
data = {"taker_ratio": 1.05, "long_short": 1.8}

# ✅ 正确（引擎期望的结构）
data = {
    "taker_futures": {"ratio": 1.05, "direction": "buy"},
    "long_short": {"top_long_pct": 64.3, "global_long_pct": 64.5},
    "binance_spot": {"price": 64000, "24h_change_pct": -2.5},
    "oi": {"btc": 500000, "change_pct": 0.05},
    "funding_rate": 0.0001,
    "rate_change": 0.00005,
}
```

**Pitfall**: 不回测永远发现不了这个问题——引擎模型在live环境中从`system_data_bridge.py`获取数据（正确格式），但回测直接构造dict（平键格式）导致7个模型全都喂了错误数据而静默失败。

## 覆盖率评估标准

```
<30%    P0 · 数据桥断裂
30-50%  P1 · 多数模型不适合当前品种
50-70%  P2 · 正常·待优化阈值
>70%    健康·部分模型需极端条件
```
