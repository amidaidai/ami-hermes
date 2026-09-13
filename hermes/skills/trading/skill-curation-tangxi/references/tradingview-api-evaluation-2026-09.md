# TradingView-API 评估记录（2026-09-13 实测）

对象：[Mathieu2301/TradingView-API](https://github.com/Mathieu2301/TradingView-API)
（4.5k⭐ / 823 fork，npm `@mathieuc/tradingview` v3.5.2，JavaScript，最后提交 2026-06-23）

结论：**不引入**（不作为浏览器 TV 链路的替代）。它只有一件事有价值，但那件事有两个硬前提。

## 实测结果

| 项 | 结果 |
|---|---|
| 安装 | `npm i @mathieuc/tradingview` → 42 包 / 3 秒 ✓；deps 仅 axios+jszip+ws，轻 |
| 网络 | TV 的 WS **直连超时，走代理 257ms 可达**（`wss://data.tradingview.com/socket.io/websocket`）|
| 库的代理支持 | **无** —— `ClientOptions` 里没有 agent/proxy，而 `ws` 不认 HTTP_PROXY |
| 绕过方式 | 在 `require('ws')` 前把 require.cache 里的 `ws` 换成自动注入 `HttpsProxyAgent` 的 Proxy 子类 → **库里直接可用**（已实测）|
| 行情 | `Client + Session.Chart` → 100 根 15m，**但最新柱滞后约 25 小时**（库给 09-12T13:45Z，Binance 实际已到 09-13T14:30Z）|
| 指标值 | `BuiltInIndicator` 只覆盖 Volume / Volume-by-Price 几个；任意指标要走 `getIndicator()`（需已发布脚本 id）或 `getPrivateIndicators()`（**需登录**）|
| `getTA` | 超时（公开辅助能力在本地不可靠）|

## 为什么不合适

1. **“Realtime” 实际需要登录**。不带凭据只能拿到滞后约 25 小时的历史 —— 对我们是废数据
   （我们已经有更快更准的：Binance REST/WS、TwelveData、OANDA）。
2. **读私有指标需要你的 TradingView 会话 cookie**（`.env.sample` 就是 `SESSION` + `SIGNATURE`）。
   代价有两层：
   · 把 TV 账号会话交给一个逆向工程的第三方库 → 账号被判定违规/封禁风险，
     而**你的图表与自研指标就是核心资产**；
   · 这个 cookie 又会成为 `.env` 里的新密钥 → 正好落进我们刚修的「终端快照明文泄露」面。
3. **能力不对口**。我们的 SVP/AggVol 消费依赖 Pine 的**表格/线/框/标签**
   （`data_get_pine_tables/lines/boxes/labels`），而该库暴露的是 plot “study 值”；
   能否读 `table.new` **未证实且存疑** —— 而 SVP 的行动格/结构位正是表格式输出。
4. 维护性：101 个 open issue；最后提交 3 个月前；GitHub API 报 `license: null`
   （package.json 写 ISC 但仓库无 LICENSE 文件）。

## 值得记住的一点

**“不走浏览器、直接用 TV 的 WS 取数据” 在这台机器上是可行的** —— 前提是走代理 +
在客户端挂 proxy agent（TV WS 直连不通）。但要用就该自写客户端，且仍要面对
“私有指标必须带账号票据”与 TOS 风险。

→ 对当前需求（SVP 主指标授权 + 表格消费 + 已稳定的 TV MCP + 5m 校核）**投入产出不划算**。

## 如果将来真要解决「后台采集切走用户图表」这个痛点

优先做**降低切图次数**（见 `tangxi-runtime-audit-and-cleanup/references/`
里的 chart-switch-reduction 参考），而不是引入需要账号票据的第三方逆向库。
