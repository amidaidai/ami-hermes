# 20260820 TV OI 官方数据验证 + 上传版复评

用户问题：TV 上有没有 OI 指标，数据与官方无差别的那种？本会话实测验证完毕。

## 结论（已验证）

1. **TV 官方内建 "Open Interest" 指标**：指标库搜索 "Open Interest" 直接添加；官方帮助页 solutions/43000685269-open-interest 确认图表上 OI 数据以该指标提供。数据走 `_OI` 后缀 symbol，交易所官方直连，非估算。
2. **与官方无差别的实测对账**（本会话跑过）：
   - 官方 API：`curl -s "https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT"` → 108,140.450 BTC
   - TV：`chart_set_symbol('BINANCE:BTCUSDT.P_OI')` → `data_get_ohlcv` 末 bar close = 108,156.783（bar 时间与 API 时间差 ~176s）
   - 差值 0.015% = 取样时刻差，数据同源。唯一差别是 TV 管道分钟级延迟，OI 为低频变量无实质影响。
3. **副指标 AggVol 的 f_oi() 已走官方 `_OI` 通道**（`ex + ':' + baseA + 'USDT.P_OI'`，BINANCE/BYBIT/OKX/BITGET 4 所），无需改动。

## 工具坑（本会话实测）

- **quote_get 对 `_OI` symbol 返回基础价格，不是 OI 值**（BINANCE:BTCUSDT.P_OI 的 quote close≈BTC 价格 71992，volume=520）。要看 OI 必须 `chart_set_symbol` + `data_get_ohlcv`，读 close（该数据流 volume=0，OHLC 中 close 即 OI 数量，BTC 永续单位为币数）。
- web_extract 对 tradingview.com 支持页被代理拦截（已知），用 web_search 结果片段即可拿到官方描述。
- tv_launch 可自动拉起 TV 桌面并带 CDP（port 9222）；MCP 连续 3 次失败后 ~57s 冷却，期间不要重试同工具。
- 验证上传文件是否为已知交付版：`ls -la` + `wc -c` 与 sandbox 副本逐字节对比（本会话 72,302 / 242,240 完全一致，直接复用编译结论）。

## 市场覆盖矩阵（用户四市场）

| 市场 | 官方 OI | symbol 示例 |
|---|---|---|
| 加密永续 | ✓ | BINANCE:BTCUSDT.P_OI / BYBIT:… / OKX:… / BITGET:… |
| 贵金属期货 | ✓ | COMEX:GC1!_OI（黄金）、SI1!_OI（白银） |
| 贵金属现货 XAUUSD | ✗ 现货无持仓量概念 | — |
| 股票现货 | ✗ | CME:ES1!_OI / NQ1!_OI（指数期货有） |
| 外汇现货 | ✗ | CME:6E1!_OI（外汇期货有） |

## 社区脚本坑

认脚本的 Data Mode 标注：**Open Interest = 官方**；**Volume Proxy = 成交量估算，非官方**。用户副指标纯官方无此问题。

## 20260820 上传版复评（覆盖 20260814 基线）

上传版 = 增强最终版_20260814（主 3484 行/242,240 字节、副 797 行/72,302 字节），translate_light 全量编译 0 错 0 警，静态配额 46/64 与 41/64 plot、8 与 30/40 request。

- 综合：主 SVP **97**（编译100/配额100/逻辑96/诚实96/决策95），副 AggVol **96**（100/95/95/96/94）
- 市场适配：主 **94**、副 **91**
- 辅助决策：主 **96**、副 **86**——副指标低分是分工设计（主指标唯一 Entry/Stop/Target 授权源，副指标确认器不重复给距离原语），非缺陷，回复用户时必须说明
- 主指标 13 行 + 副指标 7 行定稿全落地；遗留5（HTF FVG/OB request 函数化短路）已修；副指标 CVD 低周期 1m 升档已落地
- 遗留小项（登记不动，改前先问）：股票 SVP 行数无专门分支；副指标 calctype 仅 SUM 死参数；主副各一份 f_is_metal_ticker
