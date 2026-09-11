# 仓库卫生与受护栏自动化（2026-09-11）

本轮做「技能目录备份 + 自动推送 + 根目录收口」时攒下的可复用手法。
每条都有实测来源，不是想当然。

---

## 1. 受护栏的自动推送（核心模式）

**问题**：备份/快照类任务若只写进本机 git，跨盘但不跨机器；要真防换机/重装必须推远端。
但自动 push 一旦无条件执行，就会**把用户其它在途提交一起发布**。

**闸门设计**：待推提交必须**全部**是本任务自己产生的（按 subject 前缀识别），否则整体不推。

```python
SNAPSHOT_SUBJECT_PREFIX = "chore(skills): 技能快照"

def _git_push():
    repo = str(REPO)
    up = subprocess.run(["git", "rev-parse", "--abbrev-ref", "@{u}"],
                        cwd=repo, capture_output=True, text=True)
    if up.returncode != 0:
        return False, ""                      # ← 无 upstream = 配置状态，静默
    upstream = up.stdout.strip()
    if upstream in ("", "HEAD"):
        return False, ""
    ahead = subprocess.run(["git", "log", "--format=%s", f"{upstream}..HEAD"],
                           cwd=repo, capture_output=True, text=True).stdout.splitlines()
    ahead = [s.strip() for s in ahead if s.strip()]
    if not ahead:
        return False, ""                      # 没得推 = 正常，静默
    foreign = [s for s in ahead if not s.startswith(SNAPSHOT_SUBJECT_PREFIX)]
    if foreign:
        return False, (f"待推提交里有 {len(foreign)} 条非快照提交"
                       f"（如「{foreign[0]}」）——为免替你发布，本次不自动推送")
    push = subprocess.run(["git", "push", "origin", "HEAD"], cwd=repo,
                          capture_output=True, text=True,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if push.returncode != 0:
        return False, (push.stderr or push.stdout).strip()[:300]
    return True, f"{len(ahead)} 条快照提交 → {upstream}"
```

**调用点的位置比函数本身更容易写错**（本轮踩了）：

```python
# ❌ 放在「本次有漂移才执行」的分支里 → 上次推送失败后永远不再补推
if drift or written:
    ...
    _git_push()

# ✅ 放在漂移判断之外 → 无漂移也检查一次待推队列，能自愈
if drift or written:
    ...
if not args.no_push:
    _git_push()
```

**「无 upstream / 没得推」必须静默**：no_agent cron 的约定是**健康即零输出**。
把配置状态当事件报 → 每天一行噪声 → 用户开始忽略这个 cron 的全部输出。
真正该出声的只有两类：**待推里有非本任务提交**、**push 失败**。

---

## 2. fail-closed 的快照阈值

单向镜像（备份）最贵的错误不是「没备份」，是「**把备份擦成空**」。所以阈值要 fail-closed：

```python
MAX_FILE_BYTES = 2 * 1024 * 1024      # 大文件单独跳过并登记
MIN_FILES     = 100                   # 源文件数下限
MIN_RATIO     = 0.60                  # 相对上次的塌陷比

if n_files < MIN_FILES or n_files < prev_count * MIN_RATIO:
    raise SystemExit(f"源文件数异常塌陷（{n_files} < {min(MIN_FILES, int(prev_count*MIN_RATIO))}）"
                     f"—— 拒绝镜像，保留现有备份")
```

同理，**镜像必须单向**：源是唯一可写方，快照只读。反向同步（快照→源）会让一次误删
把备份里的旧内容「复活」回生产目录。

---

## 3. 密钥防护：文件名级弱、内容级强

`.gitignore` 里用 `*token*` / `*secret*` 挡密钥，实际上：

- **挡不住的**：真密钥写在名叫 `notes.md` 的文件里
- **误伤的**：`CE10117-token-上限.md`、`jbbtoken-渠道.md` 这类**谈论** token 文档

本轮实测：21 个被文件名规则挡掉的文件**全部不含真实密钥**（只是名字里有 token/secret），
同时内容级扫描**真的抓到**一个 67 位 `sk-` 明文 key。

**结论：文件名级屏蔽降级为辅助，主防线是内容级扫描 + 拒绝入库 + 登记。**
扫描器与镜像写盘的正确接法：

```python
clean, blocked = [], []
for f in files:
    if hits := SECRET_PATTERNS.findall(read(f)):
        blocked.append((f, hits)); continue
    clean.append(f)          # ← 只有通过扫描的才进写入列表
for f in clean:
    copy(f)
```

**本轮真 bug**：最初写入循环遍历的是**未过滤**的集合 → 被密钥拦下的文件**仍然被写进备份**。
测试抓出来的。**判据：拦截逻辑必须作用在「将要执行的集合」上，不能只作用在「报告」上。**

命中后不要试图「脱敏了事」：脱敏不能撤销它曾经明文存在的事实 —— 必须提示用户
**去服务商后台作废重建**。

---

## 4. argparse 重复选项 → 静态守卫 + 冒烟测试

**症状**：`argparse.ArgumentError: argument --no-push: conflicting option string`
整个脚本在解析参数阶段就崩，cron 报 `script failed`，业务代码一行没跑。

**根因**：脚本化批改时同一行被插入了两次（同轮其他替换静默失败，掩盖了它）。

**守卫（加进该脚本的测试里）**：

```python
def test_argparse_options_are_not_duplicated():
    src = (REPO / "scripts/maintenance/skills_snapshot.py").read_text(encoding="utf-8")
    opts = re.findall(r'add_argument\(\s*"(--[a-z0-9-]+)"', src)
    dupes = {o for o in opts if opts.count(o) > 1}
    assert not dupes, f"选项被重复定义: {sorted(dupes)}"

def test_help_smoke():
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr      # 解析器能起来
```

`--help` 冒烟测试的价值在于：它把「脚本能启动」变成一条 0.2 秒的回归，
挡住「参数层就崩」这一类在 cron 里才暴露的失败。

---

## 5. 脚本化批改：自证 + 回读

见 SKILL.md 同名小节。要点复述：

- 成功打印必须由**自己算出的断言**驱动，不能由「代码跑到了」驱动
- 写完**回读落盘内容**（`assert new in p.read_text()`），内存里的 `t` 不算证据
- 批量替换前后各 `assert t.count(old) == 1`；锚点不唯一就先看清楚再动手

**为什么不直接手改**：本轮同一批替换里有 3 处静默 no-op，全部靠断言+回读才发现。

---

## 6. 测试沙箱：隔离全部指向真实世界的常量

被测脚本的模块级常量（`SOURCE` / `DEST` / `REPO` / `CFG` / `JOBS` …）必须**逐个**换成沙盒路径，
并**自证隔离**：

```python
mod.SOURCE, mod.DEST = tmp_src, tmp_dst
mod.REPO = tmp_dst.parent
assert mod.REPO != REAL_REPO, "测试绝不能指向真仓库"
```

**本轮实测**：只有前两行 → 内部 git 操作落在真仓库 → 测试读到**真实的待推提交**、
打印真实警告 → 「无漂移应静默」用例假失败。表面上像被测脚本的 bug，
实际是夹具没隔离干净。

---

## 7. 结构性防呆：把静默失败改成显式标记

同轮回溯出三个同型缺陷 —— 未知输入**不报错，只是安静地退化**：

| 位置 | 退化形态 | 用户看到 | 修法 |
|---|---|---|---|
| `route_pipeline` 未知品种 | 返回**空管线** | 「没反应」 | 补 `index`/`option` 类别识别 + `assert steps, "路由为空"` |
| `analysis_mode_spec` 未知档位 | **静默回落** quick | 档位写错却照跑 | 返回 `mode_error` + `requested_mode` |
| `_TVCStub` 契约缺失 | 出**空卡** | 卡是空的，不知为何 | 置 `DEGRADED=True`，卡面必须写出「契约缺失」 |

**判据：任何「查不到 → 用默认值」的分支，都要问一句 —— 用户能从输出里看出这是降级态吗？**
看不出就是在埋静默失败。修法是**显式标记 + 断言**（`DEGRADED` / `mode_error` / `assert`），
不是把默认值调得更合理一点。

配套：**降级的默认方向要选“更保守”**。未知档位按 `full` 跑（少跑步骤比多跑危险），
未知品种按 crypto 处理（AggVol 否决权最严）。

---

## 8. 交付前的终检清单

本轮收尾用的那一组命令，可作为「仓库级改动交付前」的固定终检：

```bash
git rev-parse --short HEAD                      # 本机 HEAD
git ls-remote origin main                        # 远端是否同一提交
git log --oneline @{u}..HEAD | wc -l             # 待推数量
git status --porcelain | wc -l                   # 未提交数量（应为 0）
python -m pytest tests/ -q                       # 全量测试
python scripts/maintenance/skills_snapshot.py --status   # 0=同步
```

**每条都要读数字，不能读「看起来没问题」。** 待推 0 + 工作树 0 + 测试全绿 + 快照同步，
才是「可以交付」。
