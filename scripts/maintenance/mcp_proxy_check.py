#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 代理配置守卫 —— 防止「境外源 MCP 无代理 → 静默 429」再次复发。

背景（2026-09-13 实测定位）：
    financekit 的 Yahoo 腿被封的是**本机直连 IP**；而 MCP stdio 子进程的环境变量
    在 tools/mcp_tool.py::_build_safe_env() 里被**白名单过滤**，代理变量不在名单内，
    因此必须在 **该 server 的 `env:` 块**里显式写代理，否则调用一律
    `Too Many Requests. Rate limited.`（看起来像 Yahoo 限流，其实是自己没走代理）。

本脚本检查两层：
    ① 配置层：config.yaml 里 `mcp_servers.<name>.env` 是否含 HTTP_PROXY / HTTPS_PROXY
    ② 运行层：正在运行的该 server 进程，其环境变量里是否真的有代理
       （用于捕获「配置改了但网关没重读 → 仍是旧环境」这种假修复）

只有该 server 明确需要代理时才纳入检查（NEEDS_PROXY），不要把本地/国内源拉进来。

退出码：0 = 全部通过；2 = 发现配置或运行层问题。
默认写 data/maintenance/mcp_proxy_check.json，--no-write 可关闭。
只读：不修改任何配置、不重启任何进程。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 需要代理的 MCP server（境外源）。键=server 名，值=为什么需要。
NEEDS_PROXY: dict[str, str] = {
    "financekit": "境外源：Yahoo（行情/宏观）+ CoinGecko",
}

PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY")
PROC_HINT = {
    "financekit": "financekit",
}


def config_candidates() -> list[Path]:
    """按优先级给出 config.yaml 可能的位置（不改任何文件）。"""
    cands: list[Path] = []
    if os.environ.get("HERMES_CONFIG"):
        cands.append(Path(os.environ["HERMES_CONFIG"]))
    home = Path(os.path.expanduser("~"))
    for env_name in ("HERMES_HOME",):
        if os.environ.get(env_name):
            cands.append(Path(os.environ[env_name]) / "config.yaml")
    cands += [
        home / "AppData" / "Local" / "hermes" / "config.yaml",  # Windows 默认
        home / ".hermes" / "config.yaml",
        home / ".config" / "hermes" / "config.yaml",
    ]
    return cands


def find_config() -> Path | None:
    for p in config_candidates():
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def load_mcp_servers(config_path: Path) -> dict:
    """读 config.yaml 的 mcp_servers 段。PyYAML 缺失时抛 RuntimeError。"""
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("需要 PyYAML 才能解析 config.yaml") from exc
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    servers = data.get("mcp_servers") or {}
    return servers if isinstance(servers, dict) else {}


def check_config_env(servers: dict, needs: "dict[str, str] | None" = None) -> list[dict]:
    """配置层检查：返回问题列表（空 = 通过）。"""
    needs = NEEDS_PROXY if needs is None else needs
    problems: list[dict] = []
    for name, why in needs.items():
        cfg = servers.get(name)
        if cfg is None:
            problems.append(
                {"layer": "config", "server": name, "code": "missing_server",
                 "detail": f"config.yaml 里没有 mcp_servers.{name}（需要代理：{why}）"}
            )
            continue
        if cfg.get("enabled") is False:
            problems.append(
                {"layer": "config", "server": name, "code": "disabled",
                 "detail": f"mcp_servers.{name} 被禁用（需要代理：{why}）"}
            )
            continue
        env = cfg.get("env") or {}
        if not isinstance(env, dict):
            env = {}
        missing = [k for k in PROXY_KEYS if not str(env.get(k) or "").strip()]
        if missing:
            problems.append({
                "layer": "config", "server": name, "code": "missing_proxy_env",
                "detail": (f"mcp_servers.{name}.env 缺少 {'/'.join(missing)}；"
                           f"修复：hermes config set mcp_servers.{name}.env.HTTP_PROXY \"http://127.0.0.1:7897\""
                           f"（HTTPS_PROXY 同理）"),
            })
    return problems


def iter_process_envs(hint: str) -> list[dict]:
    """返回 [(pid, {env})]：名字含 hint 的进程及其环境变量。psutil 缺失则返回 []。"""
    out: list[dict] = []
    try:
        import psutil  # type: ignore
    except ImportError:  # pragma: no cover
        return out
    me = os.getpid()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["pid"] == me:
                continue
            pname = (proc.info.get("name") or "").lower()
            # .exe 后缀与大小写都不敏感地比
            if hint.lower() not in pname.replace(".exe", ""):
                continue
            env = proc.environ()
        except Exception:
            continue
        out.append({"pid": proc.info["pid"], "env": env})
    return out


def check_runtime_env(procs: list[dict], needs: "dict[str, str] | None" = None,
                      hints: "dict[str, str] | None" = None) -> list[dict]:
    """运行层检查：已运行的进程是否真的带代理。无进程时只记 INFO，不算失败。"""
    needs = NEEDS_PROXY if needs is None else needs
    hints = PROC_HINT if hints is None else hints
    problems: list[dict] = []
    for name in needs:
        running = [p for p in procs if p.get("server") == name]
        if not running:
            continue  # 没跑 = 无法验证，交给 info 层
        for p in running:
            env = p.get("env") or {}
            if not str(env.get("HTTP_PROXY") or "").strip():
                problems.append({
                    "layer": "runtime", "server": name, "code": "live_process_without_proxy",
                    "detail": (f"pid={p.get('pid')} 的 {name} 进程环境里没有 HTTP_PROXY——"
                               f"典型原因：配置已改但网关没重读。修复：在网关会话发 /reload-mcp"),
                })
    return problems


def collect_runtime(needs: "dict[str, str] | None" = None,
                    hints: "dict[str, str] | None" = None) -> list[dict]:
    needs = NEEDS_PROXY if needs is None else needs
    hints = PROC_HINT if hints is None else hints
    procs: list[dict] = []
    for name in needs:
        for p in iter_process_envs(hints.get(name, name)):
            procs.append({"server": name, **p})
    return procs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MCP 代理配置守卫（只读）")
    ap.add_argument("--no-write", action="store_true", help="不写 JSON 报告")
    args = ap.parse_args(argv)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"═ MCP 代理守卫 · {now} ═")

    cfg_path = find_config()
    if cfg_path is None:
        print("❌ 找不到 config.yaml（试过 HERMES_HOME / ~/AppData/Local/hermes / ~/.hermes）")
        return 2
    print(f"配置：{cfg_path}")

    try:
        servers = load_mcp_servers(cfg_path)
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 2

    procs = collect_runtime()
    cfg_problems = check_config_env(servers)
    run_problems = check_runtime_env(procs)
    problems = cfg_problems + run_problems

    for name, why in NEEDS_PROXY.items():
        env = ((servers.get(name) or {}).get("env") or {})
        live = [p["pid"] for p in procs if p.get("server") == name]
        ok = "✅" if str(env.get("HTTP_PROXY") or "").strip() else "❌"
        print(f"{ok} {name:12s} 代理={env.get('HTTP_PROXY') or '(未设)'}  "
              f"运行进程={live or '(无)'}  ← {why}")

    print()
    if problems:
        for p in problems:
            print(f"⚠️  [{p['layer']}] {p['server']}: {p['detail']}")
    else:
        print("✅ 配置层与运行层均通过：需要代理的 MCP server 都已带代理。")

    report = {
        "checked_at": now,
        "config_path": str(cfg_path),
        "needs_proxy": NEEDS_PROXY,
        "problems": problems,
        "verdict": "ok" if not problems else "problem",
        "note": "只读检查；不代表外部源可达性，仅代表本地配置/进程环境正确。",
    }
    if not args.no_write:
        out = Path("data/maintenance/mcp_proxy_check.json")
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"报告：{out}")
        except OSError as exc:
            print(f"（写报告失败，结果仍有效：{exc}）")

    return 0 if not problems else 2


if __name__ == "__main__":
    sys.exit(main())
