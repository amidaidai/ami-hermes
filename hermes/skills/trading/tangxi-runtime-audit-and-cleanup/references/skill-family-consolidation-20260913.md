# 技能家族重叠整理：定主从 + 同族导航注记（2026-09-13 落地）

> 适用：技能库出现**同名族、触发词互相抢**的成员（如 6 个审计技能、5 个 TG 投递技能）。
> 目标是把「该加载哪个」变成技能自己写着的答案，而不是靠每次猜测。
> 纪律：**只加注记，不改语义、不删内容**。

## 0. 先查来源 —— 改错对象会被 `skills update` 覆盖

**这是本流程唯一会「白干」的坑。** 同一目录下的技能归属不同，改动命运完全不同：

| 归属 | 判据 | 能不能改 |
|---|---|---|
| hub 安装 | 名字出现在 `.hub/index-cache/hermes-index.json` | ❌ 会被 `hermes skills update` 覆盖 |
| 随包附带 | 出现在 `.bundled_manifest` | ❌ 不动 |
| 本机自建 | 两个索引里都没有 | ✅ 可以改 |

```bash
cd "$HOME/AppData/Local/hermes/skills"
for n in <候选技能名...>; do
  b=$(grep -c "$n" .bundled_manifest 2>/dev/null || echo 0)
  h=$(grep -c "$n" .hub/index-cache/hermes-index.json 2>/dev/null || echo 0)
  echo "$n | bundled=$b | hub=$h"
done
# 两个都是 0 → 本机自建，可改；任一非 0 → 跳过，在交付里说明原因
```

⚠️ 不要用 frontmatter 里的 `metadata.hermes.created_by` 单独判 —— 本机自建技能经常
没有这个字段（实测 3 个自建 PPT 技能全缺），会被误判成 hub。**以 .hub/.bundled 索引为准。**

对**不能改**的成员，处理方式是在可改成员的注记里把它们的角色一并写出来
（画全家族地图），这样即使不改它们，加载到任一可改成员也能看到全局。

## 1. 定主从：每组一个「入口」

入口的选择标准（按优先级）：

1. **最常被触发的那条路径**（对应用户的最高频需求）；
2. 覆盖面最广、先做总口径的那个；
3. 与用户档案里写明的工作流一致的那个。

本轮定法（示例，可直接复用为同类家族的设计模板）：

| 家族 | 入口 | 其余分工 |
|---|---|---|
| 审计（6） | `tangxi-analysis-audit-checklist` | 全栈深挖 / 运行态清理 / 大版本后收口 / 方法论文档 / 修复验收收口 |
| TG 投递（5） | `tangxi-tg-delivery-format` | 报告质量 / topic 架构 / RichMarkdown 通道 / 投递可靠性 |
| TV 证据（5） | `tradingview-consumer-evidence` | 图表状态一致性 / packed 原始 plot / 原始 study / Pine 源码审计 |
| 卡片（4） | `tradingview-indicator-analysis` | 低周期执行卡 / 格式细则 / 生成脚本 |
| 演示 PPT（8） | `gov-presentation-creation` | 按产出物分 4 条子路线（公文 / 通用 PPTX / 网页 HTML / 图像优先） |

## 2. 注记的形状

插在 frontmatter 之后、正文之前，4-6 行，信息密度优先：

```markdown
> **同族导航** — <家族名> N 个技能各司其职，别加载错（同族入口：`<entry>`）
> · **本技能 `<me>`** = <这个技能在这个家族里管哪一段>
> · 同族其余：`<a>`（角色）、`<b>`（角色）…
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。
```

要点：

- **每个成员都写一句「本技能 = 什么」** —— 只写「入口是谁」不够，成员自己也要能自述职责。
- 成员数 > 6 时按**子路线**分组列（PPT 那组就是如此），否则一行太长没法扫读。
- 最后一行固定带上「改动要同步触发词」——这名注记的长期价值就在这句。

## 3. 落地机制：用脚本插，不要手打 20 次 patch

```python
MARK = "> **同族导航**"
DRY  = "--apply" not in sys.argv           # 默认 dry-run，先看改动清单再落盘

def insert(text, block):
    """插到 frontmatter 结束后；无 frontmatter 则插到最前。"""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            at = nl + 1 if nl != -1 else len(text)
            return text[:at] + "\n" + block + text[at:]
    return block + text

for name in members:
    p = index[name]
    t = p.read_text(encoding="utf-8", errors="replace")
    if MARK in t:            # 幂等：可反复跑
        skipped.append(name); continue
    if not DRY:
        p.write_text(insert(t, block(name)), encoding="utf-8")
```

配套三条：

1. **幂等**（`MARK in t` 即跳过）—— 这个脚本会被跑第二次。
2. **默认 dry-run**，先打印「改动 N / 跳过 N / 社区不动 N / 缺失 N」再 `--apply`。
3. **落盘前先备份整个技能目录**（`cp -r skills <temp>/skills_backup_before_nav`）。

## 4. 验收（必须逐条过，20 个里坏一个就是坏）

```python
end = t.find("\n---", 3)
data = yaml.safe_load(t[3:end])            # ① frontmatter 仍可解析
assert data["name"] == name                # ② name 与目录名一致（skill 加载依赖它）
assert data.get("description")             # ③ 描述没被吃掉
body = t[t.find("\n", end + 1) + 1:]
assert "同族导航" in body[:400]             # ④ 注记确实紧跟 frontmatter，没插进正文中段
```

再加两道项目级守卫：

```bash
python scripts/maintenance/skill_drift_scan.py        # LIVE 漂移应为 0
python scripts/maintenance/skills_snapshot.py --no-push   # 镜像进仓库（技能目录本身不在仓库内！）
```

## 5. 为什么不能省掉「镜像」这一步

技能真实目录在 `~/AppData/Local/hermes/skills`，**不在仓库内**——改完不跑
`skills_snapshot.py` 就等于没备份（详见 `references/skills-backup-mechanism-20260911.md`）。
落盘后必须镜像一次并本地提交（`git commit -- hermes/skills`），否则重装即丢。

## 6. 交付口径

汇报时对每个家族给出「入口 + 成员分工」一张表，并**显式说出哪几个没改、为什么**
（hub 技能会被 update 覆盖）——不要只报「改了 20 个」。
