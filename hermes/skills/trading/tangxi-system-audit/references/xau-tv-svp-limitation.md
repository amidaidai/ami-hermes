# XAU TV SVP v10 限制（v9.6 已知架构限制）

> 历史记录（2026-06-29）：本文记录旧版限制；当前黄金链路和指标合同以现行代码为准。

2026年6月29日发现并记录。

## 现象

SVP v10 指标（study ID: C7f7HV）在 OANDA:XAUUSD 品种上：
- `chart_get_state`: ✅ study已加载（studies列表含SVP+ICT+VWAP+CVD）
- `data_get_pine_tables(study_filter="SVP+ICT+VWAP+CVD")`: ❌ study_count=0, 无表格返回
- `data_get_pine_labels(study_filter="SVP+ICT+VWAP+CVD")`: ❌ study_count=0, 无标签返回
- `data_get_pine_lines(study_filter="SVP+ICT+VWAP+CVD")`: ❌ study_count=0, 无线条返回
- `data_get_study_values()`: ❌ 仅Volume和Volume Aggregated有数据,SVP数据完全不返回

副指标Volume和Volume Aggregated正常返回(Spot 0%/Perp 0%，因OANDA非加密)。

在BINANCE:BTCUSDT.P上所有Pine数据正常返回。

## 根因

SVP v10的`request.security`调用依赖加密独有数据字段：
- Funding rate（费率，仅永续合约）
- Open Interest（持仓量，仅期货）
- 多空比（仅合约）
- Taker买卖比

这些字段在OANDA（外汇/贵金属现货经纪商）上不可用。SVP的表/标签/线条计算需要这些数据参与公式，无数据→计算结果为空→不返回任何Pine输出。

## 影响

- XAU分析卡无法使用TV SVP行动格/关键位/标签数据
- XAU仅能通过TV截图做视觉验证，不能程序化读取指标值
- 副指标Volume Aggregated对XAU无意义（现货0%/期货0%）

## 当前解决方案

XAU分析卡使用以下数据源替代TV SVP：

| 数据 | 来源 | 质量 |
|------|------|------|
| 现货价 | gold-api.com + 金十Quote | A（双源一致） |
| 24h高/低 | 金十Quote | A（实时） |
| VAH/VAL/POC | 基于24h高/低推算（daily_range × 0.35） | B（近似值） |
| 多周期OHLCV | 无真实K线，价差推导 | C（近似值，标注来源） |
| 宏观背景 | DXY/US10Y/TIP/GLD/GDX | A（多源验证） |
| 情绪 | X/恐惧贪婪 | B（非XAU专属） |

## 未来改进方向（二选一）

### 方案A：独立XAU TV标签
在TradingView创建第二个标签/布局，加载OANDA:XAUUSD + 轻量指标（原生VWAP+EMA+Volume），不依赖SVP v10。

### 方案B：外部OHLCV API
接入OANDA REST API或Twelve Data获取XAU真实多周期K线数据，替换当前的价差推导近似值。

两个方案均未实施（2026-06-29）。
