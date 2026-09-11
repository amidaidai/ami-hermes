# 双 Python 解释器冲突 · auto_card 子命令 quick 模式 P0-5

> 2026-09-02 全面审计新发现 · 完整证据链 + 修复命令

## 现象

`auto_card BTCUSDT --quick` 在第 3841 行 `_collect_binance_data` 抛 `ModuleNotFoundError: No module named 'requests'`，但 `auto_card BTCUSDT --full` 跑通。

## 根因

`auto_card.py` 没钉死解释器，**实际跑的解释器是 uv cpython 3.11**，不是 `python`（Hermes venv）。

| 解释器 | 路径 | 状态 |
|---|---|---|
| Hermes venv | `C:/Users/Administrator/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe` | ✅ `requests 2.33` 已装 |
| uv cpython 3.11 | `C:/Users/Administrator/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe` | 🔴 缺 6 个核心包 |

uv cpython 3.11 缺什么：
- `requests`
- `pydantic`
- `aiohttp`
- `numpy`
- `pandas`
- `websockets`

## 验证

```python
# 跑一下确认两个解释器状态
import subprocess
for py in [
    'python',  # PATH 默认
    r'C:/Users/Administrator/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe',
]:
    r = subprocess.run(
        [py, '-c',
         'import requests, pydantic, aiohttp, numpy, pandas, websockets; '
         'print("all ok")'],
        capture_output=True, text=True, timeout=5,
    )
    print(f'{py:80s} {"✅" if r.returncode==0 else "🔴 " + r.stderr.strip()[:100]}')
```

## 修复

一行命令（`uv` 自动写入 `cpython-3.11` 的 site-packages）：

```bash
uv pip install -p $(uv python find) requests pydantic aiohttp numpy pandas websockets
```

## 为什么 A 阶段没暴露

- A 阶段跑的 `auto_card BTCUSDT --full` / `XAUUSD --full` 不走 `_collect_binance_data` 路径
- full 模式的 Binance 数据来自 `_collect_binance_data` 也走（行 2550），但 XAU full 完全不调这函数（走 `xau_tv_sync` 路径）
- BTC full 调 `_collect_binance_data` 但被 A 阶段 `try/except` 兜底隐藏
- **只有 quick 模式**走完整 Binance 数据采集链路 → 必崩

## 铁律

1. 任何 `auto_card <SYMBOL> --quick` 报 `ModuleNotFoundError` **先验解释器**，不直接说"包没装"
2. P0 排错清单新增第 7 项：**双解释器冲突**（不是 6 个独立包问题）
3. 若需 `auto_card` 钉解释器（避免未来 uv 升级再踩），在 `auto_card.py:4806` 改 `subprocess.run([str(Path(__file__).parent / "_pin_interpreter.py"), ...])` 写一个固定 venv python 的小 stub

## 实测错误原文

```
Traceback (most recent call last):
  File "D:\Hermes agent\scripts\auto_card.py", line 4806, in <module>
    auto_card(sym, push=do_push, mode=_mode)
  File "D:\Hermes agent\scripts\auto_card.py", line 3841, in auto_card
    _collect_binance_data(engine_data, symbol)
  File "D:\Hermes agent\scripts\auto_card.py", line 2550, in _collect_binance_data
    import requests, time as _time, hmac, hashlib, urllib.parse
ModuleNotFoundError: No module named 'requests'
```

## 相关

- 主 skill: `tangxi-analysis-audit-checklist` (P0 排错清单第 7 项)
- 落点代码: `D:/Hermes agent/scripts/auto_card.py:2550` + `D:/Hermes agent/scripts/auto_card.py:3841` + `D:/Hermes agent/scripts/auto_card.py:4806`
