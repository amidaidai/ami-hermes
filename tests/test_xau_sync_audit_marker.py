# -*- coding: utf-8 -*-
"""XAU 同步轮次取证标记（2026-09-14 自检 · P1「零输出静默轮次」定位用）。

背景：cron `XAU TV现场同步` 出现 `silent (empty output)` + ok、但已发布 pair 不前进
的轮次（16:31/17:01 实测），排除法三步后仍需现场样本。本标记把每轮同步的
「进入 / 让路 / CDP / 发布 / 错误」追加到 `data/xau_tv_sync_runs.jsonl`，
用于区分：脚本没启动（无 enter）· 中途被杀（有 enter 无终态）· 终态与输出不一致。

铁律：取证不能变成新的故障面——写标记失败必须静默吞掉，绝不影响同步主流程。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import xau_tv_sync as xau  # noqa: E402


def test_audit_marker_appends_jsonl(tmp_path, monkeypatch):
    marker = tmp_path / "runs.jsonl"
    monkeypatch.setattr(xau, "AUDIT_MARKER_FILE", marker)
    xau._audit_marker("enter", argv=[])
    xau._audit_marker("published")
    rows = [json.loads(l) for l in marker.read_text(encoding="utf-8").strip().splitlines()]
    assert [r["reason"] for r in rows] == ["enter", "published"]
    assert all(r["pid"] and r["ts"] for r in rows)


def test_audit_marker_never_raises(tmp_path, monkeypatch):
    # 目录不存在 / 路径非法 → 静默吞掉，不冒泡
    monkeypatch.setattr(xau, "AUDIT_MARKER_FILE", tmp_path / "nonexistent-dir" / "x.jsonl")
    xau._audit_marker("enter")  # 不抛即通过


def test_key_paths_are_instrumented():
    """五类终态都在源码里挂了标记（防回退：缺一个下一轮就又要靠猜）。"""
    src = (ROOT / "scripts" / "xau_tv_sync.py").read_text(encoding="utf-8")
    for reason in ("enter", "defer:cache_usable", "defer:cache_stale",
                   "cdp_closed", "cdp_probe_error", "published", "error"):
        assert f'_audit_marker("{reason}"' in src, f"缺少标记 {reason}"
