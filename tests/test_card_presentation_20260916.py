# -*- coding: utf-8 -*-
"""卡面呈现一致性回归（2026-09-16「按建议推进」）。

对应 2026-09-16 审计确认的终端呈现缺陷 —— 这些缺陷此前**没有任何测试覆盖**
（全量 1376 项通过时仍全部存在），所以单独钉一组回归：

原生卡（render_v96）
1. 首屏理由只读 FinalVerdict 主拦因；「本模块不适用」不得当禁做理由；
2. 非加密不套用加密话术（不要求「主副指标重新共振」）；
3. 不适用模块（HALDRO）与全为「—」的副读行不占正文，但缺席原因必须可见。

重排卡（card_reformat v7 表格版）
4. 价格精度与原生卡同源（外汇 4 位小数不被取整）；
5. 远端小价位（<100）不被过滤，三态不退化成「区间外」；
6. 现价在带内时三态仍有数（用现价带上下沿）、○ 横盘行与「怎么做」不消失；
7. ⭐ 只代表唯一授权（GO-A），不落在「主观察」行；
8. GO-A 卡的 ④ 执行三件套必须搬进重排卡，总结不得同时说「当前不给入场价」；
9. 关键位按距现价排序；主周期取卡面体温行（黄金 5m，不硬编码 15 分钟）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import card_reformat  # noqa: E402
import price_format  # noqa: E402
import render_v96  # noqa: E402
from card_reformat import render_tables  # noqa: E402
from render_v96 import _blocker_headline, render_v96_card  # noqa: E402

PRICE = 4333.0

# ── 原生卡样本（黄金：非加密、5m 主周期、副指标不适用） ──────────────────
XAU_KLINES = {
    "D": {"description": "偏空·平衡·", "cvd": {"direction": "卖", "value": -10}},
    "4h": {"description": "偏多·平衡·", "cvd": {"direction": "买", "value": 12}},
    "1h": {"description": "偏多·平衡·", "cvd": {"direction": "买", "value": 8}},
    "15m": {"description": "偏多·平衡·", "cvd": {"direction": "买", "value": 4}},
    "5m": {"description": "偏多·平衡·", "cvd": {"direction": "买", "value": 2}},
}

XAU_BANDS = [
    {"level": 4340.0, "kind": "4h·VAH"},
    {"level": 4331.0, "kind": "5m·阻"},
    {"level": 4328.0, "kind": "1h·支"},
    {"level": 4318.0, "kind": "D·阻"},
    {"level": 4308.0, "kind": "4h·VWAP"},
]


def _xau_final_verdict() -> dict:
    return {
        "state": "NO-GO", "executable": False, "side": "neutral",
        "reason": "硬闸门：risk_constitution",
        "primary_blocker": "risk_constitution",
        "blocker_groups": [("风控/体制/订单流拦截", ["risk_constitution", "advanced_confluence"])],
    }


def _xau_card(final_verdict: dict | None = None) -> str:
    return render_v96_card(
        symbol="XAUUSD", status="NO-GO", direction="wait", price=PRICE,
        high=4341.0, low=4260.0, chg=0.89, tf_lines="", cvd_dir="中性", cvd_quality="",
        taker_dir="", taker_ratio=None, funding_rate="", kill_zone="伦敦",
        vwap_ema={}, fg_v="", levels=list(XAU_BANDS),
        bearish=False, st_a={}, st_b={}, rr_a=1.2, rr_b=0, rr_a_note="", rr_b_note="",
        risk_amt=0, leverage_text="TVC仅数据源", inv_line="—", prot_status="通过",
        data_grade="A-", sweep_state="", displacement="", one_reason="", model_id="m",
        n5=0, eng_conf=0, klines=XAU_KLINES,
        dual_indicator={"usable": True, "asset_is_crypto": False,
                        "direction_verdict": "非加密不套HALDRO",
                        "gold_contract_cvd": True},
        final_verdict=final_verdict if final_verdict is not None else _xau_final_verdict(),
        source_matrix=[{"label": "TV五周期", "status": "live", "entered_final_verdict": True}],
    )


def _crypto_card() -> str:
    return render_v96_card(
        symbol="BTCUSDT", status="NO-GO", direction="short", price=77668.0,
        high=77864.7, low=76350.1, chg=0.73, tf_lines="", cvd_dir="买", cvd_quality="A",
        taker_dir="", taker_ratio=0.93, funding_rate="0.0087%", kill_zone="伦敦",
        vwap_ema={}, fg_v="57", levels=[{"level": 77864.7, "kind": "15m·阻"},
                                        {"level": 77597.85, "kind": "15m·POC"}],
        bearish=True, st_a={}, st_b={}, rr_a=0.5, rr_b=3.4, rr_a_note="", rr_b_note="",
        risk_amt=0, leverage_text="Binance 100x", inv_line="—", prot_status="通过",
        data_grade="A", sweep_state="", displacement="", one_reason="", model_id="m",
        n5=1, eng_conf=0, klines=XAU_KLINES,
        dual_indicator={"usable": True, "asset_is_crypto": True, "hard_conflict": True,
                        "direction_verdict": "副S3冲突·CVD/OI背离"},
        final_verdict={"state": "NO-GO", "executable": False, "reason": "dual_indicator",
                       "primary_blocker": "", "blocker_groups": []},
        source_matrix=[],
    )


# ── 1. 首屏理由 = FinalVerdict 主拦因 ───────────────────────────────────

def test_headline_uses_primary_blocker_not_module_na():
    card = _xau_card()
    lines = card.splitlines()
    head = "\n".join(lines[:3])
    assert "risk_constitution（风控/体制/订单流拦截）" in head, head
    assert "非加密不套HALDRO" not in head, head


def test_headline_matches_verdict_line_and_is_single_source():
    """首屏与【裁决】主因行必须引用同一组原因（同一函数生成，不会各自漂移）。"""
    card = _xau_card()
    head_reason = card.splitlines()[1].split("—", 1)[1].strip()
    verdict_line = next(l for l in card.splitlines() if l.startswith("主因 "))
    assert verdict_line.startswith(f"主因 {head_reason}"), (head_reason, verdict_line)


def test_blocker_headline_without_groups_falls_back_to_code():
    assert _blocker_headline({"primary_blocker": "rr_ratio"}) == "rr_ratio"
    assert _blocker_headline({}) == ""
    assert _blocker_headline(None) == ""


def test_crypto_headline_still_uses_dual_verdict_when_no_blocker():
    card = _crypto_card()
    assert "副S3冲突·CVD/OI背离" in card.splitlines()[1]


# ── 2/3. 非加密话术与不适用模块 ──────────────────────────────────────────

def test_non_crypto_does_not_borrow_crypto_phrasing():
    card = _xau_card()
    assert "主副指标重新共振" not in card, card
    assert "结构与来源方向确认" in card


def test_not_applicable_module_is_out_of_body_but_disclosed():
    card = _xau_card()
    assert "| HALDRO副驾驶 |" not in card
    assert not any(l.startswith("副读 ") for l in card.splitlines())
    assert "来源说明：HALDRO 副驾驶不适用" in card


def test_crypto_keeps_sub_read_and_haldro_rows():
    card = _crypto_card()
    assert any(l.startswith("副读 ") for l in card.splitlines())
    assert "| HALDRO副驾驶 |" in card


# ── 4/5/6/7/9. 重排卡 ───────────────────────────────────────────────────

FX_CARD = """📊 EURUSD · OANDA · 2026年09月16日15：40 · 伦敦时段 · ⚪NO-GO · 观望
⚠️主推 禁做 — 副S3冲突
结构：⚖现价 1.1638 · 🔴上 1.1680（D·VAH） · 🟢下 1.1590（4h·VAL）

① 周期体温 D🟢 · 4h🟢 · 1h🟢 · 15m⭐🟢 · 5m🟢
副读 D— · 4h— · 1h— · 15m— · 5m—

② 关键位 / 结构关键位

| 角色 | 价位 | 距现价 |
|:---|:---:|:---:|
| 主观察·D·VAH | `1.1680` | +0.36% |
| 现价所在带·1h | `1.1620–1.1660` | -0.15%~+0.19% |
| 失效/支撑带·4h·VAL | `1.1590` | -0.41% |
远端：D·支 1.1480 ／ 4h·支 1.1420

③ 多源验证 / 双指标

| 能力 | 读数 | 裁决 |
|:---|:---|:---|
| SVP主驾驶 | C等待 | 结构/入场/止损/目标优先 |
| HALDRO副驾驶 | HALDRO不适用 | 非加密不套HALDRO |
| 质量 | — | 覆盖不足不追 |

【裁决】⚠禁做 — 副S3冲突
主因 haldro_invalid（副指标未确认） · 2 类 / 3 条拦因（明细见证据层）
管线路由：7步 · 完成 6/7
"""

XAU_CARD = """📊 XAUUSD · TVC · 2026年09月16日15：01 · 伦敦时段 · ⚪NO-GO · 观望
⚠️主推 禁做 — 非加密不套HALDRO
结构：⚖现价 4,333 · 🔴上 4,334（1h·阻） · 🟢下 4,331（5m·阻）

① 周期体温 D🔴 · 4h🟢 · 1h🟢 · 15m🟢 · 5m⭐🟢
副读 D— · 4h— · 1h— · 15m— · 5m—

② 关键位 / 结构关键位

| 角色 | 价位 | 距现价 |
|:---|:---:|:---:|
| ⚖ 现价所在带·5m·阻–4h·VAH | `4,331–4,340` | -0.05%~+0.15% |
| 主观察·D·阻–1h·支 | `4,318–4,328` | -0.13%~-0.36% |
| 失效/支撑带·4h·VWAP | `4,308` | -0.58% |
远端：4h·支 4,276 ／ D·支 4,260

③ 多源验证 / 双指标

| 能力 | 读数 | 裁决 |
|:---|:---|:---|
| SVP主驾驶 | C等待 | 结构/入场/止损/目标优先 |
| HALDRO副驾驶 | HALDRO不适用 | 非加密不套HALDRO |
| 订单流 | CVD🔵中性·Binance黄金合约 | CVD/OI不配则降级 |

【裁决】⚠禁做 — risk_constitution
主因 risk_constitution（风控/体制/订单流拦截） · 7 类 / 14 条拦因（明细见证据层）
管线路由：8步 · 完成 7/8
"""

GOA_CARD = """📊 BTCUSDT.P · BINANCE · 2026年09月16日15：30 · 伦敦时段 · 🟢GO-A · 多
⭐主推 多 — 主副同向·可执行
结构：⚖现价 77,600 · 🔴上 77,800（4h·nPOC） · 🟢下 77,400（4h·DO）

① 周期体温 D🟢 · 4h🟢 · 1h🟢 · 15m⭐🟢 · 5m🟢
副读 D🟢买 · 4h🟢买

② 关键位 / 结构关键位

| 角色 | 价位 | 距现价 |
|:---|:---:|:---:|
| 价值区·VAH | `77,310` | +0.37% |
| 价值区·DO | `77,400` | +0.26% |
| 价值区·nPOC | `77,800` | -0.26% |

③ 多源验证 / 双指标

| 能力 | 读数 | 裁决 |
|:---|:---|:---|
| SVP主驾驶 | BOS↑ | 结构/入场/止损/目标优先 |

④ 最推荐方案

| 优先级 | 条件 | 动作 |
|:---|:---|:---|
| ⭐主推 多 | 77,600确认 | 多 77,600 损76,900 标78,900 · R:R 1:2.6 |
| 🔁备选 空 | 主推失效后反向确认 | 空失效路径；不与主推平权 · 观察 |

【裁决】🟢GO-A — 主副同向
主因 无拦因
管线路由：14步 · 完成 14/14
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_fx_precision_survives_reformat(tmp_path):
    out = render_tables(_write(tmp_path, "fx.md", FX_CARD))
    assert "1.1638" in out and "1.1680" in out and "1.1590" in out, out
    assert " 1 " not in out.replace("1.1638", "").replace("1.1680", "").replace("1.1590", ""), out
    assert "1–1" not in out and "收上 1 " not in out


def test_remote_levels_below_100_are_kept(tmp_path):
    out = render_tables(_write(tmp_path, "fx.md", FX_CARD))
    assert "1.1480" in out and "1.1420" in out, out
    assert "区间外" not in out, out


def test_price_inside_band_keeps_three_state_and_howto(tmp_path):
    out = render_tables(_write(tmp_path, "xau.md", XAU_CARD))
    assert "| ○ | 4,331–4,340 之间横盘 |" in out, out
    assert "收上 4,340（现价带上沿）" in out, out
    assert "- **怎么做**" in out, out
    assert "上沿 |" not in out and "区间外" not in out, out


def test_howto_uses_card_main_timeframe_not_hardcoded_15m(tmp_path):
    out = render_tables(_write(tmp_path, "xau.md", XAU_CARD))
    assert "等 5m 收线" in out, out
    assert "15 分钟收线" not in out, out
    assert "主副指标重新共振" not in out, out          # 非加密不套加密话术
    assert "结构与来源方向确认" in out, out


def test_star_only_marks_sole_goa_recommendation(tmp_path):
    no_go = render_tables(_write(tmp_path, "xau.md", XAU_CARD))
    assert "⭐主观察" not in no_go, no_go
    assert "主观察·D·阻–1h·支" in no_go, no_go

    goa = render_tables(_write(tmp_path, "goa.md", GOA_CARD))
    assert goa.splitlines()[1].startswith("⭐主推 多"), goa


def test_goa_execution_triple_is_carried_into_tables_card(tmp_path):
    out = render_tables(_write(tmp_path, "goa.md", GOA_CARD))
    assert "多 77,600 损76,900 标78,900" in out, out
    assert out.count("77,600 损76,900 标78,900") == 1, out
    assert "当前不给入场价" not in out, out             # 与首屏「可执行」自相矛盾
    assert "没有优势位置" not in out, out
    assert "执行三件套见 ④" in out, out


def test_key_levels_sorted_by_distance_to_price(tmp_path):
    out = render_tables(_write(tmp_path, "goa.md", GOA_CARD))
    rows = [l for l in out.splitlines() if l.startswith("| 价值区")]
    assert [r.split("|")[1].strip() for r in rows] == ["价值区·nPOC", "价值区·DO", "价值区·VAH"], rows


def test_reformat_head_reason_falls_back_to_card_blocker(tmp_path):
    """老卡（修复前生成）首行仍写「非加密不套HALDRO」，重排时换成同卡主因。"""
    out = render_tables(_write(tmp_path, "xau.md", XAU_CARD))
    assert "risk_constitution（风控/体制/订单流拦截）" in out.splitlines()[1]
    assert "非加密不套HALDRO" not in out


def test_no_information_rows_are_dropped_with_disclosure(tmp_path):
    out = render_tables(_write(tmp_path, "xau.md", XAU_CARD))
    assert "| 质量 |" not in out, out                      # 读数「—」= 无信息行
    assert "| 订单流 |" in out, out                        # 有读数的行必须留
    assert "来源说明：HALDRO 副驾驶不适用" in out, out


def test_remote_line_skips_count_segments_and_empty_labels(tmp_path):
    """「另N带」是数量不是价位（旧实现靠 n>100 顺带滤掉）；无标签段不得印出空括号。"""
    card = XAU_CARD.replace("远端：4h·支 4,276 ／ D·支 4,260",
                            "远端：4h·支 4,276 ／ D·支 4,260 ／ 另6带")
    out = render_tables(_write(tmp_path, "xau2.md", card))
    assert "另6带" not in out and "6.0000" not in out, out
    assert "（）" not in out, out
    assert "远端 4,276（4h·支）／4,260（D·支）" in out, out

    ranged = XAU_CARD.replace("远端：4h·支 4,276 ／ D·支 4,260",
                              "远端 77,522–77,679（15m·VAL–1h·POC）／78,467–78,528（D·VWAP–4h·VWAP）")
    out2 = render_tables(_write(tmp_path, "xau3.md", ranged))
    assert "77,522–77,679（15m·VAL–1h·POC）" in out2, out2
    assert "78,467–78,528（D·VWAP–4h·VWAP）" in out2, out2


def test_tables_is_cli_default(tmp_path):
    p = _write(tmp_path, "xau.md", XAU_CARD)
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "card_reformat.py"), str(p)],
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    assert "**① 盯什么**" in out.stdout and "```text" not in out.stdout


def test_panel_style_still_available(tmp_path):
    p = _write(tmp_path, "xau.md", XAU_CARD)
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "card_reformat.py"),
                          "--style=panel", str(p)],
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    assert "```text" in out.stdout


# ── 精度单点 ────────────────────────────────────────────────────────────

def test_fmt_price_is_single_source_for_both_layers():
    assert price_format.fmt_price(1.16382) == "1.1638"
    assert price_format.fmt_price(77310.4) == "77,310"
    assert price_format.fmt_price(108.523) == "108.52"
    assert price_format.fmt_price(None) == "—"
    # 原生卡 _num 必须与共享实现逐位一致（行为不变式）
    for v in (1.16382, 77310.4, 108.523, 0.0034567, 0, None, "x"):
        assert render_v96._num(v) == price_format.fmt_price(v), v


def test_fmt_rr_keeps_two_decimals_near_the_gate():
    assert price_format.fmt_rr(1.96) == "1:1.96"
    assert price_format.fmt_rr(1.99) == "1:1.99"
    assert price_format.fmt_rr(2.0) == "1:2.00"
    assert price_format.fmt_rr(2.03) == "1:2.03"
    assert price_format.fmt_rr(1.75) == "1:1.75"
    assert price_format.fmt_rr(1.2) == "1:1.2"
    assert price_format.fmt_rr(3.42) == "1:3.4"
    assert price_format.fmt_rr(None) == "—"


def test_rr_gate_boundary_never_reads_as_pass_or_fail_simultaneously():
    """闸门用 rr_a>=2.0 判绿、显示过 :.1f —— 1.96 曾同时印「不足1:2」与「1:2.0」。"""
    from go_nogo_gate import check_gate

    near = check_gate("BTCUSDT", {}, {"rr_a": 1.96, "status": "C等待", "direction": "wait"})
    reason = near["gates"]["rr_ratio"]["reason"]
    assert near["gates"]["rr_ratio"]["status"] == "red"
    assert "1:1.96" in reason, reason
    assert "1:2.0" not in reason, reason

    at = check_gate("BTCUSDT", {}, {"rr_a": 2.0, "status": "C等待", "direction": "wait"})
    assert at["gates"]["rr_ratio"]["status"] == "green"
    assert "1:2.00" in at["gates"]["rr_ratio"]["reason"]


def test_auto_card_price_formatter_delegates_to_single_source():
    """同一条链路上的第三份格式化实现（auto_card._fmt_price）也必须收口。"""
    import auto_card
    assert auto_card._fmt_price(1.16382) == "`1.1638`"
    assert auto_card._fmt_price(77310.4) == "`77,310`"
    assert auto_card._fmt_price(None) == "`—`"


def test_reformat_reuses_render_v96_precision():
    """重排层不得自写 :,.0f —— 只允许调用共享精度函数（注释/文档串不算代码）。"""
    import re as _re
    src = (ROOT / "scripts" / "card_reformat.py").read_text(encoding="utf-8")
    code = _re.sub(r'"""[\s\S]*?"""', "", src)              # 去 docstring
    code = "\n".join(l.split("#", 1)[0] for l in code.splitlines())  # 去注释
    assert ":,.0f" not in code, "重排层又出现整数格式化路径"
    assert "fmt_price" in code
