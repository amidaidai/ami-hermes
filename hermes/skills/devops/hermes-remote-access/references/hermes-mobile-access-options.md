# 手机/异地访问自托管对照（快照 2026-09-14）

星数与许可读自 GitHub 仓库页与 `LICENSE` 原文。**这是快照，报给用户时说明会变。**

## 项目对照

| 项目 | 星数 | 许可 | 定位 | 手机 | 安装 / 端口 |
|---|---|---|---|---|---|
| `EKKOLearnAI/hermes-studio` | 11.1k | BSL-1.1（个人免费，商用需授权） | Ekko Studio 本体：多 agent 工作台（Hermes / Ekko / Claude Code / Codex / Pi / Grok / OpenCode / DSH），含工作流、看板、10 平台渠道配置、用量统计 | 官方 App（付费项）；自托管走手机浏览器 | `npm i -g hermes-web-ui && hermes-web-ui start` → 8648；Docker `ekkoye8888/hermes-web-ui` → 6060；桌面安装包见 Releases |
| `nesquena/hermes-webui` | 18.3k | MIT | 纯 Hermes Agent Web UI，与 CLI 近 1:1（三栏、会话侧栏、工作区文件浏览、内联预览、语音输入、CLI 会话桥） | **最完整**：响应式 + PWA + 文档专章 `docs/remote-access.md`（Tailscale 走法） | `HERMES_WEBUI_PASSWORD=… ./start.sh` → 127.0.0.1:8787；`HERMES_WEBUI_HOST` 控绑定 |
| `slopus/happy` | 23.8k | MIT | Claude Code / Codex 的手机+网页客户端，端到端加密、推送通知、一键切设备 | iOS / Android / Web 原生 App | `npm i -g happy` 后以 `happy claude` / `happy codex` 启动；服务端也可自托管 |
| `siteboon/claudecodeui`（CloudCLI） | 13.7k | 开源 | Claude Code / Cursor CLI / Codex / OpenCode 的 Web+手机 UI，带文件树、Git、内建终端、浏览器会话 | 响应式 + 桌面伴侣 App | `npx @cloudcli-ai/cloudcli` → 3001 |
| `omnara-ai/omnara` | 2.8k | Apache-2.0 | agent 托管平台（Durable agents、多机器/sandbox、自带模型、RBAC、Slack 连接器） | 网页 / Slack | `docker compose --profile app up -d` → 8000 |

`omnara` 与前三者定位不同：它是「跑 agent 的平台」，不是「连你本机 agent 的客户端」。用户只是要手机连自己电脑时不要推它。

## Hermes 自带（0 元，无需安装）

- `hermes dashboard` → `http://127.0.0.1:9119`，机器级管理面（Config / API Keys / Skills / MCP / Models / Cron + Chat tab），多 profile 用 `?profile=<name>` 切换；`--host 0.0.0.0` 可外绑，但**非 loopback 绑定一律强制 auth provider**（密码或 OAuth）——`--insecure` 已废弃为 no-op。
- gateway 渠道（10 个）：Telegram、Discord、Slack、WhatsApp、Matrix、飞书、钉钉、QQBot、微信、企业微信。凭证写 `~/.hermes/.env`，行为写 `~/.hermes/config.yaml`。

## Ekko Studio 定价结构（同快照）

| 项 | 中国大陆 | 海外 | 含什么 | 不含什么 |
|---|---|---|---|---|
| 永久激活（Local & Self-hosted） | CN¥68 一次性，闲鱼下单换码 | €9 一次性 | 本机使用、同一局域网连接设备、连自建服务器、不自动续订 | 官方云服务 |
| 云服务（Cloud + App access） | CN¥25 / 31 天，可叠加、未用顺延 | €3.50 / 31 天预付，或 €3/月自动续订（Stripe 可取消） | 跨网络连接 + **有效期内**的 App 权限；云时间累计顺延 | App 永久所有权（云到期，附带 App 权限同时失效） |

账号级规则（不是按设备算）：一账号最多 **3 台手机**同时登录；连接的 Studio 数量**不限**；云传输速率限制**按账号**共享，同账号所有手机 + 所有 Studio 共用一份配额。

激活码一次性使用、绑定兑换时的账号，换不了。

## Tailscale

个人版 $0 永久免费：不限设备数、≤6 用户、3 个 ACL 组、1000 分钟/月 ephemeral 资源。

## 取数技巧

- README 正文：`https://raw.githubusercontent.com/<owner>/<repo>/<main|master>/README.md`
- 许可原文：同路径换 `LICENSE`（BSL-1.1 的免费范围写在 `Additional Use Grant:` 段）
- 星数/最后提交：仓库页 HTML（`web_extract` 抓仓库页只拿来读这些元信息，正文别指望它）
