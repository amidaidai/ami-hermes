#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把关键位穿越事件交给快速分析；本脚本不产生方向、不下单。"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_json import atomic_write_json


def load_trigger(symbol: str) -> tuple[Path, dict]:
    path = DATA / f"trigger_{symbol}.json"
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, {}


def save_status(path: Path, trigger: dict, status: str, error: str | None = None) -> None:
    trigger["analysis_status"] = status
    trigger["analysis_updated_epoch"] = time.time()
    if status == "failed":
        trigger["retry_count"] = int(trigger.get("retry_count", 0) or 0) + 1
        trigger["next_retry_epoch"] = time.time() + min(1800, 120 * (2 ** trigger["retry_count"]))
    if error:
        trigger["analysis_error"] = error[:500]
    atomic_write_json(path, trigger)


def dispatch_command(symbol: str, *, push: bool = False) -> list[str]:
    command = [sys.executable, str(ROOT / "scripts" / "auto_card.py"), symbol, "--quick"]
    if push:
        command.append("--push")
    return command


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", nargs="?", default="BTCUSDT")
    parser.add_argument("--push", action="store_true", help="显式允许分析结果推送")
    args = parser.parse_args()
    path, trigger = load_trigger(args.symbol)
    if not trigger.get("analysis_required") or trigger.get("analysis_status") not in {"pending", "failed", "analyzing", "pending_push"}:
        print("WAIT no-pending-analysis", flush=True)
        return 0

    event_id = trigger.get("event_id", "unknown")
    trigger["analysis_status"] = "analyzing"
    trigger["analysis_started_epoch"] = time.time()
    save_status(path, trigger, "analyzing")
    push_requested = args.push and os.environ.get("TANGXI_ENABLE_AUTOMATED_TG") == "1"
    if args.push and not push_requested:
        print("PUSH_DISABLED automated Telegram delivery is off", flush=True)
    command = dispatch_command(args.symbol, push=push_requested)
    try:
        result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        save_status(path, trigger, "failed", str(exc))
        print(f"ANALYSIS_FAILED event_id={event_id} error={exc}", flush=True)
        return 1
    # 分开记录分析、文字卡和截图，不能因为截图缺失而把已经成功的
    # 分析整体判成失败；stdout 是当前 auto_card 的兼容回执来源。
    out = result.stdout or ""
    text_push_ok = "Telegram文字卡已推送" in out
    photo_push_ok = "Telegram主周期截图" in out
    if push_requested:
        trigger["text_push_status"] = "sent" if text_push_ok else "failed_or_missing"
        trigger["photo_push_status"] = "sent" if photo_push_ok else "failed_or_missing"
        trigger["push_status"] = "sent" if text_push_ok and photo_push_ok else "partial" if text_push_ok or photo_push_ok else "failed_or_missing"
        if trigger["push_status"] != "sent":
            trigger["push_retry_required"] = True
            trigger["push_retry_count"] = int(trigger.get("push_retry_count", 0) or 0) + 1
            trigger["push_last_error"] = "文字卡或主周期截图投递未获得成功回执"
        else:
            trigger["push_retry_required"] = False
    else:
        trigger["text_push_status"] = "not_requested"
        trigger["photo_push_status"] = "not_requested"
        trigger["push_status"] = "not_requested"
        trigger["push_retry_required"] = False
    if result.returncode != 0:
        save_status(path, trigger, "failed", result.stderr or result.stdout)
        print(f"ANALYSIS_FAILED event_id={event_id} rc={result.returncode}", flush=True)
        return result.returncode
    log_path = DATA / f"analysis_dispatch_{event_id.replace('/', '_').replace(':', '_')}.log"
    # 日志也是消费者读取的发布物：先写临时文件再替换，避免进程中断留下半截日志。
    log_tmp = log_path.with_suffix(log_path.suffix + ".tmp")
    log_tmp.write_text(result.stdout[-20000:], encoding="utf-8")
    log_tmp.replace(log_path)
    trigger["analysis_log"] = str(log_path)
    # 分析本身成功与投递成功分开建模：失败投递不得被伪装成完整闭环。
    trigger["analysis_status"] = "analyzed"
    trigger["analysis_finished_epoch"] = time.time()
    save_status(path, trigger, "analyzed")
    print(f"ANALYSIS_DONE mode=quick symbol={args.symbol} event_id={event_id}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())