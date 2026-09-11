# Cron 输出文件路径排查

## 背景

多个 no_agent cron 脚本的 `DATA_DIR` 硬编码为 `~/AppData/Local/hermes/data/` 而非项目工作区 `D:/Hermes agent/data/`。两种路径并存，容易在审计时误判为\"脚本没输出\"。

## 已知路径分裂的脚本

| 脚本 | DATA_DIR | 输出文件 |
|------|----------|----------|
| stablecoin_collector.py | `~/AppData/Local/hermes/data` | `stablecoin_snapshot.json` |
| x_sentiment_collector.py | 项目 data/ | `x_sentiment.json` |
| liquidation_collector.py | 项目 data/ | `liquidation_pressure.json` |
| dune_collector.py | 项目 data/ | `dune_cache.json` |
| deribit_options.py | 项目 data/ | `deribit_options.json` |
| qlib_factors.py | 项目 data/ | `qlib_factors.json` |
| cot_collector.py | 项目 data/ | `cot_data.json` |

> 注意：大部分脚本写项目 `data/`，但 `stablecoin_collector.py` 是例外，走 Hermes 的 data 目录。

## 排查流程

1. `cronjob(action='list')` → 拿到脚本文件名
2. `grep -n 'DATA_DIR\\|DATA_ROOT\\|os.path.join.*data' scripts/<script_name>` → 找到输出路径
3. 确认文件存在 + 内容可解析
4. 如果路径指向 `~/AppData/Local/hermes/data/` 但审计只看项目 `data/`，标记为**静默成功**而非缺失

## 根本解决（可选）

如果想让所有脚本统一写到项目 `data/`，修改脚本的 DATA_DIR：
```python
DATA_DIR = "D:/Hermes agent/data"
```
但注意这样做的后果：其他依赖该文件放在原路径的工具（如某些 MCP server）可能找不到。
