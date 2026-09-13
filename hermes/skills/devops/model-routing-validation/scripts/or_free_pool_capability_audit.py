#!/usr/bin/env python3
"""OpenRouter free-pool capability audit — three-source, capability-first.

Why this exists: ranking fallback candidates by probe latency is WRONG for a
fallback slot (a fallback must be able to take over the primary's work, so
non-hallucination rate / tool reliability / capability come first, latency is
only a cost item). This script assembles the evidence needed to rank by
capability instead:

  Source 1 (authoritative): OpenRouter endpoints API per model ->
      uptime_last_1d, latency_last_30m p50/p90/p99, throughput_last_30m,
      supported_parameters (tools), max_completion_tokens
  Source 2 (shape): a real tool-call probe per model, which also catches the
      Nvidia-style "HTTP 200 + error body" overload shape
  Source 3 (manual): the model PAGE carries the ability numbers this script
      cannot fetch — AA Intelligence/Agentic, GPQA Diamond, IFBench, tau2-Bench,
      AA-LCR, Terminal-Bench Hard, and crucially the AA NON-HALLUCINATION rate.
      web_extract the model page for those before writing any recommendation.

Third-party daily re-test (independent reproduction of 429/403/empty answers,
NOT ability): https://klymentiev.com/blog/openrouter-free-tier
structured:  https://klymentiev.com/assets/data/openrouter-free-models.json

Read-only. Key from env OPENROUTER_API_KEY or ~/.hermes/.env.

Usage:
  python or_free_pool_capability_audit.py                # all :free models
  python or_free_pool_capability_audit.py --no-probe     # catalog metrics only
  python or_free_pool_capability_audit.py --models a:free b:free
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://openrouter.ai/api/v1"
TOOL = [{"type": "function", "function": {
    "name": "read_file", "description": "读文件",
    "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                   "required": ["path"]}}}]


def load_key():
    k = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if k:
        return k
    envp = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(envp):
        for line in open(envp, encoding="utf-8"):
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENROUTER_API_KEY not set (env or ~/.hermes/.env)")


def get(url, key):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
    return json.loads(urllib.request.urlopen(req, timeout=45).read())


def list_free(key):
    d = get(f"{API}/models", key)["data"]
    # ':free' suffix only; 'openrouter/free' is a random router, excluded below.
    return sorted(m["id"] for m in d if m["id"].endswith(":free"))


def metrics(mid, key):
    """Authoritative endpoint metrics. Returns one row per endpoint."""
    try:
        d = get(f"{API}/models/{mid}/endpoints", key)["data"]
    except Exception as e:
        return [{"model": mid, "error": str(e)[:80]}]
    arch = d.get("architecture") or {}
    mods = ",".join(arch.get("input_modalities") or [])
    rows = []
    for e in (d.get("endpoints") or []):
        lat = e.get("latency_last_30m") or {}
        thr = e.get("throughput_last_30m") or {}
        sp = e.get("supported_parameters") or []
        rows.append({
            "model": mid,
            "provider": e.get("provider_name"),
            "ctx": e.get("context_length"),
            "mods": mods,
            "vision": "image" in mods,
            "tools": "tools" in sp,
            "maxc": e.get("max_completion_tokens"),
            "up1d": round(e.get("uptime_last_1d") or 0, 1),
            "p50": round(lat["p50"] / 1000, 2) if lat.get("p50") else None,
            "p90": round(lat["p90"] / 1000, 1) if lat.get("p90") else None,
            "p99": round(lat["p99"] / 1000, 1) if lat.get("p99") else None,
            "tps": thr.get("p50"),
        })
    return rows or [{"model": mid, "error": "no endpoints"}]


def tool_probe(mid, key, budget=1500):
    """Real tool-call probe. Returns a shape verdict.

    Shape 'HTTP_200_ERROR_BODY' is the Nvidia overload pattern: status 200 with
    an error object and no 'choices'. Always parse the body before indexing it.
    """
    body = json.dumps({
        "model": mid,
        "messages": [{"role": "user",
                      "content": "用 read_file 读 D:/Hermes agent/docs/系统总览.md"}],
        "tools": TOOL,
        "max_tokens": budget,
    }).encode()
    req = urllib.request.Request(
        f"{API}/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    t0 = time.time()
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as e:
        return round(time.time() - t0, 1), "HTTP%d" % e.code, e.read()[:90].decode("utf-8", "ignore")
    except Exception as e:
        return round(time.time() - t0, 1), "ERR", str(e)[:80]
    secs = round(time.time() - t0, 1)
    if "choices" not in d:
        msg = (d.get("error") or {}).get("message") or str(d)[:90]
        return secs, "HTTP_200_ERROR_BODY", str(msg)[:90]
    ch = d["choices"][0]
    m = ch.get("message") or {}
    tc = m.get("tool_calls")
    if tc:
        try:
            args = json.loads(tc[0]["function"]["arguments"])
            return secs, ("COMPLETE" if args.get("path") else "PARTIAL"), ""
        except Exception:
            return secs, "BROKEN", ""
    return secs, "NO_CALL", str(m.get("content"))[:60]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--no-probe", action="store_true", help="skip the tool probe (catalog metrics only)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    key = load_key()
    models = args.models or list_free(key)
    print(f"# {len(models)} ':free' models — metrics from the authoritative endpoints API\n")

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        rows = [r for sub in ex.map(lambda m: metrics(m, key), models) for r in sub]

    print(f"{'model':<56} {'provider':<10} {'ctx':>8} {'vis':<4} {'tool':<5} "
          f"{'up1d%':>6} {'p50':>7} {'p90':>7} {'p99':>7} {'tps':>5}")
    print("-" * 132)
    for r in sorted(rows, key=lambda x: -(x.get("up1d") or 0)):
        if "error" in r:
            print(f"{r['model']:<56} !! {r['error']}")
            continue
        print(f"{r['model']:<56} {str(r['provider']):<10} {str(r['ctx']):>8} "
              f"{'Y' if r['vision'] else '-':<4} {'Y' if r['tools'] else '-':<5} "
              f"{r['up1d']:>6} {str(r['p50']):>7} {str(r['p90']):>7} {str(r['p99']):>7} {str(r['tps']):>5}")

    if not args.no_probe:
        print("\n## tool-shape probe (also catches 'HTTP_200_ERROR_BODY' overload)\n")
        with ThreadPoolExecutor(max_workers=min(6, args.workers)) as ex:
            probes = list(ex.map(lambda m: (m,) + tool_probe(m, key), models))
        for mid, secs, shape, note in sorted(probes, key=lambda x: x[1]):
            print(f"{mid:<56} {str(secs) + 's':>8} {shape:<20} {note}")

    print("\n" + "=" * 78)
    print("RANK BY CAPABILITY, NOT BY THE NUMBERS ABOVE.")
    print("The ability numbers live only on the model PAGE (web_extract):")
    print("  AA Intelligence / Agentic, GPQA Diamond, IFBench, tau2-Bench,")
    print("  AA-LCR, Terminal-Bench Hard, and the AA NON-HALLUCINATION rate.")
    print("Non-hallucination rate is the first criterion for a trading fallback:")
    print("  ultra-550b 70.3% vs super-120b 13.0% -> ultra leads despite 60s E2E.")
    print("Latency/availability are cost items -> cover them with chain depth.")
    print("Also check: Tool Call Error Rate, Structured Output Error Rate,")
    print("Availability (3d) [OR counts errors AND empty replies as failures],")
    print("free-endpoint training clauses, and any 'Going away <date>' banner.")


if __name__ == "__main__":
    main()
