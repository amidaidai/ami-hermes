# CoinGecko API Key 设置参考（2026-06-28 实测）

## API Key 类型

| Key 类型 | 前缀 | 请求头 | Base URL |
|---|---|---|---|
| **Demo（免费）** | `CG-...` | `x-cg-pro-api-key: CG-...` | `https://api.coingecko.com/api/v3` |
| **Pro（付费）** | `CG-...` | `x-cg-pro-api-key: CG-...` | `https://pro-api.coingecko.com/api/v3` |
| **无 Key（匿名）** | — | 不传 | `https://api.coingecko.com/api/v3` |

## 关键陷阱

### ⚠ Demo Key 用 `api.coingecko.com`，Pro Key 用 `pro-api.coingecko.com`

用错的错误码：

| 场景 | 错误 |
|---|---|
| Demo Key + `pro-api.coingecko.com` | `error_code: 10011` — "If you are using Demo API key, please change your root URL from pro-api.coingecko.com to api.coingecko.com" |
| Pro Key + `api.coingecko.com` | `error_code: 10010` — "If you are using Pro API key, please change your root URL from api.coingecko.com to pro-api.coingecko.com" |
| Demo Key + 正确 URL + 错误 Header | 400 Bad Request |

**检测方法**：先 ping `/ping` endpoint，看返回 200 还是 400。

### ⚠ Demo Key 也有速率限制

Demo 层匿名约为 10-30 req/min，带上 Key 后稍有提升但远不及 Pro 的 500 req/min。批量脚本（如扫描 10 个候选品种 × 2 次请求）需要 0.4-0.6s 间隔。

## 正确的请求方式

```python
headers = {
    "x-cg-pro-api-key": "CG-tkuaqHxNbpTQ92HgpvEc4QXY",  # Demo Key 也传此 header
    "User-Agent": "Hermes/1.0"
}
# Demo → api.coingecko.com
# Pro → pro-api.coingecko.com
req = urllib.request.Request(
    "https://api.coingecko.com/api/v3/coins/bitcoin",
    headers=headers
)
```

## 费用相关

- Demo 层：免费，注册即得
- Pro 层：$79+/月（按调用量）
- 一次订阅 = 使用 `pro-api.coingecko.com` 域名

## 验证清单

- [ ] Key 在 `.env` 中（`CG_API_KEY`）
- [ ] 代码中根据 Key 类型选择正确 Base URL
- [ ] 批量请求间隔 ≥ 0.4s（Demo 层）
- [ ] 测试 `/ping` 确认联通
