# 关键位监控与快速分析契约（2026-08）

## 唯一链路

```text
TradingView候选位 → 人工审核 → data/keylevels_config.json
→ 单实例 keylevel_guard.py → trigger_{symbol}.json
→ keylevel_read_trigger.py → keylevel_analysis_dispatcher.py
→ auto_card.py --quick → Python FinalVerdict
```

`keylevels_candidates.json` 只是候选池；`keylevels_config.json` 是唯一批准监测源；旧 `monitor_levels.json` 只能作为历史兼容/审计缓存，不能作为当前监测位输入。

## 配置契约

配置根部建议包含 `schema_version`、`approved_source`、`updated_at`。每个 level 至少包含：

```json
{"name":"...","price":123,"enabled":true,"source":"manual_review","valid_until":"2026-08-29T08:23:29+08:00"}
```

守护在每轮热读配置，跳过 disabled、过期或无法解析有效期的 level。事件携带配置内容哈希短版本 `config_revision`，用于追溯旧配置触发。

## 事件契约

价格上/下穿位只产生事件，不产生交易方向：

```json
{
  "event_type":"keylevel_cross",
  "event_class":"price_cross_only",
  "cross_direction":"up",
  "direction":"neutral",
  "analysis_required":true,
  "analysis_status":"pending",
  "analysis_mode":"quick",
  "event_id":"...",
  "config_revision":"...",
  "tv_symbol":"BINANCE:BTCUSDT.P"
}
```

`cross_direction` 仅代表价格穿越方向，严禁映射为 long/short。调度器成功后写 `analyzed`，失败写 `failed`，中间态写 `analyzing`；保留 `event_id` 和分析日志路径。

## inherit 规则

`inherit` 必须加载 symbol 匹配且不超过 4 小时的上下文。上下文缺失、过期或品种不匹配时，执行器自动升级 `full`，不能用空上下文伪装继承。成功继承时，engine_data 记录 `context_inherited=true`、`inherited_context` 和实际 `analysis_mode`。

## 单实例与看门狗

`keylevel_guard.py` 用文件锁防止并发；看门狗必须区分 0、1、多个实例：0 重启，1 正常，多个先收敛。不得只用“至少一个进程存在”作为健康条件。旧 REST/sentinel/WS 脚本在确认外部调度未引用前不要擅自删除或并行启用。

## 验证清单

```bash
python -m py_compile scripts/pipeline_router.py scripts/auto_card.py scripts/keylevel_guard.py scripts/keylevel_read_trigger.py scripts/keylevels_collect.py scripts/keylevel_analysis_dispatcher.py scripts/btc_keylevel_guard_watchdog.py
python -m pytest tests/test_analysis_modes.py tests/test_pipeline_router.py tests/test_keylevel_contract.py -q
python scripts/keylevel_analysis_dispatcher.py BTCUSDT  # 无待处理事件应输出 WAIT
python -c "import json; json.load(open('data/keylevels_config.json', encoding='utf-8'))"
git diff --check
```

验收重点：监控不判多空、不自动下单；默认 dispatcher 不推送；`WAIT/NO-GO` 不得保留可执行 entry/stop/target；Pine/副指标只提供计算和确认，Python `FinalVerdict` 是唯一最终裁决。
