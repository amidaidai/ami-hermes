# OpenAI "region not supported" 502 — 复现与修法

工作日 2026-09-01。故障：Codex CLI 与 Hermes Studio 内 Codex 账号登录均报
`API Error 502: OpenAI does not support your region. You may need to use a proxy or VPN to access Codex.`

## 结论（三连误诊后锁定）

不是模型/配置问题，是 **出口未走代理 → 落内地/被屏蔽节点 → OpenAI 边缘判地区失败**。其中最容易漏的是：

1. **Codex（Rust reqwest）只读 env `HTTPS_PROXY`，不读 Windows 系统代理注册表键**。设置系统代理键（ProxyServer=…:7897）只对 WinINET/WinHTTP/Chromium 家族（浏览器）生效，对原生 CLI 无效。
2. **子进程继承父进程环境，不继承注册表**。Hermes Studio 若在设代理前启动，它 spawn 的 codex/opencode 子进程即使更晚启动，也继承 Studio 那份旧（无代理）环境。
3. **廉价机房 ASN 即使地理在支持国也可能被 OpenAI 拉黑**——东京节点但 ISP=Kirino LLC / AS41378，`api.openai.com` 仍可能报 region 502。

## 响应码判读树（决定下一步）

用显式 `--proxy http://127.0.0.1:7897` 探测：

| 端点 | 正常通过代理 | 判定 |
|---|---|---|
| `POST api.openai.com/v1/chat/completions`（假 key） | `401` | 边缘接受出口，仅缺鉴权 → 无地区块 |
| `POST api.openai.com/v1/responses`（假 key） | `401` | 同上 |
| `GET api.openai.com/v1/models` | `401` | 同上 |
| `GET api.openai.com/`（根路径） | `421 Misdirected` | 根路径非法路由，忽略 |
| `GET auth.openai.com` / `chatgpt.com` | `403 Cf-Mitigated: challenge` | Cloudflare 反爬，不是地区块 |
| `GET api.chatgpt.com/` | `404` | 正常；`CF-RAY …-NRT(日本)` 证明该节点出口 |
| 直连（无代理） | `000` 超时 | 内地网无法直连 OpenAI 边缘，正常 |
| `GET ai.openai.com`（猜测端点） | `000` | 多为猜错/该主机经代理不通，别据此下结论 |

红线：**`api.openai.com/v1/*` 稳定 401** 却仍报 region 502 → 一定是请求进程没走这个代理（env 缺口或父进程未重启），或走了被屏蔽的廉价 ASN 节点。不要继续在 api_mode/config 上绕。

## 修法（Windows 用户级代理环境变量，持久化）

```powershell
[Environment]::SetEnvironmentVariable('HTTPS_PROXY','http://127.0.0.1:7897','User')
[Environment]::SetEnvironmentVariable('HTTP_PROXY','http://127.0.0.1:7897','User')
[Environment]::SetEnvironmentVariable('ALL_PROXY','http://127.0.0.1:7897','User')
# 小写别名同理；NO_PROXY 保持直连白名单（lingsuan/deepseek/tian-shu 等），勿含 openai
```

回读核对：`[Environment]::GetEnvironmentVariable('HTTPS_PROXY','User')`。

## 验证（全新进程、不带 --proxy，模拟 GUI 冷启动）

```powershell
# 全新 PowerShell（继承用户级 env）里：
Write-Output $env:HTTPS_PROXY      # 应= http://127.0.0.1:7897
curl.exe -s -o NUL -w "%{http_code}" -H "Authorization: Bearer sk-FAKE" https://api.openai.com/v1/models
# 期望 401 = 经代理可达、无地区块。000/超时=没走代理；502=地区被屏蔽
```

## 必须重启父应用的判定

```powershell
Get-Process | Where-Object {$_.ProcessName -match 'hermes|studio|opencode|codex'} |
  Select ProcessName,Id,StartTime | Sort StartTime
```

设代理时刻之后启动的才算干净。Hermes Studio 要托盘全退，并确认 `codex`/`codex-code-mode-host` 残留进程也清掉再重开。

## Clash 节点切换

- 控制器：`curl -H 'Authorization: Bearer set-your-secret' http://127.0.0.1:9097/…`（密钥在 clash-verge 配置，默认常为 `set-your-secret`）。
- `GET /proxies` 看组；OpenAI 组常 `→ Proxies → JP → 🇯🇵 Japan XX`。
- 出口回查：`curl --proxy 127.0.0.1:7897 http://ip-api.com/json/<exit-ip>`（用 ip-api，ipinfo 免费版易 429）。

## 关键误判修正：`api.openai.com/v1/* 401` ≠ 登录门槛放行

2026-09-01 实况：即使把用户级 HTTPS_PROXY 设好、Hermes Studio 全退重启后，登录仍连报三次 502。原因：Codex/**登录/鉴权**流的地区门槛在 `auth.openai.com` 上，而普通 API 路径 `api.openai.com/v1/*` 在**坏节点上也只返回 401**（边缘接受、仅缺鉴权）。所以单测 `api.openai.com` 会让你误判“节点没问题”。

**判别的正确端点是对比 `auth.openai.com`：**

| 节点 | `api.openai.com/v1/*` | `auth.openai.com` | 登录链路判定 |
|---|---|---|---|
| Kirino(AS41378) JP | `401` | `403 Cf-Mitigated: challenge`（被卡） | 不可用 → 502 |
| US-01 | `401` | `302`/`200`（正常跳转/放行） | 可用 ✓ |

并经 Clash `/rules` 确认：**所有 OpenAI 域名（`chatgpt.com`、`openai.com`、`ai.com`、`DomainKeyword openai`）都 → OpenAI 组**，一条漏网都没有；`ai.openai.com` 在两节点都 `000`（多为主机经代理不通或猜错，别据此下结论）。

## 换节点（env+重启仍 502 时的决定性修复）

OpenAI 组常 `→ Proxies → JP → 🇯🇵 Japan XX`（廉价 ASN）。切到另一国家组：

```powershell
[Environment]::SetEnvironmentVariable('HTTPS_PROXY','http://127.0.0.1:7897','User')
$h = @{ 'Authorization' = 'Bearer set-your-secret' }   # 密钥见 clash-verge 配置，常为默认值
Invoke-RestMethod -Uri 'http://127.0.0.1:9097/proxies/OpenAI' -Method Put \
  -Headers $h -Body '{"name":"US"}' -ContentType 'application/json'
# 回读确认
(Invoke-RestMethod -Uri 'http://127.0.0.1:9097/proxies/OpenAI' -Headers $h).now  # = US
```

切完重测 `auth.openai.com`（`302/200` 才对）与 `chatgpt.com`（`200`）。节点选择在 Clash Verge 里通常持久化（除非重载配置）。

## Windows/batch 铁律：bash 会吞 `$`，PowerShell 必须走 .ps1

在 git-bash 里用 `powershell.exe -Command "... $var ..."` 直接内联执行，`$var`、`$()`、`$_` 全被 bash 双引号吞掉 → PowerShell 解析报 "variable missing"。解决：**凡是 PowerShell 脚本含 `$`，一律写入 `.ps1` 文件，用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <file.ps1>` 执行**。这在本会话连踩 4 次。

## 最终结论（2026-09-01 二次实况）：api 层地区已干净 → 502 是账号级，不是网络

即使切换到 US 节点、auth.openai.com 变 302/200、代理/env/重启全做对，**登录仍连报 502**。此时关键测试：

**假 key 判读是陷阱**——`api.openai.com/v1/*` 对任何非法 key 都回 401（不看地区，先查鉴权）。**要用真实凭据测**才是地区判定点。取 `~/.codex/auth.json` 里真 token，经代理打 `/v1/models`：

| 真实凭据返回 | 判定 |
|---|---|
| `200`（列出模型） | 地区干净、key 有读取权限 |
| `{"error":"...Missing scopes: api.model.read..."}`（400/403） | **地区干净**（先过了地区判定、只缺权限）→ 网络端排除 |
| `502 does not support your region` | 地区确实不支持 → 网络/节点问题 |

实况：真凭据（JWT）返回 **Missing scopes** → **api 层地区已干净，问题不在代理/节点**。

**根因锁定为账号级**：`~/.codex/auth.json` 的 `auth_mode = "chatgpt"`（不是平台 API key，是 **ChatGPT 账号 OAuth**，含 id_token/access_token/refresh_token）。Codex 若用 **ChatGPT 账号 OAuth**，有**账号常驻地区判定**，基于账号注册/常驻国，不随代理 IP 变 → 这类 502 换节点/设代理**治不好**。

**出路**（治本，不再是网络层）：
- 改用 **OpenAI Platform API key（`sk-…`，api key 模式）**给 Codex/opencode —— 已证 api key 路径在本区**无地区块**；
- 或换一个**常驻地在 OpenAI 支持区**的 ChatGPT 账号登录；
- 或先确认该 ChatGPT 账号所在区（部分工具账号的区域设定）。

一旦用真凭据证明 api 层地区干净，就**停止在 proxy/env/node 上绕**，转账号层。用 JWT 解密看 token 类型：`auth.json` 顶层 `auth_mode` 与 `tokens.{id_token,access_token,refresh_token,account_id}` 即 OAuth；顶层独立 `OPENAI_API_KEY=sk-…` 才是平台 key。

## 账号级 502 的换账号流程（device-auth）与"回同一账号"陷阱

选"换一个常驻支持区的 ChatGPT 账号"时，用 `codex` CLI 的 device-auth 流：

```bash
cp ~/.codex/auth.json ~/.codex/auth.json.bak.$(date +%Y%m%d_%H%M%S)   # 先备份
codex logout          # 清旧凭据；确认 codex login status = Not logged in
codex login --device-auth   # 交互；用 process(poll) 抓 URL + 一次性 code
# 用户浏览器打开 https://auth.openai.com/codex/device，输 code，授权 → 终端打印 Successfully logged in
```

**陷阱（本会话踩到）：`Successfully logged in` ≠ 换成了新账号。** 若浏览器在授权时仍登录着旧 ChatGPT 账号，device-auth 会给**同一个账号**重发 token，等于回到原点。验证必须看**账号 ID 是否变化**，而不是登录状态：

```powershell
# ~/.codex/auth.json 的 tokens.account_id 必须不同于旧账号
$auth = Get-Content -Raw 'C:\Users\Administrator\.codex\auth.json' | ConvertFrom-Json
Write-Output $auth.tokens.account_id   # 旧值参考 2419f77a-…；变了才说明真换了账号
codex login status                    # 只显示 "Logged in using ChatGPT"，不证明换了
```

**正确换号步骤**：新开一个 device-auth → 让用户在浏览器里**退出旧账号、登录支持区新账号之后**，再输码授权。

**auth.json 结构（chatgpt OAuth）**：顶层 `auth_mode = "chatgpt"`；顶层 `OPENAI_API_KEY` **常为空**，真正 token 在 `tokens.{id_token, access_token, refresh_token, account_id}`。做"真凭据地区测试"必须读 `tokens.access_token`，不要读顶层 `OPENAI_API_KEY`（会拿到空 → curl 报 `Incorrect API key provided: ''`）。

## Codex config 侧（若要走直连 OpenAI 而非本地 relay）

`~/.codex/config.toml` 可能指向本地 relay（例：`base_url = "http://127.0.0.1:15721/v1"`，`requires_openai_auth=true`，model=gpt-5.6-sol）。若 502 与 relay 无关、要直连：

- `model_provider = "custom"` → `"openai"`
- 删除 `[model_providers.custom]` 块（否则 base_url 仍被拉回本地 relay）
- 鉴权走 `~/.codex/auth.json` 里的 OPENAI_API_KEY/OAuth
- 保留 model 名不变（如 gpt-5.6-sol）即可

前提：auth.json 确含有效凭据（`python -c "import json;d=json.load(open(r'…/auth.json'));print(bool(d.get('OPENAI_API_KEY') or d.get('access_token')))"`）。
