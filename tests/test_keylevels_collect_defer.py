"""keylevels_collect 的「没刷新成功」归类回归（2026-09-16）。

实测 2026-09-16 16:07：采集子进程 rc=0 却没形成新发布（stdout 停在
`timeframe:240:start`），`_run_cli` 按「未发布新快照」重试一次后返回 1，
于是整轮被记成 cron 失败 —— 而当时现网候选池只有 17.5 分龄（30 分合同内）。

新规则：rc=0 且**现网候选池仍在合同内** → 返回 DEFER_EXIT_CODE(7)（让路），
由上层用合同口径决定让路/失败；现网已超合同仍不发布 → 1（真失败，必须喊）。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import keylevels_collect as kc  # noqa: E402


class _Proc:
    def __init__(self, rc):
        self.returncode = rc
        self.stdout = ""
        self.stderr = ""


def _payload(ts, complete=True, n_tf=5, candidates=True):
    return {
        "ts": ts,
        "timeframes_complete": complete,
        "timeframes": {tf: {"price": 1.0} for tf in kc.TFS[:n_tf]},
        "candidates": ([{"name": "x", "price": 1.0}] if candidates else []),
    }


@pytest.fixture
def env(monkeypatch, tmp_path):
    out = tmp_path / "keylevels_candidates.json"
    out.write_text(json.dumps(_payload("2026-09-16T15:49:00")), encoding="utf-8")
    monkeypatch.setattr(kc, "OUT", out)
    monkeypatch.setattr(kc, "DIAGNOSTIC_FILE", tmp_path / "diag.json")
    return out


def _fake_child(monkeypatch, rc, *, rewrite=None):
    """把子进程替换成返回固定 rc 的假进程；可选在「跑完」后改写 OUT。"""
    class _SP:
        TimeoutExpired = subprocess.TimeoutExpired

        @staticmethod
        def run(*args, **kwargs):
            if rewrite is not None:
                kc.OUT.write_text(json.dumps(rewrite), encoding="utf-8")
            return _Proc(rc)

    monkeypatch.setattr(kc, "subprocess", _SP)


def test_early_exit_within_contract_defers_not_fails(monkeypatch, env, capsys):
    """核心用例：rc=0 无新发布 + 现网仍在合同内 → 让路(7)，不是 1。"""
    _fake_child(monkeypatch, 0)
    monkeypatch.setattr(kc, "_published_within_contract", lambda *a, **k: True)
    rc = kc._run_cli()
    err = capsys.readouterr().err
    assert rc == kc.DEFER_EXIT_CODE, "合同内的未完成刷新必须按让路交回上层"
    assert "按让路处理" in err and "早退路径未定位" in err


def test_early_exit_over_contract_still_fails(monkeypatch, env, capsys):
    """现网已超合同仍不发布 → 必须失败（不能让过期数据被读成新鲜）。"""
    _fake_child(monkeypatch, 0)
    monkeypatch.setattr(kc, "_published_within_contract", lambda *a, **k: False)
    rc = kc._run_cli()
    err = capsys.readouterr().err
    assert rc == 1
    assert "未发布新快照" in err


def test_new_valid_publish_returns_zero(monkeypatch, env):
    _fake_child(monkeypatch, 0, rewrite=_payload("2026-09-16T16:07:00"))
    monkeypatch.setattr(kc, "_published_within_contract", lambda *a, **k: True)
    assert kc._run_cli() == 0


def test_child_defer_exit_code_passes_through(monkeypatch, env, capsys):
    _fake_child(monkeypatch, kc.DEFER_EXIT_CODE)
    assert kc._run_cli() == 0
    assert "让路" in capsys.readouterr().err


def test_child_hard_failure_still_returns_one(monkeypatch, env, capsys):
    _fake_child(monkeypatch, 1)
    monkeypatch.setattr(kc, "_published_within_contract", lambda *a, **k: True)
    assert kc._run_cli() == 1, "子进程真报错（rc!=0 且非让路码）不能被洗成让路"
    assert "未发布新快照" in capsys.readouterr().err


def test_incomplete_publish_is_not_accepted(monkeypatch, env):
    """层数不全/无候选池 → 即使 ts 变了也不算成功（保留旧池、让上层判）。"""
    _fake_child(monkeypatch, 0, rewrite=_payload("2026-09-16T16:07:00", n_tf=3))
    monkeypatch.setattr(kc, "_published_within_contract", lambda *a, **k: True)
    assert kc._run_cli() == kc.DEFER_EXIT_CODE


def test_published_within_contract_reads_five_tf_contract(monkeypatch, env):
    """判据必须真的走 30 分合同口径（不是 12 分触发线）。"""
    seen = {}
    import tv_five_tf_contract as c

    def _fake(symbol, *, data_dir=None, max_age_minutes=30.0, now=None):
        seen["symbol"], seen["age"] = symbol, max_age_minutes
        return {"usable": True, "age_seconds": 1053.0}

    monkeypatch.setattr(c, "load_five_tf_snapshot", _fake)
    assert kc._published_within_contract() is True
    assert seen["symbol"] == "BTCUSDT" and seen["age"] == kc.CONTRACT_MAX_AGE_MIN


def test_published_within_contract_fails_closed_on_error(monkeypatch, env):
    import tv_five_tf_contract as c

    def _boom(*a, **k):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(c, "load_five_tf_snapshot", _boom)
    assert kc._published_within_contract() is False
