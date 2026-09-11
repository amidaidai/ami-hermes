# 社区数据仪表盘 v1.0 (2026-06-18)

## 调用入口
```python
from coingecko_collector import community_dashboard
print(community_dashboard())
```

## 输出格式
```
恐慌贪婪: 15 (Extreme Fear) · CG情绪: 72%看多 · 2,404,318人关注BTC 
· 热门: Hyperliquid·Bitcoin·Collector Crypt · 板块: World Liberty Financial Portfolio -1.4%
```

## 数据源 (7源·全免费)

| 源 | 数据 | Key |
|----|------|-----|
| alternative.me | 恐慌贪婪(0-100) | 无 |
| CoinGecko | 情绪投票(up/down%) | 无 |
| CoinGecko | 关注量(watchlist) | 无 |
| CoinGecko | 热门趋势(top 3) | 无 |
| CoinGecko | 板块热度(top 1) | 无 |
| CMC | BTC市占 | 有 |
| CMC | 总市值日变 | 有 |

## 信号解读

- **F&G < 25 + CG > 60%看多** → 恐慌底部+社区强烈看多=巨大分歧·典型底部博弈
- **F&G > 75 + CG < 40%看多** → 贪婪顶部+社区转空=顶部预警
- **F&G 与 CG 同向** → 共识形成·趋势可信
- **Trending出现新币种** → 市场轮动信号

## 写入模板
v6.8 分析卡环境段⑦「社区全景」自动填充。
