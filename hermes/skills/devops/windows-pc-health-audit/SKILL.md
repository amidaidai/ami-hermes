---
name: windows-pc-health-audit
description: Use when checking or optimizing a Windows PC for malware.
category: devops
---

# Windows 整机体检

用于回答"看一下这台电脑有什么问题 / 有什么软件 / 有病毒吗 / 怎么优化"。四份产出缺一个都算没答完：

| 问句 | 产出 |
|------|------|
| 有什么问题 | 分级表 P0/P1/P2，每行带一句实测证据（键值、状态、数字），不要只写"异常" |
| 有什么软件 | 分类清单（安全 / AI与开发 / 办公通讯 / 浏览器 / 运行库 / 右键与内核扩展）+ 明显冗余项 |
| 有病毒吗 | 先给"未发现"的逐项正面证据，再给能力边界；见 `references/windows-malware-and-persistence-forensics.md` |
| 怎么优化 | 可释放空间（GB）+ 待改配置 + 分批执行清单；见 `references/windows-machine-reclaim-and-optimization.md` |

维度明细（硬件/系统/磁盘/安全/网络/内存/驱动/用户/启动项/任务/事件/共享共 12 维）见 `system-ops` 技能的「Windows OS 级全面检查」与 `references/windows-system-audit-commands.md`；本技能在其上补第 ⑬ 维（恶意软件与持久化）和整机优化，两者一起用。

## 一、采集方式：写 .ps1 文件，不要长内联 -Command

多维度体检会产生几十条命令，长内联 `-Command` 会被 MSYS bash 的转义和长度限制打碎。固定做法：

1. 每批写一个 `.ps1` 到 `$LOCALAPPDATA/Temp/`（`write_file`，路径用 `C:/...` 正斜杠原生路径）。
2. 脚本内把结果 `$lines | Out-File -FilePath 'C:\...\audit_N.txt' -Encoding UTF8`，控制台只 `Write-Output "WROTE n lines"`。
3. 运行：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:/Users/.../audit_N.ps1"`（`-File` + 正斜杠原生路径；MSYS 不翻译路径参数）。
4. 用 `read_file` 读 txt —— 中文不乱码，且大输出可分段读。

**先跑快批次**：`scripts/windows_audit_collect.ps1` 把不递归统计目录的维度合成一个脚本，输出单个 UTF8 txt，正常 1-2 分钟。先把"必须出结论"的维度（安全策略、启动项、端口、进程签名）拿到手，再跑慢的。

**慢批次必须后台跑**：递归统计整个用户目录 / `AppData\Local` 的单批要 8-12 分钟并吃满一个核。这类批次用 `terminal(background=true, notify=true)` 启动，靠轮询输出文件（`ls -la <txt>`）判断完成，不要前台傻等。

## 二、安全结论：两个最容易写错的地方

### 第三方杀软接管 Defender 的判定

`Get-MpComputerStatus` 报 `AntivirusEnabled=False` 时不要直接写"没有杀毒软件"。先分辨是被别人接管还是真的没装：

- `HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection` 的 `DisableAntivirus` / `DisableRealtimeMonitoring`
- `HKLM:\SOFTWARE\Microsoft\Windows Defender` 的 `DisableAntiSpyware` / `DisableAntiVirus` / `ProductStatus` / `PassiveMode`
- `Get-CimInstance -Namespace root\SecurityCenter2 -ClassName AntiVirusProduct` 里注册了谁
- 实测 `Start-Service WinDefend` 能否拉起（被策略禁用时拉不起来），测完保持原状态，不要留下半启用状态

被第三方接管时系统只剩那一家在防，**必须再查它的扫描日志新鲜度**（多数国产安全软件只在前台手动点一次才全盘扫），据此给 P0 结论，而不是笼统说"没杀毒"。

### UAC 被削弱

`HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\ConsentPromptBehaviorAdmin=0` 表示管理员提权**不再弹窗**（默认应为 5 或 2），等于任何程序可静默提权。这通常是"安全软件/优化工具"改的，属 P0 级发现，必须单独报。

## 三、时间同步是交易机器的 P1 项

`w32tm /query /status` 出现"源 = Local CMOS Clock"且"上次成功同步时间 = 未指定"＝**从未同步过**；配合 System 日志 `Microsoft-Windows-HAL` Id 21（ACPI 实时时钟设置失败 `0xC0000001`）说明是固件/时钟链路问题。在修好之前不要假设任何 K 线时间戳可信；修复方向是指向可达的 NTP 源并开自动同步。

## 四、报告形态

一句话结论前置并点名最严重的 2-3 项 → 机器底表（CPU/内存/主板BIOS/引导/分区/系统版本，带"判断"列）→ 安全分级表（级别 / 问题 / 证据）→ 病毒结论 → 已装软件分类 → 优化与可释放清单 → 分批执行。表格化、少标题、不用 `═══`/`━━━` 装饰分隔符。

分级用 P0/P1/P2，证据列写**可核查的具体值**（注册表键=值、服务状态、事件 ID+时间、GB 数字），不写"存在风险"。

## 五、执行边界：体检不要顺手做破坏性清理

清缓存会强制重建（uv/npm/pip/浏览器缓存），删还原点、回收站、旧备份不可逆，BIOS 与分区操作必须用户本人在固件界面完成。把动作分三组交付，**等一句授权再动手**：

1. **我可代做（零风险）**：缓存清理、限缩卷影副本、修时间同步、电源方案、关后台录制、自启与 PATH 精简、装待装更新。
2. **需要用户在 BIOS / 软件 UI 里做**：开 XMP、刷 BIOS、卸载或更换软件、分区调整。
3. **需要用户决策**：换杀软、加内存、UEFI+GPT 转换（MBR+Legacy 引导时 Secure Boot 不可用，转换有风险）。

## 六、常见误判

- **可疑模式命中 ≠ 木马**：自建自动化（隐藏窗口拉起自己的驱动）会命中 `-WindowStyle Hidden` + `powershell.exe` 模式，必须看目标 exe 的签名主体和路径再定性。
- **未签名 ≠ 恶意**：自编译工具、便携软件、`venv`/`uv` 的 python、Electron 应用普遍未签名。可疑的是"未签名 **且** 从 Temp/Downloads/ProgramData/AppData 运行"。
- **`Get-ChildItem -Recurse -Include *.exe,*.dll` 会匹配 `.log/.dat/.tmp`**，产出上百条"新增可疑文件"假阳性；改用 `-Filter` 逐个扩展名或按 `$_.Extension` 后置过滤。
- **目录体积会被联接点重复计数**：`C:\Documents and Settings` → `C:\Users`、`AppData\Local\Application Data` → 自身，会把同一个 69GB 算两遍。
- **`$p.Threads` 在字符串插值里输出 `System.Diagnostics.ProcessThreadCollection`**，要用 `$p.Threads.Count`。
- **看累计 CPU 时间而不是瞬时占用**：输入法云组件、远控常驻、webview 这类"单次看不出、累计很吓人"的常驻进程，只有 `Get-Process | Sort-Object CPU -Descending` 才揪得出来。

## 支持文件

- `scripts/windows_audit_collect.ps1` — 快批次采集器，一次跑完 12+1 维中所有低开销项，输出单个 UTF8 txt。
- `references/windows-malware-and-persistence-forensics.md` — "有病毒吗"的取证清单、判定要点、浏览器扩展解析、结论写法。
- `references/windows-machine-reclaim-and-optimization.md` — 目录体积统计的坑、可释放项与命令、优化取数命令、执行分组。
