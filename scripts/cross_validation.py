"""Active multi-source cross-validation contract.

The module is intentionally observational at the optional-source layer.  It
records whether a source was live, cached, stale, unavailable or not routed,
and only core execution inputs can create a hard blocker.
"""
from __future__ import annotations

from typing import Any, Iterable, cast

from source_contract import get_source_contract


LIVE_STATES = {"live", "cache", "inherited"}
DEGRADED_STATES = {"stale_cache", "unavailable", "quota_cooldown", "not_run"}


def _contract(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        nested = get_source_contract(value)
        if nested is not None:
            return nested
        if {"source_id", "status", "timestamp", "payload", "error"} <= set(value):
            return cast(dict[str, Any], value)
    return {}


def _as_dict(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _status(value: Any, *, empty: str = "not_run") -> str:
    contract = _contract(value)
    if contract:
        raw = contract.get("status")
        if raw in LIVE_STATES and not contract.get("timestamp"):
            return "unavailable"
        if raw in LIVE_STATES | DEGRADED_STATES:
            return str(raw)
    if isinstance(value, dict):
        raw = value.get("_source_status") or value.get("source_status")
        if raw in LIVE_STATES | DEGRADED_STATES:
            return str(raw)
        if "usable" in value:
            return "live" if value.get("usable") is True else "unavailable"
        if value.get("stale") is True:
            return "stale_cache"
        if value.get("_error") or value.get("error"):
            return "unavailable"
        if value:
            return "cache"
        return empty
    return "live" if value not in (None, "", False) else empty


def _source_metadata(value: Any) -> dict[str, Any]:
    contract = _contract(value)
    if contract:
        payload = contract.get("payload")
        return {
            "timestamp": contract.get("timestamp"),
            "source_error": contract.get("error"),
            "payload_present": bool(
                contract.get("payload_present", payload not in (None, "", False, {}, []))
            ),
        }
    if isinstance(value, dict):
        return {
            "timestamp": value.get("_source_timestamp") or value.get("timestamp"),
            "source_error": value.get("_source_error") or value.get("error") or value.get("_error"),
            "payload_present": bool(value),
        }
    return {"timestamp": None, "source_error": None, "payload_present": value not in (None, "", False, [], {})}


def _row(
    source_id: str,
    label: str,
    status: str,
    role: str,
    entered: bool,
    impact: str,
    *,
    evidence: str = "",
    requested: bool = True,
    conflict: bool = False,
    source_value: Any = None,
) -> dict[str, Any]:
    metadata = _source_metadata(source_value)
    return {
        "id": source_id,
        "label": label,
        "status": status,
        "role": role,
        "entered_final_verdict": bool(entered),
        "impact": impact,
        "evidence": evidence,
        "requested": bool(requested),
        "conflict": bool(conflict),
        "timestamp": metadata["timestamp"],
        "source_error": metadata["source_error"],
        "payload_present": metadata["payload_present"],
    }


def _crypto_matrix(engine: dict[str, Any], dual: dict[str, Any], steps: set[str]) -> list[dict[str, Any]]:
    source_records = _as_dict(engine.get("_source_records"))
    five = engine.get("_tv_five_tf_status") if isinstance(engine.get("_tv_five_tf_status"), dict) else {}
    five_requested = bool(engine.get("_tv_five_tf_required"))
    five_status = "not_run"
    if five:
        five_status = "live" if five.get("usable") and five.get("scope") != "inherited_context" else "inherited" if five.get("usable") else "unavailable"
    rows = [
        _row(
            "tv_five_tf", "TV五周期", five_status,
            "hard_gate" if five_requested else "context",
            five_requested,
            "Full档位五层完整性硬闸" if five_requested else "高周期背景",
            evidence=f"覆盖{five.get('coverage', 0)}/5" if five else "未检测",
            requested=five_requested,
            source_value=five,
        ),
    ]

    tv_live = engine.get("_tv_live_status") or engine.get("_tv_cache_status") or {}
    tv_status = _status(tv_live)
    if not tv_live and engine.get("_tv_preflight_ok"):
        tv_status = "live"
    rows.append(_row(
        "tv_main", "TV SVP主指标", tv_status, "hard_gate", True,
        "主行动格/TV现场身份进入裁决",
        evidence=str(tv_live.get("reason") or "现场/缓存" if isinstance(tv_live, dict) else "现场"),
        source_value=tv_live,
    ))

    valid_code = 0
    try:
        valid_code = int(float(dual.get("valid_code") or 0))
    except (TypeError, ValueError):
        pass
    haldro_value = source_records.get("haldro")
    if haldro_value is not None:
        haldro_status = _status(haldro_value)
    else:
        haldro_status = "live" if valid_code >= 2 else "cache" if valid_code == 1 else "unavailable"
    rows.append(_row(
        "haldro", "HALDRO/AggVol副指标", haldro_status, "veto_confirmation", True,
        "确认/降级/否决，不单独授权",
        evidence=f"ValidCode={valid_code}",
        conflict=bool(dual.get("conflict")),
        source_value=haldro_value or dual,
    ))

    prices = _as_dict(engine.get("prices"))
    binance_ready = bool(engine.get("_binance_data_collected") and prices.get("primary"))
    binance_status = "live" if binance_ready else _status(prices)
    rows.append(_row(
        "binance_futures", "Binance合约", binance_status, "confirmation", True,
        "合约价/K线/OI/费率/多空比",
        evidence=str(prices.get("source") or "价格未确认"),
    ))

    cg = source_records.get("cg_top") or engine.get("cg_top")
    rows.append(_row(
        "cg_pro", "CoinGecko/板块", _status(cg), "context", False,
        "板块和流动性背景，不改裁决",
        requested="cg_pro" in steps,
        source_value=cg,
    ))
    macro = source_records.get("macro") or engine.get("macro") or engine.get("_macro")
    rows.append(_row(
        "macro", "宏观/事件", _status(macro), "upstream_context", False,
        "影响上游模型/事件禁做，不直接越权",
        requested="macro" in steps,
        source_value=macro,
    ))
    deribit = source_records.get("deribit") or engine.get("deribit")
    rows.append(_row(
        "deribit", "Deribit期权", _status(deribit), "context", False,
        "期权背景，不改Entry/Stop/Target",
        requested="cron_read" in steps,
        source_value=deribit,
    ))
    x_sentiment = source_records.get("x_sentiment") or engine.get("x_sentiment")
    rows.append(_row(
        "x_sentiment", "X情绪", _status(x_sentiment), "observational", False,
        "催化剂/盲点，不得改FinalVerdict",
        requested="x_sent" in steps,
        source_value=x_sentiment,
    ))
    advanced = engine.get("_advanced") if isinstance(engine.get("_advanced"), dict) else {}
    corr = (advanced.get("factors") or {}).get("correlation") if isinstance(advanced, dict) else None
    rows.append(_row(
        "correlation", "跨资产相关性", _status(corr), "risk_context", False,
        "组合风险乘数/警示",
        requested="corr" in steps,
        source_value=corr,
    ))
    return rows


def _generic_matrix(engine: dict[str, Any], steps: set[str], symbol: str = "") -> list[dict[str, Any]]:
    five = engine.get("_tv_five_tf_status") if isinstance(engine.get("_tv_five_tf_status"), dict) else {}
    five_requested = bool(engine.get("_tv_five_tf_required"))
    five_status = "not_run"
    if five:
        five_status = (
            "live" if five.get("usable") and five.get("scope") != "inherited_context"
            else "inherited" if five.get("usable")
            else "unavailable"
        )
    rows = []
    if five_requested or five:
        rows.append(_row(
            "tv_five_tf", "TV五周期", five_status,
            "hard_gate" if five_requested else "context",
            five_requested,
            "Full档位五层完整性硬闸" if five_requested else "高周期背景",
            evidence=f"覆盖{five.get('coverage', 0)}/5" if five else "未检测",
            requested=five_requested or "tv" in steps,
            source_value=five,
        ))
    xau_pair = _as_dict(engine.get("_xau_tv_contract"))
    is_gold = engine.get("asset_class") == "gold" or any(
        marker in str(symbol).upper() for marker in ("XAU", "GOLD")
    )
    xau_action_required = bool(five_requested and (is_gold or xau_pair))
    if xau_action_required:
        pair_live = xau_pair.get("live")
        live_part = pair_live if isinstance(pair_live, dict) else {}
        pair_usable = bool(xau_pair.get("usable"))
        action_status = "live" if pair_usable and live_part.get("usable") else "unavailable"
        action_reason = str(
            xau_pair.get("reason")
            or live_part.get("reason")
            or "XAU五周期与5m行动格成对状态缺失"
        )
        rows.append(_row(
            "tv_action_5m", "XAU 5m主行动格", action_status,
            "hard_gate", True, "与五周期同批次成对进入FinalVerdict",
            evidence=action_reason,
            requested=True,
            source_value=xau_pair,
        ))
    tv_live = engine.get("_tv_live_status") or engine.get("_tv_cache_status") or {}
    tv_status = _status(tv_live)
    if not tv_live and engine.get("_tv_preflight_ok"):
        tv_status = "live"
    rows.append(_row(
        "tv_main", "TV主指标", tv_status,
        "hard_gate", True, "主结构/位置/执行语义",
        source_value=tv_live,
    ))
    asset_sources = _as_dict(engine.get("_asset_sources"))
    source_records = _as_dict(asset_sources.get("_source_records"))
    for source_id, label in (("macro", "宏观"), ("fmp", "基本面"), ("td", "TwelveData"), ("av", "AlphaVantage"), ("options_chain", "期权链")):
        source_value = source_records.get(source_id) or asset_sources.get(source_id) or engine.get(source_id)
        rows.append(_row(
            source_id, label, _status(source_value),
            "upstream_context", False, "辅助验证，不越权改FinalVerdict",
            requested=source_id in steps,
            source_value=source_value,
        ))
    # 2026-09-13：XAU 黄金合约逐笔 CVD（Binance XAUUSDT）——独立辅助行，
    # 明标来源，不冒充 OANDA 现货；只展示不改裁决。
    gold_cvd = _as_dict(engine.get("gold_contract_cvd"))
    if is_gold and gold_cvd.get("direction"):
        rec = _as_dict(_as_dict(engine.get("_source_records")).get("cvd"))
        rows.append(_row(
            "gold_contract_cvd", "Binance黄金合约CVD", _status(rec) if rec else "live",
            "observational", False, "辅助展示·不越权改FinalVerdict（非OANDA现货数据）",
            evidence=f"{gold_cvd.get('direction', '?')}·{gold_cvd.get('quality', '?')}",
            requested="cvd" in steps,
            source_value=rec or gold_cvd,
        ))
    return rows


def build_source_matrix(
    symbol: str,
    engine_data: dict[str, Any] | None,
    dual: dict[str, Any] | None,
    *,
    pipeline_steps: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Build a source matrix with explicit authority and decision usage."""
    engine = engine_data if isinstance(engine_data, dict) else {}
    indicator = dual if isinstance(dual, dict) else {}
    steps = set(pipeline_steps)
    is_crypto = bool(indicator.get("asset_is_crypto", str(symbol).upper().endswith("USDT")))
    if is_crypto:
        return _crypto_matrix(engine, indicator, steps)
    return _generic_matrix(engine, steps, symbol=symbol)


def evaluate_cross_validation(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return hard blockers and visible degradation without optional-source veto."""
    row_list = list(rows)
    hard_blockers: list[str] = []
    warnings: list[str] = []
    for row in row_list:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("id") or "unknown")
        status = str(row.get("status") or "not_run")
        role = str(row.get("role") or "context")
        requested = bool(row.get("requested", True))
        if role == "hard_gate" and status not in LIVE_STATES:
            hard_blockers.append(source_id)
        elif requested and status not in LIVE_STATES and role not in {"observational", "context"}:
            warnings.append(source_id)
        elif requested and status in DEGRADED_STATES and role in {"context", "observational", "upstream_context", "risk_context"}:
            warnings.append(source_id)
    hard_blockers = list(dict.fromkeys(hard_blockers))
    warnings = list(dict.fromkeys(warnings))
    state = "blocked" if hard_blockers else "degraded" if warnings else "ok"
    return {
        "state": state,
        "hard_blockers": hard_blockers,
        "warnings": warnings,
        "rows": row_list,
    }
