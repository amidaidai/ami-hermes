# 网络代理配置笔记

## Windows Clash Verge 代理

- 代理地址: `http://127.0.0.1:7897`
- 进程: `verge-mihomo.exe`
- `.env` 中 `NO_PROXY`: `api.yairouter.com, openrouter.ai, api.deepseek.com, api.x.ai`

## Python requests 陷阱 ⚠️

**错误做法** (导致连接超时):
```python
# ❌ proxies=None 不会走系统代理，在 Windows Clash 下必超时
requests.get(url, proxies={"http": None, "https": None})
```

**正确做法**:
```python
# ✅ 不设置 proxies，让 requests 自动走系统代理
requests.get(url, timeout=10)
# ✅ 或者显式走 Clash 代理
requests.get(url, proxies={"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"})
```

**排查**：先 `curl` 验证 API 可达，再检查 Python requests 的 proxies 设置。

## Binance API

- 公开接口无需认证: `api.binance.com/api/v3/ticker/price`
- 需要走代理，不能用 `NO_PROXY` 排除（会超时）
- 偶尔超时是正常的，重试即可

## Telegram 推送

- `hermes send -t "telegram:阿弥黛黛" -q "消息"` 可在任意脚本中调用
- 不需要提取 Telegram Bot Token，复用 Hermes 的 gateway 凭据
- 调用耗时 ~1 秒
