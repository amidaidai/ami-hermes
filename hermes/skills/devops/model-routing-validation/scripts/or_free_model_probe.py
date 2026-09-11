#!/usr/bin/env python3
"""Probe OpenRouter free-tier models to pick a fixed large model.

Reusable re-run of the selection methodology in
references/or-free-model-selection.md. Tests latency, tool-call
completeness, and tier-memory across a candidate list, then prints a
verdict table. Exit code 0 on success.

Usage:
  OPENROUTER_API_KEY=sk-or-... python or_free_model_probe.py \
      [--models id1 id2 ...] [--base https://openrouter.ai/api/v1]

Reads OPENROUTER_API_KEY from env; if unset, tries ~/.hermes/.env.
"""
import argparse, json, os, subprocess, sys, time

DEFAULT_MODELS = [
    "liquid/lfm-2.5-2.6b:free",
    "minimax/minimax-m3:free",
    "minimax/minimax-m2.7:free",
    "z-ai/glm-5.2:free",
    "google/gemma-4-31b-it:free",
    "thinkingmachines/inkling:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "poolside/laguna-s-2.1:free",
]
TOOL = [{"type": "function", "function": {
    "name": "read_file", "description": "读文件",
    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]
TIER_RULES = ("规则：看下/看一眼=轻量(主周期截图+现价+行动格+Binance方向票)；"
              "现在呢=标准(轻量+邻居周期结论行)；分析/全面=完整(五周期全管线)。"
              "请用一句话回答：用户说「看下XAU」和「分析BTC」分别该走哪个档位？")


def load_key():
    k = os.getenv("OPENROUTER_API_KEY", "").strip()
    if k:
        return k
    env_home = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_home):
        for line in open(env_home, encoding="utf-8"):
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENROUTER_API_KEY not set (env or ~/.hermes/.env)")


def chat(key, base, model, messages, tools=None, max_tokens=120):
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if tools:
        payload["tools"] = tools
    t0 = time.time()
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "75",
         base.rstrip("/") + "/chat/completions",
         "-H", "Authorization: Bearer " + key,
         "-H", "Content-Type: application/json",
         "-d", json.dumps(payload)],
        capture_output=True, text=True)
    ms = int((time.time() - t0) * 1000)
    try:
        d = json.loads(r.stdout)
        msg = d["choices"][0]["message"]
        return {"ms": ms, "model": d.get("model"), "finish": msg.get("finish_reason"),
                "content": (msg.get("content") or "").strip(),
                "tool_calls": msg.get("tool_calls")}
    except Exception as e:
        return {"ms": ms, "error": str(e), "raw": r.stdout[:200]}


def tool_verdict(tc):
    if not tc:
        return "NO_CALL"
    args = tc[0]["function"]["arguments"]
    try:
        j = json.loads(args)
        return "COMPLETE" if j.get("path") else "PARTIAL"
    except Exception:
        return "BROKEN:" + str(args)[:40]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    ap.add_argument("--base", default="https://openrouter.ai/api/v1")
    args = ap.parse_args()
    key = load_key()
    print(f"{'模型':<42} {'延迟':>5} {'工具调用':<12} {'档位记忆'}")
    print("-" * 78)
    for mid in args.models:
        # 1. tool-call completeness
        tc = chat(key, args.base, mid, [{"role": "user", "content": "用read_file读 /tmp/a.txt"}], tools=TOOL)
        tv = tool_verdict(tc.get("tool_calls"))
        rc = tc.get("model")
        # model: None => endpoint anomaly
        label = "-" if rc is None else ("#" + ("?" if rc is None else ""))
        # 2. tier memory (only rerun if model responded)
        tier = "n/a"
        if tc.get("model"):
            tm = chat(key, args.base, mid, [{"role": "user", "content": TIER_RULES}], max_tokens=200)
            tier = tm.get("content", "").replace("\n", " ")[:36] or "(空/截断)"
        print(f"{mid:<42} {str(tc.get('ms','?'))+'ms':>7} {tv:<12} {tier}")
        if rc is None:
            print(f"{'':<42} {'':>7} {'MODEL=None→不可用':<12}")
    print("-" * 78)
    print("结论：三探测全过(velocity+COMPLETE+档位答对)且非小模型者胜出。")


if __name__ == "__main__":
    sys.exit(main())
