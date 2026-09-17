# Hermes 前端 / 工作台格局

适用：用户问「X 和 Hermes 自带桌面和 GitHub 上那些，哪个最好」「要不要换前端」「这个客户端值不值得买」。

星数、版本号、定价是**快照**，用前按下面命令复核；许可与定位这类结构信息较稳定。

## 一、先分辨同名产品（最高代价的一步）

「Hermes 前端」在本机指代不清，必须落到具体仓库：

| 名字 | 仓库 / 包名 | 实质 | 状态落在哪 |
|---|---|---|---|
| Hermes Agent / Hermes Desktop | `NousResearch/hermes-agent`（MIT） | agent 内核 + 一方原生桌面 + CLI + TUI + web dashboard | `~/.hermes/`（内核 home） |
| **Ekko Studio** | 仓库 `EKKOLearnAI/hermes-studio`；npm/CLI 仍是 `hermes-web-ui`；MCP 工具 `ekko_studio_*` | 第三方多 agent 工作台，曾用名 Hermes Studio / Hermes Web UI；**驱动**内核而非替代内核 | 自己的 `~/.hermes-web-ui/`（sqlite + profiles + desktop-runtime） |
| AionUi | `iOfficeAI/AionUi`（Apache-2.0） | 第三方多 CLI 协同工作台，把 Hermes 当其中一个后端（可作 Leader 编排后端） | 自己的配置目录 |
| OpenWork | `different-ai/openwork`（MIT 核心 + `ee/` 目录另授权） | Cowork 型桌面，基于 opencode；**不驱动 Hermes** | 自己的配置目录 |
| Eigent | `eigent-ai/eigent`（Apache-2.0） | 多 agent 劳动力桌面；**不驱动 Hermes** | 自己的配置目录 |

没有独立状态的（OpenWork / Eigent）对棠溪系统是**不入账**的候选 —— 不共享 skills/memory/cron 的前端换不来任何能力，只能换来皮肤。

## 二、复核命令

```bash
# 是谁在跑（进程路径 = 哪家的哪个前端）
powershell -NoProfile -Command "Get-Process | Where-Object {$_.ProcessName -match 'Hermes|Ekko|Aion|electron'} | Select Id,ProcessName,Path | Format-Table -AutoSize | Out-String -Width 200"
# 谁在挂 MCP 子进程（命令行里能看到前端名 + 内核 profile）
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -match 'hermes-web-ui|ekko|hermes'} | Select ProcessId,Name,CommandLine"

hermes --version                                    # 内核版本
ls ~/.hermes-web-ui/desktop-runtime/hermes/         # 前端自带 runtime 的版本目录
ls "$LOCALAPPDATA/Programs/Hermes Studio/Ekko Studio/resources/webui/"   # 前端本体版本（读 package.json 的 version）
cat ~/.hermes-web-ui/active-version.json
ls -la ~/.hermes-web-ui/hermes-web-ui.db            # 前端自有状态库的体量与改动时间 = 它是否仍在被使用

gh api repos/EKKOLearnAI/hermes-studio --jq '{s:.stargazers_count,l:.license.spdx_id,p:.pushed_at}'
gh api repos/iOfficeAI/AionUi      --jq '{s:.stargazers_count,l:.license.spdx_id,p:.pushed_at}'
gh api repos/different-ai/openwork --jq '{s:.stargazers_count,l:.license.spdx_id,p:.pushed_at}'
gh api repos/eigent-ai/eigent      --jq '{s:.stargazers_count,l:.license.spdx_id,p:.pushed_at}'
gh api repos/NousResearch/hermes-agent --jq '{s:.stargazers_count,l:.license.spdx_id,p:.pushed_at}'
```

`grep -n -A3 "ekko\|studio" ~/AppData/Local/hermes/config.yaml` 能把「前端是否已接进内核」查实 —— 注册了 `ekko-studio-*` MCP 段就说明前端工具面已经进内核工具目录。

## 三、横评（结构信息为主，数字复核后填）

| 产品 | 许可 | 驱动 Hermes | 状态共享 | 定位 / 代价 |
|---|---|---|---|---|
| Hermes Desktop | MIT | 就是本体 | 全共享 | 一方原生；免费；无多运行时同窗、无手机 App |
| Ekko Studio | BSL-1.1（源码可见、商用受限）+ 买断/云订阅收费 | 是（+7 运行时） | 不自有状态，Hermes profile 数据仍在 Hermes home；**自己另起 `~/.hermes-web-ui`** | 多 agent 同窗、群聊协作、可视化工作流 + 人工审批闸门、手机 App + 跨网设备、Agent Manager、技能浏览器、用量面板 |
| AionUi | Apache-2.0 | 是（+20 CLI，可作 Leader 编排后端） | 自己的配置目录 | 免费开源多 CLI 同窗；与内核原生概念（profiles/skills/cron/kanban）耦合较浅 |
| OpenWork | MIT 核心 + `ee/` | 否 | — | Cowork 型；对棠溪不入账 |
| Eigent | Apache-2.0 | 否 | — | 多 agent 劳动力桌面；对棠溪不入账 |

Ekko Studio 许可读法：仓库称 BSL-1.1（`gh api` 回 NOASSERTION，须读 `LICENSE` 原文）。定价分两层 —— **本地/自托管永久买断** 与 **云（跨网连接，含订阅期内的软件权限）**，两层权利不同：买断不含云，云到期不等于永久。

## 四、结论模板

1. 首行一句裁决，点名「你现在跑在 X 上」，再给谁最好。
2. 「为什么」按 runtime 级能力写（状态唯一、免费一方、内核级 cron/gateway/skills 只能内核拥有），不按功能数量写。
3. 一张 7 列横评表（见 SKILL.md 判定轴节）。
4. 副屏产品写清「留什么、别让它接管什么」。
5. 「换轴怎么选」三条：要全免费开源 → AionUi；要手机/工作流/多运行时 → Ekko Studio；要零缝隙零成本 → 一方桌面。
6. 风险段必含：前端自有状态库（长期两套数据）、HTTP 桥多一跳、自带 runtime 与内核版本错位。
7. 诚实标注取证深度：只读了仓库/文档的候选要写明「未实机跑过」，不要与实测过的混在一起。

## 五、长期风险清单

- **双状态库**：前端自有 sqlite（`~/.hermes-web-ui/hermes-web-ui.db`，可达数百 MB）与内核 state.db 并存，各自维护、各自备份。
- **桥接跳**：前端经 `/api/hermes/*` 调内核，多一层失败面。
- **版本错位**：前端桥自带一份 runtime（`desktop-runtime/hermes/<ver>`），落后于内核时功能会短暂对不上；评估时把两个版本号都写出来。
- **改名的历史包袱**：仓库名 / npm 名 / MCP 工具名前缀 / 安装目录四处不同名，文档与搜索都会踩歧义。
