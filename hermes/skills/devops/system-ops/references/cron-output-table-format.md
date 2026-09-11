# Cron 输出表格格式化标准

## 触发条件

用户在 Telegram 收到 cron 推送时，要求可读性好、信息密度高、一眼看清关键数据。所有需要推送到 TG 的 no_agent cron 脚本应使用 Markdown 表格格式输出。

## 标准表格模式

### 数据清单表（多行统计数据）

```python
lines = [f"标题 {timestamp}"]
lines.append("")
lines.append("| 列1 | 列2 | 列3 |")
lines.append("|-----|-----|-----|")
for item in data:
    lines.append(f"| {item['key1']} | {item['key2']} | {item['value']} |")
lines.append("")
lines.append(f"总结行")
```

### KPI 纵表（单个实体多指标）

```python
lines.append("| 指标 | 数值 |")
lines.append("|------|------|")
lines.append(f"| 总OI | ${value:.2f}B |")
lines.append(f"| C/P比 | {ratio} {signal} |")
```

## 关键约束

1. **表头与分隔符之间不要有空行**
2. **数字对齐**：金额用 `${:,.0f}`，百分比用 `{:+.1f}%`
3. **方向标注**：用 ↑↓→ 箭头，不依赖 emoji（部分客户端不渲染）
4. **中文列名**：优先中文，专有名词（RSI/MACD/OI/CVD）保留英文缩写
5. **避免空行**：表格块之间用一个空行分隔即可
6. **兼容去重**：第一行放时间戳，让 dedup 能基于时间变化检测新鲜内容

## 已应用脚本

| 脚本 | 表格类型 | 数据源 |
|------|----------|--------|
| x_sentiment_collector.py | KPI表 + 热门榜 | CG trending + 恐贪 |
| liquidation_collector.py | 数据清单表 | Binance OI |
| qlib_factors.py | KPI纵表 | QLib 30因子 |
| deribit_options.py | KPI纵表 + 行权价表 | Deribit API |
| dune_collector.py | KPI表 + 交易所表 | Dune Analytics |
| orion_screener_radar.py | 异动品种表 | Orion + Binance |
| stablecoin_collector.py | KPI表 | DeFiLlama |

## 反模式（禁止）

- 单行 `key: value | key: value` 拼接
- 原始 JSON 输出
- 无表头的自由文本
- 超过 5 行的自由描述段落（应拆为表格或要点）
