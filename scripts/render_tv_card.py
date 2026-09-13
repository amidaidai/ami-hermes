#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 · TV双指标Telegram卡 v9.9

主指标：SVP+ICT+VWAP+CVD = 结构/关键位/执行/失效
副指标：Volume Aggregated Spot & Futures = OI/CVD/覆盖/Composite/爆仓

v9.9 修正：快速卡也必须显示结构位前置、多周期、双指标，不再把能力压没。
"""
from __future__ import annotations

import math
import re
import sys
from datetime import datetime, timezone, timedelta

# 棠溪看盘顺序：从上往下（D背景 → 4h → 1h → 15m → 5m主执行层）
TF_ORDER = ("D", "4h", "1h", "15m", "5m")

# 未授权计划里的入场/止损/目标价不得出现在卡面。
# 只作用于「风控」「路径」两行——磁吸/结构/现位里的价位是行情事实，不是订单。
_ORDER_PRICE = re.compile(r"(?:候选|[入止标])\s*-?\d[\d,]*(?:\.\d+)?")
_RISK_MULT = re.compile(r"[·\s]*\d+(?:\.\d+)?\s*[AR](?![A-Za-z])")

# B/C 只是人工观察等级：定版指标里它们从不构成执行授权。
OBSERVATION_GRADES = ("B多", "B空", "C反多", "C反空")

try:  # 契约是唯一权威；直接调用渲染器时（无 scripts 路径）退回同值字面量。
    from tv_indicator_contract import SVP_AUTHORIZATION_LABEL
except Exception:  # pragma: no cover - 独立调用渲染器的兼容路径
    SVP_AUTHORIZATION_LABEL = "风控"


def _redact_order_prices(text: object) -> str:
    """剥掉未授权计划携带的下单价位与 ATR/R 倍数。"""
    s = str(text or "")
    if not s:
        return ""
    s = _RISK_MULT.sub("", _ORDER_PRICE.sub("", s))
    return re.sub(r"[·\s]{2,}", "·", s).strip("· ")


def _candidate_view(final: dict) -> dict:
    """B/C 人工候选只认 FinalVerdict 的 watch 元组。

    定版指标把「风控·观察」的观察价与执行导出彻底分开，渲染层不得
    回落到原始 entry/stop/target。元组不完整时返回 {'incomplete': True}，
    让卡面明说「候选数据不完整」，而不是补一个半个订单出来。
    """
    if not isinstance(final, dict):
        return {}
    side = str(final.get("watch_side") or "neutral").lower()
    raw = [final.get(key) for key in ("watch_entry", "watch_stop", "watch_target")]
    if side not in ("long", "short"):
        return {"incomplete": True} if any(v is not None for v in raw) else {}
    if any(v is None for v in raw):
        return {"incomplete": True}
    try:
        entry, stop, target = (float(str(v)) for v in raw)
    except (TypeError, ValueError):
        return {"incomplete": True}
    if not all(math.isfinite(v) and v > 0 for v in (entry, stop, target)):
        return {"incomplete": True}
    if side == "long" and not stop < entry < target:
        return {"incomplete": True}
    if side == "short" and not stop > entry > target:
        return {"incomplete": True}
    return {"side": side, "entry": entry, "stop": stop, "target": target,
            "rr": abs(target - entry) / abs(entry - stop)}


# 公开别名：完整报告卡 render_v96 复用同一份候选判定。
# 候选规则只允许有一个实现——两份实现必然漂移（本仓吃过的教训）。
candidate_view = _candidate_view

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (OSError, ValueError):
    pass

TZ = timezone(timedelta(hours=8))


def _now_chinese() -> str:
    return datetime.now(TZ).strftime("%Y年%m月%d日%H：%M")


def _clean_text(text: object, limit: int | None = None) -> str:
    s = "" if text is None else str(text)
    for old, new in {
        "🟢": "", "🟡": "", "🔴": "", "⚪": "", "🔥": "",
        "🔵": "", "✅": "", "⚠️": "⚠", "⚡": "",
        "📺": "TV ", "❌": "✗", "✔": "✓",
    }.items():
        s = s.replace(old, new)
    s = s.replace("|", "／")
    s = re.sub(r"\s+", " ", s).strip(" ·")
    # Legacy callers pass width hints. Never cut semantic text: a suffix
    # can contain a price, percent sign, negation, or source-state qualifier.
    return s


def _chart_evidence_lines(main: dict) -> list[str]:
    """Render compact price-bar/ICT evidence, never execution authority."""
    evidence = main.get("chart_evidence") if isinstance(main, dict) else None
    if not isinstance(evidence, dict):
        return []
    price = evidence.get("price_context") or {}
    ict = evidence.get("ict") or {}
    status = str(evidence.get("status") or "unavailable")
    identity = evidence.get("identity") or {}
    def value(key: str) -> str:
        raw = price.get(key)
        return _fmt_num(raw) if raw not in (None, "") else "—"
    lines = [f"图表证据：{status} · {identity.get('timeframe') or '周期未知'}"]
    if price.get("complete"):
        lines.append(f"价格栏：O{value('open')} H{value('high')} L{value('low')} C{value('close')} · 现{value('last_price')}")
    lines.append("ICT：" + " · ".join([
        f"FVG{len(ict.get('fvg') or [])}",
        f"OB{len(ict.get('ob') or [])}",
        f"BOS/MSS{len(ict.get('structure_labels') or [])}",
        f"流动性{len(ict.get('liquidity') or [])}",
        f"区域{len(ict.get('zones') or [])}",
    ]))
    if status != "verified":
        lines.append("ICT对象未完整读回：只观察，不升级GO-A")
    return lines


def _fmt_num(v):
    if v is None or v == "":
        return "—"
    try:
        f = float(str(v).replace(",", "").replace("`", ""))
        if f >= 1000:
            return f"{f:,.0f}"
        a = abs(f)
        if 0.01 <= a < 10:
            # 2026-09-13 FX 精度修复：与 render_v96._num 同规则。
            return f"{f:.4f}"
        if 0 < a < 0.01:
            return f"{f:.6f}".rstrip("0").rstrip(".")
        return f"{f:.2f}"
    except (TypeError, ValueError):
        return str(v).replace("`", "")


def _dir_icon(direction: str) -> str:
    if "多" in str(direction):
        return "🟢"
    if "空" in str(direction):
        return "🔴"
    return "🔵"


def _grade_icon(grade: str) -> str:
    g = str(grade or "")
    if g.startswith("A"):
        return "🟢"
    if g.startswith("B"):
        return "🔵"
    if g.startswith("C"):
        return "🟡"
    if g.startswith("X"):
        return "⚠️"
    return "⚪"


def _tf_mini(main: dict, symbol: str = "") -> str:
    kl = main.get("_klines") or main.get("klines") or {}
    main_tf = ""
    try:
        from pipeline_router import timeframe_info
        if symbol:
            main_tf = timeframe_info(symbol).get("main", "")
    except Exception:
        pass
    if not isinstance(kl, dict):
        kl = {}
    out = []
    for tf in TF_ORDER:
        k = kl.get(tf) or (kl.get("1D") if tf == "D" else None)
        mark = "⭐" if tf == main_tf else ""
        if not isinstance(k, dict) or not k:
            out.append(f"{tf}{mark}未取")
            continue
        desc = str(k.get("description") or k.get("svp") or k.get("direction") or "") if isinstance(k, dict) else ""
        emo = "🟢" if any(x in desc for x in ("多", "涨", "long")) else "🔴" if any(x in desc for x in ("空", "跌", "short")) else "⚠️" if "禁" in desc else "🔵" if desc else "⚪"
        inherited = ""
        if k.get("inherited") is True:
            inherited = "继承" + str(k.get("timestamp") or "时间未提供")
        out.append(f"{tf}{mark}{emo}{inherited}")
    return " · ".join(out)


def _level_table(vwap, vah, val, poc, price) -> str:
    """结构位前置：真管道表（上沿 / 现价 / 下沿）。替代旧的全角竖线伪表格行。"""
    try:
        px = float(price or 0)
    except Exception:
        px = 0
    if not px:
        return "| 结构 | 价格 | 距现价 |\n|:---|:---:|---:|\n| ⚠现价 | 待采集 | — |"
    vals = []
    for lab, v in (("VAH", vah), ("VWAP", vwap), ("POC", poc), ("VAL", val)):
        if v:
            try:
                vals.append((lab, float(str(v).replace(",", ""))))
            except Exception:
                pass
    if not vals:
        return f"| 结构 | 价格 | 距现价 |\n|:---|:---:|---:|\n| ⚠现价 | `{_fmt_num(px)}` | — |"
    above = sorted([x for x in vals if x[1] > px], key=lambda x: x[1])
    below = sorted([x for x in vals if x[1] < px], key=lambda x: -x[1])
    a = above[0] if above else None
    b = below[0] if below else None
    rows = []
    if a:
        dist = f"{(a[1] - px) / px * 100:+.2f}%"
        rows.append(f"| 🔴{a[0]} 上 | `{_fmt_num(a[1])}` | {dist} |")
    rows.append(f"| ⚖现价 | `{_fmt_num(px)}` | — |")
    if b:
        dist = f"{(b[1] - px) / px * 100:+.2f}%"
        rows.append(f"| 🟢{b[0]} 下 | `{_fmt_num(b[1])}` | {dist} |")
    return "| 结构 | 价格 | 距现价 |\n|:---|:---:|---:|\n" + "\n".join(rows)


def _decision_line(main: dict) -> str:
    final = main.get("_final_verdict") if isinstance(main, dict) else None
    regime = main.get("_decision_regime") if isinstance(main, dict) else None
    if not isinstance(final, dict):
        return ""
    regime_name = regime.get("name") if isinstance(regime, dict) else "待判"
    model_id = final.get("model_id") or "待判"
    state = final.get("state") or "WAIT"
    # Keep the machine state literal in the compact card.  The state is the
    # contract consumed by downstream readers; translating it here made a
    # valid FinalVerdict impossible to trace back to the decision loop.
    return f"体制{regime_name} · 模型{model_id} · {state}"


def _source_summary(main: dict) -> str:
    """Compactly expose source status and FinalVerdict usage."""
    matrix = main.get("_source_matrix") if isinstance(main, dict) else None
    if not isinstance(matrix, list):
        return ""
    parts = []
    for row in matrix:
        if not isinstance(row, dict):
            continue
        label = _clean_text(row.get("label") or row.get("id") or "来源", 12)
        status = _clean_text(row.get("status") or "not_run", 16)
        usage = "裁决" if row.get("entered_final_verdict") else "辅助"
        parts.append(f"{label}:{status}·{usage}")
    return "来源 " + " / ".join(parts) if parts else ""


def _dual_verdict_for_final(main: dict, dual: dict) -> str:
    """Prevent stale/raw dual text from contradicting FinalVerdict."""
    final = main.get("_final_verdict") if isinstance(main, dict) else None
    final = final if isinstance(final, dict) else {}
    state = str(final.get("state") or "").upper()
    reason = str(final.get("reason") or "")
    if bool(dual.get("hard_conflict")) or "dual_indicator" in reason:
        # 2026-09-13 审计修复：S3 场景优先用精确文案（副S3冲突·CVD/OI背离）。
        _dv = str(dual.get("direction_verdict") or "")
        return _dv if _dv.startswith("副S3") else "主副强冲突"
    if bool(dual.get("conflict")):
        return "主副冲突·等待"
    if state in {"WAIT", "NO-GO"} and not bool(final.get("executable")):
        return "主指标等待/禁做"
    return str(dual.get("direction_verdict") or dual.get("flow_verdict") or "主副待读")


def _final_is_executable(final: dict) -> bool:
    """Defensively verify the canonical execution tuple before rendering it."""
    if str(final.get("state") or "").upper() != "GO-A" or final.get("executable") is not True:
        return False
    try:
        entry, stop, target = (float(final[key]) for key in ("entry", "stop", "target"))
    except (KeyError, TypeError, ValueError):
        return False
    side = str(final.get("side") or "").lower()
    grade = str(final.get("grade") or "")
    side_matches = (side == "long" and grade.startswith("A多")) or (side == "short" and grade.startswith("A空"))
    geometry_ok = (side == "long" and stop < entry < target) or (side == "short" and stop > entry > target)
    if not side_matches or not geometry_ok:
        return False
    if not all(math.isfinite(v) and v > 0 for v in (entry, stop, target)):
        return False
    actual_rr = abs(target - entry) / abs(entry - stop)
    try:
        declared_rr = float(final["rr"]) if "rr" in final else actual_rr
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(actual_rr) and actual_rr >= 2 and math.isfinite(declared_rr) and declared_rr >= 2


# Both card paths share the same defensive execution boundary.
final_is_executable = _final_is_executable


def _matrix_line(main: dict) -> str:
    """裁决矩阵一行：结论 + 理由 + 解除条件（没有就不占行）。"""
    if not isinstance(main, dict):
        return ""
    final = main.get("_final_verdict") if isinstance(main.get("_final_verdict"), dict) else {}
    syn = main.get("synthesis") if isinstance(main.get("synthesis"), dict) else {}
    verdict = str(final.get("matrix_verdict") or syn.get("verdict") or "")
    if not verdict:
        return ""
    reason = str(final.get("matrix_reason") or syn.get("reason") or "")
    head = f"⚖ 裁决：{verdict}"
    if verdict == "A执行":
        rr = syn.get("rr") or {}
        tail = str(rr.get("text") or "") if isinstance(rr, dict) else ""
        return _clean_text(f"{head} · {reason}" + (f" · {tail}" if tail else ""), 150)
    parts = [head]
    if reason:
        parts.append(_clean_text(reason, 52))
    rel = str(main.get("release_text") or "")
    if rel:
        parts.append(f"解除：{_clean_text(rel, 96)}")
    return _clean_text(" · ".join(parts), 200)


def render_tv_card(main: dict | None = None, sub: dict | None = None, symbol: str = "BTCUSDT", price: float = 0, mode: str = "push") -> str:
    main = main or {}
    sub = sub or {}
    final = main.get("_final_verdict") if isinstance(main, dict) else None
    executable = False
    if not isinstance(final, dict):
        # Direct renderer calls are untrusted compatibility inputs. Without
        # the canonical FinalVerdict, legacy grade/price fields must never
        # become an executable order card.
        main = dict(main)
        main["grade"] = "C等待"
        main["treatment"] = "FinalVerdict缺失·仅观察"
        for key in ("entry", "stop", "target", "进场", "止损", "目标", "position"):
            main.pop(key, None)
        main["_executable"] = False
    if isinstance(final, dict):
        main = dict(main)
        main["grade"] = final.get("grade") or main.get("grade") or "C等待"
        main["treatment"] = final.get("reason") or main.get("treatment") or ""
        executable = _final_is_executable(final)
        if executable:
            main["entry"], main["stop"], main["target"] = final.get("entry"), final.get("stop"), final.get("target")
        else:
            # WAIT/NO-GO must never render stale execution prices.  A B/C
            # observation candidate is carried by the verdict's watch tuple
            # only; raw panel/DW prices are dropped here, not re-labelled.
            main.pop("entry", None)
            main.pop("stop", None)
            main.pop("target", None)
            main.pop("进场", None)
            main.pop("止损", None)
            main.pop("目标", None)
            main.pop("candidate_entry", None)
        main["_executable"] = executable
        # B/C 观察候选只在 WAIT + B/C 等级 + 完整 watch 元组三者同时成立时渲染。
        if (not executable
                and str(final.get("state") or "").upper() == "WAIT"
                and str(final.get("grade") or "").startswith(OBSERVATION_GRADES)):
            main["_candidate"] = _candidate_view(final)
        else:
            main["_candidate"] = {}

    grade = main.get("grade", "C等待")
    treatment = main.get("treatment", "")
    vwap = main.get("vwap")
    vah = main.get("vah")
    val = main.get("val")
    poc = main.get("poc")
    entry = main.get("entry") or main.get("进场")
    stop = main.get("stop") or main.get("止损")
    target = main.get("target") or main.get("目标")
    magnet_up = main.get("magnet_up") or main.get("磁吸↑")
    magnet_down = main.get("magnet_down") or main.get("磁吸↓")
    check = main.get("check") or main.get("核对")
    dual = main.get("_dual") or {}

    signal = sub.get("signal", "")
    conclusion = sub.get("conclusion", "")
    htf = sub.get("htf", "")
    oi_status = sub.get("oi", "")
    cvd_flow = sub.get("cvd_flow", "")
    vol_status = sub.get("volume", "")
    share_data = sub.get("share", "") or sub.get("coverage", "") or sub.get("risk", "")
    liq_data = sub.get("liquidation", "")
    operation = sub.get("operation", "")

    direction = "观望"
    if str(grade).startswith(("A多", "A空")) and executable:
        direction = "做多" if str(grade).startswith("A多") else "做空"
    # B多/B空/C反多/C反空 一律观望等触发（P0-1 2026-08-31：B/C反无自动执行权）

    if mode == "push":
        return _render_push(symbol, price, grade, direction, treatment, signal, conclusion, htf, oi_status, cvd_flow, vol_status, share_data, liq_data, vwap, vah, val, poc, operation, entry, stop, target, magnet_up, magnet_down, check, main, sub, dual)
    return _render_full(symbol, price, grade, direction, treatment, signal, conclusion, htf, oi_status, cvd_flow, vol_status, share_data, liq_data, vwap, vah, val, poc, operation, entry, stop, target, magnet_up, magnet_down, check, main, sub, dual)


def _render_push(symbol, price, grade, direction, treatment, signal, conclusion, htf, oi_status, cvd_flow, vol_status, share_data, liq_data, vwap, vah, val, poc, operation, entry, stop, target, magnet_up, magnet_down, check, main, sub, dual) -> str:
    short_sym = symbol.replace("USDT", "").replace(".P", "")
    tf_line = _tf_mini(main, symbol)
    conclusion_clean = _clean_text(main.get("conclusion") or main.get("结论") or treatment or conclusion or signal) or "待确认"
    entry_clean = _clean_text(entry, 22) if entry else _fmt_num(price)
    stop_clean = _clean_text(stop, 18) if stop else "—"

    target_clean = _clean_text(target, 22) if target else "—"
    magnet_up_clean = _clean_text(magnet_up, 18) if magnet_up and magnet_up != "--" else "—"
    magnet_down_clean = _clean_text(magnet_down, 18) if magnet_down and magnet_down != "--" else "—"
    dual_verdict = _clean_text(_dual_verdict_for_final(main, dual), 18) if isinstance(dual, dict) else "主副待读"

    # Telegram mobile layout: one visual hierarchy, narrow tables, and no
    # standalone heading immediately before a RichMarkdown table block.
    # Keep the first screen actionable instead of repeating the same verdict
    # in four different sections.
    high = main.get("high") if isinstance(main, dict) else None
    low = main.get("low") if isinstance(main, dict) else None
    change = main.get("change_pct") if isinstance(main, dict) else None
    quote_line = f"现价 `{_fmt_num(price)}`"
    if high not in (None, "") and low not in (None, ""):
        quote_line += f" · 日高 `{_fmt_num(high)}` · 日低 `{_fmt_num(low)}`"
    if change not in (None, ""):
        try:
            quote_line += f" · {float(change):+.2f}%"
        except (TypeError, ValueError):
            quote_line += f" · {_clean_text(change)}"
    lines = [
        f"📊 {short_sym} · {_now_chinese()}",
        f"{_dir_icon(direction)}{direction} · {_grade_icon(grade)}{grade}",
        f"**{conclusion_clean}**",
        quote_line,
        tf_line,
        *_chart_evidence_lines(main),
        "",
        _level_table(vwap, vah, val, poc, price),
        "",
        "| 执行 | 触发/价格 | 风险与目标 |",
        "|:---|:---|:---|",
    ]
    decision_line = _decision_line(main)
    if decision_line:
        lines.insert(4, decision_line)
    if direction == "做多":
        lines.append(f"| ⭐主推 多 | {entry_clean} | 损{stop_clean} · 标{target_clean} |")
        lines.append(f"| 🔁失效看空 | {magnet_up_clean} | 主推失效后再看 |")
    elif direction == "做空":
        lines.append(f"| ⭐主推 空 | {entry_clean} | 损{stop_clean} · 标{target_clean} |")
        lines.append(f"| 🔁失效看多 | {magnet_down_clean} | 主推失效后再看 |")
    else:
        _cand = main.get("_candidate")
        candidate = _cand if isinstance(_cand, dict) else {}
        _final = main.get("_final_verdict")
        final_state = str((_final.get("state") if isinstance(_final, dict) else "") or "").upper()
        if final_state == "NO-GO" or str(grade).startswith("X"):
            lines.append("| ⭐主推 禁做 | 禁做 | 不出价 · 不追单 |")
        elif candidate.get("entry"):
            rr_value = candidate.get("rr")
            rr_text = f" · R:R 1:{rr_value:.2f}" if isinstance(rr_value, (int, float)) and rr_value > 0 else ""
            lines.append(
                f"| ⭐主推 等待 | 【人工候选，未授权】 | "
                f"入`{_fmt_num(candidate['entry'])}` · 止`{_fmt_num(candidate['stop'])}` · "
                f"标`{_fmt_num(candidate['target'])}`{rr_text} |"
            )
        elif candidate.get("incomplete"):
            lines.append("| ⭐主推 等待 | 等待确认 | 候选数据不完整 |")
        else:
            lines.append("| ⭐主推 等待 | 等待确认 | 不追现价 |")
        lines.append("| 🔁反向观察 | 主推失效后复核 | 不自动转向 |")
    lines.append("| ⚠️禁止 | 追单/冲突 | 主副不共振不做 |")
    lines.append("")
    # Evidence stays as short labeled lines.  The screenshot carries the
    # detailed indicator view; the Telegram text card should remain a quick
    # decision companion rather than a second full report.
    # SVP 行只放人能读的理由：FinalVerdict.reason 是机器码（location/trigger/…），
    # 直接上卡等于把内部枚举丢给用户。有中文原因链就用它。
    _reason_cn = str(main.get("no_trade_reasons") or "").strip()
    svp_line = _clean_text(str(grade) + ' ' + (_reason_cn or treatment or ''), 40)
    hal_line = _clean_text((signal or ''), 24)
    flow_parts = []
    if oi_status: flow_parts.append(f"持仓{_clean_text(oi_status, 12)}")
    if cvd_flow: flow_parts.append(f"CVD{_clean_text(cvd_flow, 12)}")
    if vol_status: flow_parts.append(f"量{_clean_text(vol_status, 10)}")
    if share_data: flow_parts.append(f"覆盖{_clean_text(share_data, 10)}")
    _ml = _matrix_line(main)
    lines.append(f"SVP：{svp_line} · {dual_verdict}")
    # 只有「风控」行标签（SVP 唯一授权出口）或可执行裁决才允许卡面出现下单
    # 价位；观察/未授权/禁做计划里的 入/止/标 一律剥掉，避免被当成可下单的数。
    risk_label = str(main.get("risk_label") or "").strip()
    plan_authorized = (not risk_label and main.get("_executable") is True) or risk_label == SVP_AUTHORIZATION_LABEL
    for label, key in (
        ("位置", "position"), ("方向", "direction_text"), ("路径", "path"),
        ("风控", "risk"), ("SVP CVD", "cvd_state"), ("SVP OI", "oi_state"),
        ("协同", "sync"), ("结构", "structure"), ("磁吸↑", "magnet_up"),
        ("磁吸↓", "magnet_down"), ("前位（仅背景）", "prev_level"),
        ("风控原因", "no_trade_reasons"), ("解除", "release_text"),
    ):
        value = main.get(key)
        if key in ("path", "risk") and not plan_authorized:
            value = _redact_order_prices(value)
        if value:
            lines.append(f"{label}：{_clean_text(value)}")
    for label, value in (("信号", signal), ("结论", conclusion), ("操作", operation)):
        if value:
            lines.append(f"AggVol {label}：{_clean_text(value)}")
    if _ml:
        lines.append(_ml)
    lines.append(f"订单流：{' · '.join(flow_parts) or '待采集'}")
    lines.append("口径：当前所估算CVD≠5所主动流；OI≠人数；失衡≠爆仓")
    source_line = _source_summary(main)
    if source_line:
        source_line = source_line.replace("来源 ", "")
        lines.append(f"数据状态：{_clean_text(source_line, 52)}")
    verdict_text = f"{_dir_icon(direction)}{direction}" if direction != "观望" else "🔵等确认"
    lines.extend([
        "",
        f"**下一步**：{_clean_text(main.get('now_level') or main.get('现位') or (verdict_text + ' · 不追单'))}",
        f"**失效**：{_clean_text(check or '结构位失效后重算', 42)}",
    ])
    return "\n".join(lines) + "\n"


def _render_full(symbol, price, grade, direction, treatment, signal, conclusion, htf, oi_status, cvd_flow, vol_status, share_data, liq_data, vwap, vah, val, poc, operation, entry, stop, target, magnet_up, magnet_down, check, main, sub, dual) -> str:
    level_tbl = _level_table(vwap, vah, val, poc, price)
    lines = [
        f"📊 {symbol} · {_now_chinese()} · {_grade_icon(grade)}{grade}",
        "【结构位】",
        level_tbl,
        "【决策摘要】",
        "| 维度 | 内容 |",
        "|:---|:---|",
        f"| 主推 | {_dir_icon(direction)}{direction} · {_clean_text(treatment or operation or conclusion, 34)} |",
        f"| 裁决 | {_dir_icon(direction)}{direction} · 主副指标已纳入 · 不再只看单行信号 |",
        "",
        "① 多周期定位（D→4h→1h→15m→5m）",
        _tf_mini(main, symbol),

        "② 双指标",
        "| 指标 | 读数 | 裁决 |",
        "|:---|:---|:---|",
        f"| SVP主驾驶 | {_clean_text(str(grade) + ' ' + (treatment or ''), 34)} | 结构/执行优先 |",
        f"| HALDRO副驾驶 | {_clean_text((signal or '') + ' ' + (operation or ''), 38)} | {_clean_text(_dual_verdict_for_final(main, dual) if isinstance(dual, dict) else '待判', 18)} |",
        "",
        "③ 结构位",
        "| 结构 | 价格 | 用法 |",
        "|:---|:---:|:---|",
        f"| VAH | `{_fmt_num(vah)}` | 上沿/阻力 |",
        f"| VWAP | `{_fmt_num(vwap)}` | 均价锚 |",
        f"| POC | `{_fmt_num(poc)}` | 成交密集 |",
        f"| VAL | `{_fmt_num(val)}` | 下沿/支撑 |",
        "",
        "④ 最推荐方案",
        "| 优先级 | 条件 | 动作 |",
        "|:---|:---|:---|",
    ]
    source_line = _source_summary(main)
    if source_line:
        lines.insert(8, source_line)
    if direction == "做多":
        lines.append(f"| ⭐主推 多 | {entry or '—'} | 多 损{stop or '—'} 标{target or '—'} |")
        lines.append(f"| 🔁备选 空 | {magnet_up or '主推失效'} | 只作失效路径 |")
    elif direction == "做空":
        lines.append(f"| ⭐主推 空 | {entry or '—'} | 空 损{stop or '—'} 标{target or '—'} |")
        lines.append(f"| 🔁备选 多 | {magnet_down or '主推失效'} | 只作失效路径 |")
    else:
        if str(grade).startswith(("B多", "B空", "C反多", "C反空")):
            # P0-1 (2026-08-31): B/C反 只渲染触发条件+人工候选价，禁止"损/标"执行指令
            _trigger = _clean_text(treatment or "等结构位触发", 34)
            _cand = main.get("candidate_entry") or "—"
            lines.append(f"| 🔵主推 等 | {_trigger} | 候选 {_cand}·人工判断 |")
        else:
            lines.append("| 🔵主推 等 | — | 等结构位确认 |")
        lines.append("| 🔁备选 | 反向破位 | 只作失效路径 |")
    lines.append("| ⚠️禁止 | 追单/主副冲突 | 不做 |")
    lines.append("")
    return "\n".join(lines) + "\n"


def _unwrap_tv_tables(raw: dict) -> list:
    tables_flat = []
    studies = raw.get("studies", []) if isinstance(raw, dict) else []
    if isinstance(studies, list):
        for s in studies:
            s_name = s.get("name", "")
            for t in s.get("tables", []) or []:
                rows = t.get("rows", []) if isinstance(t, dict) else []
                if rows:
                    tables_flat.append({"name": s_name, "rows": rows})
    if not tables_flat and isinstance(raw, dict):
        for t in raw.get("tables", []) or []:
            rows = t.get("rows", []) if isinstance(t, dict) else []
            if rows:
                tables_flat.append({"name": t.get("name", ""), "rows": rows})
    return tables_flat


def _parse_table_rows(rows: list) -> dict:
    result = {}
    for row_text in rows:
        row_str = str(row_text)
        if " | " in row_str:
            parts = row_str.split(" | ", 1)
        elif "｜" in row_str:
            parts = row_str.split("｜", 1)
        elif "：" in row_str:
            parts = row_str.split("：", 1)
        else:
            continue
        if len(parts) == 2:
            result[parts[0].strip()] = parts[1].strip()
    return result


def extract_from_tv_data(tv_data: dict) -> tuple[dict, dict]:
    main, sub = {}, {}
    for s in tv_data.get("studies", []) if isinstance(tv_data, dict) else []:
        name = s.get("name", "")
        vals = s.get("values", {}) or {}
        if "SVP" in name or "ICT" in name or "CVD" in name or "VWAP" in name:
            for k, v in vals.items():
                kk = k.lower().replace(" ", "_").replace("%", "pct")
                try:
                    main[kk] = float(str(v).replace("−", "-").replace(",", ""))
                except Exception:
                    main[kk] = str(v)
        if "Volume" in name and ("Aggregated" in name or "Spot" in name):
            for k, v in vals.items():
                kk = k.lower().replace(" ", "_").replace("%", "pct")
                sub[kk] = v
    for src_key, dst_key in [("s_vwap", "vwap"), ("vah_price", "vah"), ("val_price", "val"), ("poc_price", "poc")]:
        if src_key in main and dst_key not in main:
            main[dst_key] = main[src_key]
    for t in _unwrap_tv_tables(tv_data):
        parsed = _parse_table_rows(t.get("rows", []))
        if ("结论" in parsed and ("方向" in parsed or "进场" in parsed)) or "等级" in parsed:
            main.update(parsed)
            grade_raw = main.get("等级", "")
            if not grade_raw:
                conc = main.get("结论", "")
                for p in ("A多", "A空", "B多", "B空", "C反多", "C反空", "C等待", "X"):
                    if str(conc).startswith(p):
                        grade_raw = p
                        break
            main["grade"] = grade_raw or "C等待"
            main.setdefault("treatment", main.get("结论", ""))
            main.setdefault("entry", main.get("进场", ""))
            main.setdefault("stop", main.get("止损", ""))
            main.setdefault("target", main.get("目标", ""))
            main.setdefault("magnet_up", main.get("磁吸↑", ""))
            main.setdefault("magnet_down", main.get("磁吸↓", ""))
            main.setdefault("check", main.get("核对", ""))
        elif "信号" in parsed and "操作" in parsed:
            sub.update(parsed)
            sub.setdefault("signal", sub.get("信号", ""))
            sub.setdefault("conclusion", sub.get("结论", ""))
            sub.setdefault("htf", sub.get("高周", ""))
            sub.setdefault("oi", sub.get("持仓", ""))
            sub.setdefault("cvd_flow", sub.get("流向", ""))
            sub.setdefault("volume", sub.get("量能", ""))
            sub.setdefault("coverage", sub.get("覆盖", ""))
            sub.setdefault("risk", sub.get("风险", ""))
            sub.setdefault("share", sub.get("覆盖", ""))
            sub.setdefault("liquidation", sub.get("爆仓", ""))
            sub.setdefault("operation", sub.get("操作", ""))
    return main, sub


if __name__ == "__main__":
    demo_main = {"grade":"A空","treatment":"反抽失败优先空","vwap":63342,"vah":63194,"val":62558,"poc":62876,"entry":"62,880反抽不过","stop":"63,380","target":"61,780","magnet_down":"62,558","_klines":{"D":{"description":"偏空"},"4h":{"description":"偏空"},"1h":{"description":"偏空"},"15m":{"description":"偏空"},"5m":{"description":"等待"}},"_dual":{"direction_verdict":"主副同向"}}
    demo_sub = {"signal":"🔴 偏空 · 4/4共振","conclusion":"真实下跌 · 新空进场","oi":"新空进场","cvd_flow":"卖盘占优","volume":"放量","coverage":"聚合5/5","operation":"配合主指标 A空 = 可做"}
    print(render_tv_card(demo_main, demo_sub, "BTCUSDT", 62880, "push"))
