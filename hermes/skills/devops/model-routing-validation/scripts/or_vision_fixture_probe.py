#!/usr/bin/env python3
"""OpenRouter free-pool VISION fixture probe (slow fan-out, JSONL output).

Validated 2026-09-13. A 5-way free-vision fan-out takes 18-200s PER MODEL, so
this MUST run as a background script, NOT inside execute_code: the 300s cell cap
kills the run and loses every intermediate result plus the kernel state.

Usage (background so partial progress survives):
  python or_vision_fixture_probe.py [--image PATH|DIR] [--models id1 id2 ...] [--out FILE]

Each finished model appends ONE JSONL line to --out, so poll the file or
process(action='poll') instead of waiting for the whole run.

Ground truth, do this INDEPENDENTLY before scoring:
  1) the screenshot's minute (from mtime, BJT) -> Binance **1m** klines; do NOT
     use the 15m close, the chart shows the live quote at capture time;
  2) run the session's own vision_analyze on the same PNG as the human baseline.
  TV perpetual (BTCUSDT.P) vs Binance spot is the SAME volatility dimension; a
  ~50 USD gap is NOT evidence the model misread.
"""
import argparse, base64, glob, json, os, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

DEFAULT_Q = ("这是交易软件截图。只回答四点，每点一行：1)品种代码 2)周期 3)图上最新价格读数 "
             "4)副图窗格数量与名称。看不清就说看不清，不要猜。")
DEFAULT_MODELS = [
    "inclusionai/ling-3.0-flash-vl:free",
    "dots-studio/dots-3-note-preview:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-3-super-120b-a12b:free",  # negative control: 404 no image input
]


def load_key():
    k = os.getenv("OPENROUTER_API_KEY", "").strip()
    if k:
        return k
    p = os.path.expanduser("~/.hermes/.env")
    for line in open(p, encoding="utf-8"):
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENROUTER_API_KEY not set (env or ~/.hermes/.env)")


def probe(mid, key, b64, question, out, max_tokens, timeout):
    body = {"model": mid, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}]}
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    t0 = time.time()
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        sec = round(time.time() - t0, 1)
        # 200 + error body is a REAL shape (Nvidia ResourceExhausted / provider_unavailable).
        # Never index d["choices"] before checking.
        if "choices" not in d:
            rec = {"model": mid, "sec": sec, "verdict": "UPSTREAM_OR_ERR",
                   "detail": str(d.get("error", {}).get("message", ""))[:160]}
        else:
            ch = d["choices"][0]
            msg = ch.get("message", {})
            u = d.get("usage") or {}
            rec = {"model": mid, "sec": sec, "verdict": "OK",
                   "finish": ch.get("finish_reason"),
                   "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                   "content": str(msg.get("content"))[:800]}
    except urllib.error.HTTPError as e:
        rec = {"model": mid, "sec": round(time.time() - t0, 1), "verdict": "HTTP%d" % e.code,
               "detail": e.read()[:200].decode("utf-8", "ignore")}
    except Exception as e:
        rec = {"model": mid, "sec": round(time.time() - t0, 1), "verdict": "ERR",
               "detail": str(e)[:200]}
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False)[:420], flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=r"D:/Hermes agent/tools/tradingview-mcp/screenshots")
    ap.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    ap.add_argument("--question", default=DEFAULT_Q)
    ap.add_argument("--max-tokens", type=int, default=4000,
                    help="read-image probes need >=3000; reasoning models eat the budget")
    ap.add_argument("--timeout", type=int, default=260)
    ap.add_argument("--out", default=os.path.expandvars(r"$LOCALAPPDATA\Temp\or_vision_probe.jsonl"))
    a = ap.parse_args()
    img = a.image
    if os.path.isdir(img):
        img = max(glob.glob(os.path.join(img, "*.png")), key=os.path.getmtime)
    b64 = base64.b64encode(open(img, "rb").read()).decode()
    print("image=%s  models=%d  out=%s" % (img, len(a.models), a.out), flush=True)
    open(a.out, "w").close()
    key = load_key()
    with ThreadPoolExecutor(max_workers=max(1, len(a.models))) as ex:
        list(ex.map(lambda m: probe(m, key, b64, a.question, a.out, a.max_tokens, a.timeout), a.models))
    print("DONE -> " + a.out, flush=True)


if __name__ == "__main__":
    main()
