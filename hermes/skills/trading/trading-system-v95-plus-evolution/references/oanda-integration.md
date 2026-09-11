# OANDA Practice API 接入

## 凭据准备

1. 注册 OANDA 模拟账户：https://www.oanda.com/demo-account/
2. 获取 API token：账户管理 → Personal Access Token → Generate
3. 获取 Account ID：账户管理 → 查看账户号（如 `101-004-12345678-001`）

## 凭据存放

```bash
# 写入凭据文件（不备份到 git）
echo "your-oanda-api-token" > hermes/secrets/oanda_token.txt
echo "your-account-id" > hermes/secrets/oanda_account_id.txt
```

## API 细节

- 端点：`https://api-fxpractice.oanda.com/v3/accounts/{ACCOUNT_ID}/pricing?instruments=XAU_USD`
- 认证：`Authorization: Bearer {TOKEN}`
- 响应格式：`{"prices": [{"bids": [{"price": "4324.855"}], "asks": [{"price": "4325.155"}]}]}`
- 函数取 bid/ask 中价：`(bid + ask) / 2`，四舍五入到 2 位小数
- 超时：10 秒
- 无凭据时 `oanda_spot_price()` 返回 None，调用方自动降级

## 现货 vs 期货价差

| 源 | 类型 | 当前示例 |
|---|---|---|
| OANDA:XAUUSD | 现货黄金 | ~4325 |
| 金十Quote XAUUSD | 现货黄金 | ~4324 |
| Yahoo GC=F | COMEX 黄金期货 | ~4341 |
| Yahoo MGC=F | COMEX 微型黄金期货 | ~4341 |

现货-期货价差约 0.4%（17 USD），不作为一致性校验。
OANDA + 金十同为现货，价差通常 < 0.1%，可作为双源验证。

## 质量评级表

| 数据组合 | 等级 | 置信度 |
|---|---|---|
| OANDA + 金十 + Yahoo(×2) | A | 92% |
| OANDA + 金十 + Yahoo(×1) | A | 88% |
| OANDA + Yahoo(×2) | B | 82% |
| OANDA + Yahoo(×1) | B | 78% |
| OANDA + 金十 | B | 80% |
| OANDA 单源 | C | 65% |
| 金十 + Yahoo(×2) | B | 78% |
| 金十 + Yahoo(×1) | B | 75% |
| 金十 单源 | C | 60% |
| Yahoo 单源 | C | 55% |

## 故障排查

- `oanda_spot_price()` 返回 None → 检查 `hermes/secrets/` 下两文件是否存在且非空
- API 返回非 200 → token 过期或 account_id 错误，去 OANDA 后台重新生成
- API 返回 200 但 prices 为空 → 市场休市（周末），金十通常仍可用
- 监控脚本中 OANDA 始终不出现 → 重启 `行情守望.py`（它 import `trading_system` 时已缓存）
