# 文档/技能漂移清理与根目录收口（2026-09-11 实测）

触发：用户说「全面更新/优化系统」「把杂七杂八的都去掉」「我要最终完善的系统」，
或审计后发现脚本/字段换代、技能里还写着旧事实。

本轮任务规模：3 个提交、技能改动 30+ 处、根目录 55 → 21 个文件、
新增 3 个维护工具 + 2 个技能参考文件、LIVE 漂移 129 → 31。

---

## 1. 核心教训：写「已删除」前必须实测（本轮自己打脸）

**我做了什么错事**：给 6 个 SKILL.md + 1 个技能参考文件写了退役横幅，里面断言
`btc_keylevel_ws_guard` / `btc_keylevel_sentinel` / `btc_keylevel_rest_guard` /
`btc_price_arrival_sentinel` **「已不存在（文件均已被删除）」**。

**真相（实测）**：这 4 个文件**仍在 `scripts/`**，只是（a）不在 `cron/jobs.json`，
（b）不在任何运行中的进程里。真正移入 `scripts/_archive/` 的是
`btc_alert_watch_v3` / `btc_push_cron` / `btc_collector` / `btc_fast_daemon` / `btc_alert_watch`。

**为什么危害大**：技能是**未来会话会直接读取并照做**的东西。一个错的「已删除」断言，
会让下一次会话在需要时放弃一个其实存在的脚本；或者反过来，把「仍在但停用」
当成「可用的现行工具」。而且它必须再花一整轮提交去更正（本轮即如此）。

### 三态分类（每条都要有命令证据，不凭印象）

| 态 | 判据 | 表述 |
|---|---|---|
| ① 已归档 | `scripts/<n>.py` 不存在 + 在 `_archive`/`_disabled*` 里能找到 | 「已移入 `scripts/_archive/`」 |
| ② 仍在但停用 | 在 `scripts/` + 不在 `jobs.json` + 不在进程列表 | 「文件仍在，但不在 cron/进程中运行」 |
| ③ 现行 | 在 `scripts/` + 在 cron 或进程里 | 「现行链路」 |

```bash
# 一次出全三态
for f in btc_keylevel_ws_guard btc_keylevel_sentinel btc_keylevel_rest_guard \
         btc_price_arrival_sentinel btc_alert_watch_v3 btc_push_cron \
         btc_collector btc_fast_daemon; do
  [ -f "scripts/$f.py" ] && p=在根 || p="不在根"
  find scripts/_archive scripts/_disabled_20260829 -name "$f.py" 2>/dev/null | grep -q . && a=已归档 || a=-
  grep -q "$f.py" "$LOCALAPPDATA/hermes/cron/jobs.json" && c=cron引用 || c=-
  echo "$f: $p | $a | $c"
done
```

### 子代理结论同样要复核

本轮的子代理在一条审计项里给出「当前已知存在：… `btc_keylevel_ws_guard.py` …」的建议，
把已归档的写成了现存（它把技能里的旧文本当成了事实）。

**规则：子代理的事实性结论当「未验证输入」。** 它擅长的是「帮你定位、列线索、
大范围 grep」；「文件在哪、存不存在、哪一行」这种判定必须自己用
`ls`/`find`/`git grep`/`sha256sum` 复核后再落地。**不要把它给的路径与结论直接写进技能。**

---

## 2. 根目录（及其它待清目录）分类算法

工具：`scripts/maintenance/root_clutter_audit.py`。每行输出
`文件 | 大小 | git跟踪状态 | 仓内引用数 | 技能引用数 | 建议动作`。

### 必须先做的两步（否则会误删）

1. **读 `.gitignore`**。命中即可能是有意为之，保留。
   本轮实证：`Run` / `restart_gateway.cmd|ps1` / `restart_gw.bat|ps1|vbs` 全部被
   `.gitignore` 归入「本机工具/临时启动器」（用户右键管理员运行以重启 gateway）——
   它们是**有意**留在根目录的，不是垃圾。
2. **查技能是否点名**。本轮实证：技能明确写过「`annualof.txt` / `FinComYY.txt` 是
   `cot_collector.py` 产生的公开 CFTC 持仓数据，属项目真实资产，审计见到 `M annualof.txt`
   不要当脏文件删」。只看文件名根本不像资产，差点删掉。

### 建议动作的判据

| 动作 | 判据 |
|---|---|
| delete | 文件名匹配 `*.latest.txt` / `*.final*.txt` / `*.diag.*` / `*.wrapper.*` / `*.out` / `*.err` / `tmp_*` / `nul` —— 纯运行日志，随时可重跑，零引用 |
| archive | `.pine` / `.txt` / `.json` / `.png` / `.html` 且零引用 —— 单次产物，移入 `outputs/archive_YYYYMMDD/`，写一份 README 说明每份是什么 |
| keep | `.gitignore` 命中 / 技能点名 / 有引用 |

**引用计数要排除 `.gitignore` 本身** —— 它会把被忽略的文件名列一遍，造成「有引用」的假象。

### 归档必须附一份 README

`outputs/archive_YYYYMMDD/README.md` 要写清：①每份是什么、原名是什么；
②**为什么挪走**；③**哪些保留在根目录且不能动、为什么**。
第三项最重要 —— 它防止下一次清理把同一批文件再拿出来审一遍。

---

## 3. 漂移扫描器设计（`scripts/maintenance/skill_drift_scan.py`）

### 为什么要分级

技能库里存在大量**带日期的历史文档**（`*-2026-06-xx.md`、`*-2026-07-02.md`），
它们描述的是「当时的生产状态」。这些文件里的旧字段名/旧行数**不是漂移，是记录**。
不加以区分，扫描器会给出几百条噪声，真问题反而看不见（本轮未分级时 584 条，分级后 LIVE 129）。

### 三级 + 三类抑制

| 级别 | 判据 |
|---|---|
| `LIVE` | `SKILL.md` 正文；或 `references/` 下**文头 14 行内日期 ≥ 定版日期** 的文档 |
| `HISTORICAL` | 文件名或目录名含日期；或 `references/` 下文头日期 **< 定版日期** |

抑制规则（缺一条就会被自己的正确文档淹没）：

1. **行内标记**：出现「已废止 / 已作废 / 已移入 / 已归档 / 退役 / 示意名 / 历史记录 /
   不可读 / 勿再当现行」→ 这一段正是在做正确的事，跳过。
   （本轮加这条之前，我自己写的横幅和索引贡献了 31 条假报告。）
2. **文件级横幅**：文件头 60 行内出现对照表路径（如 `dead-script-index.md`）
   → 该文件的**脚本名**类不再逐行报；**字段/行名类仍要报**（横幅没覆盖它们）。
3. **指针文件**：对照表与指针文件本身整体跳过（它们当然会列出全部废止名）。

### 扫描模式的设计教训

- **行数类模式必须要求「数字 + 行/lines」**。第一版写成 `\b(2024|2025|469) *行?`，
  把年份 `2024` / `2025` 全当成行数 → 几百条误报。收紧为
  `\b(3446|3163|469)\s*(行|lines?)\b` 后才可用。
- **不要自己拆括号/引号**。正确姿势是按 `display=` 参数分类（
  `display.data_window` = DW 字段、`display.price_scale` = 价格轴、其余 = 纯视觉），
  配一个**尊重引号与嵌套括号的参数切分器**。这样不需要维护白名单：
  「纯视觉 plot」自动不被当成缺失。

### 对照表必须是唯一一份

`references/dead-script-index.md`（放 `realtime-trading-pipeline` 下）结构：

0. 三条结论先说（现行链路是什么、唯一监控源是什么、三态不能混）
1. 已移入 `_archive/` 的表
2. 仍在 `scripts/` 但停用的表
3. 待确认归档的
4. 失效的字段/行名（另一类废止，别与脚本混）
5. 权威索引（指向仓内契约与文档）

**技能横幅与其它参考只指向它，不各自再抄一份。**

---

## 4. 模块遮蔽排查（清根目录时发现的真 bug）

| | 根目录副本 | `scripts/` 真模块 |
|---|---|---|
| `fetch_tv_mcp.py` | 113 行，**0 个 `get_*` 函数** | 251 行，含 `get_ohlcv` / `get_study_values` / `get_pine_tables` / `get_pine_boxes` |
| 谁在用 | 无 | 技能写 `from fetch_tv_mcp import ...` |

在仓库根跑 `python -c` 时 CWD 进 `sys.path` 且优先 → 命中旧副本 → ImportError。

```bash
# 全量同名检查
for f in *.py; do [ -f "scripts/$f" ] && echo "$f  root=$(sha256sum "$f"|cut -c1-12) scripts=$(sha256sum "scripts/$f"|cut -c1-12)"; done
# 确认真模块身份（不能只看行数）
grep -o "^async def get_[a-z_]*" scripts/fetch_tv_mcp.py
```

处置：归档根副本到 `outputs/archive_YYYYMMDD/`，在 README 写明「它曾遮蔽真模块」。
**判据：同名不同内容 = 定时炸弹；按「谁真正被 import」保留。**

---

## 5. 目录选择：别把维护工具放进被忽略的目录

三个体检工具最初放 `tools/`，随后发现 **`tools/` 在 `.gitignore` 里**（本机工具）
→ 不被提交 → 重装即丢。改放 `scripts/maintenance/`（`scripts/` 已被跟踪，
且它同时是 `~/AppData/Local/hermes/scripts` 的软链目标）。

```bash
git check-ignore -v scripts/maintenance/x.py    # 空输出 = 会被跟踪 ✓
git check-ignore -v tools/x.py                  # 有输出 = 不会提交 ✗
```

**顺带发现的结构缺口（要告知用户，不要擅自改）**：
`~/AppData/Local/hermes/scripts` → `D:/Hermes agent/scripts`（软链，**已**备份）；
但 `~/AppData/Local/hermes/skills` 是**真实目录、不在仓库内** → 技能改动**没有版本备份**。
处置选项：①建软链（最干净但 skill_manage 写真实目录，风险高）
②加单向快照备份脚本（安全，推荐）③只写进「已知边界」。
这是结构决策、动的是用户的 Hermes 配置目录，**列选项给用户拍板，不擅自做**。

---

## 6. 交付时要说清的三件事

本轮报告里必须点明的（用户关心「能不能直接信」）：

1. **我上一条自己说错的地方**（把「仍在但停用」写成「已删除」），以及已如何更正。
   自己打脸要主动说，别等用户发现。
2. **已归档 / 未归档的边界** —— 例如 16 个「僵尸候选」实测后发现
   `triple_confirm`（11 个技能点名）、`render_analysis_card`（5 个）、`keylevel_guard`（21 个）
   都是**有文档价值的工具、不是死码**，所以**没有删**。
3. **剩下的漂移为什么不改** —— 31 处全在带日期的历史 references 里，
   改写等于伪造历史。把「我不改的理由」写清，比默默留一堆不动强。
