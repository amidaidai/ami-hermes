#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TV Desktop 启动目录同步器 v1.0 — Windows 双路径闭环。

背景（2026-07-03 首次实测，2026-09-13 复现）：
  Windows 上 TradingView Desktop 存在两条路径：
    1) C:\\Program Files\\WindowsApps\\TradingView.Desktop_<ver>_x64__<hash>  ← Microsoft Store / MSIX 官方安装位（会随 Store 自动更新）
    2) %LOCALAPPDATA%\\TradingView\\TradingView.exe                          ← TV MCP / launch 脚本实际启动位
  二者互不同步：Store 自动更新只动 (1)，而 launch_tv_debug.bat 与
  tv_keepalive.py 优先探测 (2)，于是"软件已升级但运行链路仍是旧版"。

实测约束：不要直接启动 WindowsApps 下的 exe 并传 --remote-debugging-port，
可能报 `bad option`。正确做法是把 (1) 全量同步到 (2)，再从 (2) 启动。

用法：
  python scripts/tv_sync_appdir.py                 # 需要时同步（不杀进程）
  python scripts/tv_sync_appdir.py --kill          # 需要时先 taskkill TradingView.exe
  python scripts/tv_sync_appdir.py --dry-run       # 只报告，不落盘
  python scripts/tv_sync_appdir.py --json          # 机读输出

退出码：0 = 已一致或同步成功；1 = 同步失败（调用方可降级继续，不阻塞）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROGRAM_FILES = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
WINDOWSAPPS = PROGRAM_FILES / "WindowsApps"
LOCAL_TV_DIR = LOCALAPPDATA / "TradingView"
PKG_GLOB = "TradingView.Desktop_*_x64__*"

# Identity Version="3.4.1.8194"（双引号或单引号皆可）
_IDENTITY_RE = re.compile(r"<Identity\b[^>]*?\bVersion\s*=\s*[\"']([0-9][0-9.]*)[\"']", re.I)


def parse_identity_version(manifest: Path) -> str | None:
    """从 AppxManifest.xml 抽 Identity Version，失败返回 None（不抛异常）。"""
    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = _IDENTITY_RE.search(text)
    return m.group(1) if m else None


def vtuple(v: str | None) -> tuple[int, ...]:
    if not v:
        return ()
    try:
        return tuple(int(x) for x in v.split(".") if x != "")
    except ValueError:
        return ()


def find_windowsapps_packages() -> list[dict]:
    """列出 WindowsApps 下所有 TradingView 包，按版本降序。"""
    found: list[dict] = []
    try:
        entries = list(WINDOWSAPPS.glob(PKG_GLOB))
    except OSError:
        return found
    for d in entries:
        manifest = d / "AppxManifest.xml"
        if not manifest.exists():
            continue
        ver = parse_identity_version(manifest)
        if not ver:
            continue
        found.append({"dir": str(d), "version": ver, "key": vtuple(ver)})
    found.sort(key=lambda x: x["key"], reverse=True)
    return found


def local_version() -> str | None:
    return parse_identity_version(LOCAL_TV_DIR / "AppxManifest.xml")


def _taskkill() -> None:
    """停掉所有 TradingView 进程；失败静默（可能本就没开）。"""
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "TradingView.exe"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            timeout=60,
        )
    except Exception:
        pass


def _robocopy_mirror(src: Path, dst: Path) -> int:
    """全量镜像同步；返回 robocopy 退出码（0-7 视为成功）。"""
    cmd = [
        "robocopy", str(src), str(dst),
        "/MIR", "/NFL", "/NDL", "/NJH", "/NJS", "/R:1", "/W:1",
    ]
    try:
        return subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            timeout=900,
        ).returncode
    except Exception:
        return 16


def sync_if_needed(kill: bool = False, dry_run: bool = False) -> dict:
    """核心逻辑：Store 版本高于本地启动目录版本时全量同步。

    返回 {
      status: up_to_date | synced | sync_failed | no_windowsapps | no_local_copy,
      local_version, store_version, source, action
    }
    """
    pkgs = find_windowsapps_packages()
    cur = local_version()

    if not pkgs:
        return {"status": "no_windowsapps", "local_version": cur,
                "store_version": None, "source": None, "action": "none"}

    newest = pkgs[0]
    result = {
        "status": "up_to_date",
        "local_version": cur,
        "store_version": newest["version"],
        "source": newest["dir"],
        "action": "none",
    }

    # 本地方不存在（只有 Store 包）→ 视为需要落地一份启动副本
    if cur is None:
        result["status"] = "no_local_copy"
    elif vtuple(cur) >= newest["key"]:
        return result  # 已一致或本地更新，不动
    else:
        result["status"] = "outdated"

    if dry_run:
        result["action"] = "dry_run"
        return result

    if kill:
        _taskkill()

    rc = _robocopy_mirror(Path(newest["dir"]), LOCAL_TV_DIR)
    if rc >= 8:
        result["status"] = "sync_failed"
        result["action"] = f"robocopy_rc={rc}"
        return result

    after = local_version()
    result["local_version"] = after
    if vtuple(after) >= newest["key"] and after is not None:
        result["status"] = "synced"
        result["action"] = f"robocopy_rc={rc}"
    else:
        result["status"] = "sync_failed"
        result["action"] = f"verify_mismatch local={after} store={newest['version']}"
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="同步 TradingView Store 包到 MCP 启动目录")
    ap.add_argument("--kill", action="store_true",
                    help="同步前先 taskkill TradingView.exe（文件被占用时必须）")
    ap.add_argument("--dry-run", action="store_true", help="只报告不落盘")
    ap.add_argument("--json", action="store_true", help="机读 JSON 输出")
    ap.add_argument("--quiet", action="store_true",
                    help="仅在有动作时输出（供 bat / cron 调用）")
    args = ap.parse_args()

    res = sync_if_needed(kill=args.kill, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["status"] in ("up_to_date", "synced", "no_windowsapps") else 1

    quiet_ok = args.quiet and res["status"] in ("up_to_date", "no_windowsapps")
    if not quiet_ok:
        label = {
            "up_to_date": "✅ 启动目录已是最新",
            "synced": "✅ 已同步 Store 新版到启动目录",
            "outdated": "⬆ 检测到版本落后（dry-run）",
            "no_local_copy": "⬆ 本地无启动副本，已从 Store 包落地",
            "sync_failed": "❌ 同步失败",
            "no_windowsapps": "○ 未发现 WindowsApps 下的 TradingView 包，跳过",
        }.get(res["status"], res["status"])
        print(f"{label}: 本地={res['local_version']} Store={res['store_version']} "
              f"action={res['action']}")
        if res["source"]:
            print(f"   源: {res['source']}")
    return 0 if res["status"] in ("up_to_date", "synced", "no_windowsapps") else 1


if __name__ == "__main__":
    sys.exit(main())
