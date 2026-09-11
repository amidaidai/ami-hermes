# pydantic 版本兼容性修复记录（2026-08-29）

## 症状

`hermes-agent[mcp]` 的依赖 `pydantic-core==2.48.0` 与 `pydantic==2.13.4` 不兼容。
`from mcp.client.stdio import stdio_client` 立即抛出 `SystemError`，所有依赖 MCP stdio 的脚本（含 `fetch_tv_mcp.py` / `btc_ref_levels_sync.py` / `xau_tv_sync.py`）无法连接 TradingView MCP。

## 触发条件

所有使用 `from mcp.client.stdio import stdio_client` / `from mcp import ClientSession` 的脚本。

## 完整错误信息

```
SystemError: The installed pydantic-core version (2.48.0) is incompatible with the current pydantic version, which requires 2.46.4. If you encounter this error, make sure that you haven't upgraded pydantic-core manually.
```

## 根因

`pip install hermes-agent[mcp]` 安装时带上 `pydantic-core>=2.48`，与已安装的 `pydantic==2.13.4` 冲突。Hermes agent 虚拟环境 (`hermes-agent/venv`) 与系统 `pip` 不一致导致版本分裂。

## 修复命令

```bash
# 方式 1: 降级 pydantic-core（推荐，先试）
pip install 'pydantic-core==2.46.4' --force-reinstall

# 方式 2: 升级 pydantic（备选）
pip install 'pydantic==2.13.4' --force-reinstall

# 验证
python -c "import pydantic, pydantic_core; print(pydantic.__version__, pydantic_core.__version__)"
# 期望: 2.13.4 2.46.4
```

## 审计检查（并入 tangxi-runtime-audit-and-cleanup Step 0.5）

每次审计第一步必须执行：
```bash
python -c "import pydantic, pydantic_core; print(pydantic.__version__, pydantic_core.__version__)"
```
不兼容 → P0，立即修复。

## 影响范围

- `fetch_tv_mcp.py`（所有 `get_study_values` / `get_pine_lines` / `get_ohlcv`）
- `btc_ref_levels_sync.py`（`from fetch_tv_mcp import ...`）
- `xau_tv_sync.py`（`from fetch_tv_mcp import ...`）
- 任何 `import mcp` 的脚本

## 关联参考

- `tangxi-system-audit/SKILL.md` 中的 TV MCP CDP 恢复流程
- `references/tv-mcp-cdp-recovery.md`
