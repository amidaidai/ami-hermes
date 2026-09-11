# DeFiLlama 稳定币 API

免费公开，无需 Key。提供385个稳定币的实时流通供应量。

## 端点

```
GET https://stablecoins.llama.fi/stablecoins?includePrices=true
```

## 实测数据（2026-06-29 15:04 BJT）

| 稳定币 | 流通量 |
|------|------|
| USDT | $184,852,689,328 |
| USDC | $73,767,591,450 |
| USDS | $8,223,987,540 |
| DAI | $4,837,561,366 |
| USD1 | $4,670,889,184 |
| USDe | $4,454,785,383 |
| USYC | $3,106,125,476 |
| BUIDL | $3,054,386,055 |
| USDG | $2,901,491,167 |
| PYUSD | $2,724,881,847 |

总计385个稳定币。

## 分析用途

- **稳定币总供应量变化**：上升=资金流入加密市场（看涨先行指标），下降=资金流出
- **USDT主导率**：USDT占总稳定币比例变化反映市场风险偏好
- **新兴稳定币增长**：USDS/USDe/PYUSD等增速反映机构/DeFi资金方向

## 集成方式

```python
import urllib.request, json

url = 'https://stablecoins.llama.fi/stablecoins?includePrices=true'
req = urllib.request.Request(url, headers={'User-Agent': 'Hermes/1.0'})
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
pegged = data.get('peggedAssets', [])
```

## 待办

- [ ] 创建 `scripts/defillama_stablecoin.py` 采集脚本
- [ ] 创建 cron（每4h）推送到TG:846
- [ ] 总供应量变化率>5%/周时告警
