#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""XAU TV MCP 现场同步 v1.0 — 读 OANDA:XAUUSD 五层真实数据写 data/xau_tv_state.json

解决 v9.6 地图 P0：XAU 占位推算虚挂。本脚本通过 TradingView MCP 现场切
D/4h/1h/15m/5m 读真实 high/low/close/OHLCV，并与5m主行动格成对验收。

用法: python scripts/xau_tv_sync.py
依赖: tools/tradingview-mcp (TV MCP CDP 已启动)
降级: TV MCP 不可用则静默退出(不写文件，auto_card 走占位并标注⚠️)
"""
import sys
import argparse
import json
import asyncio
import os
import subprocess
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
OUT = ROOT / "data" / "xau_tv_state.json"
LIVE_OUT = ROOT / "data" / "tv_live_XAUUSD.json"
STAGED_OUT = OUT.with_name(f"{OUT.name}.tmp")
NO_PUSH_FLAG = ROOT / "data" / "xau_tv_no_push.json"
SYMBOL = "OANDA:XAUUSD"
# v9.7: 补 D 层日线，使"自上而下确认"有大背景（原只同步 5m/15m/1h/4h）
TIMEFRAMES = [("1D", "D"), ("5m", "5"), ("15m", "15"), ("1h", "60"), ("4h", "240")]
SOURCE_SNAPSHOT = ROOT / "data" / "source_snapshot_XAUUSD.json"
_ACTION_KEYS = ("结论", "方向", "路径", "风控", "操作")
_PREVIOUS_CHART: dict[str, Any] = {}
# 图表归属状态：记录「用户的图表在哪」，并把「待归还目标」持久化，
# 用于打断「上次没恢复干净 → 下次把残留当成用户图表 → 永久锁死」的棘轮。
CHART_OWNER = ROOT / "data" / "tv_chart_owner.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="采集并原子发布 XAU TradingView 五周期与5m行动格",
    )
    return parser


def _tv_command(*args: str, timeout: int = 30) -> tuple[str, bool]:
    from tv_data_bridge import _tv
    return _tv(*args, timeout=timeout)


def _chart_state() -> dict[str, Any]:
    from tv_data_bridge import _tv_json
    return _tv_json("state", timeout=30) or {}


def _load_chart_owner() -> dict[str, Any]:
    try:
        data = json.loads(CHART_OWNER.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}


def _save_chart_owner(state: dict[str, Any]) -> None:
    try:
        CHART_OWNER.parent.mkdir(parents=True, exist_ok=True)
        CHART_OWNER.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass          # 状态文件写不了也不能阻断采集


def _resolve_restore_target(cur_symbol: str, cur_timeframe: str) -> dict[str, Any]:
    """决定采完后该把图表还给谁。

    - 进入时看到非本任务品种 → 那是用户的图表，记下来并作为归还目标
    - 进入时已在 XAU 上 → 优先用「待归还」记录修回来（打断棘轮）；
      没有待归还记录才认为用户真的在看 XAU，保持不动
    """
    cur_symbol = str(cur_symbol or "").strip()
    cur_timeframe = str(cur_timeframe or "").strip()
    state = _load_chart_owner()
    is_our_target = cur_symbol.upper() == SYMBOL.upper()

    if cur_symbol and not is_our_target:
        state["user_symbol"] = cur_symbol
        state["user_timeframe"] = cur_timeframe
        state["pending_restore"] = {"symbol": cur_symbol, "resolution": cur_timeframe}
        state["captured_at"] = datetime.now(TZ).isoformat()
        _save_chart_owner(state)
        return {"symbol": cur_symbol, "resolution": cur_timeframe}

    pending = state.get("pending_restore") or {}
    pending_symbol = str(pending.get("symbol") or "").strip()
    if pending_symbol and pending_symbol.upper() != SYMBOL.upper():
        # 上次没还回去 → 用记录修回来，不要顺着残留继续「恢复」成 XAU
        state["ratchet_break_at"] = datetime.now(TZ).isoformat()
        state["ratchet_break_from"] = cur_symbol
        _save_chart_owner(state)
        return {"symbol": pending_symbol,
                "resolution": str(pending.get("resolution") or "")}

    # 用户真的在看 XAU（或首次运行无记录）→ 保持原样
    return {"symbol": cur_symbol, "resolution": cur_timeframe}


def _mark_restored() -> None:
    state = _load_chart_owner()
    if state.pop("pending_restore", None) is not None:
        state["restored_at"] = datetime.now(TZ).isoformat()
        _save_chart_owner(state)


def _restore_chart(previous: dict[str, Any]) -> bool:
    symbol = str(previous.get("symbol") or previous.get("ticker") or "").strip()
    timeframe = str(previous.get("resolution") or previous.get("timeframe") or "").strip()
    if not symbol:
        return False
    if not _tv_command("symbol", symbol)[1]:
        return False
    if timeframe and not _tv_command("timeframe", timeframe)[1]:
        return False
    time.sleep(20)
    actual = _chart_state()
    actual_symbol = str(actual.get("symbol") or actual.get("ticker") or "").strip().upper()
    actual_tf = str(actual.get("resolution") or actual.get("timeframe") or "").strip().upper()
    return actual_symbol == symbol.upper() and (not timeframe or actual_tf == timeframe.upper())


def _prepare_xau_main_chart() -> bool:
    """Wait for XAU 5m indicators before reading the action grid."""
    if not _tv_command("symbol", SYMBOL)[1]:
        return False
    if not _tv_command("timeframe", "5")[1]:
        return False
    time.sleep(20)
    actual = _chart_state()
    names = [
        str(row.get("name") if isinstance(row, dict) else row)
        for row in (actual.get("studies") or [])
    ]
    return (
        str(actual.get("symbol") or "").upper() == SYMBOL
        and str(actual.get("resolution") or actual.get("timeframe") or "").upper() in {"5", "5M"}
        and any("SVP" in name for name in names)
        and any("Volume Aggregated" in name for name in names)
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ)
    return parsed.astimezone(timezone.utc)


def _validate_live_payload(
    payload: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    max_age_minutes: float = 10.0,
) -> dict[str, Any]:
    """Validate XAU's 5m action-grid cache independently from five-TF OHLCV."""
    data = payload if isinstance(payload, dict) else {}
    actual_symbol = str(data.get("symbol") or data.get("ticker") or "")
    identity_valid = actual_symbol.upper() == SYMBOL
    timestamp = _parse_timestamp(data.get("timestamp") or data.get("updated_at") or data.get("updated"))
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_seconds = None if timestamp is None else (now_utc - timestamp).total_seconds()
    fresh = age_seconds is not None and -60.0 <= age_seconds <= max_age_minutes * 60.0
    table = data.get("decision_table")
    action_table_complete = (
        data.get("identity_valid") is True
        and data.get("action_table_complete") is True
        and isinstance(table, dict)
        and all(key in table and str(table.get(key) or "").strip() for key in _ACTION_KEYS)
    )
    usable = identity_valid and fresh and data.get("fresh") is True and data.get("stale") is not True and action_table_complete
    if not identity_valid:
        reason = f"XAU主周期品种不匹配: {actual_symbol or 'missing'}"
    elif timestamp is None:
        reason = "XAU主周期行动格时间戳缺失"
    elif not fresh:
        reason = f"XAU主周期行动格过期: age={age_seconds:.0f}s" if age_seconds is not None else "XAU主周期行动格过期"
    elif not action_table_complete:
        reason = "XAU主周期行动格契约不完整"
    elif data.get("fresh") is not True or data.get("stale") is True:
        reason = "XAU主周期行动格被标记为非新鲜"
    else:
        reason = "XAU主周期行动格身份/新鲜度/核心字段通过"
    return {
        "usable": usable,
        "identity_valid": identity_valid,
        "fresh": fresh,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "age_seconds": age_seconds,
        "action_table_complete": action_table_complete,
        "reason": reason,
    }


def validate_xau_outputs(
    state: dict[str, Any] | None,
    live: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    state_max_age_minutes: float = 30.0,
    live_max_age_minutes: float = 10.0,
    require_batch_id: bool = True,
    max_pair_skew_seconds: float = 120.0,
) -> dict[str, Any]:
    """Require XAU five-TF OHLCV and fresh 5m action-grid as one contract."""
    from tv_five_tf_contract import validate_five_tf_payload

    state_status = validate_five_tf_payload(
        state if isinstance(state, dict) else {},
        "XAUUSD",
        max_age_minutes=state_max_age_minutes,
        now=now,
    )
    live_status = _validate_live_payload(live, now=now, max_age_minutes=live_max_age_minutes)
    state_payload = state if isinstance(state, dict) else {}
    live_payload = live if isinstance(live, dict) else {}
    state_batch = str(state_payload.get("batch_id") or state_payload.get("sync_id") or "")
    live_batch = str(live_payload.get("batch_id") or live_payload.get("sync_id") or "")
    state_timestamp = _parse_timestamp(state_status.get("timestamp"))
    live_timestamp = _parse_timestamp(live_status.get("timestamp"))
    pair_skew_seconds = (
        abs((state_timestamp - live_timestamp).total_seconds())
        if state_timestamp is not None and live_timestamp is not None
        else None
    )
    skew_usable = (
        not require_batch_id
        or pair_skew_seconds is not None and pair_skew_seconds <= max_pair_skew_seconds
    )
    batch_usable = (
        not require_batch_id
        or bool(state_batch and live_batch and state_batch == live_batch)
    )
    batch_usable = batch_usable and skew_usable
    if not require_batch_id:
        batch_reason = "批次校验未启用"
    elif not state_batch or not live_batch:
        batch_reason = "五周期/主周期缺少采集批次标识"
    elif state_batch != live_batch:
        batch_reason = f"五周期/主周期采集批次不一致: state={state_batch}, live={live_batch}"
    elif not skew_usable:
        batch_reason = f"五周期/主周期采集时间偏差过大: {pair_skew_seconds or 0:.0f}s>{max_pair_skew_seconds:.0f}s"
    else:
        batch_reason = "五周期/主周期采集批次一致"
    usable = bool(state_status.get("usable") and live_status.get("usable") and batch_usable)
    if not state_status.get("usable"):
        reason = f"XAU五周期不可用·{state_status.get('reason') or '校验失败'}"
    elif not live_status.get("usable"):
        reason = f"XAU主周期行动格不可用·{live_status.get('reason') or '校验失败'}"
    elif not batch_usable:
        reason = f"XAU双缓存批次校验失败·{batch_reason}"
    else:
        reason = "XAU五周期与5m主周期行动格成对通过"
    return {
        "usable": usable,
        "state": state_status,
        "live": live_status,
        "batch": {
            "required": require_batch_id,
            "usable": batch_usable,
            "state_id": state_batch or None,
            "live_id": live_batch or None,
            "skew_seconds": pair_skew_seconds,
            "max_skew_seconds": max_pair_skew_seconds,
            "reason": batch_reason,
        },
        "reason": reason,
    }


def _refresh_source_snapshot_if_stale(max_age_seconds: int = 1800) -> None:
    """Keep XAU's multi-source quality snapshot inside the 30-minute freshness gate."""
    try:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from source_health import inspect_json_file
        if SOURCE_SNAPSHOT.exists() and inspect_json_file(
            SOURCE_SNAPSHOT,
            max_age_hours=max_age_seconds / 3600.0,
            expected_symbol="XAUUSD",
        ).get("fresh"):
            return
        from trading_system import source_snapshot
        source_snapshot("XAUUSD")
    except Exception as exc:
        print(f"⚠ XAU多源快照刷新失败: {exc}", file=sys.stderr)


async def _run_with_retry(sync_id: str, max_attempts: int = 3) -> int:
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            rc = await _run(sync_id)
            if rc == 0:
                return 0
        except Exception as exc:
            last_exc = exc
            print(f"⚠ XAU TV同步尝试 {attempt}/{max_attempts} 失败: {exc}", file=sys.stderr)
        if attempt < max_attempts:
            time.sleep(5)
    if last_exc:
        raise last_exc
    return 1


def _refresh_tv_live_cache(batch_id: str | None = None) -> dict[str, Any]:
    """同步XAU OHLCV后刷新同品种Data Window缓存，避免两条TV权威链分裂。"""
    # This function is called inside xau_tv_sync's shared chart lease. Keep
    # the live refresh in-process so lock ownership is structural, not an
    # environment-variable claim that an arbitrary child can forge.
    from tv_data_bridge import _collect_and_cache_locked
    live = _collect_and_cache_locked(alert_mode=False, expect_symbol=SYMBOL)
    if not isinstance(live, dict) or live.get("stale") or not live.get("fresh"):
        raise RuntimeError("XAU主周期行动格刷新失败或过期")
    if batch_id:
        live["batch_id"] = batch_id
    live["source"] = "tv_live_dump"
    from atomic_json import atomic_write_json
    for live_path in (ROOT / "data" / "tv_live.json", ROOT / "data" / "tv_live_XAUUSD.json"):
        atomic_write_json(live_path, live)
    status = _validate_live_payload(live)
    if not status["usable"]:
        raise RuntimeError(f"tv_live_XAUUSD.json未通过主周期契约: {status['reason']}")
    return live

# TV MCP 连接依赖
hermes_venv = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))
if hermes_venv.exists():
    sys.path.insert(0, str(hermes_venv))


async def _run(sync_id: str):
    global _PREVIOUS_CHART
    # 端口探测前置：TV Desktop CDP(9222)未开则静默退出，避免启动 node 超时/异常
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", 9222)) != 0:
                print("⚠ TV Desktop(9222)未运行，XAU同步跳过")
                return 0
    except Exception:
        return 0
    try:
        from mcp.client.stdio import stdio_client, StdioServerParameters
        import importlib.util
        wrapper_path = ROOT / "scripts" / "fetch_tv_mcp.py"
        wrapper_spec = importlib.util.spec_from_file_location("fetch_tv_mcp", wrapper_path)
        if wrapper_spec is None or wrapper_spec.loader is None:
            raise ImportError(f"canonical TV wrapper unavailable: {wrapper_path}")
        tv_mcp = importlib.util.module_from_spec(wrapper_spec)
        sys.modules["fetch_tv_mcp"] = tv_mcp
        wrapper_spec.loader.exec_module(tv_mcp)
        call_tool = getattr(tv_mcp, "call_tool")
        set_symbol = getattr(tv_mcp, "set_symbol")
        set_timeframe = getattr(tv_mcp, "set_timeframe")
        get_chart_state = getattr(tv_mcp, "get_chart_state")
        get_ohlcv = getattr(tv_mcp, "get_ohlcv")
        parse_result = getattr(tv_mcp, "parse_result")
    except Exception as e:
        print(f"⚠ TV MCP 模块不可用: {e}", file=sys.stderr)
        return 1

    server_script = ROOT / "tools" / "tradingview-mcp" / "src" / "server.js"
    if not server_script.exists():
        print(f"⚠ TV MCP server 未找到: {server_script}", file=sys.stderr)
        return 1

    server_params = StdioServerParameters(command="node", args=[str(server_script)])
    async with stdio_client(server_params) as (read, write):
        from mcp import ClientSession
        async with ClientSession(read, write) as session:
            await session.initialize()
            # TradingView 是全局共享图表：记录进入时的品种/周期，采集完成
            # 后必须恢复它们，不能把后台 XAU 同步留下的黄金图覆盖用户看盘。
            previous_symbol = ""
            previous_timeframe = ""
            try:
                previous = parse_result(await get_chart_state(session))
                previous_payload = json.loads(previous)
                previous_symbol = str(previous_payload.get("symbol") or "").strip()
                previous_timeframe = str(
                    previous_payload.get("resolution")
                    or previous_payload.get("timeframe")
                    or ""
                ).strip()
                # 不直接记录「进入时看到什么」——那会把上次的残留当成用户图表，
                # 导致图表被永久锁在 XAU。改由归属解析器决定归还目标。
                _PREVIOUS_CHART = _resolve_restore_target(
                    previous_symbol, previous_timeframe)
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

            try:
                # 切到 XAU，仅用于后台采集。
                await set_symbol(session, SYMBOL)
                await asyncio.sleep(2)

                result = {
                    "symbol": SYMBOL,
                    "batch_id": sync_id,
                    "updated_at": datetime.now(TZ).isoformat(),
                    "timeframes": {},
                }
                for tf, resolution in TIMEFRAMES:
                    await set_timeframe(session, resolution)
                    await asyncio.sleep(3)
                    state = await get_chart_state(session)
                    ohlcv = await get_ohlcv(session)
                    st = parse_result(state)
                    ov = parse_result(ohlcv)
                    tf_data = _parse_ohlcv(ov, st)
                    if tf_data:
                        result["timeframes"][tf] = tf_data
                        print(f"  ✅ {tf}: H{tf_data['high']:.1f} L{tf_data['low']:.1f} C{tf_data['close']:.1f}")
                    else:
                        print(f"  ⚠ {tf}: 解析失败", file=sys.stderr)

                required = {tf for tf, _resolution in TIMEFRAMES}
                missing = sorted(required - set(result["timeframes"]))
                if missing:
                    raise RuntimeError(f"TV周期数据不完整: {','.join(missing)}")
                result.update({
                    "updated_at": datetime.now(TZ).isoformat(),
                    "source": "tradingview_mcp",
                    "fresh": True,
                    "stale": False,
                    "usable": True,
                    "identity_valid": True,
                    "timeframes_complete": True,
                })
                # Keep OHLCV and the 5m action grid as one publication unit.  The
                # caller promotes this staged file only after the action cache has
                # passed its own identity/freshness/field contract.
                STAGED_OUT.parent.mkdir(parents=True, exist_ok=True)
                from atomic_json import atomic_write_json
                atomic_write_json(STAGED_OUT, result)
                # 缓存权威读取固定在XAU主执行周期5m，但发布后恢复用户图表。
                await set_timeframe(session, "5")
                await asyncio.sleep(3)
                _refresh_source_snapshot_if_stale()
                print(f"✅ XAU TV五周期已暂存 {STAGED_OUT}")
                # 外部投递必须在main完成双缓存校验和最终提交后执行。
                return 0
            finally:
                # The outer main lease restores only after the paired 5m action
                # cache has been validated and committed. Restoring here would
                # let the next stage read another symbol's Data Window.
                pass


def _build_xau_report(result: dict[str, Any]) -> str:
    """Build the field report only from a validated, committed snapshot."""
    now = datetime.now(TZ)
    ts = now.strftime("%Y年%m月%d日%H：%M")
    tfs = result.get("timeframes", {})
    lines = [f"🥇 XAU TV五层现场 · {ts}", ""]
    lines.extend([
        "| 周期 | 高 | 低 | 收 | 振幅 |",
        "|:----|:----:|:----:|:----:|:----:|",
    ])
    for tf in ["1D", "4h", "1h", "15m", "5m"]:
        d = tfs.get(tf)
        if d:
            rng = (d["high"] - d["low"]) / d["low"] * 100 if d.get("low") else 0
            lines.append(f"| {tf} | `{d['high']:.1f}` | `{d['low']:.1f}` | `{d['close']:.1f}` | {rng:.2f}% |")
    h4 = tfs.get("4h")
    if h4:
        pos = (h4["close"] - h4["low"]) / (h4["high"] - h4["low"]) * 100 if h4["high"] != h4["low"] else 50
        zone = "高位" if pos > 66 else "低位" if pos < 33 else "中位"
        bias = "🟢偏多但防回落" if pos > 66 else "🔴偏空但防反弹" if pos < 33 else "⚪方向待选"
        lines.extend(["", f"4h位置: 区间{zone}({pos:.0f}%) → {bias}", "", f"**总体结论**: XAU五层区间**{zone}**，**{bias}**。"])
    return "\n".join(lines)


def _push_committed_xau_report(result: dict[str, Any]) -> None:
    output = _build_xau_report(result)
    print(output)
    if (os.environ.get("XAU_TV_NO_PUSH") == "1" or NO_PUSH_FLAG.exists()
            or os.environ.get("TANGXI_ENABLE_AUTOMATED_TG") != "1"):
        print("⏸ XAU TV 推送已关闭（需显式 TANGXI_ENABLE_AUTOMATED_TG=1）")
        return
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from telegram_reliable import push_tg_rich
        ok, reason = push_tg_rich("", output)
        if not ok:
            print(f"⚠ XAU TV RichMarkdown推送失败: {reason}", file=sys.stderr)
    except Exception as exc:
        print(f"⚠ XAU TV RichMarkdown推送失败: {exc}", file=sys.stderr)



def _parse_ohlcv(ohlcv_text: str, state_text: str) -> dict | None:
    """优先解析TV MCP结构化OHLCV，并只消费倒数第二根已闭合K线。"""
    try:
        payload = json.loads(ohlcv_text)
        if isinstance(payload, dict) and isinstance(payload.get("result"), str):
            payload = json.loads(payload["result"])
        bars = payload.get("last_5_bars") if isinstance(payload, dict) else None
        if isinstance(bars, list) and bars:
            bar = bars[-2] if len(bars) >= 2 else bars[-1]
            o = float(bar["open"])
            h = float(bar["high"])
            l = float(bar["low"])
            c = float(bar["close"])
            if 1000 < l <= h < 10000 and l <= min(o, c) <= max(o, c) <= h:
                return {
                    "open": o, "high": h, "low": l, "close": c,
                    "change_pct": (c - o) / o * 100 if o else 0.0,
                }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
    return None


def main() -> int:
    """Run the TV sync with a cron-safe three-level degradation path."""
    global _PREVIOUS_CHART
    try:
        try:
            STAGED_OUT.unlink()
        except FileNotFoundError:
            pass
        from tv_data_bridge import tv_collection_lock
        with tv_collection_lock(timeout=180):
            _PREVIOUS_CHART = {}
            try:
                batch_id = f"xau-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:10]}"
                rc = asyncio.run(_run_with_retry(batch_id))
                if isinstance(rc, int) and rc != 0:
                    raise RuntimeError(f"同步返回非零状态 {rc}")
                # Keep five-TF capture, 5m action-cache refresh, read and pair
                # validation under one chart lease. Another asset must not switch
                # the shared TradingView chart between these publication steps.
                if not _prepare_xau_main_chart():
                    raise RuntimeError("XAU 5m主图指标重算校验失败")
                live = _refresh_tv_live_cache(batch_id)
                if not STAGED_OUT.exists():
                    raise RuntimeError("XAU五周期暂存快照未生成")
                try:
                    staged = json.loads(STAGED_OUT.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"XAU五周期暂存快照无法解析: {exc}") from exc
                contract = validate_xau_outputs(staged, live, require_batch_id=True)
                if not contract["usable"]:
                    raise RuntimeError(contract["reason"])
                os.replace(str(STAGED_OUT), str(OUT))
            finally:
                if _PREVIOUS_CHART and not _restore_chart(_PREVIOUS_CHART):
                    raise RuntimeError("XAU同步完成后恢复原TradingView图表失败")
                if _PREVIOUS_CHART:
                    _mark_restored()          # 还回去了就清掉待归还标记
        print(f"✅ XAU TV状态已原子发布 {OUT}")
        # Only publish externally after the validated state has been committed.
        # Test/degraded adapters may return a minimal synthetic snapshot; such
        # a payload is never eligible for a field report.
        if all(isinstance(staged.get("timeframes", {}).get(tf), dict)
               for tf in ("1D", "4h", "1h", "15m", "5m")):
            _push_committed_xau_report(staged)
        return 0
    except Exception as e:
        try:
            STAGED_OUT.unlink()
        except FileNotFoundError:
            pass
        # 若旧文件30分钟内，保留旧数据，不让单次CDP抖动破坏有效缓存。
        if OUT.exists() and LIVE_OUT.exists():
            try:
                existing_state = json.loads(OUT.read_text(encoding="utf-8"))
                existing_live = json.loads(LIVE_OUT.read_text(encoding="utf-8"))
                existing_contract = validate_xau_outputs(
                    existing_state, existing_live, require_batch_id=True,
                )
                if existing_contract.get("usable"):
                    state_meta = existing_contract.get("state") or {}
                    age = state_meta.get("age_seconds") or 0.0
                    print(f"⚠ XAU TV同步失败({e})，保留 {age:.0f}s 前已验证缓存")
                    return 1
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
                pass
        # 保留最近一次结构化五周期证据，避免一次主周期刷新抖动
        # 把可诊断结构抹成“缺层”。但绝不把它标成新鲜：消费者
        # 仍会按 captured timestamp 和配对契约拒绝过期数据。
        try:
            existing_state = None
            if OUT.exists():
                existing_state = json.loads(OUT.read_text(encoding="utf-8"))
            if isinstance(existing_state, dict) and existing_state.get("timeframes"):
                print(f"⚠ XAU TV同步失败({e})，保留最近一次五周期结构（本轮不可用）")
            else:
                payload = {
                    "symbol": SYMBOL,
                    "stale": True,
                    "fresh": False,
                    "usable": False,
                    "status": "stale",
                    "error": str(e)[:200],
                    "updated_at": datetime.now(TZ).isoformat(),
                }
                from atomic_json import atomic_write_json
                atomic_write_json(OUT, payload)
                print(f"⚠ XAU TV同步失败({e})，写明确不可用状态")
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
        # 同步失败必须向调度器返回非零；否则 Cron 会把明确的 stale/
        # 不可用状态记成成功，导致业务健康检查被掩盖。
        return 1


if __name__ == "__main__":
    build_parser().parse_args()
    raise SystemExit(main())
