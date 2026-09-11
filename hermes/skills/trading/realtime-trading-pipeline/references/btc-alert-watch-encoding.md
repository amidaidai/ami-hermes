# Windows no_agent cron GBK 编码 — 修复方案

## 根因
Windows 下 no_agent cron 的 stdout 管道使用 GBK (cp936) 而非 UTF-8。
Python 的 `print()` 输出中文/emoji → GBK 编码 → cron 捕获 → Telegram 显示为 `馃煛 绔欏洖VAL` 等乱码。

## 修复方案 A：TextIOWrapper（适用于只需 print 的脚本）

```python
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", write_through=True)
```

**必须加在所有 print() 调用之前**，推荐 import 块之后立即添加。

注意：当 stdout 是管道时，TextIOWrapper 可能缓冲。加上 `write_through=True` 让数据立即写入底层 buffer。

## 修复方案 B：emit() 函数（更可靠，适合有分析的脚本）

```python
import io, sys

_OUT = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True)
def emit(text):
    """UTF-8 安全输出。"""
    try:
        _OUT.write(text.rstrip() + "\n")
        _OUT.flush()
    except Exception:
        # Fallback: 直接写 UTF-8 字节
        try:
            sys.stdout.buffer.write((text.rstrip() + "\n").encode("utf-8"))
            sys.stdout.buffer.flush()
        except Exception:
            pass

# 使用
emit(f"⚡ 触发 · 价`{price:,.0f}`")
```

## 验证是否修复
```bash
cd scripts && python btc_alert_watch.py
# 输出：[18:48] 监控中 · 价`64,123` · 最近位`$21`
# 如果看到正常中文 = 修复成功
# 如果看到 鏃犳硶鑾峰彇 等乱码 = 未修复
```

## 常见错误

1. **TextIOWrapper + `write_through=False`（默认）** — 管道模式下数据被缓冲，cron 捕获到空输出。必须 `write_through=True`。
2. **`print()` 被 TextIOWrapper 包装后仍然乱码** — 改用 `emit()` 方案 B 直接写 bytes。
3. **忽略 stderr** — cron 也会捕获 stderr，`sys.stderr` 必须同步修复。无论用方案 A 还是 B，stderr 都要一起处理。代码中的 `try/except` 会吞掉 stderr 的错误输出——调试时手动测试改用 `python script.py 2>&1` 查看完整输出。

## 脚本内字符串注意事项

Python 3 的字符串字面量默认 UTF-8。以下情况需特别确认：
- 通过 `write_file` 写入的 `.py` 文件 — 确保文件编码为 UTF-8（Hermes write_file 默认保存为 UTF-8）
- 通过 `patch` 修改的 `.py` 文件 — patch 工具保持原文件编码
- 模板字符串中的 Unicode（如 `\u2193`）— 在 Python 运行时会正确转义，但无必要；直接写中文更可靠

## 新增脚本：btc_alert_watch.py

**用途**：no_agent cron 价格提醒 + 嵌入式分析。每分钟检查 3 个关键位，距触发窗 ±$15 时自动生成含方向判断的分析推送。

**监控关键位**：
| 名称 | 价位 | 触发窗 | 方向 | 说明 |
|------|------|--------|------|------|
| B1_bear | $64,102 | ±$15 | ↓做空 | 破-B1 15m |
| VWAP_bull | $64,233 | ±$15 | ↑做多 | 站上VWAP 15m |
| B2_bear | $63,971 | ±$12 | ↓做空 | 破-B2 15m |

**冷却机制**：同价位触发后 15 分钟静默期，防重复推送。

**分析流程**：触发时读取 TV 缓存 → 比较价格与 VWAP/EMA/CVD → 统计多空指标倾向 → 输出止损止盈目标。

**数据来源**：`btc_tv_data.json`（TV 数据桥缓存）+ Binance 实时价格。TV 数据桥每 2 分钟更新，分析脚本每分运行，所以分析基准价是实时但指标有 ≤2min 滞后。
