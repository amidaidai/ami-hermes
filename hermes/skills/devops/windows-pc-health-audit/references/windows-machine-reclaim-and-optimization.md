# Windows 整机优化与空间回收

用于回答"怎么优化"。两部分：先量（谁占了空间），再决定清什么。**量完不要直接清** —— 把清单交给用户等授权，见末尾执行分组。

## 一、目录体积统计：先避开三个坑

### 坑 1：全量 `Get-ChildItem -Recurse` 很慢

递归扫整个 `C:\Users\<user>` 或 `AppData\Local` 单次 8-12 分钟，容易把前台调用拖死。做法：按"已知易胖目录"逐个量，而不是一次扫全盘。优先量这些：

```
%LOCALAPPDATA%\uv              # uv 包缓存，常见十几 GB
%LOCALAPPDATA%\npm-cache
%LOCALAPPDATA%\pip\Cache
%LOCALAPPDATA%\Google\Chrome\User Data\Default
%LOCALAPPDATA%\Microsoft\Edge\User Data\Default
%LOCALAPPDATA%\Temp
%LOCALAPPDATA%\ms-playwright
%LOCALAPPDATA%\<各产品>-updater # 残留 installer
%APPDATA%\<各产品>
%USERPROFILE%\.cache  .codex  .grok  .workbuddy  .hermes-web-ui
C:\Windows\WinSxS  C:\Windows\Installer  C:\Windows\Temp
C:\Windows\SoftwareDistribution\Download
C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization
```

度量函数：`Get-ChildItem -LiteralPath $p -Recurse -Force -File | Measure-Object Length -Sum`，包成函数逐目录调用；对 `%LOCALAPPDATA%` 这类父目录，只列其子目录中 > 200MB 的项，避免刷屏。

### 坑 2：联接点/自引用会重复计数

`C:\Documents and Settings` 指向 `C:\Users`，`AppData\Local\Application Data` 指向自身。不排除 reparse point 会把同一个 69GB 算两遍，得出"用户目录 139GB"这种结论。用 `-Attributes !ReparsePoint`，或过滤 `$_.LinkType`。

判断捷径：**某个目录的体积恰好等于它的父目录，基本就是自引用**。

### 坑 3：`-Include` 配 `-Recurse` 会匹配到无关扩展名

`Get-ChildItem <dir> -Recurse -Force -File -Include *.exe,*.dll,*.ps1` 在递归模式下会把 `.log`/`.dat`/`.tmp` 之类也匹配进来，产出上百条"新增可疑文件"假阳性。改用 `-Filter` 逐个扩展名循环，或后置按 `$_.Extension` 过滤。

## 二、常见可释放项与对应动作

| 项目 | 动作 |
|------|------|
| uv 包缓存 | `uv cache clean`（清完重建要重新下载，先量体积再报给用户） |
| npm 缓存 | `npm cache clean --force` |
| pip 缓存 | `pip cache purge` |
| Chrome 端侧 AI 模型 `OptGuideOnDeviceModel\*\weights.bin` | 常 4GB 级，删掉或关闭该功能，不影响浏览 |
| 卷影副本/还原点 | `vssadmin list shadowstorage` 看已用/分配/最大；`Get-CimInstance Win32_ShadowCopy`、`Get-ComputerRestorePoint` 看还原点；限缩最大占用即可回收大部分 |
| Delivery Optimization 缓存 | `C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization` |
| WinSxS 组件 | `DISM /Online /Cleanup-Image /StartComponentCleanup` |
| 用户 TEMP / `C:\Windows\Temp` | 直接清（占用中的文件自动跳过） |
| 回收站 | `(New-Object -ComObject Shell.Application).NameSpace(10)` 数条目与体积，删前确认 |
| 旧备份 zip / `*.bak_*` | 备份目录里的历史归档，保留最近一份 |
| 各类 `*-updater` 残留 | 已升级完的 installer 目录 |
| 页面文件 | 迁到数据盘可等量空出系统盘 |

## 三、常见优化项与实测取数命令

| 优化项 | 取数命令 / 判定 |
|--------|----------------|
| 内存频率被浪费 | `Get-CimInstance Win32_PhysicalMemory | Select Capacity,Speed,ConfiguredClockSpeed`；`(Get-CimInstance Win32_PhysicalMemoryArray).MemoryDevices` 看槽位。Speed 明显低于 CPU 支持频率 = BIOS 没开 XMP/DOCP；槽位有余 = 可升级 |
| 内存压力 | 性能计数器 `Memory\Committed Bytes` 与 `Memory\Commit Limit` 对比 + `FreePhysicalMemory` + `Memory\Page Faults/sec`。提交量贴近上限、空闲长期偏低、页错误高 = 瓶颈是内存而不是 CPU/磁盘 |
| 电源方案 | `powercfg /getactivescheme` / `powercfg /list`；生产机可切高性能 |
| 后台录制 | `HKCU\System\GameConfigStore\GameDVR_Enabled=1` = 开着，可关 |
| 快速启动名存实亡 | `HiberbootEnabled=1` 但 `powercfg /a` 报"休眠不可用" = 配置矛盾，该功能实际无效 |
| 自启冗余 | Run 键指向已卸载/旧版本路径（系统内已装新版本但自启仍指便携旧版）→ 清掉 |
| PATH 卫生 | 分别量 User/Machine PATH 长度，找重复项与 `Test-Path` 失败项 |
| 驱动/固件落伍 | `Get-CimInstance Win32_PnPSignedDriver` 按 `DriverDate` 排序；BIOS 日期过旧列入建议（刷 BIOS 属"需用户自己动手"） |
| 常驻进程隐性消耗 | `Get-Process | Sort-Object CPU -Descending` 看**累计** CPU 时间，能揪出输入法云组件、远控常驻、webview 这类单次看不出的长期消耗 |
| 进程数爆炸 | `Get-Process | Group-Object ProcessName | Sort-Object Count -Descending` 看谁开了几十个实例 |
| 磁盘分区失衡 | `Get-Partition` 看各区大小与实际占用；系统盘紧张而数据盘大空是典型可优化点 |

## 四、交付与执行分组

报告里给两列"项目 | 可释放 GB"，合计一个总数，让用户一眼看到收益。然后按风险分三组交付，**等授权再动手**：

1. **我可代做（零风险）**：缓存清理、限缩卷影副本、修时间同步、电源方案、关 GameDVR、自启与 PATH 精简、装待装更新。
2. **需要用户在 BIOS / 软件 UI 里做**：开 XMP、刷 BIOS、卸载或更换软件、分区调整。
3. **需要用户决策**：换杀软、加内存、UEFI+GPT 转换（MBR+Legacy 引导时 Secure Boot 不可用，转换有风险）。

破坏性动作（删缓存、删还原点、删回收站、删备份、卸载）一律先列清单再问，不因为"体检顺带优化"就默认执行。
