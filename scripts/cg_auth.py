"""CoinGecko 认证头的唯一出口（2026-09-14 建立）。

根因（本轮实测，非推测）：仓库里 8 处把 `hermes/secrets/coingecko_api_key.txt`
里的 **Demo key（`CG-` 前缀）** 当成 Pro key，用 `x-cg-pro-api-key` 发给公共主机
`api.coingecko.com`。实测结果：

  public host + `x-cg-pro-api-key`（旧用法）  → HTTP 400 · error_code 10010
  public host + `x-cg-demo-api-key`（正解）   → HTTP 200 · 正常返回
  public host + 不带 key                     → HTTP 200（公共端点，147 次/分会被 429）
  pro host   + `x-cg-pro-api-key`             → HTTP 400 · error_code 10011

于是「每次调用必 400」被上层读成「源不可用」，`cg_pro` 步每轮只产出一条恒 ⚠️
—— 这才是用户判定该步「无效」的真实原因。凭据本身是好的，用法错了。

用法：
    from cg_auth import auth_headers
    headers = {"User-Agent": UA, **auth_headers(CG_KEY)}

禁止再在别处手写 `x-cg-pro-api-key` / `x-cg-demo-api-key`：
`tests/test_cg_auth.py` 会扫全仓，硬编码即变红。
"""

DEMO_PREFIX = "CG-"

# 公共主机 api.coingecko.com：Demo key 与无 key 都走这里。
# 真正 Pro 订阅需要 pro-api.coingecko.com，本仓未订阅，不做自动切换以免掩盖配置问题。
PUBLIC_BASE = "https://api.coingecko.com/api/v3"


def auth_headers(key: str | None) -> dict:
    """按 key 形态返回正确的认证头。

    - `CG-…`（Demo key）→ `x-cg-demo-api-key`
    - 其它非空值       → `x-cg-pro-api-key`
    - 空/None/纯空白   → 不带认证头（公共端点，仍可用但会限流）
    """
    k = (key or "").strip()
    if not k:
        return {}
    if k.startswith(DEMO_PREFIX):
        return {"x-cg-demo-api-key": k}
    return {"x-cg-pro-api-key": k}


def credential_kind(key: str | None) -> str:
    """给日志/卡面用的凭据类型说明 —— 永不回显 key 本体。"""
    k = (key or "").strip()
    if not k:
        return "无凭据（公共端点·会限流）"
    return "Demo key" if k.startswith(DEMO_PREFIX) else "Pro key"
