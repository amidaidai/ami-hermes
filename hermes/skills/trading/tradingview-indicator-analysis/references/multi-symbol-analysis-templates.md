# 多品种分析模板索引

以下模板由 scripts/multi_symbol_templates.py 生成。

# 比特币 分析模板

① 品种：BTCUSDT · 加密主流 · 杠杆 100x
② 周期：日内 5m · 15m · 1h · 4h · Swing 15m · 1h · 4h · 日
③ 风控：单笔上限 `10U` · 默认风险 `3U`
④ 术语：固定英文保留 VWAP/POC/VAH/VAL/CVD/DO/OI/Funding/Basis/Taker/ATR/R:R/ETF，其余尽量中文

## 数据源
- 价格：Binance现货；Binance合约；FinanceKit/CoinGecko；TradingView
- 催化：金十Flash；web_search；X/社区情绪；ETF/宏观新闻
- 衍生/背景：Funding；OI；多空比；Taker；Basis；清算区

## 固定模型
- VWAP反抽；VAH/VAL回收；POC拒绝；扫流动性回收；突破接受

## 监控位
- 前高/前低；日内VWAP；1h VWAP；清算密集区；扫损位

## 输出顺序
① 状态 → ② 环境 → ③ 结构 → ④ 模型 → ⑤ 操作 → ⑥ 风控 → ⑦ 监控闭环

## 特别规则
- 社区情绪只调仓位，不覆盖结构；CVD低质量时必须降权。
- C级数据最高只能 B等待；R:R 低于 1:2 直接 X禁做。
- 社区情绪只调仓位，不覆盖结构。

---

# 以太坊 分析模板

① 品种：ETHUSDT · 加密主流 · 杠杆 100x
② 周期：日内 5m · 15m · 1h · 4h · Swing 15m · 1h · 4h · 日
③ 风控：单笔上限 `10U` · 默认风险 `3U`
④ 术语：固定英文保留 VWAP/POC/VAH/VAL/CVD/DO/OI/Funding/Basis/Taker/ATR/R:R/ETF，其余尽量中文

## 数据源
- 价格：Binance现货；Binance合约；FinanceKit/CoinGecko；TradingView
- 催化：金十Flash；web_search；X/社区情绪；ETF/链上/生态新闻
- 衍生/背景：Funding；OI；多空比；Taker；Basis；清算区

## 固定模型
- VWAP反抽；VAH/VAL回收；POC拒绝；扫流动性回收；突破接受

## 监控位
- BTC联动分歧位；日内VWAP；前高/前低；清算密集区；生态催化价位

## 输出顺序
① 状态 → ② 环境 → ③ 结构 → ④ 模型 → ⑤ 操作 → ⑥ 风控 → ⑦ 监控闭环

## 特别规则
- 必须同步看 BTC 强弱；ETH 单独走强才允许提高置信。
- C级数据最高只能 B等待；R:R 低于 1:2 直接 X禁做。
- 社区情绪只调仓位，不覆盖结构。

---

# Solana 分析模板

① 品种：SOLUSDT · 加密高波动 · 杠杆 20x
② 周期：日内 5m · 15m · 1h · 4h · Swing 15m · 1h · 4h · 日
③ 风控：单笔上限 `10U` · 默认风险 `2U`
④ 术语：固定英文保留 VWAP/POC/VAH/VAL/CVD/DO/OI/Funding/Basis/Taker/ATR/R:R/ETF，其余尽量中文

## 数据源
- 价格：Binance现货；Binance合约；FinanceKit/CoinGecko；TradingView
- 催化：web_search；X/社区情绪；生态新闻；BTC/ETH联动
- 衍生/背景：Funding；OI；多空比；Taker；Basis；清算区

## 固定模型
- 扫流动性回收；突破接受；POC拒绝；VWAP反抽

## 监控位
- 前高/前低；快速插针位；VWAP；清算密集区

## 输出顺序
① 状态 → ② 环境 → ③ 结构 → ④ 模型 → ⑤ 操作 → ⑥ 风控 → ⑦ 监控闭环

## 特别规则
- 波动更快，默认轻仓；只做清晰触发，不追第一根放量。
- C级数据最高只能 B等待；R:R 低于 1:2 直接 X禁做。
- 社区情绪只调仓位，不覆盖结构。

---

# BNB 分析模板

① 品种：BNBUSDT · 交易所平台币 · 杠杆 20x
② 周期：日内 5m · 15m · 1h · 4h · Swing 15m · 1h · 4h · 日
③ 风控：单笔上限 `10U` · 默认风险 `2U`
④ 术语：固定英文保留 VWAP/POC/VAH/VAL/CVD/DO/OI/Funding/Basis/Taker/ATR/R:R/ETF，其余尽量中文

## 数据源
- 价格：Binance现货；Binance合约；FinanceKit/CoinGecko；TradingView
- 催化：Binance公告；web_search；监管新闻；BTC联动
- 衍生/背景：Funding；OI；多空比；Taker；Basis

## 固定模型
- 突破接受；VWAP反抽；VAH/VAL回收；POC拒绝

## 监控位
- 平台公告触发位；前高/前低；VWAP；成交密集区

## 输出顺序
① 状态 → ② 环境 → ③ 结构 → ④ 模型 → ⑤ 操作 → ⑥ 风控 → ⑦ 监控闭环

## 特别规则
- 受 Binance 事件影响大，突发公告时先降仓。
- C级数据最高只能 B等待；R:R 低于 1:2 直接 X禁做。
- 社区情绪只调仓位，不覆盖结构。

---

# 黄金 分析模板

① 品种：XAUUSD · 贵金属 · 杠杆 1000x
② 周期：日内 5m · 15m · 1h · 4h · Swing 15m · 1h · 4h · 日
③ 风控：单笔上限 `10U` · 默认风险 `2U`
④ 术语：固定英文保留 VWAP/POC/VAH/VAL/CVD/DO/OI/Funding/Basis/Taker/ATR/R:R/ETF，其余尽量中文

## 数据源
- 价格：金十Quote；TradingView；FinanceKit/现货代理源
- 催化：金十Flash；财经日历；美元指数；美债收益率；地缘风险
- 衍生/背景：不使用加密Funding/OI；看美元/美债/实际利率；事件波动

## 固定模型
- VWAP反抽；VAH/VAL回收；POC拒绝；扫流动性回收；突破接受

## 监控位
- 亚盘高低；伦敦高低；纽约开盘位；日内VWAP；前高/前低

## 输出顺序
① 状态 → ② 环境 → ③ 结构 → ④ 模型 → ⑤ 操作 → ⑥ 风控 → ⑦ 监控闭环

## 特别规则
- 高杠杆默认轻仓；数据公布前后禁追价，优先等扫流动性回收。
- C级数据最高只能 B等待；R:R 低于 1:2 直接 X禁做。
- 社区情绪只调仓位，不覆盖结构。

---

# 原油 分析模板

① 品种：USOIL · 能源商品 · 杠杆 按账户规则
② 周期：日内 5m · 15m · 1h · 4h · Swing 15m · 1h · 4h · 日
③ 风控：单笔上限 `10U` · 默认风险 `2U`
④ 术语：固定英文保留 VWAP/POC/VAH/VAL/CVD/DO/OI/Funding/Basis/Taker/ATR/R:R/ETF，其余尽量中文

## 数据源
- 价格：金十Quote；TradingView；FinanceKit/期货代理源
- 催化：EIA/API库存；OPEC新闻；地缘风险；美元
- 衍生/背景：库存/期限结构；事件波动；不使用加密Funding/OI

## 固定模型
- 突破接受；POC拒绝；VWAP反抽；扫流动性回收

## 监控位
- EIA前区间；日内VWAP；前高/前低；新闻跳空位

## 输出顺序
① 状态 → ② 环境 → ③ 结构 → ④ 模型 → ⑤ 操作 → ⑥ 风控 → ⑦ 监控闭环

## 特别规则
- 库存和地缘事件权重高，事件窗口内无确认不做。
- C级数据最高只能 B等待；R:R 低于 1:2 直接 X禁做。
- 社区情绪只调仓位，不覆盖结构。

---

# 标普500 分析模板

① 品种：SPX · 美股指数 · 杠杆 按账户规则
② 周期：日内 5m · 15m · 1h · 4h · Swing 15m · 1h · 4h · 日
③ 风控：单笔上限 `10U` · 默认风险 `2U`
④ 术语：固定英文保留 VWAP/POC/VAH/VAL/CVD/DO/OI/Funding/Basis/Taker/ATR/R:R/ETF，其余尽量中文

## 数据源
- 价格：TradingView；FinanceKit；金十Quote如可用
- 催化：美股财报；CPI/FOMC；VIX；美债收益率；美元
- 衍生/背景：VIX；美债；期权隐波；市场宽度

## 固定模型
- 突破接受；VWAP反抽；VAH/VAL回收；POC拒绝

## 监控位
- 美股开盘区间；前高/前低；VWAP；VIX突变位

## 输出顺序
① 状态 → ② 环境 → ③ 结构 → ④ 模型 → ⑤ 操作 → ⑥ 风控 → ⑦ 监控闭环

## 特别规则
- 指数优先看宏观/财报/美债/VIX，不套用加密衍生指标。
- C级数据最高只能 B等待；R:R 低于 1:2 直接 X禁做。
- 社区情绪只调仓位，不覆盖结构。

---
