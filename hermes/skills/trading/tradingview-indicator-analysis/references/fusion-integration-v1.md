# GitHub 开源方案融合全记录 · 2026-06-18

## 搜索项目（7个）

| 项目 | Stars | 语言 | 核心 | 结果 |
|------|-------|------|------|------|
| smart-money-concept | ~200 | Python | SMC BOS/CHoCH/OB/FVG检测 | ❌ pandas 2.x read-only bug |
| tvdatafeed | ~2k | Python | TradingView OHLCV+LiveFeed | ⚠ 未采用（已有MCP） |
| trading-scanner | ~100 | Python | 14分评分+风险宪法 | ✅ 融合到scoring_engine+risk_constitution |
| analyseur-crypto | ~150 | Python | 规则化setup_generator | ✅ 融合到five_model_matcher |
| regime-mcp-server | ~50 | Python | VIX体制分类 | ✅ 自贸实现regime_classifier |
| Freqtrade | 33k+ | Python | 回测引擎+超参优化 | ❌ 需Docker·已删模板 |
| strata | ~50 | Python | LangGraph多Agent | 📋 架构参考（未实现） |

## Freqtrade vs 棠溪策略对比

Freqtrade 策略生态：**纯指标流**（RSI/MACD/EMA/Bollinger/ADX交叉）
棠溪五模型：**SMC/ICT结构流**（VWAP反抽/VAH-VAL回收/POC拒绝/扫流动性回收/突破接受）

GitHub 搜索 `freqtrade SMC order block liquidity sweep` → **0 条匹配**。
结论：Freqtrade 无 SMC 策略。棠溪的 `five_model_matcher.py` 是目前唯一把 SMC 结构策略做成可执行 Python + 自动入场/止损/止盈的方案。

## 核心教训

1. **GitHub项目≠拿来即用**：7个项目中2个因bug/依赖不可用，2个需重写为自贸版本，只有3个能直接融合概念
2. **Freqtrade 不在此赛道**：33k星的标杆项目也帮不了 SMC 策略
3. **删除比保留好**：不可用的半成品（SMC库/Freqtrade模板）直接删，不留技术债
