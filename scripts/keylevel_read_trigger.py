#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一关键位触发读取 — 读实时守卫(keylevel_guard.py)写给各品种的 trigger_{symbol}.json。

守卫 0.5s 轮询配置(keylevels_config.json)里所有品种所有顶点，穿越任一位 →
写 data/trigger_{symbol}.json（含 level/price/dir/ts/cooldown_until）。
本脚本每2min 查各品种触发文件：有未过期的 TRIGGER 且未处理 → 输出 TRIGGER 供 agent 分析推送；
无 → 静默 WAIT。到价捕捉由实时守卫负责，cron 只做分析搬运。
"""
import json
import os
import argparse
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = Path("D:/Hermes agent/data")
STATE_FILE = Path(os.path.expanduser("~/AppData/Local/hermes/data/keylevel_agent_state.json"))

# 支持的品种（守卫配置里出现过）；分析搬运按需扩展
TRIGGER_FILES = {
    "BTCUSDT": DATA / "trigger_BTCUSDT.json",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-dispatch", action="store_true", help="只读取请求，不运行分析推送")
    args = parser.parse_args()
    # 先读配置，拿到所有品种
    try:
        cfg = json.loads((DATA / "keylevels_config.json").read_text(encoding="utf-8"))
    except Exception:
        cfg = {"symbols": {}}

    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        state = {}

    triggers = []
    for sym in cfg.get("symbols", {}).keys():
        fname = TRIGGER_FILES.get(sym, DATA / f"trigger_{sym}.json")
        try:
            trig = json.loads(fname.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not trig.get("triggered"):
            continue
        status = trig.get("analysis_status")
        if status == "analyzed" and not trig.get("push_retry_required"):
            continue
        if status == "analyzed" and int(trig.get("push_retry_count", 0) or 0) >= 3:
            continue
        if status == "analyzed":
            # 分析结果已落盘，但投递未完成；只允许受控补投递，
            # 不重复重跑分析本身。
            trig["analysis_status"] = "pending_push"
            status = "pending_push"
        if status == "pending_push" and int(trig.get("push_retry_count", 0) or 0) >= 3:
            continue
        if status == "analyzing" and time.time() - float(trig.get("analysis_updated_epoch", 0) or 0) < 900:
            continue
        if status == "failed":
            retry_at = float(trig.get("next_retry_epoch", 0) or 0)
            if int(trig.get("retry_count", 0) or 0) >= 3 or time.time() < retry_at:
                continue
        ts_key = trig.get("ts", "")
        zone = trig.get("level", "")
        cooldown_until = trig.get("cooldown_until", 0.0)
        last_done_ts = state.get(sym, {}).get(zone, "")
        if last_done_ts == ts_key:
            continue   # 已处理过，静默
        triggers.append({
            "event_id": trig.get("event_id", f"{sym}-{zone}-{ts_key}"),
            "event_type": trig.get("event_type", "keylevel_cross"),
            "symbol": sym,
            "tv_symbol": trig.get("tv_symbol", f"BINANCE:{sym}.P"),
            "level": zone,
            "level_price": trig.get("level_price"),
            "price": trig.get("price"),
            # dir 是价格穿越方向，不是交易方向；禁止把它转成多/空建议。
            "dir": trig.get("cross_direction", trig.get("cross_dir", "")),
            "analysis_required": True,
            "analysis_mode": "quick",
            "analysis_status": status or "pending",
            "source": trig.get("source", "binance_rest"),
            "config_revision": trig.get("config_revision", "unknown"),
            "level_source": trig.get("level_source", "keylevels_config"),
            "event_class": trig.get("event_class", "price_cross_only"),
            "level_valid_until": trig.get("level_valid_until"),
            "ts": ts_key,
            "cooldown_until": cooldown_until,
        })

    if not triggers:
        print("WAIT no-trigger", flush=True)
        sys.exit(0)

    # 只输出最新一条请求；读取器不判断方向，dir 仅表示价格穿越方向。
    trig = max(triggers, key=lambda item: str(item.get("ts", "")))
    print(
        f"ANALYSIS_REQUEST mode=quick symbol={trig['symbol']} level={trig['level']} "
        f"price={trig['price']} dir={trig['dir']} event_id={trig['event_id']} ts={trig['ts']}",
        flush=True,
    )
    if args.no_dispatch:
        return

    # 定时任务默认只完成“读取→快速分析”本地闭环；TG 外发必须由
    # 显式环境授权，读取器本身仍不判断方向、不下单。
    dispatcher = Path("D:/Hermes agent/scripts/keylevel_analysis_dispatcher.py")
    push_requested = os.environ.get("TANGXI_ENABLE_AUTOMATED_TG") == "1"
    result = subprocess.run(
        [sys.executable, str(dispatcher), trig["symbol"]] + (["--push"] if push_requested else []),
        cwd="D:/Hermes agent", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=240,
    )
    print(result.stdout.rstrip(), flush=True)
    if result.returncode:
        print(result.stderr[-500:], file=sys.stderr, flush=True)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
