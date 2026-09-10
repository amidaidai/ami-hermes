#!/usr/bin/env python3
"""棠溪 · 裁决矩阵 v13（2026-09-10）

把三件过去只写在文档里的规则落成可执行判定：

1. **解除条件清单** —— `MCP NoTrade Reason Code` 的每个置位对应「要等什么才解除」。
   回答用户每天问的那句：「现在是 A 禁，那我到底在等什么？」
2. **R:R 档位** —— 对齐指标侧 `rrHardOk>=2.0` / `bcDirectOk>=1.5`，
   把「这个 R:R 到底够不够做 A」变成结论而不是让模型自己算。
3. **主副合成裁决（九宫格）** —— 主指标等级 × 副指标状态码 S0-S4。

铁律（不可违）
--------------
- 主指标是唯一执行授权源；副指标**只能确认 / 降权 / 否决**，永远不能把 B/C 提成 A。
- 优先级：`X > WAIT > A > B/C`。X 与 WAIT 一律清空执行三件套。
- 非加密品种副指标不参与（不得把加密订单流逻辑套到 XAU/外汇/股票）。
- 合成只允许**往保守方向调**（降级/否决），不允许升级。
"""

from __future__ import annotations

from typing import Any

try:
    from tv_indicator_contract import (
        NO_TRADE_BITS, RR_HARD_MIN, RR_BC_MIN,
        decode_haldro_state, decode_no_trade, rr_gate,
    )
except Exception:  # pragma: no cover - 契约缺失时退化，不阻断出卡
    NO_TRADE_BITS = {}
    RR_HARD_MIN, RR_BC_MIN = 2.0, 1.5

    def decode_no_trade(_c): return []

    def decode_haldro_state(_c): return "缺失"

    def rr_gate(_r): return "R:R缺失"


MATRIX_VERSION = "v13"

# ── 1. 解除条件 ──────────────────────────────────────────────────────
# 每个位对应一个「可验证的等待条件」，不是安慰话术。
# 判定标准：这句话必须能让用户回答「现在满足了吗」。
RELEASE_ACTIONS: dict[int, str] = {
    1: "等 HTF 与本级同向（HTF 冲突解除）",
    2: "等过热回落（回到结构位/ATR 正常范围）",
    4: "等流动性窗口（避开低流动时段）",
    8: "等价格几何成立（入场位与止损位顺序正确、贴近结构位）",
    16: f"等 R:R ≥ {RR_HARD_MIN}（等更近的入场或更远的目标）",
    32: "等 CVD 质量达标（采样源恢复/连续性满足）",
    64: "等 ADR 空间打开（当日波动耗尽解除，隔日再看）",
    128: "等溢价/折价回到允许侧",
    256: "等本根收线（K 未收盘不算）",
    512: "等新触发出现（旧触发已过期，别追）",
    1024: "先修副指标总线（主指标「免费版唯一总线」指向 Basic Packed Bus）",
}

# 这些位属于「本根就能好」的临时项，与「要等行情」的结构项分开列
TRANSIENT_BITS = {256, 512, 1024}


def release_plan(code) -> list[dict[str, Any]]:
    """位掩码 → 解除条件清单（按位序，标注是临时项还是结构项）。"""
    bits = [b for b in sorted(NO_TRADE_BITS) if _bit_set(code, b)]
    return [
        {
            "bit": b,
            "reason": NO_TRADE_BITS.get(b, f"未知位{b}"),
            "release": RELEASE_ACTIONS.get(b, "—"),
            "transient": b in TRANSIENT_BITS,
        }
        for b in bits
    ]


def _bit_set(code, bit: int) -> bool:
    n = _as_int(code)
    return bool(n and n > 0 and (n & bit))


def _as_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(str(value).replace("−", "-").replace(",", "").strip())))
    except (TypeError, ValueError):
        return None


def format_release(code, sep: str = "；") -> str:
    """一行版解除条件（临时项在前，便于先做能立刻做的）。"""
    plan = release_plan(code)
    if not plan:
        return ""
    plan.sort(key=lambda p: (not p["transient"], p["bit"]))
    return sep.join(p["release"] for p in plan)


# ── 2. R:R 档位 ──────────────────────────────────────────────────────

def rr_tier(rr) -> dict[str, Any]:
    """R:R → 档位结论。对齐指标侧 rrHardOk / bcDirectOk。"""
    try:
        v = float(str(rr).replace("−", "-")) if rr not in (None, "") else None
    except (TypeError, ValueError):
        v = None
    if v is None:
        return {"value": None, "tier": "缺失", "a_ok": False, "bc_ok": False,
                "text": "R:R缺失（不给执行价）"}
    return {
        "value": v,
        "tier": "A级" if v >= RR_HARD_MIN else "B/C" if v >= RR_BC_MIN else "不足",
        "a_ok": v >= RR_HARD_MIN,
        "bc_ok": v >= RR_BC_MIN,
        "text": rr_gate(v),
    }


# ── 3. 主副合成裁决（九宫格）─────────────────────────────────────────

SUB_ROLE = {
    "confirm": "确认",
    "veto": "否决（硬阻断）",
    "degrade": "降权",
    "absent": "未接/无效",
    "n/a": "不参与（非加密）",
}


def _side_of(grade: str) -> int:
    """A多/B多/C反多 → +1；A空/B空/C反空 → -1；其余 0。"""
    g = str(grade or "")
    if g.startswith("X"):
        return 0
    if "多" in g:
        return 1
    if "空" in g:
        return -1
    return 0


def synthesis_verdict(
    *,
    main_grade: str,
    haldro_state=None,
    haldro_valid=None,
    rr=None,
    is_crypto: bool = True,
) -> dict[str, Any]:
    """主指标等级 × 副指标状态 → 最终裁决。

    返回 dict：
      verdict        最终裁决（A执行 / A降级候选 / 不执行·副冲突 / B/C人工候选 / C等待 / X禁做）
      authority      这次裁决由谁定
      sub_role       副指标扮演了什么角色
      executable     bool，是否可给执行三件套
      hard_block     bool，是否硬阻断（副冲突）
      rr             R:R 档位 dict
      reason         一句话理由
    """
    grade = str(main_grade or "").strip()
    rr_info = rr_tier(rr)
    state = _as_int(haldro_state)
    valid = _as_int(haldro_valid)

    # 非加密：副指标完全不参与
    if not is_crypto:
        verdict = _base_verdict(grade)
        return _pack(verdict, "主指标（副指标不参与）", "n/a", rr_info,
                     hard_block=False, reason="非加密品种·副指标不参与")

    sub_reported = state is not None and state != 0
    sub_usable = bool(valid is not None and valid >= 1 and sub_reported)

    # 副指标没接上/无效：按降权处理，且必须显式说明（不能假装副指标同意）
    if not sub_usable:
        base = _base_verdict(grade)
        if base in ("A执行",):
            return _pack("A降级候选", "主指标（副未接·降权）", "absent", rr_info,
                         hard_block=False, reason="副指标未接/S0无效 → A 降权为人工候选")
        return _pack(base, "主指标（副未接）", "absent", rr_info,
                     hard_block=False, reason=f"副指标未接/S0无效（{decode_haldro_state(state)}）")

    side = _side_of(grade)
    aligned = (side == 1 and state == 1) or (side == -1 and state == 2) or side == 0

    # 副指标否决：只对「方向明确的主 A」构成硬阻断
    if state == 3:
        base = _base_verdict(grade)
        if base == "A执行":
            return _pack("不执行·副冲突", "副指标否决", "veto", rr_info, hard_block=True,
                         reason=f"主{grade} vs 副S3冲突 → 硬阻断（副指标只可否决，不可升级）")
        return _pack(base, "主指标（副S3冲突·降级提示）", "degrade", rr_info, hard_block=False,
                     reason=f"副S3冲突，主{grade} 本就非 A，维持原级但标注冲突")

    # 副指标降权
    if state == 4:
        base = _base_verdict(grade)
        if base == "A执行":
            return _pack("A降级候选", "副指标降权", "degrade", rr_info, hard_block=False,
                         reason="副S4降权 + 主A → 降为人工候选，不给 A 级授权")
        return _pack(base, "主指标（副S4降权）", "degrade", rr_info, hard_block=False,
                     reason="副S4降权，维持主指标原级")

    # 副指标确认
    base = _base_verdict(grade)
    if base == "A执行" and aligned:
        return _pack("A执行", "主指标 + 副指标确认", "confirm", rr_info, hard_block=False,
                     reason=f"主A + 副{decode_haldro_state(state)}顺向 + {rr_info['text']}")
    if base == "A执行" and not aligned:
        return _pack("A降级候选", "主指标（副反向）", "degrade", rr_info, hard_block=False,
                     reason=f"主A 与 副{decode_haldro_state(state)} 反向 → 降为人工候选")
    if base == "B/C人工候选" and aligned and rr_info["bc_ok"]:
        return _pack("B/C人工候选", "主指标 + 副指标确认", "confirm", rr_info, hard_block=False,
                     reason=f"主{grade} + 副确认 + {rr_info['text']} → 给触发条件与候选价，不给执行指令")
    return _pack(base, f"主指标（副{decode_haldro_state(state)}）", "confirm" if aligned else "degrade",
                 rr_info, hard_block=False, reason=f"主{grade} · 副{decode_haldro_state(state)}")


def _base_verdict(grade: str) -> str:
    """主指标等级 → 基础裁决（不含副指标）。"""
    g = str(grade or "").strip()
    if g.startswith("X"):
        return "X禁做"
    if not g or g in ("?", "待判") or "等待" in g:
        return "C等待"
    if g.startswith("A"):
        return "A执行"
    if g.startswith(("B", "C")):
        return "B/C人工候选"
    return "C等待"


def _pack(verdict, authority, sub_role, rr_info, *, hard_block, reason) -> dict[str, Any]:
    return {
        "matrix_version": MATRIX_VERSION,
        "verdict": verdict,
        "authority": authority,
        "sub_role": SUB_ROLE.get(sub_role, sub_role),
        "executable": verdict == "A执行",
        "hard_block": bool(hard_block),
        "rr": rr_info,
        "reason": reason,
    }


def format_synthesis(syn: dict, release_code=None, sep: str = " · ") -> str:
    """一行版合成裁决，供卡片渲染。"""
    if not isinstance(syn, dict) or not syn.get("verdict"):
        return ""
    parts = [f"{syn['verdict']}（{syn['authority']}）"]
    if syn.get("reason"):
        parts.append(syn["reason"])
    release = format_release(release_code) if release_code is not None else ""
    if release and syn.get("verdict") in ("X禁做", "C等待", "不执行·副冲突", "A降级候选"):
        parts.append(f"解除：{release}")
    return sep.join(parts)
