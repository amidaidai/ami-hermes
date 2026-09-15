"""cron 失败聚合看门狗回归。

背景：Hermes 把 cron 非零退出写进 executions.db 的 cron_incidents，但没人读 →
2026-09-15 实测积压 3,806 条 state='detected'（一个作业 3,745 条），
而查 cron 健康时只看到 `[active]`，于是"连错上千次"被读成"0 error"。
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cron_incident_watchdog as cw  # noqa: E402


def _mkdb(tmp_path: Path, rows):
    db = tmp_path / "executions.db"
    con = sqlite3.connect(db)
    con.execute("create table cron_incidents (id text, job_id text, error_sig text, state text,"
                " failure_type text, first_seen_at text, last_seen_at text, acked_at text,"
                " closed_at text, error text, output_file text)")
    con.executemany("insert into cron_incidents values (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return db


def _patch(monkeypatch, tmp_path, rows, jobs=None):
    db = _mkdb(tmp_path, rows)
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps({"jobs": jobs or [{"id": "aaa", "name": "甲作业"}]}), encoding="utf-8")
    monkeypatch.setattr(cw, "DB", db)
    monkeypatch.setattr(cw, "JOBS", jobs_file)
    monkeypatch.setattr(cw, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(cw, "HEARTBEAT", tmp_path / "hb.json")


def test_recent_window_uses_latest_seen_and_latest_error(monkeypatch, tmp_path):
    """同一作业多条 incident：按 incident 各自的 last_seen 分桶（旧→积压，新→窗口内）。"""
    _patch(monkeypatch, tmp_path, [
        ("1", "aaa", "s1", "detected", "script", "2026-09-01T10:00:00", "2026-09-01T10:00:00",
         None, None, "旧错误", None),
        ("2", "aaa", "s2", "detected", "script", "2026-09-01T10:00:00", "2030-01-01T00:00:00",
         None, None, "新错误", None),
    ])
    got = cw.collect(24.0, include_backlog=True)
    assert got["healthy"] is False and got["recent_total"] == 1 and got["backlog_total"] == 1
    job = got["recent_jobs"][0]
    assert job["job"] == "甲作业" and job["count"] == 1
    assert job["last_seen"].startswith("2030-01-01") and job["error"] == "新错误"


def test_old_incidents_go_to_backlog_not_recent(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path, [
        ("1", "aaa", "s1", "detected", "script", "2026-01-01T00:00:00", "2026-01-01T00:00:00",
         None, None, "陈年老错", None),
    ])
    got = cw.collect(24.0, include_backlog=True)
    assert got["healthy"] is True and got["recent_total"] == 0
    assert got["backlog_total"] == 1 and got["total_unclosed"] == 1


def test_missing_db_is_not_silent(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cw, "DB", tmp_path / "nope.db")
    monkeypatch.setattr(cw, "HEARTBEAT", tmp_path / "hb.json")
    monkeypatch.setattr(sys, "argv", ["cron_incident_watchdog.py"])
    rc = cw.main()
    out = capsys.readouterr().out
    assert rc == 2 and "无法运行" in out, "读不到 DB 必须出声，不能看起来干净"
    hb = json.loads((tmp_path / "hb.json").read_text(encoding="utf-8"))
    assert hb["db_ok"] is False


def test_findings_still_exit_zero_to_avoid_self_noise(monkeypatch, tmp_path, capsys):
    """发现失败也必须 exit 0：否则 Hermes 把退出码 1 记成 incident，看门狗自己变成噪声源。"""
    _patch(monkeypatch, tmp_path, [
        ("1", "aaa", "s1", "detected", "script", "2026-09-15T10:00:00", "2030-01-01T00:00:00",
         None, None, "boom", None),
    ])
    monkeypatch.setattr(sys, "argv", ["cron_incident_watchdog.py", "--hours", "24"])
    rc = cw.main()
    out = capsys.readouterr().out
    assert rc == 0, "有发现时仍须 exit 0（可见性靠 stdout）"
    assert "cron 失败告警" in out


def test_closed_incidents_are_ignored(monkeypatch, tmp_path):
    """已关闭 = 已解决；不能因为“24h 前发生过”就继续报警（告警疲劳）。"""
    _patch(monkeypatch, tmp_path, [
        ("1", "aaa", "s1", "closed", "script", "2026-09-15T10:00:00", "2030-01-01T00:00:00",
         None, None, "已修好的错误", None),
    ])
    got = cw.collect(24.0, include_backlog=True)
    assert got["healthy"] is True and got["recent_total"] == 0 and got["total_unclosed"] == 0


def test_freshness_watchdog_covers_cron_failure_aggregator():
    """新看门狗必须进 freshness WATCH_FILES，否则它自己停摆没人知（同类静默失败）。"""
    import data_freshness_watchdog as dfw
    assert "cron_incident_watchdog_heartbeat.json" in dfw.WATCH_FILES
    assert "cron_incidents_report.json" in dfw.WATCH_FILES


def test_unknown_job_falls_back_to_id(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path, [
        ("1", "zzz", "s1", "detected", "script", "2026-09-15T10:00:00", "2030-01-01T00:00:00",
         None, None, "boom", None),
    ], jobs=[])
    got = cw.collect(24.0, include_backlog=False)
    assert got["recent_jobs"][0]["job"] == "zzz"
