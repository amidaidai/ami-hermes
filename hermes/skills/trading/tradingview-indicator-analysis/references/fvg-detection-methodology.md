# FVG (Fair Value Gap) 检测方法

> 2026-06-30 安禾纠正：FVG是**中线（4h/D）**概念，不是短线15m执行信号。分析FVG时必须从4h/D出发，15m只做回测执行参考。

## ICT 三烛FVG定义

FVG（公允价值缺口）是ICT/SMC的核心结构概念，指三根连续K线之间价格未填充的区间：

- **看涨FVG（Bullish FVG）**：Candle1.HIGH < Candle3.LOW → 中间K线价格未覆盖的看涨缺口
  - 缺口区间：Candle1.HIGH → Candle3.LOW
  - 含义：买方强势推动，价格跳过此区间上行
  
- **看跌FVG（Bearish FVG）**：Candle1.LOW > Candle3.HIGH → 中间K线价格未覆盖的看跌缺口
  - 缺口区间：Candle3.HIGH → Candle1.LOW
  - 含义：卖方强势推动，价格跳过此区间下行

## 检测算法（Python）

```python
# 4h/D 周期FVG检测
def detect_fvg(candles):
    """candles = [(time, o, h, l, c), ...]"""
    bullish, bearish = [], []
    for i in range(len(candles) - 2):
        c1, c3 = candles[i], candles[i+2]
        # 看涨FVG: c1.high < c3.low
        if c1[3] < c3[4]:  # c1.high < c3.low
            gap = (c1[3], c3[4])
            width = round((c3[4] - c1[3]) / c1[3] * 100, 2)
            midpoint = round((c1[3] + c3[4]) / 2, 3)
            filled = _check_filled(candles, i+3, gap, 'bullish')
            bullish.append((i, gap, midpoint, width, filled))
        # 看跌FVG: c1.low > c3.high
        if c1[4] > c3[3]:  # c1.low > c3.high
            gap = (c3[3], c1[4])
            width = round((c1[4] - c3[3]) / c1[4] * 100, 2)
            midpoint = round((c1[4] + c3[3]) / 2, 3)
            filled = _check_filled(candles, i+3, gap, 'bearish')
            bearish.append((i, gap, midpoint, width, filled))
    return bullish, bearish

def _check_filled(candles, start, gap, fvg_type):
    low_gap, high_gap = gap
    for j in range(start, len(candles)):
        c = candles[j]
        if fvg_type == 'bullish' and c[4] <= high_gap:  # low hit the gap
            return True
        if fvg_type == 'bearish' and c[3] >= low_gap:    # high hit the gap
            return True
    return False
```

## 周期选择铁律（2026-06-30 安禾纠正）

| 周期 | FVG用途 | 信号强度 |
|:--:|:--|:--:|
| **D** | 中线结构骨架·最有效 | ⭐⭐⭐⭐⭐ |
| **4h** | 中线执行层·标准FVG周期 | ⭐⭐⭐⭐ |
| 1h | 不宜独立使用·需4h验证 | ⭐⭐ |
| 15m | ❌ **不用于FVG结构判断** | × |
| 5m | ❌ 噪音层·完全无意义 | × |

**核心规则**：
- FVG的第一识别周期：**4h**（标准中线）和 **D**（长线骨架）
- 15m/5m上的FVG是执行噪音，不用于结构判断
- 15m上的FVG只能用于确定回测进场精确价位（在4h FVG框架内）

## FVG 填充判定

- **未填充（Open）**：价格从FVG生成后一直没有回到缺口区间内 → 对价格有磁吸力
- **已填充（Filled）**：价格已回到缺口区间 → 磁吸力消失，结构意义减弱
- **部分填充**：价格触碰缺口边缘但未完全穿过 → 仍有一定磁吸力

## FVG交易策略

### 中线策略（4h/D FVG）

1. **回踩未补看涨FVG做多**（⚠优先）
   - 条件：4h/D看涨FVG未补 + 价格回踩到缺口区间 + 较低周期（15m）出现反转确认
   - 目标：前高点 / VAH / nPOC
   - 止损：缺口下沿下方

2. **回抽未补看跌FVG做空**
   - 条件：4h/D看跌FVG未补 + 价格回抽到缺口区间
   - 目标：前低点 / VAL

3. **FVG被补 = 结构失效**
   - 看涨FVG被跌破 → 多头结构破坏
   - 看跌FVG被升破 → 空头结构破坏

### 多FVG重叠（高概率区）

当多个周期的FVG在同一区域重叠时构成**高概率支撑/阻力区**：
- 4h看涨FVG + 15m看涨FVG重叠 → 强支撑
- D看跌FVG + 4h看跌FVG重叠 → 强阻力
- 看涨FVG + 看跌FVG重叠 → 关键价值区（通常位于POC附近）

## 实战案例 (GASUSDT, 2026-06-30)

- 中线唯一未补FVG：**4h看涨FVG #97 @ 1.111-1.118**
- 现价1.155，距FVG上沿+3.5%
- 15m上虽然也有FVG（1.137-1.144），但那只是短线执行参考
- 用户纠正：「FVG是中线概念」→ 分析时必须从4h/D入手

## 常见错误（Pitfalls）

- ❌ 用15m FVG作为中线结构判断 → 被安禾纠正过
- ❌ 忽略FVG的填充状态 → 已填充的FVG没有磁吸力
- ❌ 在所有周期上同等看待FVG → D/4h才是中线的正确周期
- ❌ 假设Pine指标会显式绘制FVG box → 安禾的SVP v10指标（2024行）不包含显式FVG检测代码，FVG需从OHLCV手动计算
- ✅ 正确做法：先扫4h/D的未补FVG，再用15m做回测执行

## 安禾SVP v10指标与FVG的关系（2026-06-30发现）

安禾的SVP+ICT+VWAP+EMA+CVD指标（`svp_indicator.txt`，2024行）**没有显式的FVG检测或绘制代码**。FVG相关的结构信息散落在以下组件中：

| 指标组件 | 行数范围 | 与FVG的关系 |
|:--|:--:|:--|
| ICT Session Levels（亚/伦/纽高低点） | 952-1260 | 扫掠检测 → 扫掠后的位移易产生FVG |
| Sweep Detection | 1497-1512 | 当日扫掠事件命名（扫亚高、扫伦低等） |
| SVP VAH/VAL/POC | 455-650 | 价值区边界辅助判断FVG位置 |
| DMI决策表（A/B/C/X评分） | 1386-1973 | FVG回测后的结构评分验证 |
| 多市场预设 | 25-27 | 不同市场的FVG加权不同 |

**实操协议**：
1. Pine指标提供ICT背景（已扫/未扫的session高低点）
2. FVG本身需从4h OHLCV用3-candle算法计算
3. 将发现的FVG与指标显示的VWAP/VAH/VAL/扫掠事件交叉验证
4. 最终以4h/D FVG为中线结构骨架，15m FVG只作执行参考
