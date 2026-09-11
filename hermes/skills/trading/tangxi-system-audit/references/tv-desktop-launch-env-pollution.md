# TV Desktop 启动失败根因：ELECTRON_RUN_AS_NODE env 污染

## 症状（2026-07-09 实测）

从 Hermes 终端（git-bash / terminal 工具）启动 TradingView Desktop 带 CDP 端口时：

```
C:/Users/Administrator/AppData/Local/TradingView/TradingView.exe --remote-debugging-port=9222
# 输出: bad option: --remote-debugging-port=9222  → 立刻退出
```

用 `start "" "TV.exe" --remote-debugging-port=9222` 则报「拒绝访问」（乱码 GBK）。
端口 `127.0.0.1:9222` 始终 `connect_ex=10061`（拒绝=TV 没起来）。

## 根因

TV Desktop 是 **Electron 应用**。Hermes 终端默认注入 `ELECTRON_RUN_AS_NODE=1`
（在 `env` 里能看到 `ELECTRON_RUN_AS_NODE=1`、`NODE_ENV=production` 等）。
当这个 env 存在时，Electron 以 **node 模式** 启动，于是把 `--remote-debugging-port`
当成 node 参数拒绝，报 `bad option`，进程立即退出。

> 印证：`tools/tradingview-mcp/src/core/health.js` 的 `launch()`（约 224-229 行）
> 注释明确写「that env makes it reject Chromium flags ("bad option: --remote-debugging-port")
> and exit immediately. Strip Electron-for-node env before launching TV.」——MCP 的
> `tv_launch` 工具内部已 strip 该 env，所以 MCP 启动能用；但**手动启动 / keepalive
> 脚本启动**必须自己 strip，否则同样地失败。

## 修复（三选一，都已实测可用）

### A. bash 直接启动（最常用）
```bash
cd "D:/Hermes agent"
env -u ELECTRON_RUN_AS_NODE -u ELECTRON_DISABLE_SANDBOX \
  "C:/Users/Administrator/AppData/Local/TradingView/TradingView.exe" \
  --remote-debugging-port=9222
# 后台常驻用 terminal(background=true)，不要 shell &
```

### B. Python subprocess（keepalive 看门狗用）
```python
import os, subprocess
child_env = os.environ.copy()
child_env.pop("ELECTRON_RUN_AS_NODE", None)
child_env.pop("ELECTRON_DISABLE_SANDBOX", None)
subprocess.Popen(
    [tv_exe, f"--remote-debugging-port={PORT}"],
    env=child_env,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
)
```

### C. Windows .bat 启动脚本
```bat
set ELECTRON_RUN_AS_NODE=
set ELECTRON_DISABLE_SANDBOX=
start "" "%TV_EXE%" --remote-debugging-port=%PORT%
```
（已落地于 `tools/tradingview-mcp/scripts/launch_tv_debug.bat`）

## 验证（启动后轮询）
```bash
# 任一返回即成功
curl -s -m 3 http://127.0.0.1:9222/json/version   # 返回 TV Desktop 版本 JSON
python -c "import socket; print(socket.socket().connect_ex(('127.0.0.1',9222)))"  # 0=开放
```

## 适用范围

**任何从 Hermes 终端启动的 Electron 应用**，只要需要传 Chromium flag
（`--remote-debugging-port` / `--user-data-dir` / `--remote-debugging-address` 等），
都必须先清掉 `ELECTRON_RUN_AS_NODE`。不止 TV Desktop。

## 关联

- `scripts/tv_keepalive.py`（TV 保活看门狗，回退路径已加 child_env strip）
- `tools/tradingview-mcp/scripts/launch_tv_debug.bat`（已加 `set ELECTRON_RUN_AS_NODE=`）
- 审计铁律：TV 依赖管线前先探 9222；TV 关时作战室融合周期一致性显示 `[REST]` 属正常降级
