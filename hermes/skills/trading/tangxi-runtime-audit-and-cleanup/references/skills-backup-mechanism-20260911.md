# 技能目录备份（2026-09-11 建立 · 2026-09-26 补核验与归档处置）

## 问题

`~/AppData/Local/hermes/skills` 是**真实目录，不在仓库内**；而 `~/AppData/Local/hermes/scripts`
是指向 `D:/Hermes agent/scripts` 的**符号链接**（已受 git 管理）。
结果：脚本有备份，**技能没有** —— 而技能才是核心资产（授权铁律、字段契约、几十次踩坑的教训）。
换机或重装即失。

## 机制

```
~/AppData/Local/hermes/skills  ──(单向镜像)──▶  D:/Hermes agent/hermes/skills  ──git──▶  GitHub 远端
        ↑ 真实源（唯一可写）                        ↑ 只读快照 + _snapshot_manifest.json
```

执行者 `scripts/maintenance/skills_snapshot.py`，cron 任务 **技能快照备份**（`948f28dfaf76`，
每日 04:20，`no_agent` + `deliver=local`）。

### 必知的五条

1. **fail-closed**：源文件数骤降到上次 60% 以下、或少于 100 个 → **拒绝镜像并报错**，
   绝不擦掉仓库里的备份。盘未挂载/路径写错时不会造成灾难。
2. **只提交 `hermes/skills` 这一条路径**（`git commit -- hermes/skills`）：
   同时存在别的已暂存改动也不会被顺手带走。
3. **推送也有护栏**：只在**待推提交全部是技能快照**时才 `git push`。
   本地只要有一条在途的功能提交，就停下并报告「未推送：待推提交里有 N 条非快照提交」
   —— 自动推送等于替你发布，不允许。
4. **内容级密钥扫描**：命中 `sk-`/`ghp_`/`AIza`/Telegram bot token/私钥块/JWT 等特征的文件
   **拒绝入库**并写进清单 `blocked_secrets`。
   这条比 `.gitignore` 的 `*token*` 文件名规则强得多——后者会误伤文档
   （「CE10117 token 上限」「jbbtoken 渠道」「如何写密钥」）。
5. **静默=健康**：无漂移不输出。有漂移才打印 `+新增/~/变更/-删除`。

## 日常用法

```bash
python scripts/maintenance/skills_snapshot.py              # 镜像 + 提交 + 推送（默认）
python scripts/maintenance/skills_snapshot.py --status     # 0=同步 / 2=有漂移（可做巡检）
python scripts/maintenance/skills_snapshot.py --dry-run    # 只看差异
python scripts/maintenance/skills_snapshot.py --no-commit  # 只镜像
python scripts/maintenance/skills_snapshot.py --no-push    # 镜像+提交但不推
```

## 判定语义：全部相对 manifest，不是相对仓库内容

脚本的逐文件分支只有三条（`main()` 内）：

```python
if rel not in prev_files:                      added.append(rel)      # 新增
elif prev_files[rel] != sha[:16]:              changed.append(rel)    # 变更
elif not target.exists():                      added.append(rel)
# 都不命中 → 不复制（哪怕仓库里那份内容已经不同）
removed = [r for r in prev_files if r not in current and r not in blocked]
```

`prev_files` 来自 `DEST/_snapshot_manifest.json`，记的是**上次快照时的本机状态**。三个直接后果：

1. `+N ~N -N` 读作「相对上次快照」的增/改/删，**不是**「相对仓库当前内容」。
2. **仓库侧被直接改过的文件会被静默冻结**：本机 sha 没变 → 走不到复制分支 → 仓库的新版留着，
   本机继续跑旧版，而 `--status` 一句都不报。发现它只能用内容 diff（见下节）。
3. 备份洞（`--status` 报 2 但无人处理）= 无人看见的长期不一致，每次审计都会重新踩一遍。

## 内容漂移 vs 状态漂移：判据与方向

```bash
diff -rq --exclude=__pycache__ --exclude='*.pyc' \
  "$HOME/AppData/Local/hermes/skills" "D:/Hermes agent/hermes/skills" > "$LOCALAPPDATA/Temp/skills_diff.txt"
wc -l < "$LOCALAPPDATA/Temp/skills_diff.txt"
grep -c "differ" "$LOCALAPPDATA/Temp/skills_diff.txt"      # 真实内容漂移条数
```

| 形态 | 谁先发现 | 方向 |
|---|---|---|
| 本机改了文件 | `--status` / `--dry-run` 报 `~N` / `+N` | 本机 → 仓库（脚本自动） |
| **仓库侧被直接改过** | `--status` **不报**；只有 `diff -rq` 的 `differ` 行 | 仓库 → 本机（人工回灌） |
| 本机归档/删除 | `-N` | 见「归档孤儿搬运」；默认会把备份删薄 |

正常噪声，不算漂移：本机独有的顶层点文件（`.archive` / `.curator_*` / `.curator_backups` / `.hub` / `.usage.json`）
——脚本 `_skip()` 有意排除运行态；仓库独有的 `_snapshot_manifest.json` 是清单本身。

**报告「本机是旧版」前先确认运行链路用的是哪一份。** 实测：技能目录里的 `tv_keepalive.py` 是 7 月版，
而 cron `TV Desktop保活` 的 `script` 指向仓库根 `scripts/tv_keepalive.py`（新版，带 Store 双路径同步）——
副本旧 **≠** 功能旧。回灌副本是为了消除「备份与运行态的表述不一致」，不是修故障，交付时要这么讲。

## 远端备份是不是最新的？核验顺序（只读，30 秒）

```bash
git ls-remote origin refs/heads/main            # GitHub 侧真实 ref —— 权威
git rev-parse main                              # 本地 ref，逐位比对
git rev-list --count origin/main..main ; git rev-list --count main..origin/main   # 期望 0 / 0
git status --porcelain | wc -l                  # 0 = 工作区干净
curl -s "https://api.github.com/repos/<owner>/<repo>" > "$LOCALAPPDATA/Temp/gh_repo.json"
```

- `git fetch` 只让本地 refs 跟上，**不构成**「远端已更新」的证据；结论必须落在 `ls-remote` 或 API 上。
- `pushed_at` = 最新一次推送的 UTC 时刻，可与本地 HEAD 的提交时间直接对上；
  同一次响应还能答「这是不是我们自己的备份仓库」：`full_name` / `fork` / `private` / `default_branch`。
  **备份仓是 public 时要在报告里提醒用户**（策略代码、卡片模板、审计记录人人可读），并给出改 private 的选项。
- 落盘用 bash 重定向（`> "$LOCALAPPDATA/Temp/x.json"`）。本机 MSYS 路径转换关闭，
  `curl -o /c/Users/...` 不会写到那个路径，紧接着读文件就是 `FileNotFoundError`。

**三层诊断（用户说「看看是不是没更新」时按这个分）**：

| 层 | 现象 | 判据 |
|---|---|---|
| 推送链断 | 本地领先 N 条 | `rev-list --count origin/main..main > 0` 且 `ls-remote` 落后 |
| 本地在途未提交 | 工作区有改动 / 未跟踪 | `git status --porcelain` 非空 |
| **备份内容薄了**（最常见，也最容易被说成「没更新」） | 远端 = 本地，但备份里少了东西 | 技能归档 / 脚本批改 / 技能副本漂移 —— 见下节 |

## 归档孤儿搬运 recipe（curator 归档后保住备份）

curator 把技能移进 `~/AppData/Local/hermes/skills/.archive/` 时只动本机 ⇒ 快照下一轮会把这些文件
**从仓库镜像删掉并提交推送**。要保留就先搬到仓库内的归档目录，再让清单归位。

```python
import shutil, sys
from pathlib import Path
REPO = Path("D:/Hermes agent"); DEST = REPO / "hermes/skills"
ARCHIVE = REPO / "hermes/skills_archive_<YYYYMMDD>"
sys.path.insert(0, str(REPO / "scripts/maintenance"))
import skills_snapshot as ss

current = ss.collect(ss.SOURCE)                      # 本机现有（已 skip 顶层点目录 / __pycache__）
prev = ss.read_manifest().get("files", {})           # 上次快照时的本机状态
removed = sorted(r for r in prev if r not in current)  # 仓库镜像里的孤儿
assert len(removed) == <预期数量>, "数量对不上先停手，别误搬"

for rel in removed:
    src = DEST / rel
    if not src.exists():
        continue
    dst = ARCHIVE / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
```

搬完清掉因搬移而空的目录，然后按固定顺序收口：

```bash
git add -- hermes/skills hermes/skills_archive_<YYYYMMDD>
git commit -q -m "chore(backup): N 个已归档技能移入 skills_archive_<date>，避免快照删除" \
  -- hermes/skills hermes/skills_archive_<YYYYMMDD>
GIT_TERMINAL_PROMPT=0 git push origin main
python scripts/maintenance/skills_snapshot.py            # 让 manifest 归位
python scripts/maintenance/skills_snapshot.py --status   # 期望退出码 0
git ls-remote origin refs/heads/main ; git rev-parse main # 期望两条 SHA 相同
```

- 搬移被 git 识别为 rename（实测 `117 files changed, 0 insertions(+), 0 deletions(-)`），内容零改动。
- **顺序不能反**：手动提交必须先推，再跑快照脚本。脚本的推送护栏只在「待推提交全是快照提交」时推，
  混着手动提交会拒推（设计如此，别用 `--no-push` 绕）。
- 不归位 manifest 的后果：下一轮照旧报 `-N`（`DEST/rel` 已不存在所以无副作用，但清单与实际长期不一致）。
- 回灌个别文件到本机后同样要跑一次快照：新增文件会让 `--status` 报 `+1`，跑一次即回到 0。

## 首次推送

2026-09-11：`4883e1b..c89fc1e main -> main`，远端 `hermes/skills` 1913 文件已核实
（`git cat-file -e origin/main:hermes/skills/_snapshot_manifest.json`）。

## 别踩的坑

- **`.gitignore` 不支持行尾注释**：`!pattern  # 说明` 会把整行（含 `#说明`）当成模式，永不匹配。
  注释必须单独一行。
- **`git ls-files` 默认转义中文名**（`core.quotepath`），做集合比对时要加
  `git -c core.quotepath=false ls-files`，否则中文文件名会被误判成「未入库」。
- 备份洞检查：`git status --porcelain --ignored=matching -uall hermes/skills | grep '^!!'`
  —— 只应剩生成物（`outputs/`）与锁文件（`bun.lock`）。
- 运行时状态**不进备份**：`.hub`（39MB 索引缓存）、`.curator_ledger.jsonl`（9.6MB）、
  `.curator_backups/*.tar.gz`、`__pycache__`、`node_modules`。
- **curator 归档是「备份侧的删除事件」**，不是单纯的本地整理：`git status` 干净 + `--status` 报 `-N`
  同时成立，就是它的指纹。
- 判断孤儿数量时不要靠印象：用 `ss.read_manifest()` 与 `ss.collect()` 两个集合算差集，
  数量与用户预期不符就停下来问，别按「差不多是这些」动手。

## 首次快照

2026-09-11：1913 文件 / 15.0 MB（入库 1912 内容 + 1 清单）。
护栏回归：`tests/test_skills_snapshot_20260911.py`（13 项，含「源目录塌陷时拒绝擦备份」
与「无关改动不被顺手提交」）。

## 已验证（端到端）

2026-09-11 cron 实跑：技能改动 → 快照 → 提交 → **推送**，远端 `main` 与本地一致。
推送护栏也实测过：本地有待推的非快照提交时，脚本会报告
「未推送：待推提交里有 N 条非快照提交」而**不推**。

2026-09-26 归档处置实跑：117 个已归档技能搬入 `hermes/skills_archive_20260926/`
（manifest `file_count` 2022 → 1905 → 1906），`--status` 退出码回到 0，
`diff -rq` 内容漂移归零，远端 `main` = 本地 `main`。

## 自检三点（每次改完机制后跑）

```bash
python scripts/maintenance/skills_snapshot.py --status      # 0=同步 / 2=有漂移
git log --oneline -1                                        # 看有没有新快照提交
git log --oneline @{u}..HEAD                                # 空=已推送干净
```

`--status` 报 2 而 `--dry-run` 显示差异很小 → 正常；报 2 且差异巨大 → **先去查源目录**，
不要盲目跑镜像（虽然 fail-closed 会拦，但要知道它在拦什么）。
`--status` 退出码 0 之后仍值得跑一次 `diff -rq`：内容漂移是它唯一看不见的一类。
