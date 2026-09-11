# Cron-Read 协议 v1.0

> 2026-06-29 · 驾驶舱 v9.5 引入。核心原则：cron 已跑的数据，分析时不重跑。

## 触发条件

当 `pipeline_router` 返回步骤列表包含 `cron_read` 时执行此协议。

## 核心规则

1. **只读不跑**：读取 `data/` 目录下 cron 最近输出的 JSON 文件，不调用脚本
2. **新鲜度检查**：文件 >30 分钟标注「过期·跳过」，不尝试重跑
3. **缺失不阻塞**：文件不存在的源跳过，在分析卡中标注
4. **不重跑脚本**：避免浪费 API 额度 (Dune 40req/min, CG Pro 500req/min)

## 各市场 cron_read 源

| 市场 | 读取文件 | 频率 | 新鲜度阈值 |
|------|---------|:--:|:--:|
| 加密 | `data/dune_cache.json` | 2h | 120min |
| 加密 | `data/deribit_options.json` | 15min | 30min |
| 加密 | `data/x_sentiment.json` | 30min | 30min |
| 加密 | `data/qlib_factors.json` | 30min | 30min |
| 加密 | `data/liquidation.json` | 30min | 30min |
| 加密 | `data/stablecoin.json` | 2h | 120min |
| 黄金 | `data/cot_data.json` | 周六 | 7天 |
| 黄金 | `data/xau_macro_context.json` | 按需 | 24h |
| 外汇 | `data/cot_data.json` | 周六 | 7天 |

## 读取代码模板

```python
import json, os
from pathlib import Path

data_dir = Path("data")
sources = ["x_sentiment", "deribit_options", "dune_cache"]  # router 返回

for src in sources:
    path = data_dir / f"{src}.json"
    if not path.exists():
        print(f"  ⚠️ {src}: 文件不存在·跳过")
        continue
    mtime = path.stat().st_mtime
    age_min = (time.time() - mtime) / 60
    if age_min > 30:
        print(f"  ⚠️ {src}: 过期({age_min:.0f}min)·跳过")
        continue
    data = json.loads(path.read_text())
    print(f"  ✅ {src}: 新鲜({age_min:.0f}min)")
```

## 已知陷阱

- **COT 数据周更新**：`cot_data.json` 只在周六更新，平时 >7 天新鲜度正常，不报过期
- **x_sentiment 双落盘**：脚本写两处（hermes data + 项目 data），路由读项目侧
- **部分 cron 无落盘**：qlib/liquidation/stablecoin 通过 cron delivery 推 TG，本机可能无文件 → 跳过并标注「TG推送·本地无落盘」
- **首次运行**：新脚本第一次跑可能无历史文件 → 等下一轮 cron 后再分析
