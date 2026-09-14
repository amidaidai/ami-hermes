---
name: hermes-remote-access
description: Use when accessing Hermes from a phone or remote network.
version: 1.0.0
created_by: agent
metadata:
  hermes:
    tags: [hermes, remote-access, mobile, tailscale, self-hosted, ekko-studio]
---

# Hermes 远程访问（手机 / 异地 / 自托管）

触发：
- 「手机怎么用我电脑上的 Hermes」「我想在手机这里同步」
- 「在外网 / 4G 怎么连家里电脑」「怎么从别的网络访问」
- 「Ekko Studio 该买哪个」「这个定价是什么意思」
- 「有没有一样的开源项目」「觉得订阅太麻烦了」
- 「手机有 VPN / 电脑开着 Clash，会不会连不上」「内网穿透怎么配」

## 结论：按成本升序给答案，0 元优先

**先判一个前提：手机和电脑是不是同一个 WiFi。** 是的话整条组网/付费链路都不需要——Web UI 绑到局域网可达地址，手机浏览器直接开 `http://<电脑内网IP>:<端口>`，零成本零冲突。只有「人不在家还要连」才需要下面的方案。这一问能省掉后面所有配置讨论。

1. **Hermes 自带 gateway 渠道**（Telegram / 飞书 / Discord / Slack …）：0 元、官方支持、配好即可用，但**只是聊天通道**——没有会话列表、文件树、终端。
2. **自托管 Web UI + Tailscale 组网**：0 元，功能最接近桌面端。**默认推荐这条。**
3. **官方客户端 + 官方云**：付费且按月续，只在用户明确要原生 App 体验时推荐。

用户对订阅制敏感（「感觉这个有点麻烦」= 想要免费且少折腾的方案）。先给 0 元路径，再谈买哪个档；不要一上来就报付费方案。

## 关键事实（核清一次，别重复调研）

- 用户看到的 **Ekko Studio** 就是 GitHub 上的 `EKKOLearnAI/hermes-studio`（原 Hermes Studio / Hermes Web UI；npm 包名仍是 `hermes-web-ui`）。许可 **BSL-1.1：个人、教育、研究免费；商用（SaaS 托管 / 嵌入商业产品 / 销售）需单独商业授权**。
- 所以它的付费项买的**不是软件本体**，而是**官方 App 的联网能力 + 官方云中转**：一次性激活只含本机、同一局域网、自建服务器；云订阅在有效期内附带 App 权限，云到期 App 权限同时到期；**两者互不包含**。解释定价页必须把这个边界拆开讲。
- **Tailscale 个人版 $0 永久免费**（不限设备数、≤6 用户），正好替代「云中转」那笔月费。
- Hermes 侧已有 0 元入口：`hermes dashboard`（内置管理面 + Chat tab，默认 `127.0.0.1:9119`）与 gateway 的 10 个平台渠道。

## 自托管 Web UI 选型

| 项目 | 许可 | 什么时候选 |
|---|---|---|
| `EKKOLearnAI/hermes-studio` | BSL-1.1（个人免费） | 要保住用户已经熟悉的 Studio 界面；有 Windows 安装包 / Docker |
| `nesquena/hermes-webui` | MIT | 纯 Hermes 前端、与 CLI 近 1:1；**手机支持最完整**（响应式 + PWA + Tailscale 专章文档） |
| `slopus/happy` | MIT | 目标其实是 Claude Code / Codex，且要原生 iOS/Android App |
| `siteboon/claudecodeui` | 开源 | Claude Code / Cursor CLI / Codex / OpenCode 的 Web+手机 UI |
| `omnara-ai/omnara` | Apache-2.0 | 要自托管 agent 托管平台（多机器 / RBAC / Postgres 状态 / Slack） |

完整对照（星数快照、定位、端口、安装命令）与 Ekko Studio 定价结构拆解见 `references/hermes-mobile-access-options.md`。

## Tailscale 组网（官方文档的标准三段式）

```bash
HERMES_WEBUI_PASSWORD=*** ./start.sh      # 保持只绑 127.0.0.1:8787，同时开密码
```

1. 电脑与手机装同一个 Tailscale 账号（个人版免费）。
2. 服务保持 loopback，发布给 tailnet：`tailscale serve --bg 8787`。
3. 手机浏览器打开 Tailscale 输出的 HTTPS MagicDNS 地址 → **添加到主屏幕**（PWA，接近原生 App）。

Serve 报 `Access denied: serve config denied` 时先 `sudo tailscale set --operator=$USER`；仍不行才退到直连 tailnet IP——此时**必须同时设密码**，因为它已绑到 loopback 之外：

```bash
HERMES_WEBUI_HOST=0.0.0.0 HERMES_WEBUI_PASSWORD=*** ./start.sh   # 手机访问 http://<tailscale-ip>:8787
```

自托管 Studio 端口：npm 起 → **8648**；Docker（`ekkoye8888/hermes-web-ui`）→ **6060**；hermes-webui 默认 → **8787**；`hermes dashboard` → **9119**。

## 代理 / VPN 共存（中国大陆用户的必答题）

用户跑 Clash（电脑）和各种代理 App（手机）时问「会不会连不上」，答案要**先分层**，别把两件事混成一句：

- **电脑端 = 路由劫持**。Clash 的 TUN 模式会连 Tailscale 的流量一起抓走，**加分流规则可解**。
- **手机端 = 系统硬限制**。Android/iOS 强制同一时间只能有一个 VPN 激活（Tailscale 官方 FAQ 明写），代理 App 和 Tailscale 抢同一个槽位，**配置绕不过去，只能换思路**。

配套规则（电脑端 Clash 放行）：

```yaml
rules:
  - IP-CIDR,100.64.0.0/10,DIRECT,no-resolve
  - IP-CIDR6,fd7a:115c:a1e0::/48,DIRECT,no-resolve
  - DOMAIN-SUFFIX,ts.net,DIRECT
  - DOMAIN-SUFFIX,tailscale.com,DIRECT
dns:
  fake-ip-filter:            # 伪 IP 模式必须加，否则 MagicDNS 解析被污染
    - "*.ts.net"
    - "*.tailscale.com"
```

手机端三条路（按折腾程度升序）：**① 电脑当 exit node**（免 root，Windows 官方支持，手机只开 Tailscale，外网流量交给电脑的 Clash）；**② 手动切换**（连自己电脑走内网不需要代理，两个需求本不必同时满足）；**③ root 后 Magisk-Tailscaled 走 userspace SOCKS5**（最彻底但没 MagicDNS，只能用 IP）。

完整决策表、exit node 的 Windows 操作步骤、root 方案片段、大陆 DERP 现状、以及完全避开 VPN 槽位的 Cloudflare Tunnel 备选，见 `references/proxy-vpn-coexistence.md`。

## Windows 现实约束

本机是 Windows，`hermes-webui` 仓库**含 `start.ps1`**，官方 README 也给了原生 Windows 路径：Python 3.11+ → `python -m venv venv` → `pip install -r requirements.txt` → `pwsh .\start.ps1`（自动发现 `venv\Scripts\python.exe`）。**别因为 `start.sh` 是 POSIX 就断言它只能跑 WSL**——先探一下原生入口在不在，再决定推荐谁。

原生 Windows 的已知限制：工作区浏览器会露出 POSIX 风格路径；假定 bash 存在的 agent 工具可能不工作。**WSL2 建的 venv（`venv/bin/python`，ELF）不能被原生 Windows Python 调用**，两条路各建各的 venv；WSL2 版内存约 1GB vs 原生约 330MB。

Studio 自托管在 Windows 上最省事（桌面安装包 + Docker 镜像都有），需要 Studio 独有的图形化工作流 / 多 agent 编排 / 群聊时才选它。Hermes 数据目录在 `%LOCALAPPDATA%\hermes`。

## Pitfalls

- **取 GitHub 正文走 raw**：`https://raw.githubusercontent.com/<owner>/<repo>/<main|master>/README.md`。仓库页的 `web_extract` 结果大半是导航/侧栏，README 正文常被 `[... middle omitted ...]` 截断，拿不到能力清单；许可靠不住仓库页徽章，要单独取 `LICENSE` 读「Additional Use Grant」段落。
- **许可决定能不能推荐**：区分「开源」和「商用免费」。BSL-1.1 / Apache-2.0 / MIT 的个人免费额度要写明，否则用户会以为自托管商用也免费。
- **别说官方 App 的门槛「可以绕过」**：正确表述是两条正当路径——官方 App 走付费，自托管走浏览器/PWA。
- **星数与许可是一手证据**：直接读仓库页，不凭记忆报数；报数时说明这是快照。
- **别把一次性当订阅、也别把订阅当买断**：报价必须标明「一次性 / 每期」，并给回本点（一次买断 X 元 vs Y 元/月 → 几个月回本）。
- 正文抓取优先 `web_extract`；某个入口当轮取到空内容时换文档抓取方式重试，不要把一次取数失败写成「该页面不可读」的结论。
- **平台支持性断言先做存在性探测，别拿 README 散文当证据**：`curl -s -o /dev/null -w "%{http_code}" https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<file>`，200 即文件确实在仓库里。这一步直接决定「Windows 能不能跑」这类结论，猜错会让整条推荐跑偏。
- **代理问题的答案必须先说清是「电脑端劫持」还是「手机端槽位争用」**：前者给配置，后者只能换思路（exit node / 切换 / root 共存）。混着讲会让用户以为加条规则就能解决单 VPN 槽位的硬限制。分类完后要**诚实报代价**——原生模式限制、exit node 的带宽与依赖、P2P 打洞失败的备用路径，都要写明，不要只给好消息。
- **推荐必须结论前置 + 明确排序**：用户问「哪一个最好」要直接给第一名和理由，并单独点出「不用考虑」的选项及原因（例如 happy / CloudCLI 是 Claude Code / Codex 的客户端，不是 Hermes 的），避免用户被无关项目分散。

## 相关技能
- `hermes-windows-maintenance` — 这台机器上 Studio 实例、agent-bridge 与 `hermes update` 的锁关系。
- `provider-subscription-comparison` — 需要横向比对多个付费方案并出对比卡时用。
