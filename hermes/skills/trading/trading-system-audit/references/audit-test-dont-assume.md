# 审计铁律：实测优先，不假设

> 2026-06-30 会话用户纠正后的沉淀。用于所有「全方位多维度」审计场景。

## 用户纠正原文

> "余留⚠️这些不是有工具吗？可以直接用啊，你不用怎么知道可不可以正常"

## 错误模式

审计管线发现 ⚠️（如 CoinGecko Pro ⚠️ / 深度数据 ⚠️ / X情绪 ⚠️ / 相关性 ⚠️），
直接标注「外部依赖不可用 / 需要 Pro key / 数据源未触发」—— **这是偷懒**。

## 正确流程

1. **先实测**：直接调用该工具/API/文件。
   - `curl -s "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=5"` 看深度能否返回
   - `cat data/x_sentiment_context.json` 看 X 情绪缓存是否存在
   - `python -c "from coingecko_collector import community_dashboard; print(community_dashboard())"` 看 CoinGecko 数据
   - `cat data/orphan_signals_BTCUSDT.json` 看相关性/吸收信号
2. **诊断**：
   - 数据存在 → 管线没读 → **接线问题**（auto_card 未 import/未调用），不是工具不可用
   - 数据返回 401/超时/空 → 再写「外部依赖不可用」，同时给出回退方案
3. **标注**：审计报告中的 ⚠️ 必须有实测证据链，不能是无校验的猜测

## 2026-06-30 实战案例

| 步骤 | 错误假设 | 实测结果 | 真实问题 |
|:---|---:|:---|---:|
| CoinGecko Pro ⚠️ | 需要 Pro API key | ✅ `CoinGecko Top10: 同步` 数据正常 | 审计关键字大小写不匹配 `Coingecko` vs `CoinGecko` |
| X情绪 ⚠️ | x_search 平台工具未配置 | ✅ `data/x_sentiment_context.json` 完整 | auto_card 从未读缓存文件 |
| 深度数据 ⚠️ | 需要特殊 MCP | ✅ Binance 公开 API 直接可用 | auto_card 从未调用 depth 端点 |
| 相关性 ⚠️ | FinanceKit 数据不足 | ✅ `orphan_signals corr_multiplier=1.0` 就位 | 审计关键词路径 `_advanced.orphan.corr_multiplier` |

## 管线完成度审计方法论

审计表检测改用 **`engine_data` 键值判定** 而非「卡文本关键词匹配」：

```python
# 可靠（engine_data 实时追踪）
if engine_data.get("x_sentiment"): completed_steps.add("x_sent")
if engine_data.get("depth"): completed_steps.add("depth")

# 脆弱（卡文本匹配，render后未必包含关键词）
if "X情绪" in card: completed_steps.add("x_sent")  # ❌
```

`engine_data` 方案免疫渲染模板变化，只要数据被采集就能正确标记。
