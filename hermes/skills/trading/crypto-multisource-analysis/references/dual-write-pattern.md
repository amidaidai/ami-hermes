# Cron脚本双落盘模式 v1.0

> 2026-06-29 · 用于所有需要被 pipeline_router cron_read 读取的 cron 脚本

## 问题

cron 脚本的输出由 Hermes scheduler 捕获推送到 Telegram，但本地无落盘文件。
`cron_read` 步骤需要在 `data/` 目录下找到 JSON 文件来读取，而不是重跑脚本。

## 解决方案

每个 cron 脚本在 `main()` 结束时写两处：
1. Hermes data 目录（现有路径，不破坏）
2. 项目 `data/` 目录（cron_read 读取）

## 代码模板

```python
import json, os

def main():
    # ... 采集逻辑 ...
    result = {"ts": now.isoformat(), "data": collected_data}  # 统一结果字典
    
    # 落盘1: Hermes data 目录（现有路径）
    data_dir1 = os.path.expanduser("~/AppData/Local/hermes/data")
    os.makedirs(data_dir1, exist_ok=True)
    with open(os.path.join(data_dir1, "output.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False)
    
    # 落盘2: 项目 data 目录（cron_read 读取）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir2 = os.path.join(script_dir, "..", "data")
    os.makedirs(data_dir2, exist_ok=True)
    with open(os.path.join(data_dir2, "output.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False)
```

## 已应用此模式的脚本

| 脚本 | 输出文件 | 状态 |
|------|---------|:--:|
| `x_sentiment_collector.py` | `data/x_sentiment.json` | ✅ |
| `deribit_options.py` | `data/deribit_options.json` | ✅ (已有) |
| `dune_collector.py` | `data/dune_cache.json` | ✅ (已有) |

## 待迁移的脚本

以下 cron 脚本尚未双落盘，分析时 cron_read 读不到：

| 脚本 | 建议输出 | 优先级 |
|------|---------|:--:|
| `liquidation_collector.py` | `data/liquidation.json` | P1 |
| `qlib_factors.py` | `data/qlib_factors.json` | P1 |
| `stablecoin_collector.py` | `data/stablecoin.json` | P2 |
| `cot_collector.py` | `data/cot_data.json` | ✅ 已有 |

## 命名规范

- 文件名与脚本名对应：`xxx_collector.py` → `data/xxx.json`
- JSON 结构统一：`{"ts": ISO8601, "data": {...}, "signal": "方向", "ok": bool}`
- 编码：UTF-8，`ensure_ascii=False`
