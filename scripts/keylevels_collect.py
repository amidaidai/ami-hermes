#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BTC 关键位采集 + 六层分级推荐 — 一次读齐图表上所有关键位，输出候选监测位清单。

读取来源（走 fetch_tv_mcp stdio，与 btc_ref_levels_sync 同源）：
  - data_get_pine_labels  → ICT 会话位（上周高/周四高/周五亚高/前高前低...）
  - data_get_pine_lines   → 全部水平关键位
  - data_get_study_values → SVP 价值区(POC/VAH/VAL/nPOC/DO/周月VWAP)
  - data_get_pine_boxes   → FVG 缺口 / OB订单块 / Breaker 框
  - data_get_pine_tables  → 主指标行动格(磁吸↑↓/现位/路径/协同) + 副指标
  - data_get_ohlcv        → 现价

输出：
  1) 打印六层分级候选监测位表
  2) 写 data/keylevels_candidates.json（含距现价，供用户勾选→keylevels_config.json）
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Make direct execution independent of the caller's current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_json import atomic_write_json

stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(stdout_reconfigure):
    stdout_reconfigure(encoding="utf-8", errors="replace")
stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if callable(stderr_reconfigure):
    stderr_reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
OUT = DATA / "keylevels_candidates.json"
SYMBOL = "BINANCE:BTCUSDT.P"
TF = "15"
TZ = timezone(timedelta(hours=8))

# 需要采集的周期数组（从高到低），主执行=15 用于磁吸/现位（行动格在该周期最完整）
TFS = ["D", "240", "60", "15", "5"]   # D/4h/1h/15m/5m
# Symbol/timeframe changes update OHLCV quickly but SVP's tables, boxes and
# Data Window require longer to recalculate. Never collect stale prior-TF data.
INDICATOR_RECALC_SECONDS = 20
MCP_CALL_TIMEOUT_SECONDS = 45
# 20260910：切周期后的确认重试。TV 会在图表真正切过去之前 ACK；共享图表上还有
# XAU 同步/到价触发/用户看盘在抢周期。只重试 1 次太脆（实测五周期续航失败 54 次），
# 改为最多 4 次、等待 5/10/15s 递增，总代价上限约 30s，仍远小于一次采集耗时。
_TF_SET_ATTEMPTS = 4
_TF_SET_RETRY_WAIT = 5
# 本轮让路（交互式分析进行中）的专用退出码：cron 侧必须能区分「让路」与「失败」。
DEFER_EXIT_CODE = 7
TV_CLI = ROOT / "tools" / "tradingview-mcp" / "src" / "cli" / "index.js"


async def _mcp_call(label: str, awaitable, *, timeout: float = MCP_CALL_TIMEOUT_SECONDS):
    """Bound every MCP await and expose the exact stage when it stalls."""
    print(f"[TV] 开始 {label}", flush=True)
    try:
        result = await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"TradingView MCP阶段超时: {label} > {timeout:.0f}s") from exc
    print(f"[TV] 完成 {label}", flush=True)
    return result


def now_bjt_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


DIAGNOSTIC_FILE = DATA / "keylevels_collect_diagnostic.json"


def _diagnostic(stage: str, *, status: str = "running", error: str | None = None,
                data_by_tf: dict | None = None) -> None:
    """Publish observable progress for MCP/lock waits and failed refreshes."""
    payload = {
        "symbol": SYMBOL,
        "stage": stage,
        "status": status,
        "updated_at": now_bjt_iso(),
        "pid": os.getpid(),
        "collected_timeframes": sorted((data_by_tf or {}).keys()),
    }
    if error:
        payload["error"] = error[:1000]
    try:
        atomic_write_json(DIAGNOSTIC_FILE, payload)
    except OSError:
        pass
    print(f"[BTC关键位] {status} stage={stage} collected={payload['collected_timeframes']}", flush=True)


def _require_no_analysis_lease() -> None:
    """交互式分析进行中 → 本轮让路（抛 AnalysisLeaseActive，由调用方按成功处理）。

    20260911：共用同一张 TradingView 图表。后台续航按 cron 切周期，而对话里的
    分析是直接读行动格 + 截图、不持 tv_collection_lock，于是续航会在读图中途把图
    切走（实测 14:07 读 5m 被连抢两次，行动格读成空表）。租约把「分析进行中」
    变成后台任务看得见的事实：让路一轮不丢数据，比硬闯读出一张空表划算。
    """
    from tv_data_bridge import AnalysisLeaseActive, analysis_lease_status
    status = analysis_lease_status()
    if status.get("active"):
        _diagnostic(
            "lease:deferred", status="deferred",
            error=(f"交互式分析进行中（剩 {status.get('remaining_seconds')}s）"
                   f"，本轮续航让路"),
        )
        raise AnalysisLeaseActive(status.get("reason") or "analysis in progress")


def _resolve_restore_target(cur_symbol: str, cur_timeframe: str) -> dict:
    """棘轮保护：决定采完后把图还给谁（与 XAU 同步同一套规则，见 tv_data_bridge）。"""
    from tv_data_bridge import chart_owner_resolve_restore
    return chart_owner_resolve_restore(SYMBOL, cur_symbol, cur_timeframe)


# ── JSON 解析兜底：mcp 返回的是 CallToolResult，先 parse_result 再 json.loads ──
def _j(raw):
    try:
        from fetch_tv_mcp import parse_result
        import json as _json
        parsed = _json.loads(parse_result(raw))
        # Direct stdio responses wrap the actual tool JSON in {success,result}.
        # Without unwrapping, every parser sees no studies/tables and silently
        # writes an empty candidate pool.
        if isinstance(parsed, dict) and isinstance(parsed.get("result"), str):
            nested = _json.loads(parsed["result"])
            if isinstance(nested, dict):
                return nested
        return parsed
    except Exception:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, dict) and isinstance(parsed.get("result"), str):
                nested = json.loads(parsed["result"])
                if isinstance(nested, dict):
                    return nested
            return parsed
        except Exception:
            return {}


def num(v):
    if v is None:
        return None
    text = str(v).strip().replace(",", "").replace("\u202f", "").replace(" ", "")
    text = text.replace("\u2212", "-")
    mult = 1.0
    if text and text[-1].upper() in {"K", "M", "B"}:
        s = text[-1].upper()
        text = text[:-1]
        mult = {"K": 1e3, "M": 1e6, "B": 1e9}[s]
    try:
        return float(text) * mult
    except Exception:
        return None


def parse_study_values(raw) -> dict:
    d = _j(raw)
    vals = {}
    for st in d.get("studies", []):
        if "SVP" in str(st.get("name", "")) or "ICT" in str(st.get("name", "")) or "VWAP" in str(st.get("name", "")):
            vals = st.get("values", {}) or {}
            break
    return {k.strip().upper().replace(" ", "_"): v for k, v in vals.items()}


def parse_pine_lines(raw) -> list[float]:
    d = _j(raw)
    levels = []
    for st in d.get("studies", []):
        for lvl in st.get("horizontal_levels", []) or []:
            try:
                levels.append(float(lvl))
            except Exception:
                continue
    return sorted(set(levels), reverse=True)


def parse_pine_labels(raw) -> list[dict]:
    d = _j(raw)
    out = []
    for st in d.get("studies", []):
        for lb in st.get("labels", []) or []:
            t = lb.get("text", "")
            try:
                p = float(lb.get("price"))
            except Exception:
                p = None
            if t or p:
                out.append({"text": t, "price": p})
    return out


def parse_pine_boxes(raw) -> list[dict]:
    d = _j(raw)
    out = []
    for st in d.get("studies", []):
        for z in st.get("zones", []) or []:
            try:
                hi = float(z.get("high"))
                lo = float(z.get("low"))
            except Exception:
                continue
            if hi and lo:
                out.append({"high": hi, "low": lo, "mid": (hi + lo) / 2})
    return out


def parse_action_grid(raw) -> dict:
    """主指标行动格 -> dict; 磁吸↕/现位/路径/协同/方向/结构"""
    d = _j(raw)
    grid = {}
    for st in d.get("studies", []):
        if "SVP" in str(st.get("name", "")) or "ICT" in str(st.get("name", "")):
            for tbl in st.get("tables", []):
                for row in tbl.get("rows", []):
                    if "|" in row:
                        k, v = row.split("|", 1)
                        grid[k.strip()] = v.strip()
            break
    return grid


def parse_sub_raw(raw) -> dict:
    d = _j(raw)
    sig = {}
    for st in d.get("studies", []):
        if "Volume Aggregated" in str(st.get("name", "")):
            for tbl in st.get("tables", []):
                for row in tbl.get("rows", []):
                    if "|" in row:
                        k, v = row.split("|", 1)
                        sig[k.strip()] = v.strip()
            break
    return sig


# ── 从行动格文本提取磁吸位（名称 价格 分NN ★HTF 距离A）──
import re

# 磁吸文本形如: ↑周五 亚 高 81500·6.1A·分33·66%  /  ↓nPOC 78390.1·3.1A·分47
MAGNET_RE = re.compile(
    r"([↑↓]?)\s*([^\s·]+)\s*([0-9][0-9,]*\.?\d*)\s*(?:·|,)?\s*(\d+\.?\d*)?A?\s*分?(\d+)?\s*(?:·|,)?\s*(★HTF)?\s*(\d+)?%?"
)


def parse_magnet(text):
    if not text or "--" in text:
        return None
    m = MAGNET_RE.search(text)
    if not m:
        return None
    return {
        "dir": m.group(1) or "",
        "name": m.group(2),
        "price": num(m.group(3)),
        "dist_atr": float(m.group(4)) if m.group(4) else None,
        "score": int(m.group(5)) if m.group(5) else None,
        "htf": bool(m.group(6)),
    }


# ── 六层分级采集 ──
async def _await_with_timeout(awaitable, stage: str, timeout: float = 45.0):
    """Bound one MCP operation and leave a durable diagnostic on timeout."""
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError as exc:
        _diagnostic(stage, status="timeout", error=f"MCP operation exceeded {timeout:.0f}s")
        raise TimeoutError(f"MCP操作超时: {stage}") from exc


async def collect_tf(session, tf: str) -> dict:
    _diagnostic(f"timeframe:{tf}:start", data_by_tf={})
    import fetch_tv_mcp as tv
    _diagnostic(f"timeframe:{tf}:wrapper_loaded")
    # MCP wrapper exports are dynamic; getattr keeps static checkers from
    # treating the runtime tool facade as a typed data module.
    set_timeframe = getattr(tv, "set_timeframe")
    get_chart_state = getattr(tv, "get_chart_state")
    get_ohlcv = getattr(tv, "get_ohlcv")
    get_study_values = getattr(tv, "get_study_values")
    get_pine_lines = getattr(tv, "get_pine_lines")
    get_pine_labels = getattr(tv, "get_pine_labels")
    get_pine_boxes = getattr(tv, "get_pine_boxes")
    get_pine_tables = getattr(tv, "get_pine_tables")
    await _await_with_timeout(set_timeframe(session, tf), f"timeframe:{tf}:set", 45)
    await asyncio.sleep(INDICATOR_RECALC_SECONDS)

    # 先验证图表真的切换成功，再读取线/标签/行动格，避免把上一周期缓存当当前周期。
    state = _j(await _await_with_timeout(get_chart_state(session), f"timeframe:{tf}:state", 45))
    # TV 会在图表**真正切过去之前**就 ACK 掉 timeframe 变更；而且共享图表上
    # 还有别的任务（XAU 同步 / 到价触发 / 用户自己看盘）会抢周期。
    # 20260910：原来只重试 1 次（等 5s）就抛错，一旦撞上就直接中止整轮五周期采集
    # → 快照不发布 → TV 五周期过期（实测 BTC 续航失败 54 次、age 达 2254s）。
    # 改为有界重试：重新下发 set_timeframe 并逐步拉长等待，最多 _TF_SET_ATTEMPTS 次。
    expected_tf = {"D": "1D", "240": "4H", "60": "1H", "15": "15M", "5": "5M"}.get(tf, tf)
    state_tf_probe = str(state.get("timeframe") or state.get("resolution") or "")
    attempt = 0
    while (state_tf_probe and state_tf_probe.upper() not in {tf.upper(), expected_tf.upper()}
           and attempt < _TF_SET_ATTEMPTS):
        attempt += 1
        _diagnostic(f"timeframe:{tf}:retry{attempt}", status="retry",
                    error=f"got {state_tf_probe}")
        await _await_with_timeout(
            set_timeframe(session, tf), f"timeframe:{tf}:retry{attempt}:set", 45)
        await asyncio.sleep(_TF_SET_RETRY_WAIT * attempt)
        state = _j(await _await_with_timeout(
            get_chart_state(session), f"timeframe:{tf}:retry{attempt}:state", 45))
        state_tf_probe = str(state.get("timeframe") or state.get("resolution") or "")
    state_symbol = str(state.get("symbol") or state.get("ticker") or "").upper()
    state_tf = str(state.get("timeframe") or state.get("resolution") or "")
    expected_symbol = SYMBOL.upper()
    if state_symbol and expected_symbol not in state_symbol and state_symbol not in expected_symbol:
        raise RuntimeError(f"symbol mismatch: expected {SYMBOL}, got {state_symbol}")
    if state_tf and state_tf.upper() not in {tf.upper(), expected_tf.upper()}:
        raise RuntimeError(
            f"timeframe mismatch: expected {tf}, got {state_tf}（已重试 {attempt} 次）")

    ohlcv_raw = await _await_with_timeout(
        get_ohlcv(session, summary=True), f"timeframe:{tf}:ohlcv", 45
    )
    ov = _j(ohlcv_raw)
    price = num(ov.get("close")) or num(ov.get("lastPrice"))
    # Preserve the summary OHLC evidence.  The five-TF contract validates
    # semantic evidence per layer; keeping only ``price`` makes an otherwise
    # valid timeframe look empty when its SVP/table payload is unavailable.
    bars = ov.get("last_5_bars")
    last_closed = bars[-2] if isinstance(bars, list) and len(bars) >= 2 and isinstance(bars[-2], dict) else None
    opening = num(ov.get("open")) or num(last_closed.get("open") if last_closed else None)
    high = num(ov.get("high")) or num(last_closed.get("high") if last_closed else None)
    low = num(ov.get("low")) or num(last_closed.get("low") if last_closed else None)
    close = num(ov.get("close")) or num(last_closed.get("close") if last_closed else None)
    volume = num(ov.get("volume")) or num(ov.get("avg_volume")) or num(last_closed.get("volume") if last_closed else None)

    sv_raw = await _await_with_timeout(get_study_values(session), f"timeframe:{tf}:study_values", 60)
    sv = parse_study_values(sv_raw)

    lines_raw = await _await_with_timeout(get_pine_lines(session), f"timeframe:{tf}:pine_lines", 60)
    lines = parse_pine_lines(lines_raw)

    lb_raw = await _await_with_timeout(get_pine_labels(session), f"timeframe:{tf}:pine_labels", 60)
    labels = parse_pine_labels(lb_raw)

    bx_raw = await _await_with_timeout(get_pine_boxes(session), f"timeframe:{tf}:pine_boxes", 60)
    boxes = parse_pine_boxes(bx_raw)

    grid_raw = await _await_with_timeout(get_pine_tables(session, study_filter="SVP+ICT+VWAP+CVD"), f"timeframe:{tf}:action_grid", 60)
    grid = parse_action_grid(grid_raw)

    sub_raw = await _await_with_timeout(get_pine_tables(session, study_filter="Volume Aggregated"), f"timeframe:{tf}:sub_grid", 60)
    sub = parse_sub_raw(sub_raw)

    return {
        "tf": tf, "price": price,
        "open": opening, "high": high, "low": low, "close": close,
        "volume": volume,
        "sv": sv, "lines": lines,
        "chart_state": {"symbol": state_symbol, "timeframe": state_tf},
        "labels": labels, "boxes": boxes, "grid": grid, "sub": sub,
    }


def _cli(*args: str, timeout: float = MCP_CALL_TIMEOUT_SECONDS) -> str:
    """Call the stable one-shot TV CLI and return its JSON payload."""
    result = subprocess.run(
        ["node", str(TV_CLI), *args], cwd=str(TV_CLI.parents[2]),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "TV CLI failed").strip()
        raise RuntimeError(f"TV CLI {' '.join(args)} failed: {detail[:300]}")
    payload = _j(result.stdout)
    if not isinstance(payload, dict) or payload.get("success") is False:
        raise RuntimeError(f"TV CLI {' '.join(args)} returned invalid payload")
    return result.stdout


def collect_tf_cli(tf: str) -> dict:
    """Collect one timeframe without a fragile long-lived stdio session."""
    _diagnostic(f"timeframe:{tf}:start")
    _cli("timeframe", tf)
    time.sleep(INDICATOR_RECALC_SECONDS)
    state = _j(_cli("state"))
    state_symbol = str(state.get("symbol") or state.get("ticker") or "").upper()
    state_tf = str(state.get("timeframe") or state.get("resolution") or "")
    expected_tf = {"D": "1D", "240": "4H", "60": "1H", "15": "15M", "5": "5M"}.get(tf, tf)
    # 20260910：TV 会在图表真正切过去之前 ACK timeframe；共享图表上还有 XAU 同步、
    # 到价触发和用户看盘在抢周期。原先 CLI 路径一次确认不对就抛错，会中止整轮采集
    # → 快照不发布 → 五周期过期（实测 btc_tv_refresh 失败 54 次、age 2254s）。
    # 改为有界重试，重试耗尽后照旧抛错，绝不放过周期错配的数据。
    _attempt = 0
    while (state_tf and state_tf.upper() not in {tf.upper(), expected_tf.upper()}
           and _attempt < _TF_SET_ATTEMPTS):
        _attempt += 1
        _diagnostic(f"timeframe:{tf}:retry{_attempt}", status="retry",
                    error=f"got {state_tf}")
        _cli("timeframe", tf)
        time.sleep(_TF_SET_RETRY_WAIT * _attempt)
        state = _j(_cli("state"))
        state_symbol = str(state.get("symbol") or state.get("ticker") or "").upper()
        state_tf = str(state.get("timeframe") or state.get("resolution") or "")
    if state_symbol and SYMBOL.upper() not in state_symbol and state_symbol not in SYMBOL.upper():
        raise RuntimeError(f"symbol mismatch: expected {SYMBOL}, got {state_symbol}")
    if state_tf and state_tf.upper() not in {tf.upper(), expected_tf.upper()}:
        raise RuntimeError(
            f"timeframe mismatch: expected {tf}, got {state_tf}（已重试 {_attempt} 次）")

    ov = _j(_cli("ohlcv", "--summary"))
    bars = ov.get("last_5_bars")
    last_closed = bars[-2] if isinstance(bars, list) and len(bars) >= 2 and isinstance(bars[-2], dict) else None
    result = {
        "tf": tf, "price": num(ov.get("close")) or num(ov.get("lastPrice")),
        "open": num(ov.get("open")) or num(last_closed.get("open") if last_closed else None),
        "high": num(ov.get("high")) or num(last_closed.get("high") if last_closed else None),
        "low": num(ov.get("low")) or num(last_closed.get("low") if last_closed else None),
        "close": num(ov.get("close")) or num(last_closed.get("close") if last_closed else None),
        "volume": num(ov.get("volume")) or num(ov.get("avg_volume")) or num(last_closed.get("volume") if last_closed else None),
        "sv": parse_study_values(_cli("values")),
        "lines": parse_pine_lines(_cli("data", "lines")),
        "labels": parse_pine_labels(_cli("data", "labels")),
        "boxes": parse_pine_boxes(_cli("data", "boxes")),
        "grid": parse_action_grid(_cli("data", "tables", "--filter", "SVP+ICT+VWAP+CVD")),
        "sub": parse_sub_raw(_cli("data", "tables", "--filter", "Volume Aggregated")),
        "chart_state": {"symbol": state_symbol, "timeframe": state_tf},
    }
    return result


def _chart_identity(payload: dict) -> tuple[str, str]:
    return (
        str(payload.get("symbol") or payload.get("ticker") or "").strip(),
        str(payload.get("resolution") or payload.get("timeframe") or "").strip(),
    )


def _restore_chart_state(previous: dict) -> bool:
    """Restore and verify the chart identity captured before background collection."""
    symbol, timeframe = _chart_identity(previous if isinstance(previous, dict) else {})
    if not symbol:
        return False
    _cli("symbol", symbol)
    if timeframe:
        _cli("timeframe", timeframe)
    # Indicators belong to shared mutable chart state too. Do not release the
    # chart lease while the restored symbol still displays the collector's SVP.
    time.sleep(INDICATOR_RECALC_SECONDS)
    restored_symbol, restored_tf = _chart_identity(_j(_cli("state")))
    symbol_ok = restored_symbol.upper() == symbol.upper()
    tf_ok = not timeframe or restored_tf.upper() == timeframe.upper()
    if not symbol_ok or not tf_ok:
        raise RuntimeError(
            f"chart restore mismatch: expected {symbol} {timeframe}, got {restored_symbol} {restored_tf}"
        )
    # 归还成功才清「待归还」——失败时保留记录，下一轮据此打断棘轮。
    from tv_data_bridge import chart_owner_mark_restored
    chart_owner_mark_restored()
    return True


def _dump_candidate_diagnosis(data_by_tf: dict, path: str) -> None:
    """候选池为空时，把每个周期实际拿到了什么打出来（20260911 新增）。

    没有这段时只看到一句 RuntimeError，无法区分是「图没切过去」、
    「SVP 位没渲染完」还是「解析规则不匹配」。
    """
    print(f"  [诊断:{path}] 候选池为空，分周期明细：")
    for tf in TFS:
        d = data_by_tf.get(tf)
        if not isinstance(d, dict):
            print(f"    {tf:>4}: 缺失")
            continue
        sym = d.get("symbol") or d.get("ticker") or "?"
        lv = d.get("levels") or d.get("key_levels") or []
        try:
            n = len(lv)
        except TypeError:
            n = -1
        print(f"    {tf:>4}: symbol={sym} price={d.get('price')} levels={n} keys={sorted(d.keys())[:8]}")
    print(f"  [诊断:{path}] 若 symbol 不是 {SYMBOL} → 图被别人切走了；"
          f"若 symbol 对但 levels=0 → 指标没渲染完或解析不匹配。")


def main_cli():
    """Collect and publish all five timeframes through isolated CLI calls."""
    if not TV_CLI.exists():
        raise RuntimeError(f"TradingView CLI不存在: {TV_CLI}")
    from tv_data_bridge import tv_collection_lock
    _require_no_analysis_lease()
    data_by_tf: dict[str, dict] = {}
    _diagnostic("cli:lock_wait")
    with tv_collection_lock(timeout=180):
        # 拿到锁后再查一次：排队等锁的这段时间里用户可能刚开始分析。
        _require_no_analysis_lease()
        _diagnostic("cli:lock_acquired")
        previous = _j(_cli("state"))
        _prev_symbol, _prev_tf = _chart_identity(previous)
        # 棘轮保护：不把上一轮残留的采集周期当成「用户图表」。
        previous = _resolve_restore_target(_prev_symbol, _prev_tf)
        try:
            _cli("symbol", SYMBOL)
            time.sleep(INDICATOR_RECALC_SECONDS)
            for tf in TFS:
                data_by_tf[tf] = collect_tf_cli(tf)
                _diagnostic(f"timeframe:{tf}:done", data_by_tf=data_by_tf)
            candidates = dedupe(build_report(data_by_tf))
            if not candidates:
                # 20260911：这个守卫本身是对的（禁止用空池覆盖旧池），
                # 但只报一句话无法定位。失败前打出每个周期拿到了什么。
                _dump_candidate_diagnosis(data_by_tf, "cli")
                raise RuntimeError("empty candidate pool")
            main_data = data_by_tf.get("15") or next(iter(data_by_tf.values()))
            atomic_write_json(OUT, build_snapshot_payload(
                data_by_tf, price=main_data.get("price"),
                timestamp=now_bjt_iso(), candidates=candidates,
            ))
            # Refresh BTC's strict main-action cache before restoring the user's
            # chart. The five-TF and 15m publications remain one chart lease.
            _cli("timeframe", "15")
            time.sleep(INDICATOR_RECALC_SECONDS)
            from tv_data_bridge import collect_and_cache
            live = collect_and_cache(expect_symbol=SYMBOL)
            if not isinstance(live, dict) or not live.get("fresh"):
                raise RuntimeError("BTC 15m主行动缓存刷新失败")
            live_payload = dict(live)
            live_payload["source"] = "keylevels_collect_cli"
            atomic_write_json(DATA / "tv_live.json", live_payload)
            atomic_write_json(DATA / "tv_live_BTCUSDT.json", live_payload)
        finally:
            if not _restore_chart_state(previous):
                _diagnostic("cli:restore_skipped", status="failed", error="previous chart identity unavailable")
    return main_data.get("price"), candidates


def build_report(data_by_tf: dict[str, dict]) -> list[dict]:
    """六层分级：价值区/会话位/结构位/FVG/OB/磁吸+现位。返回候选列表 [{name, price, layer, tf, note}]"""
    cands = []
    main = data_by_tf.get("15") or data_by_tf.get("5") or next(iter(data_by_tf.values()))
    price = main.get("price")

    # ① 价值区（15m 主）
    sv = main.get("sv", {})
    value_layers = [
        ("POC", sv.get("POC_PRICE") or sv.get("POC")),
        ("nPOC", sv.get("NPOC_PRICE") or sv.get("NPOC")),
        ("VAH", sv.get("VAH_PRICE") or sv.get("VAH")),
        ("VAL", sv.get("VAL_PRICE") or sv.get("VAL")),
        ("DO", sv.get("DO_PRICE") or sv.get("DO")),
        ("W-VWAP", sv.get("W_VWAP_PRICE") or sv.get("W_VWAP")),
        ("M-VWAP", sv.get("M_VWAP_PRICE") or sv.get("M_VWAP")),
    ]
    for name, val in value_layers:
        p = num(val)
        if p and price:
            cands.append({"name": f"价值区·{name}", "price": round(p, 2), "layer": "价值区", "tf": "15m", "dist": round(p - price, 2)})

    # ② ICT 会话位（labels 带名字）
    for lb in main.get("labels", []):
        t = lb.get("text", "")
        p = lb.get("price")
        if not p:
            continue
        if any(k in t for k in ("上周", "周四", "周五", "周六", "周日", "亚", "纽", "高", "低", "POC", "VAH", "VAL")):
            name = t if t else "会话位"
            cands.append({"name": f"会话·{name}", "price": round(p, 2), "layer": "会话位", "tf": "15m", "dist": round(p - price, 2) if price else None})

    # ③ 结构位 FVG/OB (boxes)
    for bx in main.get("boxes", []):
        mid = bx.get("mid")
        if mid and price:
            side = "牛FVG/OB" if mid > price else "熊FVG/OB"
            cands.append({"name": f"结构·{side}", "price": round(mid, 2), "layer": "结构位", "tf": "15m", "dist": round(mid - price, 2), "box": bx})

    # ④ 磁吸位（主指标行动格）
    grid = main.get("grid", {})
    for tag, key in (("磁吸↑", "磁吸↑"), ("磁吸↓", "磁吸↓")):
        txt = grid.get(key, "")
        mag = parse_magnet(txt)
        if mag and mag.get("price"):
            cands.append({"name": f"磁吸{tag}·{mag['name']}", "price": round(mag["price"], 2), "layer": "磁吸位", "tf": "15m", "dist": round(mag["price"] - price, 2) if price else None, "score": mag.get("score"), "htf": mag.get("htf"), "atr": mag.get("dist_atr")})

    # ⑥ HTF 磁吸位（来自4h行动格，若15m与4h磁吸不同价则作为高周期候选）
    htf_d = data_by_tf.get("240") or data_by_tf.get("4h")
    if htf_d:
        for tag, key in (("磁吸↑", "磁吸↑"), ("磁吸↓", "磁吸↓")):
            txt = htf_d.get("grid", {}).get(key, "")
            mag = parse_magnet(txt)
            if mag and mag.get("price"):
                cands.append({"name": f"磁吸HTF·{mag['name']}", "price": round(mag["price"], 2), "layer": "HTF磁吸", "tf": "4h", "dist": round(mag["price"] - price, 2) if price else None, "score": mag.get("score"), "htf": True, "atr": mag.get("dist_atr")})

    # ⑤ 现位 + 路径（行动格，下一步关注位）
    look = grid.get("现位", "") or grid.get("看位", "")
    path = grid.get("路径", "")
    if price:
        # 从现位/路径文本抽价格
        path_text = re.sub(r"B[0-9][0-9,.]*", "", look + " " + path)
        m = re.search(r"(?<![0-9])([0-9][0-9,.]{3,})", path_text)
        if m:
            p = float(m.group(1).replace(",", ""))
            cands.append({"name": f"现位/路径·{look[:18]}", "price": round(p, 2), "layer": "现位", "tf": "15m", "dist": round(p - price, 2)})
    return cands


def dedupe(cands: list[dict]) -> list[dict]:
    """按价格去重（容差0.15%），只去同层的重复；跨层（如磁吸 vs 会话位同价）保留，
    因为磁吸位自带评分价值，不能因与会话位价格相同而被吞掉。"""
    seen = {}
    out = []
    for c in sorted(cands, key=lambda x: (x.get("layer"), -(x.get("score") or 0))):
        key = (c.get("layer"), round(c["price"] / 100))
        if key in seen:
            continue
        seen[key] = True
        out.append(c)
    return out


def build_snapshot_payload(
    data_by_tf: dict[str, dict],
    *,
    price,
    timestamp: str,
    candidates: list[dict],
    symbol: str = SYMBOL,
) -> dict:
    """Build a candidate file that also preserves every collected TF record.

    ``layers`` is only a declaration of the requested resolutions.  The
    ``timeframes`` map is the evidence consumed by the full-card contract;
    ``timeframes_complete`` makes a partial collection observable instead of
    letting it masquerade as a five-timeframe refresh.
    """
    ordered = {
        tf: data_by_tf[tf]
        for tf in TFS
        if isinstance(data_by_tf.get(tf), dict) and data_by_tf[tf]
    }
    return {
        "symbol": symbol,
        "tf": "15",
        "layers": TFS,
        "timeframes": ordered,
        "timeframes_complete": len(ordered) == len(TFS),
        "price": price,
        "ts": timestamp,
        "source": "tradingview_mcp",
        "status": "candidate_pool_only",
        "grid": (ordered.get("15") or {}).get("grid", {}),
        "sub": (ordered.get("15") or {}).get("sub", {}),
        "candidates": candidates,
    }


async def main():
    _diagnostic("startup")
    # Load the canonical wrapper by absolute path.  The repository root also
    # contains a legacy fetch_tv_mcp.py, which otherwise shadows this module
    # when launched as ``python scripts/keylevels_collect.py``.
    import importlib.util
    import sys as _sys
    wrapper_path = ROOT / "scripts" / "fetch_tv_mcp.py"
    spec = importlib.util.spec_from_file_location("fetch_tv_mcp", wrapper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"canonical TV wrapper unavailable: {wrapper_path}")
    tv_wrapper = importlib.util.module_from_spec(spec)
    _sys.modules["fetch_tv_mcp"] = tv_wrapper
    spec.loader.exec_module(tv_wrapper)
    set_symbol = getattr(tv_wrapper, "set_symbol")
    get_chart_state = getattr(tv_wrapper, "get_chart_state")
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp import ClientSession

    server = ROOT / "tools" / "tradingview-mcp" / "src" / "server.js"
    if not server.exists():
        raise RuntimeError(f"TradingView MCP server不存在: {server}")
    # Cron may invoke this script from any directory; the MCP server resolves
    # packages/configuration relative to its working directory.
    sp = StdioServerParameters(
        command="node",
        args=[str(server)],
        cwd=str(server.parent.parent),
        encoding_error_handler="replace",
    )
    _diagnostic("mcp:process_configured", data_by_tf={})
    _diagnostic("mcp:parameters", data_by_tf={})

    data_by_tf = {}
    # Serialize this five-timeframe chart mutation with all other TV jobs.
    from tv_data_bridge import tv_collection_lock
    _diagnostic("lock:waiting")
    lease = tv_collection_lock(timeout=180)
    lease.__enter__()
    _diagnostic("lock:acquired")
    try:
        async with stdio_client(sp) as (r, w):
            _diagnostic("mcp:connected")
            async with ClientSession(r, w) as s:
                await _await_with_timeout(s.initialize(), "mcp:initialize", 60)
                _diagnostic("mcp:initialized")
                await _await_with_timeout(set_symbol(s, SYMBOL), "symbol:set", 60)
                _diagnostic("symbol:set_done")
                await asyncio.sleep(INDICATOR_RECALC_SECONDS)
                state = _j(await _await_with_timeout(get_chart_state(s), "symbol:state", 45))
                actual_symbol = state.get("symbol")
                if actual_symbol != SYMBOL:
                    raise RuntimeError(f"symbol mismatch after set_symbol: expected {SYMBOL}, got {actual_symbol}")
                for tf in TFS:
                    try:
                        data_by_tf[tf] = await collect_tf(s, tf)
                        _diagnostic(f"timeframe:{tf}:done", data_by_tf=data_by_tf)
                    except Exception as e:
                        _diagnostic(f"timeframe:{tf}:failed", status="failed", error=f"{type(e).__name__}: {e}", data_by_tf=data_by_tf)
                        print(f"  ⚠ {tf} 采集失败: {type(e).__name__}: {e}", flush=True)
                # Publish before leaving the MCP context. Some stdio client
                # versions can terminate/close noisily during __aexit__; a
                # complete snapshot must not be lost after all five reads have
                # already succeeded.
                if set(data_by_tf) == set(TFS):
                    early_candidates = dedupe(build_report(data_by_tf))
                    if early_candidates:
                        early_main = data_by_tf.get("15") or next(iter(data_by_tf.values()))
                        early_payload = build_snapshot_payload(
                            data_by_tf,
                            price=early_main.get("price"),
                            timestamp=now_bjt_iso(),
                            candidates=early_candidates,
                        )
                        atomic_write_json(OUT, early_payload)
                        _diagnostic("publish:early_success", status="success", data_by_tf=data_by_tf)
    finally:
        lease.__exit__(None, None, None)

    if not data_by_tf:
        raise RuntimeError("no valid TradingView timeframe data; candidate pool preserved")
    missing_timeframes = [tf for tf in TFS if tf not in data_by_tf]
    if missing_timeframes:
        raise RuntimeError(f"incomplete TradingView timeframe data: {','.join(missing_timeframes)}; candidate pool preserved")
    cands = build_report(data_by_tf)
    cands = dedupe(cands)
    if not cands:
        # A stale/mismatched TV chart must never overwrite the previous
        # candidate pool with a syntactically-valid but empty “success”.
        # 20260911：加分周期明细，把「为什么空」变成可定位的。
        _dump_candidate_diagnosis(data_by_tf, "stdio")
        raise RuntimeError("empty candidate pool")

    main_d = data_by_tf.get("15") or next(iter(data_by_tf.values()))
    price = main_d.get("price")
    ts = now_bjt_iso()

    payload = build_snapshot_payload(
        data_by_tf,
        price=price,
        timestamp=ts,
        candidates=cands,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(OUT, payload)

    # ── 打印六层分级表 ──
    print(f"BTC 关键位六层分级推荐 · {ts}")
    print(f"现价 {price:,.0f}" if price else "现价未知")
    layer_order = ["价值区", "会话位", "结构位", "磁吸位", "现位"]
    for layer in layer_order:
        rows = [c for c in cands if c["layer"] == layer]
        if not rows:
            continue
        print(f"\n【{layer}】")
        for c in sorted(rows, key=lambda x: abs(x.get("dist") or 0)):
            dist = c.get("dist")
            dstr = f"{dist:+,.0f}" if dist is not None else "?"
            extra = ""
            if c.get("score"):
                extra += f" 分{c['score']}"
            if c.get("htf"):
                extra += " ★HTF"
            if c.get("atr"):
                extra += f" 距{c['atr']}A"
            print(f"  {c['name']:26s} {c['price']:>10,.0f}  (现价{dstr}){extra}")
    print(f"\n已写 {OUT}")

    return price, cands


def _run_worker() -> int:
    """Run collection and fail closed if no fresh candidate publication lands."""
    from tv_data_bridge import AnalysisLeaseActive
    previous_ts = None
    try:
        previous = json.loads(OUT.read_text(encoding="utf-8"))
        previous_ts = str(previous.get("ts") or "")
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    try:
        result = main_cli()
    except AnalysisLeaseActive:
        # 让路不是失败：分析只占几分钟，下一轮 cron 自然补上。
        print("BTC关键位采集本轮让路（交互式分析进行中），不计失败", file=sys.stderr, flush=True)
        return DEFER_EXIT_CODE
    except KeyboardInterrupt:
        print("BTC关键位采集被中断", file=sys.stderr, flush=True)
        return 1
    except BaseException as exc:
        # stdio/MCP clients may terminate through SystemExit on EOF. Treat
        # every non-normal termination as a failed refresh instead of allowing
        # cron to record a false success.
        print(f"BTC关键位采集异常终止: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    try:
        published = json.loads(OUT.read_text(encoding="utf-8"))
        published_ts = str(published.get("ts") or "")
        complete = published.get("timeframes_complete") is True
        timeframes = published.get("timeframes") or {}
        candidates = published.get("candidates") or []
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"BTC关键位采集未生成可读候选池: {exc}", file=sys.stderr, flush=True)
        return 1
    if result is None or not published_ts or published_ts == previous_ts or not complete or len(timeframes) < len(TFS) or not candidates:
        reason = "未形成新的完整五周期候选发布"
        _diagnostic("publish:failed", status="failed", error=reason,
                    data_by_tf=timeframes)
        print(f"BTC关键位采集{reason}，保留旧候选池", file=sys.stderr, flush=True)
        return 1
    _diagnostic("publish:success", status="success", data_by_tf=timeframes)
    return 0


def _run_cli() -> int:
    """Supervise the collector so a hard child exit cannot report false success."""
    try:
        previous = json.loads(OUT.read_text(encoding="utf-8"))
        previous_ts = str(previous.get("ts") or "")
    except (OSError, UnicodeError, json.JSONDecodeError):
        previous_ts = ""
    for attempt in range(2):
        try:
            child = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker"],
                cwd=str(ROOT), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=360,
            )
        except subprocess.TimeoutExpired:
            print(f"BTC关键位采集子进程超时(第{attempt + 1}次)", file=sys.stderr, flush=True)
            continue
        if child.stdout:
            print(child.stdout, end="", flush=True)
        if child.stderr:
            print(child.stderr, end="", file=sys.stderr, flush=True)
        if child.returncode == DEFER_EXIT_CODE:
            # 让路：本轮没有新发布是**预期**的，不能记成采集失败再去重试一遍。
            print("BTC关键位采集本轮让路（交互式分析进行中），不计失败", file=sys.stderr, flush=True)
            return 0
        try:
            published = json.loads(OUT.read_text(encoding="utf-8"))
            changed = str(published.get("ts") or "") not in ("", previous_ts)
            valid = (
                published.get("timeframes_complete") is True
                and len(published.get("timeframes") or {}) == len(TFS)
                and bool(published.get("candidates"))
            )
        except (OSError, UnicodeError, json.JSONDecodeError):
            changed = valid = False
        if child.returncode == 0 and changed and valid:
            return 0
        print(
            f"BTC关键位采集未发布新快照(第{attempt + 1}次, rc={child.returncode})",
            file=sys.stderr, flush=True,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(_run_worker() if "--worker" in sys.argv else _run_cli())
