#!/usr/bin/env python3
"""Hermes 模型通道体检（默认只读，不打印任何密钥）。

用 Hermes venv 的 python 运行，保证 yaml 可导入：
    "$LOCALAPPDATA/hermes/hermes-agent/venv/Scripts/python.exe" channel_audit.py
可选：
    --latency   从 logs/agent.log 聚合 provider/model 真实延迟
    --versions  只打印版本与配置路径

输出对应 skill 的「全通道体检」第 1–4 步：配置层 → 凭据层 → 各通道目录 → 会话/YAML 路由差异。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SECRET_RE = re.compile(r"key|token|secret|password|access_token|refresh_token", re.I)

def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "hermes"
    return Path.home() / ".hermes"


def load_config(home: Path) -> dict:
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        print("! 需要 Hermes venv 的 python（缺 yaml）；配置层跳过")
        return {}
    p = home / "config.yaml"
    if not p.exists():
        print(f"! 未找到 {p}")
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, str) and SECRET_RE.search(k) and len(v) > 8:
                out[k] = f"<{len(v)}B>"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def head(title: str) -> None:
    print(f"\n=== {title} ===")


def section_config(cfg: dict) -> None:
    head("配置层")
    print("model:", json.dumps(cfg.get("model"), ensure_ascii=False))
    print("fallback_providers:", json.dumps(cfg.get("fallback_providers"), ensure_ascii=False))
    print("delegation:", json.dumps(cfg.get("delegation"), ensure_ascii=False))
    aux = cfg.get("auxiliary") or {}
    for slot in ("vision", "compression"):
        print(f"auxiliary.{slot}:", json.dumps(aux.get(slot), ensure_ascii=False))
        prov = (aux.get(slot) or {}).get("provider")
        if prov == "auto":
            print(f"  !! {slot}=auto 会跟随主模型：主模型额度/故障会一起传导（视觉槽必须显式钉死）")
    moa = cfg.get("moa") or {}
    print("moa.active_preset:", repr(moa.get("active_preset")), "| default_preset:", repr(moa.get("default_preset")))
    for name, preset in (moa.get("presets") or {}).items():
        print(f"  preset {name}: enabled={preset.get('enabled')} refs={len(preset.get('reference_models') or [])}")
    print("providers:", json.dumps(sorted((cfg.get("providers") or {}).keys()), ensure_ascii=False))
    for cp in cfg.get("custom_providers") or []:
        print("custom_provider:", redact({k: cp.get(k) for k in ("name", "base_url", "model", "api_mode")}))
    pf = cfg.get("prefill_messages_file") or (cfg.get("agent") or {}).get("prefill_messages_file")
    if pf:
        p = (home / pf) if not Path(pf).is_absolute() else Path(pf)
        print(f"prefill: {pf} {'OK' if p.exists() else 'MISSING'}")
        if p.exists():
            txt = p.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"(GPT-[\w.\-]+|gpt-[\w.\-]+|deepseek-[\w.\-]+|grok-[\w.\-]+)", txt):
                print(f"  !! prefill 内写死了模型名 {m.group(1)}：换主模型时必须同步")
                break


def section_credentials(home: Path) -> dict:
    head("凭据层 auth.json")
    p = home / "auth.json"
    if not p.exists():
        print(f"! 未找到 {p}")
        return {}
    auth = json.loads(p.read_text(encoding="utf-8"))
    pool = auth.get("credential_pool") or {}
    for name in sorted(pool):
        creds = pool[name] or []
        if not creds:
            print(f"  {name:<28} 0 条凭据（残留引用，不是通道）")
            continue
        for c in creds:
            bits = [c.get("auth_type"), c.get("last_status"), c.get("failure_reason"), c.get("last_error_reason"), c.get("last_error_code")]
            print(f"  {name:<28} {c.get('id','?'):<28} " + " | ".join(str(b) for b in bits if b))
    for name, info in (auth.get("providers") or {}).items():
        err = (info or {}).get("last_auth_error") or {}
        if err.get("relogin_required"):
            print(f"  !! {name}: relogin_required ({err.get('reason')}, {err.get('message')})")
    return auth


def load_env(home: Path) -> dict:
    out = {}
    p = home / ".env"
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def section_catalogs(cfg: dict, env: dict) -> None:
    head("各通道目录（只读 GET /models）")
    import urllib.error
    import urllib.request

    targets = []
    if env.get("DEEPSEEK_API_KEY"):
        targets.append(("deepseek(直连)", "https://api.deepseek.com/models", env["DEEPSEEK_API_KEY"]))
    if env.get("OPENROUTER_API_KEY"):
        targets.append(("openrouter", "https://openrouter.ai/api/v1/models", env["OPENROUTER_API_KEY"]))
    for cp in cfg.get("custom_providers") or []:
        base = (cp.get("base_url") or "").rstrip("/")
        name = cp.get("name") or base
        key = env.get("BAI_API_KEY") if "b.ai" in base else None
        if base and key:
            targets.append((f"custom:{name}", base + "/models", key))
    for name, url, key in targets:
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key, "User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            ids = [m.get("id") for m in data.get("data", [])]
            print(f"  {name:<22} {len(ids)} 个模型")
            print("      ", ", ".join(ids[:24]), "..." if len(ids) > 24 else "")
        except urllib.error.HTTPError as e:
            print(f"  {name:<22} HTTP {e.code} {e.read().decode('utf-8','replace')[:120]}")
        except Exception as e:  # noqa: BLE001
            print(f"  {name:<22} ERR {type(e).__name__}: {str(e)[:100]}")


def section_routes(cfg: dict) -> None:
    head("路由差异")
    print("YAML 默认:", json.dumps(cfg.get("model"), ensure_ascii=False))
    print("会话实际请以系统提示的 Model/Provider 为准；两者不一致属会话级覆盖，报告里必须分开写。")
    print("看图：/model、/reasoning、/moa 属于会话级；config.yaml 只决定新会话默认。")


def section_latency(home: Path) -> None:
    head("真实延迟（logs/agent.log 聚合）")
    import collections
    import statistics

    agg = collections.defaultdict(list)
    for f in sorted((home / "logs").glob("agent.log*")):
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for ln in lines:
            if "API call #" not in ln:
                continue
            mo = re.search(r"model=([^\s,]+)", ln)
            pr = re.search(r"provider=([^\s,]+)", ln)
            la = re.search(r"latency=([\d.]+)", ln)
            if mo and pr and la:
                agg[(pr.group(1), mo.group(1))].append(float(la.group(1)))
    for (prov, model), vals in sorted(agg.items(), key=lambda kv: -len(kv[1])):
        print(f"  {prov:<16} {model:<44} n={len(vals):<6} avg={statistics.mean(vals):.1f}s p50={statistics.median(vals):.1f}s max={max(vals):.0f}s")
    if not agg:
        print("  （没有带 latency= 的行；日志格式可能已变）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latency", action="store_true", help="聚合 agent.log 真实延迟")
    ap.add_argument("--versions", action="store_true", help="只打印路径")
    args = ap.parse_args()

    home = hermes_home()
    print(f"HERMES_HOME = {home}")
    cfg = load_config(home)
    if args.versions:
        return 0
    if cfg:
        section_config(cfg)
    section_credentials(home)
    env = load_env(home)
    print("\n.env 中的密钥名：", ", ".join(sorted(k for k in env if k.endswith("_API_KEY"))) or "（无）")
    section_catalogs(cfg, env)
    section_routes(cfg)
    if args.latency:
        section_latency(home)
    print("\n提醒：目录能列出 ≠ 可用；付费/免费能力要分开验，凭据 4xx 与模型 4xx 要分开报。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
