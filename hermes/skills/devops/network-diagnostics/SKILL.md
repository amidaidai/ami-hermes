---
name: network-diagnostics
description: 网络诊断技能 — 端口检查、代理检测、DNS 解析、延迟/丢包测试、路由追踪、TLS/SSL 证书检查、HTTP 响应分析。适用于排查连接超时、代理路由问题、API 不可达等场景。
category: devops
---

# Network Diagnostics

> 适用场景：API 连接超时、代理路由异常、TradingView MCP 断连、DNS 解析失败、端口占用。

## 快速检查清单

```bash
# 1. 本地网络
ping -c 4 8.8.8.8              # 基础连通性
ping -c 4 baidu.com             # DNS + 连通性

# 2. 代理状态（Windows Clash Verge）
curl -v --proxy http://127.0.0.1:7897 https://www.google.com

# 3. DNS 解析
nslookup api.openrouter.ai
dig +short api.openrouter.ai

# 4. 端口可达
nc -zv api.openrouter.ai 443      # TCP 端口测试
curl -v --connect-timeout 5 https://api.openrouter.ai

# 5. 延迟测量（排除代理影响）
time curl -s -o /dev/null https://api.deepseek.com/v1/models
```

## 代理路由诊断

### 检测代理是否生效
```bash
# 查看本地代理端口
netstat -ano | grep 7897
# 或
ss -tlnp | grep 7897

# 测试走代理 vs 直连
curl -s -o /dev/null -w "%{time_total}s\n" https://api.openai.com
HTTP_PROXY=http://127.0.0.1:7897 curl -s -o /dev/null -w "%{time_total}s\n" https://api.openai.com
```

### NO_PROXY 配置检查
```bash
# 环境中的 NO_PROXY
echo $NO_PROXY

# 测试某个域名是否走代理
curl -v --noproxy '*' https://api.deepseek.com/v1/models
```

## HTTP API 响应分析
```bash
# 查看完整响应头和耗时
curl -v -o /dev/null -w "\n\n--- Timing ---\n\
time_connect: %{time_connect}s\n\
time_starttransfer: %{time_starttransfer}s\n\
time_total: %{time_total}s\n\
http_code: %{http_code}\n" https://api.openrouter.ai/v1/models

# 如果 time_connect 很高 → 网络/代理问题
# 如果 time_starttransfer 很高 → 服务端处理慢
```

## TLS/SSL 检查
```bash
# 证书详情
openssl s_client -connect api.openai.com:443 -servername api.openai.com
# 证书过期日期
echo | openssl s_client -connect api.openai.com:443 2>/dev/null | openssl x509 -noout -dates
```

## 路由追踪
```bash
# Windows 用 tracert，Linux 用 traceroute
tracert api.openrouter.ai
# mtr 更友好（如已安装）
mtr --report api.openrouter.ai
```

## 端口占用排查
```bash
# Windows
netstat -ano | findstr :9222
# 或 PowerShell（如果在 PowerShell 环境）
# Get-Process -Id (Get-NetTCPConnection -LocalPort 9222).OwningProcess

# Linux/Mac
lsof -i :9222
ss -tlnp | grep 9222
```

## Windows 专用

### 代理设置检查
```bash
# 检查系统代理
curl -s --proxy http://127.0.0.1:7897 https://httpbin.org/ip
```

### WSL2 网络
```bash
# WSL2 IP
ip addr show eth0 | grep inet
# Windows 主机 IP (从 WSL 访问)
cat /etc/resolv.conf | grep nameserver
```

## Provider/API proxy bypass pattern

When an API provider is reachable both through a local proxy and by direct connection, benchmark both before changing routing. Test at least:

- Environment default (`HTTP_PROXY` / `HTTPS_PROXY` active)
- Forced local proxy, usually `http://127.0.0.1:<port>`
- Forced direct with proxy environment ignored

If direct is faster or more stable for only one provider, prefer adding that hostname to both `NO_PROXY` and `no_proxy` instead of disabling the global proxy. This preserves proxy routing for other blocked/foreign APIs while letting the fast provider go direct.

Verify open local ports are actually HTTP proxies before using them. A listening port may be SOCKS, redir, TProxy, or a controller port and can reset HTTP-proxy requests.

## 常规工作流

1. 先 `ping` 确认基础连通性，但不要把 ICMP 超时直接等同于 HTTPS/API 不可用；很多 API/CDN 禁 ping。
2. 检查代理端口是否监听。
3. 比较「走代理 vs 直连」的延迟，统一用 `curl -k -L -s -o /dev/null --connect-timeout 8 --max-time 20 -w 'code=%{http_code} connect=%{time_connect} ttfb=%{time_starttransfer} total=%{time_total}\n' URL`。
4. 检查 NO_PROXY 是否包含目标域名；若环境变量全局有 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY`，实际“直连”测试要显式设置/清空代理或用 `--noproxy`，否则会被环境代理影响。
5. 如果 http_code=401/403，通常说明网络和 TLS 已通，下一步检查认证/API Key；不要把未授权响应当连接失败。
6. 如果连接重置或超时，尝试 traceroute 定位断点，并把当前代理模式、DNS 结果、timing 输出一起保存。

## Windows / Clash Verge / Mihomo 代理排查补充

当用户问“是不是代理问题”“我电脑有什么代理”时，不要只看系统代理；同时检查环境变量、Windows 注册表代理、监听端口和进程名，避免把模型服务端排队误判成本机代理慢。

### 推荐检查顺序

1. **环境变量代理**：读取 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY` 以及小写版本。Hermes/requests/curl 常受这些变量影响。
2. **Windows 系统代理**：查询 `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings` 的 `ProxyEnable`、`ProxyServer`、`ProxyOverride`、`AutoConfigURL`。
3. **本地代理端口**：扫描常见端口，例如 `7890`、`7891`、`7892`、`7897`、`1080`、`10808`、`10809`。
4. **进程归因**：用 `netstat -ano` 找 PID，再用 `tasklist //FI "PID eq <pid>"` 确认是否为 `verge-mihomo.exe`、Clash、sing-box 等。
5. **代理类型验证**：不要假设所有开放端口都是 HTTP 代理。某些端口可能是 socks/mixed/redir/tproxy/control；用 HTTP proxy 方式测试若出现 `ConnectionResetError 10054`，只说明该端口不适合当前 HTTP_PROXY 用法，不代表代理软件整体不可用。

### 代理节点级诊断：不要把“当前节点失败”误判为“代理失败”

当代理客户端使用 Selector/URLTest 等策略组时，必须区分三层：

1. **直连路径**是否可用；
2. **本地代理端口/协议**是否可用；
3. **当前选中出口节点**是否允许目标服务。

如果代理可正常访问控制站点，但目标域名 TLS 失败、HTTP 451 或被重置，不能直接得出“走代理不行”。应在同一代理组中临时测试多个地区节点，并在测试后恢复原选择。交易所、流媒体和AI服务尤其容易因出口地区产生不同结果。

推荐验收矩阵：

- 强制直连：`curl --noproxy '*' ...`
- 强制当前代理：`curl --proxy http://127.0.0.1:<port> ...`
- 多节点逐个测试：记录 HTTP 状态、TLS耗时、总耗时
- 控制站点：同时测试 Google 204 或其他已知可用HTTPS站点，确认代理端口本身正常
- 服务的多个官方端点：例如现货、衍生品、备用域名分别测试

判读铁律：

- `200/204`：网络与TLS可用；再进入鉴权验证。
- `401/403`：链路已通，检查凭据或套餐。
- `451`：通常是出口地区限制，换地区节点。
- 控制站点成功、目标TLS失败：优先怀疑当前出口节点/地区策略，而不是代理客户端整体。
- 直连超时、某代理节点200：该服务应走代理，并固定到通过验证的节点/策略组。

通过本地控制器API临时切节点时，必须：①记录原选择；②逐节点测试；③用`finally`恢复原选择；④未获用户授权不要永久改全局代理。完整复现与判读示例见 `references/proxy-node-vs-proxy-path.md`。

### 代理 vs 服务端/模型延迟的判定

对同一个 HTTPS API 做四组对比：

- 环境默认：使用当前 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY`。
- 强制指定可用 HTTP 代理：例如 `127.0.0.1:7897`。
- 强制直连：Python `requests.Session().trust_env=False` 且 `proxies={}`，或 curl 配合 `--noproxy '*'`。
- 错误/可疑端口：只用于确认端口类型，不作为性能结论。

判读：

- 强制代理≈强制直连：本机代理不是主瓶颈。
- 环境默认明显更慢但强制代理正常：可能是环境变量、NO_PROXY、规则匹配、连接复用、节点切换或 DNS 缓存造成抖动。
- 短请求快、长/推理请求慢：优先判断为模型选项、服务端排队、上下文/工具负载，而不是网络代理。
- `/v1/models` 等未授权接口能快速返回 `401`：说明 TCP/TLS/路由基本可用；慢点通常在推理服务端或模型处理阶段。
