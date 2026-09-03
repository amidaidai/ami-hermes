#!/usr/bin/env python3
"""
交易执行桥接器 v1.0
五层架构执行层 — 连接 pipeline_integration → trading_system
将信号转换为可追踪的交易事件，写入 trade_events.jsonl
"""
import json, sys, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_json import append_text_line, _file_lock, _thread_lock


def _event_payload(event_type: str, symbol: str, details: dict) -> dict:
    return {
        "ts": datetime.now(TZ).isoformat(),
        "type": event_type,
        "symbol": symbol,
        **details,
    }


def _append_event_unlocked(event_type: str, symbol: str, details: dict) -> None:
    event = _event_payload(event_type, symbol, details)
    path = Path(TRADE_EVENTS)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _append_event_once(event_type: str, symbol: str, details: dict, event_key: str) -> bool:
    path = Path(TRADE_EVENTS)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock(path), _file_lock(path):
        if _entry_event_already_logged(event_key):
            return False
        _append_event_unlocked(event_type, symbol, {**details, "event_key": event_key})
        return True


def _authorized_final_verdict(signals: dict) -> bool:
    """Only a complete, geometrically valid GO-A may enter execution events."""
    verdict = signals.get("_final_verdict") or signals.get("final_verdict")
    if not isinstance(verdict, dict):
        return False
    if verdict.get("state") != "GO-A" or verdict.get("executable") is not True:
        return False
    if any(verdict.get(key) in (None, "") for key in ("entry", "stop", "target")):
        return False
    try:
        entry = float(verdict["entry"])
        stop = float(verdict["stop"])
        target = float(verdict["target"])
    except (TypeError, ValueError):
        return False
    side = str(verdict.get("side") or "").lower()
    if side in {"long", "buy", "多"}:
        return stop < entry < target
    if side in {"short", "sell", "空"}:
        return target < entry < stop
    return False


def _safe_event_target() -> str | None:
    """Legacy bridge never inherits a hard-coded Telegram topic."""
    return os.environ.get("TANGXI_AUTOMATED_TG_TARGET") if os.environ.get("TANGXI_ENABLE_AUTOMATED_TG") == "1" else None


def _append_final_verdict(details: dict, signals: dict) -> dict:
    verdict = signals.get("_final_verdict") or signals.get("final_verdict")
    if isinstance(verdict, dict):
        details["final_verdict_state"] = verdict.get("state")
        details["final_verdict_executable"] = verdict.get("executable") is True
        details["final_verdict_id"] = verdict.get("verdict_id") or verdict.get("id")
    return details


TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))

# The repository data directory is the single runtime authority.  Do not read
# a second Hermes-home copy: it can contain a different signal generation.
DATA_DIR = str(ROOT / "data")
os.makedirs(DATA_DIR, exist_ok=True)

TRADE_EVENTS = os.path.join(DATA_DIR, "trade_events.jsonl")


def _signal_symbol(signals: dict) -> str:
    raw = str(signals.get("symbol") or signals.get("ticker") or "BTCUSDT").upper()
    return raw.rsplit(":", 1)[-1].replace(".P", "")


def _entry_event_key(signals: dict) -> str:
    verdict = signals.get("_final_verdict") or signals.get("final_verdict") or {}
    verdict_id = verdict.get("verdict_id") or verdict.get("id") or signals.get("setup_id")
    if verdict_id:
        return f"{_signal_symbol(signals)}:entry_signal:{verdict_id}"
    return ""


def _entry_event_already_logged(key: str) -> bool:
    if not key:
        return False
    try:
        with open(TRADE_EVENTS, encoding="utf-8") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("event_key") == key:
                    return True
    except OSError:
        return False
    return False


def log_event(event_type: str, symbol: str, details: dict):
    """写入交易事件日志"""
    event = {
        "ts": datetime.now(TZ).isoformat(),
        "type": event_type,
        "symbol": symbol,
        **details,
    }
    append_text_line(TRADE_EVENTS, json.dumps(event, ensure_ascii=False))


def bridge_signal_to_execution():
    """将最新分析信号桥接到执行层"""
    # 读取最新信号
    signals_file = os.path.join(DATA_DIR, "btc_signals.json")
    try:
        with open(signals_file) as f:
            signals = json.load(f)
    except FileNotFoundError:
        return {"status": "no_signal", "msg": "无信号文件"}
    
    # 读取因子
    factors_file = os.path.join(DATA_DIR, "qlib_factors.json")
    factors = {}
    try:
        with open(factors_file) as f:
            factors = json.load(f).get("factors", {})
    except FileNotFoundError:
        pass
    
    # 读取风控状态
    protection_file = os.path.join(DATA_DIR, "protections_state.json")
    protections = {}
    try:
        with open(protection_file) as f:
            protections = json.load(f)
    except FileNotFoundError:
        pass
    
    signal_symbol = _signal_symbol(signals)
    if signal_symbol != "BTCUSDT":
        return {"status": "rejected", "reason": "unsupported_symbol", "symbol": signal_symbol}

    price = signals.get("price", 0)
    stage = signals.get("stage", "idle")
    score = signals.get("scoring_total", 0)
    factor_score = factors.get("SIGNAL_SCORE", 0)
    factor_bias = factors.get("SIGNAL_BIAS", "neutral")
    
    # 判断是否值得记录
    is_notable = (
        stage == "entry_ready" or
        abs(factor_score) >= 3 or
        score >= 12 or
        protections.get("breach", False)
    )
    
    if not is_notable:
        return {"status": "quiet", "stage": stage, "price": price}
    
    # 记录事件
    details = {
        "price": price,
        "stage": stage,
        "score": score,
        "factor_score": factor_score,
        "factor_bias": factor_bias,
        "dmi_adx": signals.get("dmi", {}).get("adx", 0),
        "protections": protections.get("active", []),
    }
    
    authorized = _authorized_final_verdict(signals)
    details["final_verdict_authorized"] = authorized
    _append_final_verdict(details, signals)
    log_event("signal_check", "BTCUSDT", details)

    # Legacy entry_ready is not an execution authorization. Only a complete
    # GO-A FinalVerdict may enter the execution-event stream.
    if stage == "entry_ready" and authorized:
        verdict = signals.get("_final_verdict") or signals.get("final_verdict")
        event_key = _entry_event_key(signals)
        details = {
            "direction": verdict.get("side") or signals.get("direction", "wait"),
            "entry_price": verdict.get("entry"),
            "stop_price": verdict.get("stop"),
            "target_price": verdict.get("target"),
            "score": score,
            "factor_score": factor_score,
            "final_verdict_state": verdict.get("state"),
            "final_verdict_executable": True,
        }
        if event_key:
            if not _append_event_once("entry_signal", signal_symbol, details, event_key):
                return {
                    "status": "already_logged",
                    "stage": stage,
                    "price": price,
                    "factor_bias": factor_bias,
                    "final_verdict_authorized": True,
                    "event_key": event_key,
                }
        else:
            log_event("entry_signal", signal_symbol, details)
    elif stage == "entry_ready":
        log_event("execution_blocked", "BTCUSDT", {
            "reason": "legacy_entry_ready_without_authorized_final_verdict",
            "stage": stage,
            "score": score,
            "factor_score": factor_score,
        })

    return {
        "status": "logged",
        "stage": stage,
        "price": price,
        "factor_bias": factor_bias,
        "final_verdict_authorized": authorized,
    }


def main():
    now = datetime.now(TZ)
    ts = f"{now.year}年{now.month}月{now.day}日{now.hour:02d}：{now.minute:02d}"
    
    result = bridge_signal_to_execution()
    
    if result["status"] in {"no_signal", "quiet"}:
        # 静默：无信号/普通状态只落盘数据，不生成 cron 输出。
        return 0
    else:
        now = datetime.now(TZ)
        ts = now.strftime("%Y年%m月%d日%H：%M")
        stage = result.get("stage", "?")
        bias = result.get("factor_bias", "?")
        # 结构化表
        lines = [f"🔗 交易执行桥 · {ts}"]
        lines.append("")
        lines.append("| 项目 | 数据 |")
        lines.append("|:----|:----|")
        lines.append(f"| 阶段 | {stage} |")
        lines.append(f"| 因子偏置 | {bias} |")
        lines.append(f"| 价格 | `{result.get('price', 0):,.0f}` |")
        lines.append("")
        lines.append("✅ 已记录 trade_events.jsonl（仅审计事件，不代表已下单）")
        lines.append("")
        conclusion = (
            "↑GO-A执行事件已落盘；后续仍由人工控制"
            if result.get("final_verdict_authorized")
            else "○仅审计事件已落盘；未获得GO-A授权，不得执行"
        )
        lines.append(f"**总体结论**: **{conclusion}**；当前阶段`{stage}`、因子偏置`{bias}`。")
        output = "\n".join(lines)
        print(output)
        # v9.8: 推 TG 真表格（原本只 print 退化文本）
        try:
            target = _safe_event_target()
            if target and result.get("final_verdict_authorized"):
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from telegram_reliable import push_tg_rich
                push_tg_rich(target, output)
            else:
                print("⏸ 交易执行桥未外发：缺少显式TG授权目标或GO-A FinalVerdict")
        except Exception as _te:
            print(f"⚠ 交易执行桥RichMarkdown推送失败: {_te}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
