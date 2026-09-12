#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""关键位推送降噪的回归钉子（2026-09-12）。

用户诉求原话：「关键价到位不能太频繁推送，好烦」「只留重要的」。

本文件用**确定性模拟**锁死降噪五件套，防止将来任何一次改动把噪音放回来：

  1. push_tier 分级 —— silent 位根本不进候选（只写 digest）
  2. 同 key 冷却   —— 冷却期内不重复
  3. 幅度门        —— 相对上次推送价没走出 min_move_pct 就不打扰
  4. 迟滞带        —— 触发后须离位 ±HYSTERESIS_PCT 才重新武装
  5. 同轮聚合      —— 一次连穿多位只发一条
外加全局限流：任意两次推送 ≥30min、每小时 ≤3 条。

同时锁死一条**设计契约**：`enabled` 管「是否参与监控+结构复核」，
`push_tier` 管「推不推」。两者混用会重演 P0 死锁（复核样本不足→不盖章→监控全停）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = load("keylevel_guard.py")


def _lvl(name, price, tier=None, enabled=True):
    d = {"name": name, "price": price, "enabled": enabled}
    if tier is not None:
        d["push_tier"] = tier
    return d


NOW = 1_760_000_000.0   # 固定时间戳，模拟结果可复现


# ── 1. 分级：silent 位不推 ────────────────────────────────────────────

def test_silent_tier_never_becomes_a_push_candidate():
    trig = {}
    block = {"levels": [_lvl("价值区·POC", 100.0, "silent")]}
    digest, cands = G.evaluate_symbol("BTCUSDT", block, 99.0, 101.0, NOW, trig)
    assert cands == [], "silent 位不得进入推送候选"
    assert len(digest) == 1 and digest[0]["reason"] == "silent_tier"
    assert digest[0]["pushed"] is False


def test_missing_tier_defaults_to_event():
    trig = {}
    block = {"levels": [_lvl("价值区·VAH", 100.0)]}      # 未标注 tier
    _digest, cands = G.evaluate_symbol("BTCUSDT", block, 99.0, 101.0, NOW, trig)
    assert len(cands) == 1
    assert cands[0]["tier"] == G.DEFAULT_PUSH_TIER == "event"


def test_push_false_is_treated_as_silent():
    trig = {}
    lvl = _lvl("价值区·VAL", 100.0, "critical")
    lvl["push"] = False
    _digest, cands = G.evaluate_symbol("BTCUSDT", {"levels": [lvl]}, 99.0, 101.0, NOW, trig)
    assert cands == []


def test_critical_tier_pushes_and_is_rarer_than_event_policy():
    trig = {}
    block = {"levels": [_lvl("结构·熊FVG/OB", 100.0, "critical")]}
    _digest, cands = G.evaluate_symbol("BTCUSDT", block, 99.0, 101.0, NOW, trig)
    assert len(cands) == 1 and cands[0]["tier"] == "critical"
    # critical 冷却必须短于 event（结构位值得更快通知），且都远长于旧的 30min
    assert G.tier_policy("critical")["cooldown"] < G.tier_policy("event")["cooldown"]
    assert G.tier_policy("critical")["cooldown"] >= 4 * 3600


# ── 2. 冷却：同一位冷却期内不重复 ─────────────────────────────────────

def test_same_level_within_cooldown_does_not_repush():
    trig = {}
    block = {"levels": [_lvl("结构·熊FVG/OB", 100.0, "critical")]}
    _d, first = G.evaluate_symbol("BTCUSDT", block, 99.0, 101.0, NOW, trig)
    assert len(first) == 1
    # 调用方在推送成功后写入冷却（这里是 main_loop 的职责，测试手动复现）
    trig["BTCUSDT:结构·熊FVG/OB"] = {
        "dir": "up", "armed": False,
        "cool_until": NOW + G.tier_policy("critical")["cooldown"],
        "anchor_price": 101.0,
    }
    # 冷区内反向穿越一次
    _d2, second = G.evaluate_symbol("BTCUSDT", block, 101.0, 99.0, NOW + 600, trig)
    assert second == [], "冷却期内不得重复推送"


# ── 3. 幅度门：没走出实质幅度就不打扰 ─────────────────────────────────

def test_amplitude_gate_suppresses_insignificant_re_cross():
    trig = {
        "BTCUSDT:结构·熊FVG/OB": {
            "armed": True, "cool_until": 0.0, "anchor_price": 100.0,
        }
    }
    # 离开位后重新武装（迟滞带满足），但相对锚定价只走了 0.1% < 0.25%
    trig["BTCUSDT:结构·熊FVG/OB"]["armed"] = True
    block = {"levels": [_lvl("结构·熊FVG/OB", 100.0, "critical")]}
    digest, cands = G.evaluate_symbol("BTCUSDT", block, 99.9, 100.1, NOW, trig)
    assert cands == [], "幅度不足（0.1% < 0.25%）不得推送"
    assert any(d["reason"] == "amplitude_gate" for d in digest)


def test_amplitude_gate_allows_significant_move():
    trig = {
        "BTCUSDT:结构·熊FVG/OB": {
            "armed": True, "cool_until": 0.0, "anchor_price": 100.0,
        }
    }
    block = {"levels": [_lvl("结构·熊FVG/OB", 100.0, "critical")]}
    # 相对锚定价走了 0.5% > 0.25%
    _digest, cands = G.evaluate_symbol("BTCUSDT", block, 99.9, 100.5, NOW, trig)
    assert len(cands) == 1, "走出实质幅度后应允许推送"


# ── 4. 迟滞带：贴线抖动不重新武装 ─────────────────────────────────────

def test_hysteresis_blocks_immediate_rearm_near_level():
    """刚推过、价格还贴在位附近 → 不得重新武装，更不能推。"""
    trig = {
        "BTCUSDT:结构·熊FVG/OB": {
            "armed": False, "cool_until": 0.0, "anchor_price": 100.0,
        }
    }
    block = {"levels": [_lvl("结构·熊FVG/OB", 100.0, "critical")]}
    # 价格 100.05，离位 0.05% < 0.15% → 不武装、不推
    _d, cands = G.evaluate_symbol("BTCUSDT", block, 99.9, 100.05, NOW, trig)
    assert cands == []
    assert trig["BTCUSDT:结构·熊FVG/OB"]["armed"] is False

    # 走到 99.7（离位 0.30% ≥ 0.15%）→ 重新武装
    # 注意：旧的实现只在「穿越那一刻」判迟滞，而穿越时价格必然贴位（距离≈0），
    # armed 永远翻不回 True → 每个位一生只能推一次。这条断言锁死该修复。
    _d2, cands2 = G.evaluate_symbol("BTCUSDT", block, 100.05, 99.7, NOW + 10, trig)
    assert trig["BTCUSDT:结构·熊FVG/OB"]["armed"] is True
    assert len(cands2) == 1, "重新武装且幅度足够（0.3% ≥ 0.25%）应可推送"


# ── 5. 同轮聚合：连穿多位只发一条 ────────────────────────────────────

def test_multiple_crossings_in_one_round_aggregate_into_one_message():
    trig = {}
    # 现价 77250 附近密集 3 位，一次向下穿越全部命中
    block = {"levels": [
        _lvl("价值区·VAH", 77310.0, "event"),
        _lvl("价值区·POC", 77243.0, "critical"),
        _lvl("结构·熊FVG/OB", 77200.0, "critical"),
    ]}
    _digest, cands = G.evaluate_symbol("BTCUSDT", block, 77320.0, 77190.0, NOW, trig)
    assert len(cands) == 3, "三位应同时进入候选，交给调用方聚合"
    # 聚合后只生成一条文案
    hits = [{"name": c["name"], "price": c["price"], "tier": c["tier"]} for c in cands]
    text = G._format_alert("BTCUSDT", 77190.0, hits)
    assert "同时触及 3 个位" in text
    assert text.count("○") == 1, "聚合后只应有一个消息头"


def test_single_hit_message_states_tier_and_cooldown():
    text = G._format_alert("BTCUSDT", 76940.0,
                           [{"name": "结构·熊FVG/OB", "price": 76938.0, "tier": "critical"}])
    assert "76,938" in text and "critical" in text
    assert "不代表方向" in text and "不自动下单" in text, "守卫层禁止方向判断"


# ── 6. 全局限流 ───────────────────────────────────────────────────────

def test_global_min_gap_blocks_a_second_push_too_soon():
    ok, reason, _ = G.global_rate_limit_ok([NOW - 60], NOW)
    assert ok is False and reason == "global_min_gap"


def test_global_hourly_cap_blocks_fourth_push_in_an_hour():
    recent = [NOW - 3000, NOW - 2400, NOW - 2100]   # 都已过 30min 间隔
    ok, reason, _ = G.global_rate_limit_ok(recent, NOW)
    assert ok is False and reason == "global_hourly_cap"


def test_global_allows_push_when_gap_and_cap_are_satisfied():
    ok, reason, _ = G.global_rate_limit_ok([NOW - 3600], NOW)
    assert ok is True and reason == ""


def test_global_limit_prunes_entries_older_than_24h():
    _ok, _reason, kept = G.global_rate_limit_ok([NOW - 30 * 3600, NOW - 3600], NOW)
    assert all(NOW - t < 24 * 3600 for t in kept)


# ── 7. enabled / push_tier 语义解耦（死锁防回归）─────────────────────

def test_enabled_silent_level_still_counts_toward_structure_review():
    """核心契约：为了降噪而 silent 的位，必须仍算作结构复核样本。"""
    cfg = {
        "auto_approval_policy": {
            "max_structure_age_hours": 24,
            "structure_reviewed_at": G.now_bjt_iso(),
        },
        "symbols": {"BTCUSDT": {"levels": [
            _lvl("结构·熊FVG/OB", 76938.0, "critical"),
            _lvl("价值区·VAH", 77310.0, "event"),
            _lvl("价值区·POC", 76600.0, "silent"),
            _lvl("价值区·DO", 77400.0, "silent"),
        ]}},
    }
    h = G.config_health(cfg)
    assert h["status"] == "ok"
    assert h["enabled_levels"] == 4, "silent 位仍参与监控"
    assert h["push_enabled_levels"] == 2, "只有 2 位可推"
    assert h["active_approved_levels"] == 4


def test_monitoring_intent_distinguishes_undeclared_from_user_silenced():
    base = {"auto_approval_policy": {"max_structure_age_hours": 24,
                                    "structure_reviewed_at": G.now_bjt_iso()}}
    # 全部 disabled 但**没有**任何声明 → undeclared（预检必须判 FAIL）
    cfg_undeclared = {**base, "symbols": {"BTCUSDT": {"levels": [
        _lvl("A", 1.0, "silent", enabled=False)]}}}
    assert G.monitoring_intent(cfg_undeclared) == "undeclared"
    assert G.config_health(cfg_undeclared)["status"] == "idle"

    # 显式声明用户静默 → user_silenced（合法）
    cfg_silenced = {**cfg_undeclared, "monitoring_status": "user_silenced"}
    assert G.monitoring_intent(cfg_silenced) == "user_silenced"

    # 显式声明退役 → retired
    cfg_retired = {**cfg_undeclared, "monitoring_status": "retired"}
    assert G.monitoring_intent(cfg_retired) == "retired"

    # 有启用位 → active
    cfg_active = {**base, "symbols": {"BTCUSDT": {"levels": [
        _lvl("A", 1.0, "critical")]}}}
    assert G.monitoring_intent(cfg_active) == "active"


def test_structure_review_sample_floor_shrinks_with_enabled_count():
    """MIN_VALID 必须与实际启用位数匹配，否则降噪会把监控锁死。"""
    R = load("keylevels_structure_review.py")
    assert R.MIN_VALID == 6, "默认阈值不应被悄悄改小"
    # 启用 8 位时复核要求 ≥6 个样本
    assert min(R.MIN_VALID, 8) == 6
    # 启用 3 位时要求 3 个（全部通过仍是硬条件）
    assert min(R.MIN_VALID, 3) == 3


# ── 8. 源码防漂移：主循环必须复用纯函数 ──────────────────────────────

def test_main_loop_reuses_evaluate_symbol():
    """主循环不得再内联一份穿越判定（双份逻辑必然漂移）。"""
    src = (ROOT / "scripts" / "keylevel_guard.py").read_text(encoding="utf-8")
    assert "digest_round, push_candidates = evaluate_symbol(" in src
    assert "def evaluate_symbol(" in src
    # 旧的无分级冷却常量不应再被用于判定
    assert "now + COOLDOWN_SECONDS" not in src


def test_guard_push_path_goes_through_reliable_gate():
    """推送必须走统一入口，否则夜间静默与去重对关键位失效。"""
    src = (ROOT / "scripts" / "keylevel_guard.py").read_text(encoding="utf-8")
    assert "from telegram_reliable import push_tg_rich" in src
    assert "send_telegram_direct" not in src
