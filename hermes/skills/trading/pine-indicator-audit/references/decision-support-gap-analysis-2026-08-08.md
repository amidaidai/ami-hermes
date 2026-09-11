# 决策辅助审计与功能缺口分析（2026-08-08）

## 触发条件

用户问"怎么优化辅助决策 / 还差什么功能 / 还缺什么指标"时读取本文件。这是从**代码正确性审计**升级到**决策辅助有效性审计**的方法论。

## 决策辅助审计三原语

用户反馈"信息都看懂了但还是下不了决策"时，根因不是缺信息，而是缺三个即时感知原语：

| 原语 | 含义 | 当前缺口 | 实现方式 |
|------|------|----------|----------|
| **多远** | 当前价距入场价多远 | 进场行只显示价格不显示距离 | `math.abs(close - replayPlanPrice) / currATR` 追加 "距0.3A" |
| **多久了** | 信号存活多久 / KillZone剩多少分钟 | 就绪度只显示%不显示年龄 | `triggerAge` 已有变量追加 "·3K"；会话剩余 `math.round((sessEnd - time)/60000)` |
| **该不该现在动** | 所有信息汇总后的一个动作词 | 方向行信息多但无收尾判断 | executablePlan/rdyPct/regime 组合 → "→进/等/退/禁" |

**审计方法**：读行动格每一行，问"用户看了这行能立刻做出一个动作吗？"如果不能，该行缺少决策收尾原语。

## 功能缺口分析方法论

### 步骤 1：覆盖度图谱

用 execute_code 批量扫描两指标源码，构建已覆盖功能清单：

```python
features = {
    'main': {}, 'sub': {}
}
# 检测已有功能（按关键词匹配）
features['main']['SVP Volume Profile'] = 'volumeDistribution' in main_code
features['main']['ICT FVG'] = 'fvgList' in main_code
features['main']['CVD Divergence'] = 'cvdBullDiv' in main_code
# ... 30+ 项
# 输出已覆盖 vs 缺失
```

### 步骤 2：社区对标

对比 2026 年社区前沿的完整决策工具链：
- ICT/SMC 基础5件套 + 高级6种Block + 模型
- 订单流：CVD + OI + Taker Ratio + Liquidation
- 量能分布：SVP + Session VP + HVN/LVN + 前日投影
- 趋势：VWAP + EMA + Anchored VWAP
- 风控：ADR + 波动率分位数 + Funding Rate Extreme

### 步骤 3：零成本增强识别

**核心洞察**：最大缺口不是"缺更多指标"，而是"已有数据没有提取二阶导数"。

| 已有一阶数据 | 缺失的二阶导数 | 实现成本 | 决策价值 |
|-------------|---------------|----------|----------|
| oiAggA（OI绝对值） | OI变化率（OI Momentum） | 0（差值运算） | 量价四象限判断 |
| currATR（ATR绝对值） | ATR分位数（Volatility Percentile） | 0（ta.percentrank） | 入场窗口质量判断 |
| basisEma（基差EMA） | 基差极端检测（Funding Extreme） | 0（阈值判断） | 拥挤度反转预警 |
| volume（内置变量） | Taker Buy/Sell Ratio | ⚠不可行（见下） | ~~真实主动方向~~ |
| cvdAgg（CVD累积值） | CVD加速度/减速度 | 0（ta.change斜率比较） | 避免追在动能衰减末端 |

**全部零配额成本**——不增加 request.security、不增加 plot、不增加计算时限压力。

## v2 指标基线（2026-08-08 上传版）

| 项目 | SVP+ICT+VWAP+CVD v2（主） | AggVol v2（副） |
|------|--------------------------|----------------|
| 总行数 | 3,033 | 655 |
| 文件大小 | 199KB | 49KB |
| request.security | 7 + 2 lower_tf = 9 | 7（含OI 4所+LSR+基差+HTF） |
| plot 总数 | 37（含27个Data Window） | 40（含22个Data Window） |
| series色plot估算 | ~12个×2 | 12个×2 |
| 估算 plot count | ~52-55 / 64 | ~52 / 64 |
| alertcondition | 0（已事件化alert()）✓ | 0（已事件化alert()）✓ |
| 死函数 | 0 ✓ | 0 ✓ |
| 死变量 | 0 ✓ | 2个（maxValidExchangeSeenA/maxOiVenueSeenA） |

**与 v1 对比变化**：主指标从 ~2835→3033 行（+200行），副指标从 ~529→655 行（+126行）。新增内容主要为行动格增强（共振度/就绪度/触发链）、nPOC限时逻辑、OB HTF确认链。

## 10 项缺失功能（2026-08-08 确认）

### 必加（零配额成本）

1. ~~**Taker Buy/Sell Ratio**~~ — ⚠ **20260812 撤销：`taker_buy_volume` 不是 TV 内置变量**（编译报 Undeclared identifier）。Pine v6 无 taker 数据入口，真实主动方向只能走影线/实体估算 CVD 或外部 API（Binance fapi 等）。引用任何"内置变量"前先查 TV 官方内置变量列表。

2. **OI 动量变化率** — 对已有 `oiAggA` 做差值。价涨+OI涨=新钱入场做多；价涨+OI跌=空头平仓推动不可持续。加密期货基本功。

3. **波动率分位数** — 对已有 ATR 做 `ta.percentrank(ta.atr(14), 100)`。<20=极低波动即将爆发；>80=极高波动止损要放宽。

4. **资金费率极端检测** — 对已有 `basisEma` 加阈值。>0.10=多头拥挤可能反转；<-0.05=空头拥挤可能反转。

### 高优先级（零或低成本）

5. **HVN/LVN 标记** — SVP 引擎已有 volumeDistribution 数组，只需找 top-3 和 bottom-3 桶标记。HVN=强支撑/阻力减速区，LVN=价格真空加速区。

6. **锚定 VWAP** — 从特定事件（前日收盘/扫高扫低点/KillZone开盘）拉 VWAP。ICT 的 LDI 就是前日收盘锚定 VWAP，机构多空分界线。

7. **清算级位** — 用 LSR+OI+价格位置反推。LSR极端偏多+OI高位+价格接近支撑=多头清算密集区。

### 中优先级

8. **BTC 大盘风向** — +1 request.security，非 BTC 品种需要 BTC 上下文。已有逻辑（内存提到），可强化为行动格显示。

9. **会话 VP** — SVP 引擎加 session 过滤，按亚/伦/纽独立构建量能分布。ICT KillZone 核心需求。

10. **复合 VP 共振区** — +1 request.security，多周期 POC 重叠=铁壁支撑/阻力。

## 社区证据来源

- ~~TradingView 官方 `taker_buy_volume` 内置变量文档~~ ⚠ 不存在（20260812 实测撤销）
- Bookmap 2026 CVD 教学量价四象限
- LuxAlgo 2026 CVD 背离 + 价格行为组合
- ICT 2026 KillZone + Session VP 共识
- Quant SMC Pro 2026 EQL/iFVG/Mitigation Block
- Pine v6 2026-01 release notes: request.footprint() Premium-only