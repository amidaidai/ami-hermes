"""FinanceMCP 实跑探针：启动 npx finance-mcp 走 stdio JSON-RPC，列出真实 tools 目录。

用于验证 README 声称的 19 个 tool 是否真实存在、以及无 Tushare 积分时
tools/list 会不会按凭证裁剪（README 声称"按凭证动态显示 Tools"）。
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

CMD = ["npx.cmd", "-y", "finance-mcp"]

# 带真实 Tushare token 再测一次：验证 README 的"按凭证裁剪 tools/list"行为
# （凭证存在就展示 → 积分不足的工具会出现在目录里，但 call 时必然失败）
if "--with-token" in sys.argv:
    tok = Path("D:/Hermes agent/hermes/secrets/tushare_token.txt").read_text(encoding="utf-8").strip()
    import os
    os.environ["TUSHARE_TOKEN"] = tok
    print(f"已注入 TUSHARE_TOKEN ({tok[:6]}...{tok[-4:]})", flush=True)


def main() -> int:
    print("启动:", " ".join(CMD), flush=True)
    try:
        proc = subprocess.Popen(
            CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", shell=False)
    except Exception as exc:
        print("启动失败:", type(exc).__name__, exc)
        return 2

    err_lines: list[str] = []

    def drain() -> None:
        assert proc.stderr
        for line in proc.stderr:
            err_lines.append(line.rstrip())

    threading.Thread(target=drain, daemon=True).start()

    def send(obj: dict) -> None:
        assert proc.stdin
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    def read_reply(want_id: int, timeout: float = 90.0) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = proc.stdout.readline()  # type: ignore[union-attr]
            if not line:
                return None
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == want_id:
                return msg
        return None

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2024-11-05",
                     "capabilities": {},
                     "clientInfo": {"name": "tangxi-probe", "version": "1"}}})
    init = read_reply(1)
    if not init:
        print("initialize 无响应（可能 npx 拉包超时或包名不存在）")
        print("stderr 尾部:", "\n".join(err_lines[-15:]))
        proc.kill()
        return 3
    info = (init.get("result") or {}).get("serverInfo") or {}
    print(f"握手成功: {info.get('name')} v{info.get('version')}")

    send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    reply = read_reply(2)
    if not reply:
        print("tools/list 无响应")
        print("stderr 尾部:", "\n".join(err_lines[-15:]))
        proc.kill()
        return 4

    tools = (reply.get("result") or {}).get("tools") or []
    print(f"\ntools/list 返回 {len(tools)} 个工具")
    for t in tools:
        desc = (t.get("description") or "").splitlines()
        head = desc[0][:56] if desc else ""
        print(f"  - {t.get('name'):<26} {head}")

    proc.kill()
    if err_lines:
        print("\nstderr 尾部:")
        for line in err_lines[-10:]:
            print("  ", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
