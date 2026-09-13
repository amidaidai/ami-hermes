"""X 情绪上下文刷新：客观部分真刷新，取不到如实标 stale，不洗新旧值。"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("x_sentiment_refresh", ROOT / "scripts/x_sentiment_refresh.py")
assert spec is not None and spec.loader is not None
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(X, "CONTEXT_PATH", tmp_path / "ctx.json")


def _stub(monkeypatch, *, fg=True, gm=True, tr=True):
    monkeypatch.setattr(X, "fetch_fear_greed",
                        lambda: {"value": 62, "classification": "Greed", "ts": "2026-09-13T12:00:00+08:00"} if fg else _boom())
    monkeypatch.setattr(X, "fetch_global_market",
                        lambda: {"btc_dominance": 56.1, "ts": "2026-09-13T12:00:00+08:00"} if gm else _boom())
    monkeypatch.setattr(X, "fetch_trending",
                        lambda limit=5: [{"symbol": "BTC", "name": "Bitcoin", "rank": 1}] if tr else _boom())


def _boom():
    raise OSError("offline")


def test_writes_fresh_context_with_x_note(monkeypatch, tmp_path):
    _stub(monkeypatch)
    out = tmp_path / "ctx.json"
    code = X.main(["--output", str(out), "--x-note", "X 上情绪谨慎·等待 FOMC"])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["fear_greed"]["value"] == 62
    assert data["global_market"]["btc_dominance"] == 56.1
    assert data["x_note"]["text"] == "X 上情绪谨慎·等待 FOMC"
    assert data["x_note"]["source"] == "x_search"
    assert data["ts"]
    assert data["refresh_status"]["fear_greed"] == "live"
    assert data["producer"] == "x_sentiment_refresh.py"


def test_partial_failure_keeps_previous_and_marks_stale(monkeypatch, tmp_path):
    out = tmp_path / "ctx.json"
    _stub(monkeypatch)
    assert X.main(["--output", str(out)]) == 0
    old = json.loads(out.read_text(encoding="utf-8"))

    _stub(monkeypatch, fg=False)          # 恐贪这轮取不到
    assert X.main(["--output", str(out)]) == 0
    new = json.loads(out.read_text(encoding="utf-8"))
    assert new["refresh_status"]["fear_greed"].startswith("stale_cache")
    # 不能把旧值洗成新值：恐贪没有自己的新 ts，其余部分才是本轮
    assert new["fear_greed"] == old["fear_greed"]
    assert new["refresh_status"]["global_market"] == "live"


def test_x_note_is_preserved_when_not_supplied(monkeypatch, tmp_path):
    out = tmp_path / "ctx.json"
    _stub(monkeypatch)
    X.main(["--output", str(out), "--x-note", "first"])
    X.main(["--output", str(out)])         # 不带新叙述
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["x_note"]["text"] == "first"
    assert data["refresh_status"]["x_note"] == "kept_previous"


def test_all_sources_failing_does_not_claim_live(monkeypatch, tmp_path, capsys):
    out = tmp_path / "ctx.json"
    _stub(monkeypatch, fg=False, gm=False, tr=False)
    assert X.main(["--output", str(out)]) == 2
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "fear_greed" not in data and "global_market" not in data
    assert all(not str(v).startswith("live") for v in data["refresh_status"].values())
    assert "stale_cache" in capsys.readouterr().out
