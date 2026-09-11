# 技能目录备份（2026-09-11 建立）

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

## 首次快照

2026-09-11：1913 文件 / 15.0 MB（入库 1912 内容 + 1 清单）。
护栏回归：`tests/test_skills_snapshot_20260911.py`（13 项，含「源目录塌陷时拒绝擦备份」
与「无关改动不被顺手提交」）。
