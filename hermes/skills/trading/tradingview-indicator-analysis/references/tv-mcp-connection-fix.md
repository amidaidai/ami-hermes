# TV MCP 连接修复流程（2026-08-29 全面修订）

## ⚠️ 第一优先：pydantic-core 版本冲突（2026-08-29 新发现）

**症状**: `tv_health_check` 失败、`fetch_tv_mcp.py` 报 `The installed pydantic-core version (2.48.0) is incompatible with the current pydantic version, which requires 2.46.4`

**排查顺序**:
```
python -c "import pydantic; import pydantic_core; print(pydantic.__version__, pydantic_core.__version__)"
```
→ 若显示 `pydantic=2.13.4` 但 `pydantic_core=2.48.0` → 版本不匹配

**修复**:
```bash
pip install pydantic-core==2.46.4 --force-reinstall
# 验证
python -c "import pydantic_core; print(pydantic_core.__version__)"  # 应输出 2.46.4
```

**预防**: 每次分析前先 `tv_health_check` 验证 CDP 连接 + API 可用；若失败先修复版本冲突再重试 TV 连接。**此版本冲突是 TV MCP 不可用的首因**，不应误判为 TV Desktop 进程或网络问题。

---

## Step 1: 检查 CDP 端口（pydantic 已修复后）
```bash
# 端口探测
curl http://127.0.0.1:9222/json/version
```
→ 若返回 JSON（Browser: TradingView）→ TV Desktop 进程在运行

## Step 2: 若 TV 未运行 — 启动带 CDP
```bash
# 方法1: 用 node 直接拉起 MCP server（TV Desktop 自动启动）
cd D:/Hermes\ agent/tools/tradingview-mcp/src
node server.js
# 方法2: PowerShell
powershell -Command "Start-Process 'C:\Users\Administrator\AppData\Local\TradingView\TradingView.exe' -ArgumentList '--remote-debugging-port=9222'"
```

## Step 3: 验证 TV MCP
```bash
cd D:/Hermes\ agent/scripts
python btc_ref_levels_sync.py
```
→ 输出含 `✅ BTC关键位` → TV MCP 正常

## Step 4: 已知陷阱 — fetch_tv_mcp.py 的 sys.path 注入
`fetch_tv_mcp.py` 开头有错误的 hermes venv 路径注入：
```python
# 原（有bug）:
hermes_venv = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))
sys.path.insert(0, str(hermes_venv))
# 这会加载错误的 pydantic_core 2.48.0（应为 hermes-agent venv 的 2.46.4）
```
**修复**: 注释掉这两行，使用默认 Python 环境（`hermes-agent/venv` 的 Python 已有正确版本）。
```python
# 修复后:
# TANGXI-FIX 2026-08-29: 禁用错误的 hermes venv site-packages 注入
# hermes_venv = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))
# sys.path.insert(0, str(hermes_venv))
```

## Step 5: 若 CDP 连通但 API 不可用
TV Desktop 可能在初始化图表，等待 8-10 秒后重试。

## 截图最大化
截图前调用 `ui_fullscreen()` 确保 TV 窗口全屏。
截图用 `capture_screenshot(region="full")` 获取全窗口（含价格轴 + CVD 窗格）。