"""技能快照的护栏回归 —— 备份工具最怕「把备份擦掉」，这里锁死行为。

用临时目录做沙盒，不碰真实的 ~/AppData/Local/hermes/skills 与仓库。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "maintenance" / "skills_snapshot.py"


def _load(tmp_root: Path, tmp_dest: Path):
    """加载脚本并把 SOURCE/DEST 指向沙盒。"""
    spec = importlib.util.spec_from_file_location("skills_snapshot_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.SOURCE = tmp_root
    mod.DEST = tmp_dest
    return mod


def _make_skill(root: Path, name: str, body: str = "x") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _run(mod, *args) -> int:
    argv = ["skills_snapshot.py", *args]
    old = sys.argv
    sys.argv = argv
    try:
        return mod.main()
    finally:
        sys.argv = old


def _seed(tmp_path: Path, count: int = 120):
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    for i in range(count):
        _make_skill(source, f"skill_{i}/SKILL.md", f"body {i}")
    return source, dest


def test_first_run_mirrors_and_writes_manifest(tmp_path):
    source, dest = _seed(tmp_path)
    mod = _load(source, dest)
    assert _run(mod) == 0
    assert (dest / "skill_0" / "SKILL.md").read_text(encoding="utf-8") == "body 0"
    manifest = json.loads((dest / "_snapshot_manifest.json").read_text(encoding="utf-8"))
    assert manifest["file_count"] == 120
    assert len(manifest["files"]) == 120


def test_second_run_is_silent_and_writes_nothing(tmp_path, capsys):
    source, dest = _seed(tmp_path)
    mod = _load(source, dest)
    _run(mod)
    stamp = (dest / "skill_0" / "SKILL.md").stat().st_mtime_ns
    capsys.readouterr()
    assert _run(mod) == 0
    assert capsys.readouterr().out == ""          # 静默=健康（no_agent cron 约定）
    assert (dest / "skill_0" / "SKILL.md").stat().st_mtime_ns == stamp
    assert _run(mod, "--status") == 0             # 无漂移


def test_changed_and_added_and_removed_files_are_mirrored(tmp_path, capsys):
    source, dest = _seed(tmp_path)
    mod = _load(source, dest)
    _run(mod)
    # 改一个、加一个、删一个
    _make_skill(source, "skill_0/SKILL.md", "changed")
    _make_skill(source, "brand_new/references/x.md", "new")
    (source / "skill_7").mkdir(exist_ok=True)
    (source / "skill_7" / "SKILL.md").unlink()
    assert _run(mod, "--status") == 2              # 有漂移
    capsys.readouterr()
    assert _run(mod) == 0
    out = capsys.readouterr().out
    assert "+1" in out and "~1" in out and "-1" in out
    assert (dest / "skill_0" / "SKILL.md").read_text(encoding="utf-8") == "changed"
    assert (dest / "brand_new" / "references" / "x.md").exists()
    assert not (dest / "skill_7").exists()         # 镜像语义：源删了，仓库侧也删


def test_runtime_dot_state_is_never_backed_up(tmp_path):
    source, dest = _seed(tmp_path)
    # 顶层点目录/点文件 = 运行态（.hub 39MB 索引、curator 账本…），必须排除
    (source / ".hub").mkdir()
    (source / ".hub" / "index-cache.json").write_text("{}", encoding="utf-8")
    (source / ".curator_ledger.jsonl").write_text("{}", encoding="utf-8")
    _make_skill(source, "skill_0/__pycache__/x.pyc", "junk")
    _make_skill(source, "skill_0/node_modules/dep/index.js", "junk")
    mod = _load(source, dest)
    assert _run(mod) == 0
    assert not (dest / ".hub").exists()
    assert not (dest / ".curator_ledger.jsonl").exists()
    assert not (dest / "skill_0" / "__pycache__").exists()
    assert not (dest / "skill_0" / "node_modules").exists()


def test_refuses_to_wipe_backup_when_source_collapses(tmp_path, capsys):
    """护栏：源文件数骤降（盘未挂载/路径写错）→ 拒绝镜像，备份保持原样。"""
    source, dest = _seed(tmp_path, count=120)
    mod = _load(source, dest)
    assert _run(mod) == 0
    before = json.loads((dest / "_snapshot_manifest.json").read_text(encoding="utf-8"))
    assert before["file_count"] == 120
    # 源目录"塌"到只剩 5 个文件
    for i in range(5, 120):
        (source / f"skill_{i}" / "SKILL.md").unlink()
    capsys.readouterr()
    assert _run(mod) == 1                          # 拒绝，非 0
    out = capsys.readouterr().out
    assert "拒绝镜像" in out
    after = json.loads((dest / "_snapshot_manifest.json").read_text(encoding="utf-8"))
    assert after["file_count"] == 120              # 备份没被动
    assert (dest / "skill_50" / "SKILL.md").exists()


def test_refuses_on_empty_source(tmp_path, capsys):
    source = tmp_path / "empty"
    source.mkdir()
    dest = tmp_path / "dest"
    mod = _load(source, dest)
    assert _run(mod) == 1
    assert "拒绝镜像" in capsys.readouterr().out


def test_oversized_file_is_registered_but_not_copied(tmp_path):
    source, dest = _seed(tmp_path)
    big = source / "skill_0" / "huge.bin"
    big.write_bytes(b"0" * (2 * 1024 * 1024 + 1))
    mod = _load(source, dest)
    assert _run(mod) == 0
    manifest = json.loads((dest / "_snapshot_manifest.json").read_text(encoding="utf-8"))
    assert "skill_0/huge.bin" in manifest["oversized"]
    assert "skill_0/huge.bin" not in manifest["files"]
    assert not (dest / "skill_0" / "huge.bin").exists()


def test_default_run_builds_a_scoped_commit(tmp_path):
    """默认提交且只提交 hermes/skills 路径；无变更时不产生空提交。"""
    import subprocess
    repo = tmp_path / "repo"
    (repo / "hermes" / "skills").mkdir(parents=True)
    (repo / "other.txt").write_text("unrelated", encoding="utf-8")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    import os
    run_env = {**os.environ, **env}
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=run_env)
    # 仓库级身份：脚本内部调 git 时不传 env，必须靠本地 config 才认得出作者
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True, env=run_env)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True, env=run_env)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=run_env)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True, env=run_env)

    source = tmp_path / "source"
    for i in range(120):
        _make_skill(source, f"skill_{i}/SKILL.md", f"body {i}")
    # 故意把无关改动留在暂存区：--commit 不得把它带走
    (repo / "other.txt").write_text("staged change", encoding="utf-8")
    subprocess.run(["git", "add", "--", "other.txt"], cwd=repo, check=True, env=run_env)

    mod = _load(source, repo / "hermes" / "skills")
    mod.REPO = repo
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["skills_snapshot.py"]   # 默认即提交
    try:
        assert mod.main() == 0
    finally:
        _sys.argv = old_argv

    files = subprocess.run(["git", "show", "--stat", "--name-only", "--format=", "HEAD"],
                           cwd=repo, capture_output=True, text=True).stdout
    assert "hermes/skills/skill_0/SKILL.md" in files
    assert "other.txt" not in files, "无关改动被顺手提交了"
    dirty = subprocess.run(["git", "status", "--short", "--", "other.txt"],
                          cwd=repo, capture_output=True, text=True).stdout
    assert dirty.strip().startswith("M"), "other.txt 应仍停在暂存/未提交状态"


def test_dry_run_does_not_touch_dest(tmp_path):
    source, dest = _seed(tmp_path)
    mod = _load(source, dest)
    assert _run(mod, "--dry-run") == 0
    assert not (dest / "_snapshot_manifest.json").exists()
    assert not (dest / "skill_0").exists()


def test_secret_content_is_blocked_from_the_backup(tmp_path, capsys):
    """内容含密钥特征 → 拒绝入库并在清单里登记（绝不能写进 git 历史）。"""
    source, dest = _seed(tmp_path)
    leak = source / "skill_0" / "notes.md"
    faketg = "123456789:" + "A" * 35
    leak.write_text(f"api_key = sk-{'Z' * 40}\nbot = {faketg}\n", encoding="utf-8")
    mod = _load(source, dest)
    assert _run(mod) == 0
    manifest = json.loads((dest / "_snapshot_manifest.json").read_text(encoding="utf-8"))
    assert "skill_0/notes.md" in manifest["blocked_secrets"], "含密钥的文件必须被拦"
    assert "skill_0/notes.md" not in manifest["files"]
    assert not (dest / "skill_0" / "notes.md").exists()
    assert "拒绝入库" in capsys.readouterr().out, "必须大声报告，不能静默跳过"


def test_clean_file_after_redaction_is_copied_again(tmp_path):
    """脱敏后（密钥被打断）应恢复正常入库 —— 否则备份会永久留洞。"""
    source, dest = _seed(tmp_path)
    leak = source / "skill_0" / "notes.md"
    leak.write_text(f"key = sk-{'Z' * 40}", encoding="utf-8")
    mod = _load(source, dest)
    _run(mod)
    assert not (dest / "skill_0" / "notes.md").exists()
    leak.write_text("key = sk-1f3…<已脱敏·原长67位>…05fe", encoding="utf-8")   # 脱敏
    _run(mod)
    manifest = json.loads((dest / "_snapshot_manifest.json").read_text(encoding="utf-8"))
    assert "skill_0/notes.md" in manifest["files"]
    assert manifest["blocked_secrets"] == {}


def test_secret_patterns_do_not_flag_placeholder_text(tmp_path):
    """占位符/缩写不能被误判（否则真文档进不了备份）。"""
    source, dest = _seed(tmp_path)
    (source / "skill_0" / "doc.md").write_text(
        "Authorization: \"Bearer sk-xxx...xxxx\"\n"
        "key was 67 chars: `sk-1f3...05fe`\n"
        "echo -n \"sk-full...here...\" | base64\n"
        "data: {accessToken: \"***\"}\n",
        encoding="utf-8")
    mod = _load(source, dest)
    assert _run(mod) == 0
    manifest = json.loads((dest / "_snapshot_manifest.json").read_text(encoding="utf-8"))
    assert manifest["blocked_secrets"] == {}
    assert (dest / "skill_0" / "doc.md").exists()


def test_no_commit_flag_writes_snapshot_without_committing(tmp_path):
    source, dest = _seed(tmp_path)
    mod = _load(source, dest)
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["skills_snapshot.py", "--no-commit"]
    try:
        assert mod.main() == 0
    finally:
        _sys.argv = old_argv
    assert (dest / "_snapshot_manifest.json").exists()
    assert not (dest / ".git").exists()
