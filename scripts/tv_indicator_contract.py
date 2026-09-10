#!/usr/bin/env python3
"""棠溪 · 双指标 TV 接口契约 v13（2026-09-10）

为什么要有这个文件
------------------
v13 之前，「指标 DW 字段名 / 行动格行名」被硬编码在至少三处
（auto_card._tv_cache_indicators_to_studies、auto_card._build_tv_main_data、
 tv_data_bridge 的别名表），三处各自漂移，结果：
  - 主指标 v13 的 13 行里只有 4 行能被卡片吃到（其余静默丢弃）
  - 副指标 DW 的 `OI Total` / `Estimated CVD Value` 等早已不存在，映射恒空
所以把「唯一权威接口」收到这里，其它模块一律引用本文件，不再自写字符串。

权威来源
--------
- 主指标：`SVP_主指标_优化v13_清理死码_20260910.pine`（sha256[:24]=98d6338b4cb77e5d4e56e5e4）
- 副指标：`AggVol_副指标_优化v13_清理死码_20260910.pine`（sha256[:24]=9f71366943a2d773ccb0c1c4）
- 行名取自实盘 Pine table 读取；DW 名取自两份源码的 plot(title=)

变更纪律
--------
指标侧改行名/字段名后，**必须先改本文件**，再改消费方；
`LEGACY_*` 一律只增不删，保证旧缓存与历史测试不被打断。
"""

from __future__ import annotations

import re

CONTRACT_VERSION = "v13"

# ── 1. 行动格行名（顺序 = 面板渲染顺序，卡片按此顺序输出）────────────

# 主指标 SVP v13：13 行。相对旧 10 行的变化：
#   删掉 进场/止损/目标/确认/核对（价格与 R:R 并入「风控」行，
#   `入X·止Y·n.nA·标Z·n.nR`），新增 位置/路径/CVD/OI/协同/结构/前位/现位。
MAIN_ROW_LABELS = [
    "位置", "结论", "方向", "路径", "风控", "CVD", "OI",
    "协同", "结构", "磁吸↑", "磁吸↓", "前位", "现位",
]

# 副指标 AggVol v13：6 行。旧的 风险/高周/覆盖/爆仓 已并入其它行或删除。
SUB_ROW_LABELS = ["信号", "结论", "流向", "持仓", "量能", "操作"]

# 旧行名白名单：只用于兼容历史缓存，不再出现在新面板里。
LEGACY_MAIN_ROWS = ["进场", "止损", "目标", "确认", "核对", "风险", "背景", "执行", "等级", "处理"]
LEGACY_SUB_ROWS = ["风险", "高周", "覆盖", "占比", "爆仓"]

# 卡片缓存合成行（由 grade/treatment 生成，不是指标输出）
SYNTH_ROWS = ["等级", "处理"]

# 「风控」行可能带动态授权等级标签：风控 / 风控·观察 / 风控·未授权 / 禁做·不出价
RISK_ROW_VARIANTS = ["风控", "风控·观察", "风控·未授权", "禁做·不出价"]

# ── 2. Data Window 字段（v13 实测全量）────────────────────────────────

DW_MAIN = [
    "S VWAP", "S VWAP +Band1", "S VWAP -Band1",
    "EMA 9", "EMA 21", "EMA 34", "EMA 55",
    "MCP Side Code", "MCP Grade Code", "MCP Setup Score",
    "MCP Entry Price", "MCP Stop Price", "MCP Target Price",
    "MCP CVD Method Code (0=不参与决策,2=lower-TF estimate,1=bar estimate)",
    "MCP Quality Code", "MCP FVG Quality Score", "MCP OB Quality Score",
    "MCP Entry Valid Code", "MCP RR Ratio", "MCP NoTrade Reason Code",
    "MCP Execution Pack", "MCP Trigger Pack", "MCP Regime Pack", "MCP Contract Pack",
    "MCP Evidence Pack", "MCP Evidence Bar Time", "MCP Evidence Close Time",
    "MCP StructPack (FvgQ*10000+(OB+1)*100+(BOS+2)*10+(LV+1))",
    "POC Price", "VAH Price", "VAL Price", "nPOC Price",
    "W VWAP Price", "M VWAP Price", "DO Price",
]

DW_SUB = [
    "HALDRO Valid Code", "OI Change % (Normalized)",
    "OI Price Direction (same ACT_LB: 1涨/-1跌)",
    "CVD Value", "CVD Method Code (1=当前所K线方向/2=当前所1m方向)",
    "CVD Quality Code", "LSR", "Volume Ratio",
    "Coverage Exchanges", "Coverage Spot", "Coverage Perp", "Coverage Feed Mode",
    "Exchange Dominance %", "Confirm Score",
    "Basic Packed Bus (唯一主副连接)",
    "HALDRO State Pack (0无效/1支持多/2支持空/3冲突/4降权)",
    "HALDRO Risk Code", "OI Breadth", "OI Agreement %",
    "HALDRO OI Pack (方向*100+一致%)", "OI Dispersion Ratio",
    "HALDRO Freshness Pack", "Stale Venue Count (连续缺失>=3K)",
    "HALDRO Contract Pack", "HALDRO Flow Pack (OI*100+CVD*10+SP)",
    "Composite", "CVD Anchor Value",
]

# v13 新增、旧消费方完全没接的决策级字段（本轮接入重点）
NEW_IN_V13 = {
    "MCP RR Ratio": "R:R 比值；硬闸 rrHardOk = rrRatio >= 2.0，B/C 直通闸 >= 1.5",
    "MCP Entry Valid Code": "入场有效性 -3..3，见 ENTRY_VALID",
    "MCP NoTrade Reason Code": "禁做/降级原因的位掩码，见 NO_TRADE_BITS（最有价值）",
    "MCP Execution Pack": "priceGeom*1e6 + confirmed*1e5 + stopATR*10 + (entryValid+3)",
    "MCP Trigger Pack": "(triggerCode+10)*1e5 + age*100 + fresh*10 + (signalState+1)",
    "MCP Regime Pack": "regimeCode*1e4 + preferredModel*100 + confidence",
    "MCP Contract Pack": "171000 + marketCode*10 + 1（市场身份校验）",
    "MCP Evidence Pack": "证据包版本戳",
    "MCP Evidence Bar Time": "证据K线开盘时间（ms）",
    "MCP Evidence Close Time": "证据K线收盘时间（ms）",
    "Basic Packed Bus (唯一主副连接)": "主副唯一总线（合同号 22002）",
    "HALDRO State Pack (0无效/1支持多/2支持空/3冲突/4降权)": "副指标状态码 S0-S4",
    "OI Price Direction (same ACT_LB: 1涨/-1跌)": "同窗口 OI 与价格方向",
    "OI Breadth": "四所多空扩张广度差",
    "HALDRO OI Pack (方向*100+一致%)": "OI 方向*100 + 一致度%",
    "OI Dispersion Ratio": "四所 OI 离散度",
    "HALDRO Freshness Pack": "各源新鲜度包",
    "Stale Venue Count (连续缺失>=3K)": "连续缺失 >=3 根的源数量",
    "CVD Anchor Value": "当前 CVD 锚值",
}

# 已废止的 DW 名（保留映射只为不打断历史缓存/测试；命中即为空，属预期）
LEGACY_DW_ONLY = [
    "MCP CVD Value", "MCP EMA Length 1", "MCP EMA Length 2",
    "MCP EMA Length 3", "MCP EMA Length 4",
    "MCP Risk Pack (Risk%*10000+DailyLoss%*100+WeeklyLoss%)",
    "MCP Bull FVG CE", "MCP Bear FVG CE", "OI Total", "Estimated CVD Value",
]

# ── 3. snake_case → DW 名（tv_data_bridge 缓存反查用）─────────────────

# 主指标：值 = (v13权威名, 旧名或 None)
DW_ALIASES_MAIN = {
    "s_vwap": "S VWAP", "vah_price": "VAH Price", "val_price": "VAL Price",
    "poc_price": "POC Price", "npoc_price": "nPOC Price",
    "w_vwap_price": "W VWAP Price", "m_vwap_price": "M VWAP Price", "do_price": "DO Price",
    "ema_9": "EMA 9", "ema_21": "EMA 21", "ema_34": "EMA 34", "ema_55": "EMA 55",
    "mcp_side_code": "MCP Side Code",
    "mcp_grade_code": "MCP Grade Code",
    "mcp_setup_score": "MCP Setup Score",
    "mcp_entry_price": "MCP Entry Price",
    "mcp_stop_price": "MCP Stop Price",
    "mcp_target_price": "MCP Target Price",
    "mcp_quality_code": "MCP Quality Code",
    "mcp_fvg_quality_score": "MCP FVG Quality Score",
    "mcp_ob_quality_score": "MCP OB Quality Score",
    # v13 新增
    "mcp_entry_valid_code": "MCP Entry Valid Code",
    "mcp_rr_ratio": "MCP RR Ratio",
    "mcp_no_trade_reason_code": "MCP NoTrade Reason Code",
    "mcp_execution_pack": "MCP Execution Pack",
    "mcp_trigger_pack": "MCP Trigger Pack",
    "mcp_regime_pack": "MCP Regime Pack",
    "mcp_contract_pack": "MCP Contract Pack",
    "mcp_evidence_pack": "MCP Evidence Pack",
    "mcp_evidence_bar_time": "MCP Evidence Bar Time",
    "mcp_evidence_close_time": "MCP Evidence Close Time",
    "mcp_cvd_method_code": "MCP CVD Method Code (0=不参与决策,2=lower-TF estimate,1=bar estimate)",
    "mcp_struct_pack": "MCP StructPack (FvgQ*10000+(OB+1)*100+(BOS+2)*10+(LV+1))",
}

DW_ALIASES_SUB = {
    "haldro_valid_code": "HALDRO Valid Code",
    "oi_change_pct_normalized": "OI Change % (Normalized)",
    "cvd_value": "CVD Value",
    "cvd_method_code": "CVD Method Code (1=当前所K线方向/2=当前所1m方向)",
    "cvd_quality_code": "CVD Quality Code",
    "lsr": "LSR", "long_short_ratio": "LSR",
    "volume_ratio": "Volume Ratio",
    "coverage_exchanges": "Coverage Exchanges",
    "coverage_spot": "Coverage Spot", "coverage_perp": "Coverage Perp",
    "coverage_feed_mode": "Coverage Feed Mode",
    "exchange_dominance_%": "Exchange Dominance %",
    "exchange_dominance_pct": "Exchange Dominance %",
    "confirm_score": "Confirm Score",
    "haldro_risk_code": "HALDRO Risk Code",
    "composite": "Composite",
    # v13 新增
    "basic_packed_bus": "Basic Packed Bus (唯一主副连接)",
    "haldro_state_pack": "HALDRO State Pack (0无效/1支持多/2支持空/3冲突/4降权)",
    "oi_price_direction": "OI Price Direction (same ACT_LB: 1涨/-1跌)",
    "oi_breadth": "OI Breadth",
    "oi_agreement_pct": "OI Agreement %",
    "haldro_oi_pack": "HALDRO OI Pack (方向*100+一致%)",
    "oi_dispersion_ratio": "OI Dispersion Ratio",
    "haldro_freshness_pack": "HALDRO Freshness Pack",
    "stale_venue_count": "Stale Venue Count (连续缺失>=3K)",
    "haldro_contract_pack": "HALDRO Contract Pack",
    "haldro_flow_pack": "HALDRO Flow Pack (OI*100+CVD*10+SP)",
    "cvd_anchor_value": "CVD Anchor Value",
}

# 旧缓存里仍可能存在的 snake_case（保留兼容，命中才用）
LEGACY_DW_ALIASES_SUB = {
    "oi_total": "OI Total",
    "estimated_cvd_value": "Estimated CVD Value",
}

# ── 4. 解码器 ────────────────────────────────────────────────────────

# 来源：主指标 v13 L2909 noTradeReasonCode（逐位相加，可多位置位）
NO_TRADE_BITS = {
    1: "HTF冲突X",
    2: "过热追高X",
    4: "低流动性",
    8: "价格几何不成立",
    16: "R:R不足",
    32: "CVD质量不达标",
    64: "ADR禁追",
    128: "溢折价不允许",
    256: "本根未收线",
    512: "触发不新鲜",
    1024: "副指标冲突/降权",
}

# 来源：主指标 v13 L2907 entryValidCode
ENTRY_VALID = {
    -3: "X禁做",
    -2: "价格几何不成立",
    -1: "R:R不足",
    0: "无方向",
    1: "待确认",
    2: "可执行(B/C)",
    3: "可执行(A)",
}

# 来源：副指标 v13 L901 aggStateCode / 主指标 L2592-2596
HALDRO_STATE = {
    0: "S0未接/无效",
    1: "S1支持多",
    2: "S2支持空",
    3: "S3冲突",
    4: "S4降权",
}

# R:R 硬闸：A 级 >= 2.0；B/C 直通 >= 1.5
RR_HARD_MIN = 2.0
RR_BC_MIN = 1.5


def _as_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(str(value).replace("−", "-").replace(",", "").strip())))
    except (TypeError, ValueError):
        return None


def decode_no_trade(code) -> list[str]:
    """位掩码 → 原因短语列表。0/None → 空列表（= 无阻断）。"""
    n = _as_int(code)
    if n is None or n <= 0:
        return []
    return [text for bit, text in sorted(NO_TRADE_BITS.items()) if n & bit]


def format_no_trade(code, sep: str = "+") -> str:
    """位掩码 → 一行可读原因链；无阻断返回空串。"""
    reasons = decode_no_trade(code)
    return sep.join(reasons) if reasons else ""


def decode_entry_valid(code) -> str:
    n = _as_int(code)
    return ENTRY_VALID.get(n, "未知") if n is not None else "缺失"


def decode_haldro_state(code) -> str:
    n = _as_int(code)
    return HALDRO_STATE.get(n, "未知") if n is not None else "缺失"


def rr_gate(rr) -> str:
    """R:R → 闸门结论（对齐指标 rrHardOk / bcDirectOk）。"""
    if rr is None or rr == "":
        return "R:R缺失"
    try:
        v = float(str(rr).replace("−", "-"))
    except (TypeError, ValueError):
        return "R:R缺失"
    if v >= RR_HARD_MIN:
        return f"R:R {v:.1f} 过硬闸"
    if v >= RR_BC_MIN:
        return f"R:R {v:.1f} 仅B/C直通"
    return f"R:R {v:.1f} 不足"


# ── 4b. 按面板顺序取行（风控行动态标签也认）──────────────────────────

def ordered_main_rows(rows: dict) -> list[tuple[str, str]]:
    """按 v13 面板顺序取出主表行；「风控」行会命中 风控/风控·观察/风控·未授权 之一。

    旧缓存里的残留行（进场/止损/…）追加在后，保证历史缓存不丢信息。
    """
    rows = rows or {}
    out: list[tuple[str, str]] = []
    for label in MAIN_ROW_LABELS:
        if label == "风控":
            for variant in RISK_ROW_VARIANTS:
                if variant in rows:
                    out.append((variant, rows[variant]))
                    break
        elif label in rows:
            out.append((label, rows[label]))
    seen = {l for l, _ in out}
    for label in LEGACY_MAIN_ROWS:
        if label in rows and label not in seen:
            out.append((label, rows[label]))
    return out


def ordered_sub_rows(rows: dict) -> list[tuple[str, str]]:
    rows = rows or {}
    out = [(l, rows[l]) for l in SUB_ROW_LABELS if l in rows]
    seen = {l for l, _ in out}
    for label in LEGACY_SUB_ROWS:
        if label in rows and label not in seen:
            out.append((label, rows[label]))
    return out


def risk_row_value(rows: dict) -> str:
    """取「风控」行的值（不论标签是哪种变体）。"""
    for variant in RISK_ROW_VARIANTS:
        if variant in (rows or {}):
            return rows[variant]
    return ""


# ── 5. 「风控」行解析（v13 把 入场/止损/目标 折进这一行）──────────────

def parse_risk_row(text: str) -> dict:
    """解析 v13 风控行：`风控·观察 | 入79056.6·止80482.8·1.8A·标76151.9·2.0R`
    或只传右侧值 `入…·止…`、观察态 `止80482.8·1.8A`、禁做态 `禁做·不出价`。

    传整行时行标签（风控·观察 等）会写进 label；
    传纯值时 label 取值为文本里能识别到的授权等级前缀，识别不到则空串。

    返回 {'entry','stop','target','stop_atr','rr','label'}；取不到的键为 None。
    """
    out = {"entry": None, "stop": None, "target": None,
           "stop_atr": None, "rr": None, "label": ""}
    if not text:
        return out
    s = str(text).strip()
    # 整行形态：先剥掉行标签
    if " | " in s:
        lhs, s = s.split(" | ", 1)
        s = s.strip()
        for variant in ("禁做·不出价", "风控·未授权", "风控·观察", "风控"):
            if lhs.strip().startswith(variant):
                out["label"] = variant
                break
    if not out["label"]:
        for variant in ("禁做·不出价", "风控·未授权", "风控·观察", "风控"):
            if s.startswith(variant):
                out["label"] = variant
                break

    def grab(marker: str):
        # 匹配 `入79056.6` 直到下一个「·」或结尾；允许负数与千分位
        m = re.search(re.escape(marker) + r"(-?[\d,]+(?:\.\d+)?)", s)
        if not m:
            return None
        return float(m.group(1).replace(",", ""))

    out["entry"] = grab("入")
    out["stop"] = grab("止")
    out["target"] = grab("标")
    m = re.search(r"(-?[\d.]+)\s*A(?![A-Za-z])", s)
    if m:
        out["stop_atr"] = float(m.group(1))
    m = re.search(r"(-?[\d.]+)\s*R(?![A-Za-z])", s)
    if m:
        out["rr"] = float(m.group(1))
    return out
