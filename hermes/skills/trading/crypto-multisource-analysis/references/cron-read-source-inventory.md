# cron_read 数据源清单 v1.0

> 2026-06-29 · v9.5 cron_read 捷径依赖的数据源现状

## 设计原则

cron_read 替代了旧版"分析时重跑脚本"的模式。cron 已在后台采集数据，分析时直接读取最近输出文件。

## 数据源状态

| 来源 | cron脚本 | cron频率 | 落盘路径 | 状态 | 备注 |
|------|---------|:--:|---------|:--:|------|
| Deribit期权 | deribit_options.py | 15min | `data/deribit_options.json` | ✅ 可用 | BTC/ETH C/P比+MaxPain |
| Dune链上 | dune_collector.py | 2h | `data/dune_cache.json` | ✅ 可用 | BTC流/CEX净流 |
| COT持仓 | cot_collector.py | 周六 | `data/cot_data.json` | ✅ 可用 | 投机/商业持仓 |
| XAU宏观 | xau相关 | — | `data/xau_macro_context.json` | ✅ 可用 | TIP/GLD/GDX |
| **X情绪** | x_sentiment_collector.py | 30min | **无本地落盘** | ❌ 缺失 | 仅stdout→cron抓取→TG推送 |
| 清算压力 | liquidation_collector.py | 30min | **无本地落盘** | ❌ 缺失 | 仅stdout→cron抓取→TG推送 |
| QLib因子 | qlib_factors.py | 30min | **无本地落盘** | ❌ 缺失 | 仅stdout→cron抓取→TG推送 |
| 稳定币 | stablecoin_collector.py | 2h | **无本地落盘** | ❌ 缺失 | 仅stdout→cron抓取→TG推送 |

## 缺口修复计划

### x_sentiment_collector.py 加落盘

```python
# 在脚本末尾加：
import json, os
data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
output = {"timestamp": datetime.now().isoformat(), "signal": {...}, ...}
with open(os.path.join(data_dir, "x_sentiment.json"), "w") as f:
    json.dump(output, f, ensure_ascii=False)
```

同理：liquidation→`liquidation.json`、qlib→`qlib_factors.json`、stablecoin→`stablecoin.json`

### 读取时的新鲜度检查

```python
import time, json
from pathlib import Path

def read_cron_source(name: str, max_age_seconds: int = 1800) -> dict | None:
    """读取cron输出，过期>30分钟返回None"""
    path = Path("data") / f"{name}.json"
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > max_age_seconds:
        print(f"⚠ {name} 过期 {age/60:.0f}min·跳过")
        return None
    return json.loads(path.read_text())
```

## 回退策略

当 cron_read 数据不可用时（文件过期/不存在）：
1. 标注「cron缓存过期·跳过」
2. 不重跑脚本（浪费API额度，违背cron_read设计初衷）
3. 只在 card 步骤汇总时列出哪些源可用、哪些跳过
4. 关键源（X情绪）缺失时用 web_search 补充并标注「web源·非X实时」
