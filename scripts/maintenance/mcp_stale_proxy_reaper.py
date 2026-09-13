"""清理"无代理环境"的 financekit MCP 进程树。

背景：config.yaml 的 env 块会被 _build_safe_env 无条件合并（mcp_tool.py:763），
所以新 spawn 的 financekit 一定带 HTTP_PROXY；但 reload 之前启的陈旧进程仍是无代理环境，
它们对 Yahoo 的调用必然 429。杀掉它们，其客户端会在下次使用时自动重连并拿到正确环境。

安全边界：
  · 只杀 cmdline 含 financekit 且环境里【没有】HTTP_PROXY 的进程
  · 连同其 uvx/uv 父链一起杀（否则父进程会立即重新拉起同一个坏环境）
  · 带代理的进程一律不动
"""
from __future__ import annotations

import psutil

TARGET = "financekit"


def has_proxy(proc: psutil.Process) -> bool:
    try:
        env = proc.environ()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return True  # 读不到就保守当有，不动
    return bool(env.get("HTTP_PROXY") or env.get("HTTPS_PROXY")
                or env.get("http_proxy") or env.get("https_proxy"))


def main() -> int:
    victims: list[psutil.Process] = []
    kept: list[int] = []
    for p in psutil.process_iter(["pid", "cmdline", "name"]):
        cmd = " ".join(p.info["cmdline"] or [])
        if TARGET not in cmd.lower():
            continue
        try:
            proc = psutil.Process(p.info["pid"])
        except psutil.NoSuchProcess:
            continue
        if has_proxy(proc):
            kept.append(proc.pid)
        else:
            victims.append(proc)

    print(f"financekit 相关进程: 无代理 {len(victims)} 个 / 有代理 {len(kept)} 个")
    print(f"  保留(有代理): {sorted(kept)}")

    killed: list[str] = []
    for proc in victims:
        # 先抓父链再杀，避免父进程立刻复活坏环境
        chain = []
        cur = proc
        for _ in range(3):
            try:
                par = cur.parent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            if not par or par.pid in (0, 1):
                break
            cmd = " ".join(par.cmdline() or [])
            if TARGET not in cmd.lower() or has_proxy(par):
                break
            chain.append(par)
            cur = par
        for target in [proc, *reversed(chain)]:
            try:
                target.kill()
                killed.append(f"{target.pid}({target.name()})")
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                killed.append(f"{target.pid} 失败:{type(exc).__name__}")

    print(f"  已杀: {killed}")
    print(f"  共终止 {len(killed)} 个进程")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
