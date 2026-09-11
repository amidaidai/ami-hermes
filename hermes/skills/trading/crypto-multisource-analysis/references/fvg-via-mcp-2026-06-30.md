# FVG 通过 TV MCP 读取协议（2026-06-30 实战）

## 核心教训

**安禾的SVP v10指标（主指标.txt 3134行）有完整FVG检测。** 旧版 `svp_indicator.txt`（2024行）没有FVG。分析前必须确认用户加载的是哪个版本。

## TV MCP 工具

```python
# 读FVG框（box.new）
tool_call(name="mcp_tradingview_data_get_pine_boxes",
  arguments={"study_filter": "SVP"})
# 返回: {zones: [{high, low}, ...]}
```

## 指标FVG参数（主指标.txt L110-L124）

| 参数 | 默认 | 含义 |
|:--|:--:|:--|
| `FVG_HTF_ALIGN` | true | 只保留顺HTF方向：4h看多→不画看跌FVG |
| `FVG_REQUIRE_DISP` | true | 中间K需实体≥1.0×ATR |
| `FVG_NEAR_ATR` | 4.0 | 距价>4×ATR的框隐藏 |
| `FVG_SHOW_CE` | true | 框内画50%中点虚线(Consequent Encroachment) |
| `FVG_MAX_COUNT` | 5 | 最多5个框 |
| `SHOW_HTF_FVG` | true | 高周期FVG确认→标`FVG✓HTF` |

## FVG检测源码条文（L2509-2522）

看涨: `low > high[2]` → 缺口 `high[2] → low` → box top=low, box bot=high[2]
看跌: `high < low[2]` → 缺口 `high → low[2]` → box top=low[2], box bot=high
CE: `(top + bot) / 2`

## 多周期FVG注意事项

1. **FVG是中线概念**（安禾纠正）。主分析周期为4h/D。15m/5m FVG只作执行参考
2. **HTF对齐过滤**：`fvgBullGate = not htfBearConfirmed`，看涨FVG在HTF确认空时被过滤
3. **不同周期FVG不同**：每个时序周期独立检测FVG，4h有4h的框、15m有15m的框。框不跨周期继承

## GASUSDT 2026-06-30 实测

15m实际FVG框（data_get_pine_boxes输出）：
- 1.17-1.20（Bearish，新出现，价格正框内填充）
- 1.10-1.12（Bullish，等于4h中线FVG 1.111-1.118）
- 1.07-1.08（Bullish）
- 1.05（Bullish）

错误做法：自己用15m OHLCV算FVG → 得到1.137-1.144（不存在）和1.142-1.151（被HTF过滤不画）
