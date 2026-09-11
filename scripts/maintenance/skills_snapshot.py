#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能目录单向快照 → 仓库（唯一备份路径）。

为什么需要
----------
`~/AppData/Local/hermes/skills` 是**真实目录、不在仓库内**；而 `~/AppData/Local/hermes/scripts`
是符号链接指向 `D:/Hermes agent/scripts`（已受 git 管理）。
结果：技能——系统的核心资产（授权铁律、字段契约、血泪教训）——**换机或重装就没了**。

本脚本把技能单向镜像到 `D:/Hermes agent/hermes/skills`，让它进 git。

设计要点
--------
* **单向**：只从 hermes 目录读到仓库，永不反向写。绝不"修复"源目录。
* **fail-closed**：源文件数骤降（< 上次清单的 60%，或 < 100 个）就**拒绝镜像并报错**，
  防止盘未挂载/路径写错时把仓库里的备份擦掉。
* **静默=健康**：无事发生不输出（适配 no_agent cron）；只在「有变更」或「报错」时说话。
* 运行态物不了：顶层点文件/点目录（`.hub` 39MB 索引缓存、`.curator_ledger.jsonl` 9.6MB、
  `.curator_backups/*.tar.gz`、`.usage.json` 等）是缓存与账本，不进备份。
* 排除 `__pycache__` / `node_modules` / `*.pyc` / `.DS_Store`。
* 清单 `hermes/skills/_snapshot_manifest.json` 记录每文件 sha256 前缀 + 计数，
  既是「快照可信」的证据，也是下次 fail-closed 判断的基线。

用法:
    python scripts/maintenance/skills_snapshot.py               # 镜像 + 提交 + 推送（静默成功）
    python scripts/maintenance/skills_snapshot.py --no-commit    # 只镜像不提交
    python scripts/maintenance/skills_snapshot.py --dry-run      # 只看差异，不写
    python scripts/maintenance/skills_snapshot.py --status       # 只报漂移，不写（0=同步/2=有漂移）

默认**提交**是刻意的：cron 无法给脚本传参数，而「只写盘不提交」的备份在若干周后
就会与仓库历史脱节。提交范围严格限定 `hermes/skills`，不推送。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SOURCE = Path.home() / "AppData/Local/hermes/skills"
REPO = Path("D:/Hermes agent")
DEST = REPO / "hermes/skills"
MANIFEST_NAME = "_snapshot_manifest.json"

SKIP_DIRS = {"__pycache__", "node_modules", ".git"}
SKIP_NAMES = {".DS_Store"}
SKIP_SUFFIX = {".pyc", ".pyo"}
MAX_FILE_BYTES = 2 * 1024 * 1024      # 单文件上限：超出的只登记不复制
MIN_FILES = 100                        # 源文件数下限（绝对）
MIN_RATIO = 0.60                       # 相对上次清单的最低比例
TZ = timezone(timedelta(hours=8))

# ── 内容级密钥扫描（比 .gitignore 的文件名规则强得多）─────────────────
# .gitignore 用 `*token*` / `*secret*` 挡密钥，会误伤文档（如「CE10117 token 上限」）；
# 而真正该做的是看**内容**。命中即拒绝入库并大声报告 —— 备份宁可少一个文件，
# 也不能把凭据写进 git 历史。
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI/兼容 sk-", re.compile(r"sk-[A-Za-z0-9_\-]{24,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{20,}")),
    ("Telegram bot token", re.compile(r"\b[0-9]{8,10}:[A-Za-z0-9_\-]{32,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("私钥块", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{10,}")),
]


def scan_secret(path: Path) -> str:
    """返回命中的密钥类型名；干净返回空串。只在文本文件里找。"""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return name
    return ""


def _skip(rel: Path) -> bool:
    if any(part in SKIP_DIRS for part in rel.parts):
        return True
    if rel.name in SKIP_NAMES or rel.suffix in SKIP_SUFFIX:
        return True
    # 顶层点文件/点目录 = 运行态（缓存/账本/状态），不进备份
    return bool(rel.parts) and rel.parts[0].startswith(".")


def collect(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if _skip(rel):
            continue
        found[rel.as_posix()] = path
    return found


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest() -> dict:
    path = DEST / MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _git_commit() -> tuple[bool, str]:
    """把 hermes/skills 的变更提交进仓库（**只提交该路径**，不碰其它在途改动，不推送）。

    `git commit -- <path>` 只提交该路径，因此同时存在别的已暂存改动时也不会被顺手带走。
    """
    import subprocess
    rel = "hermes/skills"
    try:
        add = subprocess.run(["git", "add", "--", rel], cwd=REPO, capture_output=True, text=True)
        if add.returncode != 0:
            return False, f"git add 失败: {add.stderr.strip()[:200]}"
        diff = subprocess.run(["git", "diff", "--cached", "--quiet", "--", rel], cwd=REPO)
        if diff.returncode == 0:
            return False, ""          # 无变更，不产生空提交
        msg = (f"chore(skills): 技能快照 {datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}\n\n"
               f"由 scripts/maintenance/skills_snapshot.py 自动生成（cron）。\n"
               f"只提交 hermes/skills 路径，不代表其它改动。")
        commit = subprocess.run(["git", "commit", "-q", "-m", msg, "--", rel],
                                cwd=REPO, capture_output=True, text=True)
        if commit.returncode != 0:
            return False, f"git commit 失败: {(commit.stderr or commit.stdout).strip()[:200]}"
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                              capture_output=True, text=True)
        return True, head.stdout.strip()
    except OSError as exc:
        return False, f"git 调用异常: {exc}"


SNAPSHOT_SUBJECT_PREFIX = "chore(skills): 技能快照"


def _git_push() -> tuple[bool, str]:
    """推送 —— 但**只在待推提交全部是技能快照时**才推。

    本地随时可能有你在途的功能提交；自动推送等于替你发布，必须停下来报告而不是推上去。
    这条护栏让「备份每天上云」与「不擅自发布工作成果」同时成立。
    """
    import subprocess
    try:
        upstream = subprocess.run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                                  cwd=REPO, capture_output=True, text=True)
        if upstream.returncode != 0:
            # 「没有 upstream」是配置状态，不是事件：静默跳过，否则每天刷一行噪声
            return False, ""
        up = upstream.stdout.strip()
        ahead = subprocess.run(["git", "log", "--format=%s", f"{up}..HEAD"],
                               cwd=REPO, capture_output=True, text=True).stdout.splitlines()
        ahead = [s for s in ahead if s.strip()]
        if not ahead:
            return False, ""                        # 没有待推内容
        foreign = [s for s in ahead if not s.startswith(SNAPSHOT_SUBJECT_PREFIX)]
        if foreign:
            return False, (f"待推提交里有 {len(foreign)} 条非快照提交（如「{foreign[0][:40]}」）——"
                           f"为免替你发布，本次不自动推送；需要时手动 git push")
        branch = up.split("/", 1)[1] if "/" in up else "main"
        proc = subprocess.run(["git", "push", "origin", branch], cwd=REPO,
                              capture_output=True, text=True, timeout=280,
                              env={**__import__("os").environ, "GIT_TERMINAL_PROMPT": "0"})
        if proc.returncode != 0:
            return False, f"git push 失败：{(proc.stderr or proc.stdout).strip()[:200]}"
        return True, f"已推送 {len(ahead)} 条快照提交 → {up}"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"git push 异常：{exc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只显示差异，不写盘")
    ap.add_argument("--status", action="store_true", help="只报漂移（有漂移则退出码 2）")
    ap.add_argument("--no-push", action="store_true",
                    help="不推送（默认推送，但只在待推提交全是技能快照时才推）")
    ap.add_argument("--no-commit", action="store_true",
                    help="只写快照，不提交（默认为提交：cron 无法传参数，默认才是有用的备份）")
    args = ap.parse_args()

    if not SOURCE.is_dir():
        print(f"✗ 源目录不存在：{SOURCE}")
        return 1

    files = collect(SOURCE)
    previous = read_manifest()
    prev_files: dict[str, str] = previous.get("files", {})
    prev_count = len(prev_files) or 0

    # ── fail-closed：源目录看起来"塌了"就拒绝镜像，别把备份擦了 ──
    if files and prev_count:
        ratio = len(files) / prev_count
        if len(files) < MIN_FILES or ratio < MIN_RATIO:
            print(f"✗ 拒绝镜像：源文件数 {len(files)} 对比上次 {prev_count}（比例 {ratio:.0%}）——"
                  f"疑似源目录异常/盘未挂载。备份未被修改。")
            return 1
    if not files:
        print("✗ 拒绝镜像：源目录读到 0 个文件")
        return 1

    oversized = {rel: p.stat().st_size for rel, p in files.items() if p.stat().st_size > MAX_FILE_BYTES}
    copyable = {rel: p for rel, p in files.items() if rel not in oversized}

    # ── 逐文件比对 ──
    current: dict[str, str] = {}
    added, changed = [], []
    blocked: dict[str, str] = {}
    for rel, path in sorted(copyable.items()):
        hit = scan_secret(path)
        if hit:
            blocked[rel] = hit
            continue
        try:
            sha = digest(path)
        except OSError as exc:
            print(f"✗ 读取失败 {rel}: {exc}")
            return 1
        current[rel] = sha[:16]
        target = DEST / rel
        if rel not in prev_files:
            added.append(rel)
        elif prev_files[rel] != sha[:16]:
            changed.append(rel)
        elif not target.exists():
            added.append(rel)
    removed = [r for r in prev_files if r not in current and r not in blocked]

    drift = bool(added or changed or removed) or bool(oversized) != bool(previous.get("oversized"))
    if args.status:
        if not drift:
            return 0
        print(f"技能快照漂移：+{len(added)} ~{len(changed)} -{len(removed)}")
        return 2
    if args.dry_run:
        print(f"将镜像 {len(copyable)} 个文件（源 {len(files)}）")
        print(f"  新增 {len(added)}：{added[:8]}")
        print(f"  变更 {len(changed)}：{changed[:8]}")
        print(f"  删除 {len(removed)}：{removed[:8]}")
        print(f"  超大跳过 {len(oversized)}：{list(oversized)[:5]}")
        print(f"  密钥拦截 {len(blocked)}：{list(blocked)[:5]}")
        return 0

    # ── 执行镜像（先写新文件，再删多余，最后写清单）──
    written = 0
    for rel in sorted(current):                      # 只写通过扫描的文件
        path = copyable[rel]
        target = DEST / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or prev_files.get(rel) != current[rel]:
            shutil.copy2(path, target)
            written += 1
    # 删除：源已删的 + 被密钥扫描拦下的（后者可能在上一次运行里已进过备份）
    for rel in sorted(set(removed) | set(blocked)):
        stale = DEST / rel
        if stale.exists():
            stale.unlink()
    # 清掉空目录（镜像语义：仓库侧不应留下源已删的目录）
    for directory in sorted((d for d in DEST.rglob("*") if d.is_dir()), key=lambda d: -len(d.parts)):
        try:
            if not any(directory.iterdir()):
                directory.rmdir()
        except OSError:
            pass

    manifest = {
        "generated_at": datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": SOURCE.as_posix(),
        "file_count": len(current),
        "total_bytes": sum((DEST / rel).stat().st_size for rel in current if (DEST / rel).exists()),
        "oversized": {rel: size for rel, size in sorted(oversized.items())},
        "blocked_secrets": blocked,   # 内容命中密钥特征 → 拒绝入库（绝不写进 git 历史）
        "files": current,
    }
    MANIFEST_NAME_PATH = DEST / MANIFEST_NAME
    print_manifest = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True)
    # 清单只在内容变化时重写（避免每天产生无意义 diff）
    old_text = MANIFEST_NAME_PATH.read_text(encoding="utf-8") if MANIFEST_NAME_PATH.exists() else ""
    new_text = print_manifest + "\n"
    if old_text != new_text:
        MANIFEST_NAME_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_NAME_PATH.write_text(new_text, encoding="utf-8")

    if drift or written:
        print(f"技能快照已更新 → {DEST.as_posix()}")
        print(f"  +{len(added)} 新增 / ~{len(changed)} 变更 / -{len(removed)} 删除（写入 {written} 个文件）")
        print(f"  共 {len(current)} 个文件 · {manifest['total_bytes'] / 1048576:.1f} MB"
              + (f" · 超大跳过 {len(oversized)}" if oversized else ""))
        if blocked:
            print(f"  ⛔ 拒绝入库 {len(blocked)} 个（内容含密钥特征）：")
            for rel, kind in sorted(blocked.items()):
                print(f"      {rel}  ← {kind}")
        if not args.no_commit:
            ok, detail = _git_commit()
            if ok:
                print(f"  已提交 hermes/skills（{detail}）")
            elif detail:
                print(f"  ⚠ 提交未完成：{detail}")
        else:
            print("  记得在仓库提交：git add hermes/skills && git commit")
    # 推送刻意放在 drift 判断之外：即便本轮无漂移，也要补推上一次没推成功的快照提交。
    if not args.no_commit and not args.no_push:
        pushed, push_detail = _git_push()
        if pushed:
            print(f"  {push_detail}")
        elif push_detail:
            print(f"  ⚠ 未推送：{push_detail}")
    # 无漂移 = 静默（no_agent cron 约定）
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
