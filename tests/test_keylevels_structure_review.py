#!/usr/bin/env python3
"""结构复核 + 缓存品种隔离测试（2026-09-10 现场事故的回归钉子）。

三件现场事故：
  1. 关键位批准因「24h 内无人复核结构」到期 → 到价监控停摆 5 天
  2. tv_dmi_cache.json 被 XAU 采集整份覆盖 → BTC 消费者读到黄金价
  3. 结构复核若拿错品种的快照，会得出「漂移 1600%」的假结论
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import keylevels_structure_review as R
import tv_data_bridge as B

TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 9, 10, 22, 0, tzinfo=TZ)

# 真实配置（2026-09-10 实读 data/keylevels_config.json 的 8 个批准位）
LEVELS = [("价值区·VAH", 77310.0), ("价值区·DO", 77400.0), ("价值区·M-VWAP", 77520.0),
          ("价值区·nPOC", 77800.0), ("价值区·POC", 76600.0), ("价值区·VAL", 76450.0),
          ("结构·熊FVG/OB", 76938.0), ("磁吸HTF·高", 79196.0)]


def _config(levels=None):
    return {
        "symbols": {"BTCUSDT": {
            "levels": [{"name": n, "price": p} for n, p in (levels or LEVELS)]}},
        "auto_approval_policy": {"max_structure_age_hours": 24},
    }


def _snapshot(price=77113.5, symbol="BINANCE:BTCUSDT.P", **dw):
    ind = {"vah_price": 78518.0, "val_price": 77153.0, "poc_price": 77958.35,
           "npoc_price": 78884.65, "m_vwap_price": 78880.02, "do_price": 78264.0}
    ind.update(dw)
    return {"symbol": symbol, "last_price": price, "indicators": ind,
            "timestamp": NOW.isoformat()}


def test_real_levels_pass_the_review():
    """2026-09-10 现场：8 个批准位对上当时的 SVP 读数，应当 8/8 通过。"""
    r = R.review(config=_config(), snapshot=_snapshot(), now=NOW)
    assert r["ok"] is True
    assert (r["valid"], r["checked"]) == (8, 8)
    assert r["invalid"] == []


def test_symbol_mismatch_refuses_instead_of_reporting_1600pct_drift():
    """核心回归：缓存里是黄金（4374）时绝不能拿它核 BTC 关键位。"""
    gold = _snapshot(price=4374.615, symbol="OANDA:XAUUSD",
                     vah_price=4430.6, val_price=4375.2, poc_price=4414.0)
    r = R.review(config=_config(), snapshot=gold, now=NOW)
    assert r["ok"] is False
    assert r.get("symbol_mismatch") is True
    assert r["valid"] == 0
    assert "品种不匹配" in r["reasons"][0]


def test_drift_beyond_tolerance_refuses():
    """价值区真漂了就不该盖章 —— 安全闸必须保留。"""
    # VAH 漂到 20% 外
    r = R.review(config=_config(), snapshot=_snapshot(vah_price=77310.0 * 1.2), now=NOW)
    assert r["ok"] is False
    assert any("VAH" in i["name"] for i in r["invalid"])


def test_band_check_for_levels_without_svp_counterpart():
    """无同名 SVP 读数的位（结构·/磁吸HTF·）走价格带检查。"""
    far = _snapshot(price=50000.0)          # 现价离批准位 50% 外
    r = R.review(config=_config(), snapshot=far, now=NOW)
    assert r["ok"] is False
    names = {i["name"] for i in r["invalid"]}
    assert "结构·熊FVG/OB" in names and "磁吸HTF·高" in names


def test_min_valid_threshold_blocks_partial_review():
    """只有 5/8 成立时不得盖章（阈值 6）。"""
    cfg = _config()
    snap = _snapshot(vah_price=77310.0 * 1.5, val_price=76450.0 * 1.5,
                     poc_price=76600.0 * 1.5, do_price=77400.0 * 1.5)
    r = R.review(config=cfg, snapshot=snap, now=NOW)
    assert r["ok"] is False
    assert r["valid"] < R.MIN_VALID
    assert ("失效" in " ".join(r["reasons"])) or ("样本不足" in " ".join(r["reasons"]))


def test_missing_or_invalid_price_never_stamps():
    for snap in ({}, {"last_price": None}, {"last_price": 0}, {"last_price": "abc"}):
        assert R.review(config=_config(), snapshot=snap, now=NOW)["ok"] is False


def test_empty_config_never_stamps():
    assert R.review(config={"symbols": {}}, snapshot=_snapshot(), now=NOW)["ok"] is False


def test_apply_review_only_stamps_when_ok(tmp_path):
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(_config(), ensure_ascii=False), encoding="utf-8")

    bad = R.apply_review(config_path=cfg_path,
                         result={"ok": False, "reasons": ["x"]}, now=NOW)
    assert bad["stamped"] is False
    assert "不盖章" in bad["stamp_reason"]
    # 没通过就不许改文件
    assert "structure_reviewed_at" not in json.loads(
        cfg_path.read_text(encoding="utf-8")).get("auto_approval_policy", {})

    good = R.apply_review(config_path=cfg_path,
                          result={"ok": True, "valid": 8, "checked": 8,
                                  "method": "svp-drift+band"}, now=NOW, force=True)
    assert good["stamped"] is True
    pol = json.loads(cfg_path.read_text(encoding="utf-8"))["auto_approval_policy"]
    assert pol["structure_reviewed_at"] == NOW.isoformat()
    assert pol["structure_review_valid"] == 8


def test_apply_review_throttles_repeated_stamps(tmp_path):
    """看门狗每 2 分钟跑一次，不能每次都写盘。"""
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(_config(), ensure_ascii=False), encoding="utf-8")
    ok_result = {"ok": True, "valid": 8, "checked": 8, "method": "svp-drift+band"}
    R.apply_review(config_path=cfg_path, result=ok_result, now=NOW, force=True)
    again = R.apply_review(config_path=cfg_path, result=ok_result,
                           now=NOW + timedelta(minutes=5))
    assert again["stamped"] is False and "不足" in again["stamp_reason"]
    later = R.apply_review(config_path=cfg_path, result=ok_result,
                           now=NOW + timedelta(minutes=R.MIN_STAMP_INTERVAL_MIN + 1))
    assert later["stamped"] is True


# ── 缓存品种隔离 ─────────────────────────────────────────────────────

def test_symbol_cache_paths_are_per_symbol():
    assert B._symbol_cache_path("BINANCE:BTCUSDT.P").name == "tv_live_BTCUSDT.json"
    assert B._symbol_cache_path("OANDA:XAUUSD").name == "tv_live_XAUUSD.json"
    assert B._symbol_cache_path("BINANCE:ETHUSDT.P").name == "tv_live_ETHUSDT.json"


def test_save_cache_never_lets_other_symbols_clobber_the_btc_primary(monkeypatch, tmp_path):
    """现场事故：XAU 采集把黄金整份写进了 BTC 主缓存。"""
    written = {}

    def fake_write(path, data):
        written[str(path)] = data

    monkeypatch.setattr(B, "atomic_write_json", fake_write)
    monkeypatch.setattr(B, "CACHE", tmp_path / "tv_dmi_cache.json")

    B.save_cache({"symbol": "OANDA:XAUUSD", "last_price": 4374.615})
    assert not any("tv_dmi_cache" in p for p in written), "XAU 不许写主缓存"
    assert any(p.endswith("tv_live_XAUUSD.json") for p in written), "XAU 应写自己的文件"

    written.clear()
    B.save_cache({"symbol": "BINANCE:BTCUSDT.P", "last_price": 77113.5})
    assert any("tv_dmi_cache" in p for p in written), "BTC 仍写主缓存"


def test_save_cache_without_symbol_still_writes_primary(monkeypatch, tmp_path):
    written = {}
    monkeypatch.setattr(B, "atomic_write_json", lambda p, d: written.update({str(p): d}))
    monkeypatch.setattr(B, "CACHE", tmp_path / "tv_dmi_cache.json")
    B.save_cache({"grade": "?"})
    assert any("tv_dmi_cache" in p for p in written)

def test_apply_review_always_writes_report_even_when_skip_stamp(monkeypatch, tmp_path):
    """20260911 回归：报告文件必须在【跳过盖章】时也落盘。

    线上症状：structure_reviewed_at 是新的（复核天天在跑），
    但 keylevels_structure_review.json 停在 12.6 小时前 ——
    因为报告写盘只在 main() 里，而守护是直接调 apply_review() 的。
    该文件是数据新鲜度看门狗的监视对象 → 造成「有信号但是假信号」。
    """
    import importlib
    R = importlib.import_module("keylevels_structure_review")

    out = tmp_path / "review.json"
    monkeypatch.setattr(R, "REVIEW_OUT", out)

    # 复核通过、但距上次盖章不足 → stamped=False 的跳过分支
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    cfg = tmp_path / "cfg.json"
    cfg.write_text(
        '{"auto_approval_policy": {"structure_reviewed_at": "'
        + (now - timedelta(minutes=1)).isoformat() + '"}}',
        encoding="utf-8",
    )
    result = R.apply_review(config_path=cfg, result={"ok": True, "valid": 8, "checked": 8,
                                                    "method": "svp-drift+band", "price": 1.0},
                            now=now)
    assert result["stamped"] is False
    assert out.exists(), "跳过盖章路径也必须写报告（否则看门狗误报）"
    import json as _json
    assert _json.loads(out.read_text(encoding="utf-8"))["ok"] is True


def test_apply_review_writes_report_on_failure(monkeypatch, tmp_path):
    """复核未通过时更要留痕 —— 那是安全闸的现场证据。"""
    import importlib
    R = importlib.import_module("keylevels_structure_review")
    out = tmp_path / "review.json"
    monkeypatch.setattr(R, "REVIEW_OUT", out)
    cfg = tmp_path / "cfg.json"
    cfg.write_text('{"auto_approval_policy": {}}', encoding="utf-8")
    result = R.apply_review(config_path=cfg, result={"ok": False, "valid": 0, "checked": 8,
                                                    "method": "svp-drift+band"})
    assert result["stamped"] is False
    assert out.exists()
    import json as _json
    assert _json.loads(out.read_text(encoding="utf-8"))["stamped"] is False
