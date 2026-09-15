#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 级可达性诊断探针 —— 回答「A 级到底卡在哪一项」。

起因（2026-09-15）：影子账本 2026-07-10→09-15 共 454 个信号，GO-A 出现 **0 次**，
grade 从未出过 A。要分辨「行情真没 A 级机会」还是「A 级被工程问题物理封死」，
必须把 A 级要求的每一项在现场逐条对照，而不是继续猜。

数据源：auto_card 落盘的 TV Data Window 缓存 `data/tv_live_<SYM>.json`
（字段权威 = docs/tv-indicator-field-map.md + scripts/tv_indicator_contract.py）。
本脚本只读缓存、只解码、不改判；不连 TV、不抢图。

用法：
    python scripts/a_grade_probe.py            # 默认 BTCUSDT
    python scripts/a_grade_probe.py XAUUSD
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tv_indicator_contract import (  # noqa: E402
    RR_BC_MIN, RR_HARD_MIN,
    decode_entry_valid, decode_evidence_pack, decode_haldro_state,
    decode_no_trade, decode_quality_code, decode_regime_pack,
    decode_struct_pack, decode_trigger_pack, format_no_trade,
)

DATA = ROOT / "data"
CRYPTO_SUFFIXES = ("USDT", "USDC", "BUSD", "PERP")


def cache_path(symbol: str) -> Path:
    raw = str(symbol or "").upper().split(":")[-1]
    if raw.endswith(".P"):
        raw = raw[:-2]
    key = "".join(ch for ch in raw if ch.isalnum())
    if key.endswith("PERP"):
        key = key[:-4]
    return DATA / f"tv_live_{key}.json"


def _f(value, default=None):
    try:
        return float(str(value).replace("−", "-").replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return default


def main() -> int:
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT").upper()
    path = cache_path(symbol)
    if not path.exists():
        print(f"[FAIL] 找不到 TV 缓存 {path}；先跑一次分析让 auto_card 落盘。")
        return 2
    cache = json.loads(path.read_text(encoding="utf-8-sig"))
    ind = cache.get("indicators") or {}
    age_min = (time.time() - path.stat().st_mtime) / 60.0

    is_crypto = symbol.endswith(CRYPTO_SUFFIXES)

    print("=" * 68)
    print(f"A 级可达性诊断 · {symbol} · 缓存 {path.name}")
    print(f"缓存年龄 {age_min:.1f} 分钟 · 周期 {cache.get('timeframe')} · "
          f"fresh={cache.get('fresh')} stale={cache.get('stale')} "
          f"identity_valid={cache.get('identity_valid')}")
    print("=" * 68)

    rows: list[tuple[str, str, bool, str]] = []

    def add(name, value, ok, note=""):
        rows.append((name, str(value), bool(ok), note))

    # 1) 主指标等级与授权码 —— A 级的入口
    grade = ind.get("mcp_grade_code")
    ev = ind.get("mcp_entry_valid_code")
    add("MCP Grade Code", f"{grade}（3=A/2=B/1=C/-1=X）", _f(grade) == 3,
        "A 级必须 =3；非 3 时后面全部无意义")
    add("MCP Entry Valid Code", f"{ev} → {decode_entry_valid(ev)}", _f(ev) == 3,
        "-3 X禁做 / -2 几何无效 / -1 R:R不足 / 0 无方向 / 1 待确认 / 2 B·C / 3 A")

    # 2) 五周期与方向
    side = ind.get("mcp_side_code")
    add("MCP Side Code", f"{side}（1多/-1空/0无/9等待）", _f(side) in (1, -1),
        "9 或 0 = 指标自身不给方向 → 结构未成立")

    # 3) 证据四要素 —— 用分量字段（decision_loop:1311-1313 消费的就是这四个），
    #    缓存不落合并的 Evidence Pack，只有 mcp_evidence_* 分量。
    evp = decode_evidence_pack(ind.get("mcp_evidence_pack"))
    ev_dir = ind.get("mcp_evidence_direction")
    if ev_dir is None and evp:
        ev_dir = evp.get("direction")
    ev_loc = ind.get("mcp_location_valid")
    if ev_loc is None and evp:
        ev_loc = evp.get("locationValid")
    ev_trg = ind.get("mcp_trigger_confirmed")
    if ev_trg is None and evp:
        ev_trg = evp.get("triggerConfirmed")
    ev_cls = ind.get("mcp_bar_closed")
    if ev_cls is None and evp:
        ev_cls = evp.get("barClosed")
    add("证据·方向", f"{ev_dir}（1多/-1空/0无）", _f(ev_dir) in (1, -1),
        "0 = 指标无方向；A 级硬门（decision_evidence）")
    for key, label in ((ev_loc, "证据·位置有效"), (ev_trg, "证据·触发确认"),
                       (ev_cls, "证据·闭柱")):
        add(label, key, key is True, "非 True 即不得授权 A（真值必须字面 True）")
    add("证据版本", ind.get("mcp_evidence_version"), True, "证据包 schema 版本，非新鲜度")

    # 4) 触发包：新鲜度与年龄
    trg = decode_trigger_pack(ind.get("mcp_trigger_pack")) or {}
    add("触发·fresh", trg.get("fresh"), trg.get("fresh") is True, "触发不新鲜 → trigger")
    add("触发·age", trg.get("age"), (trg.get("age") or 0) > 0, "age=0 → 无触发")
    add("触发·signalState", trg.get("signalState"), trg.get("signalState") not in (None, -2),
        "-2 = 无可执行触发态")

    # 5) 区域质量（<55 直接 wait: zone_quality）
    for key, label in (("mcp_fvg_quality_score", "FVG 质量"), ("mcp_ob_quality_score", "OB 质量")):
        q = _f(ind.get(key))
        add(label, q, (q or 0) >= 55, "<55 → zone_quality（模型不同取不同字段）")

    # 6) NoTrade 位掩码
    nt = ind.get("mcp_notrade_reason_code") or ind.get("mcp_no_trade_reason_code")
    reasons = decode_no_trade(nt)
    add("NoTrade 位掩码", format_no_trade(nt) or "无", not reasons, "任一位置位都是阻断证据")

    # 7) 质量码
    qc = decode_quality_code(ind.get("mcp_quality_code")) or {}
    qc_bad = [k for k in ("htfConflict", "cvdLowQuality", "lowLiquidity",
                          "adrBlocked", "htfFvg", "mss", "emaOrderMissing") if qc.get(k)]
    add("MCP Quality Code", qc.get("raw"), not qc_bad, ",".join(qc_bad) or "无质量问题")

    # 8) 体制包
    rg = decode_regime_pack(ind.get("mcp_regime_pack")) or {}
    add("体制 confidence", rg.get("confidence"), (rg.get("confidence") or 0) > 0, "0 = 体制未定")
    add("体制 regimeCode", rg.get("regimeCode"), rg.get("regimeCode") is not None, "")

    # 9) 结构包
    st = decode_struct_pack(ind.get("mcp_structpack") or ind.get("mcp_struct_pack")) or {}
    add("结构·FVG质量", st.get("fvgQuality"), (st.get("fvgQuality") or 0) > 0, "")

    # 10) 副指标（加密才需要）
    if is_crypto:
        vc = _f(ind.get("haldro_valid_code"))
        hs = ind.get("haldro_state_pack") or ind.get("haldro_state")
        add("HALDRO Valid Code", vc, (vc or 0) >= 2,
            "<=0 → haldro_invalid（wait）；==1 单源回退不能授权 A")
        if hs is None:
            hs = ind.get("haldro_state_code")
        hs_n = _f(hs)
        add("HALDRO State Pack", f"{hs_n} → {decode_haldro_state(hs_n)}",
            hs_n in (1, 2),
            "A 级要求 S1(支持多)/S2(支持空)；S3 冲突=S硬门 / S0·S4=降权")
        oi_ag = _f(ind.get("oi_agreement"))
        if oi_ag is not None:
            add("OI 一致度 %", oi_ag, oi_ag >= 50, "<50 → oi_agreement_low")
        oi_dis = _f(ind.get("oi_dispersion_ratio"))
        if oi_dis is not None:
            add("OI 离散度", oi_dis, oi_dis <= 2.5, ">2.5 → oi_dispersion_high")
        cq = _f(ind.get("cvd_quality_code"))
        add("CVD Quality Code", cq, (cq or 0) > 0, "<=0 → cvd_quality_unavailable")

    # 11) 合约包
    cp = ind.get("mcp_contract_pack")
    add("Contract Pack", cp, cp is not None and int(_f(cp, 0)) >= 171001,
        "11001 之后为 171xxx 合同；无效 → 合同损坏")

    # 12) R:R（若缓存里有三价）
    entry = _f(ind.get("mcp_entry_price"))
    stop = _f(ind.get("mcp_stop_price"))
    target = _f(ind.get("mcp_target_price"))
    rr = None
    if entry and stop and target and abs(entry - stop) > 0:
        rr = abs(target - entry) / abs(entry - stop)
    add("R:R（三价推算）", f"{rr:.2f}" if rr else "缓存无三价", rr is not None and rr >= RR_HARD_MIN,
        f"A 级硬线 {RR_HARD_MIN}；{RR_BC_MIN}-{RR_HARD_MIN} 只能 B/C 人工候选")

    # 输出
    name_w = max(len(r[0]) for r in rows)
    passed = 0
    for name, value, ok, note in rows:
        mark = "✅" if ok else "❌"
        passed += 1 if ok else 0
        print(f"{mark} {name.ljust(name_w)} | {value[:34].ljust(34)} | {note}")
    total = len(rows)
    print("-" * 68)
    print(f"本帧通过 {passed}/{total} 项。A 级要求全部通过。")

    failed = [r[0] for r in rows if not r[2]]
    if failed:
        print("\n未通过（按 A 级门槛，任何一项都足以把 A 压成 B/C 或等待）：")
        for f in failed:
            print(f"  · {f}")
    # 工程性 vs 行情性：Grade/Side/EntryValid 是 SVP 的行情判断，不算故障；
    # 只有「字段缺失」或「副指标有效性/合同」这类硬接线项才疑似工程问题。
    WIRING = {"HALDRO Valid Code", "Contract Pack"}
    MISSING = [r[0] for r in rows if r[1] in ("None", "缺失", "")]
    wiring_hit = [f for f in failed if f in WIRING] + MISSING
    wiring_hit = list(dict.fromkeys(wiring_hit))
    if wiring_hit:
        print("\n⚠ 疑似工程问题（不是行情判断，需查接线/Bus/缓存字段是否落盘）：")
        for f in wiring_hit:
            print(f"  · {f}")
    else:
        print("\n未通过项看起来都是行情/结构条件（SVP 的等级与方向判断），不是接线故障。")
    if age_min > 30:
        print(f"\n⚠ 缓存已 {age_min:.0f} 分钟，先重跑分析再看结论。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
