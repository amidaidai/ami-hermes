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

配置根部建议包含 `schema_version`、`approved_source`、`updated_at`、`approval_renewal`、`auto_approval_policy`、`push_tier_policy`。每个 level 建议包含：

```json
{"name":"结构·周三高","price":76540,"note":"用户会话请求实时到价；随分析更新",
 "enabled":true,"source":"user_session_<日期>","valid_until":"<ISO +24h>",
 "tf":"15m","layer":"结构","push_tier":"critical"}
```

守护在每轮热读配置，跳过 disabled、过期或无法解析有效期的 level；**改配置无需重启守护**。事件携带配置内容哈希短版本 `config_revision`，用于追溯旧配置触发。

- `approval_renewal.mode = existing_levels_only`：自动续期只延长**既有批准位**的有效期（ttl 6h、提前 30min），不得把分析候选升格为监控位——新位只能来自用户请求。
- `valid_until` 到期即静默失效；要长盯就按「加位/更新位操作规程」显式加入。

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

## 加位/更新位操作规程（用户请求实时盯位时）

1. 备份：`data/keylevels_config.json` → `keylevels_config.json.bak.<YYYYMMDD_HHMM>`。
2. 读 `symbols.<SYM>.levels`：同价（±0.5）已存在 → 就地更新 `name/enabled/push_tier/valid_until/source`；不存在 → append 完整对象（字段见「配置契约」）。
3. 原子写回（`.tmp` + `replace`），刷新顶层 `updated_at`。
4. **不重启守护**：主循环每轮（0.5s）热读该文件，加位即时生效。
5. 等 ≤2 分钟，核 `data/.keylevel_guard_health.json`（看门狗每 2min 写）：`active_approved_levels`／`push_enabled_levels` 应出现增量 —— **有增量才可回报「已生效」**。
6. 回报内容：加了哪些位、推送分级、到价后去哪看；不承诺方向、不自动下单。

## 推送分级与限流（口径取配置里的 `push_tier_policy`）

| tier | 适用 | 冷却 |
|:--|:--|:--|
| `critical` | 结构位（FVG/OB/前高前低/HTF 磁吸） | 4h |
| `event` | 价值区边界 | 6h |
| `silent` | 只进卡面与 digest：不推送、不触发分析 | — |

- 跨位全局限流：两次推送 ≥30min、每小时 ≤3 条；触发后须离位 ±0.15% 才重新武装；同轮多穿合并成一条消息。
- 静默整个价值区层＝给这些位设 `push_tier: "silent"`（保留 `enabled`、不删条目）；编辑后核 health：`push_enabled_levels` 降、`active_approved_levels` 不变。
- `structure_reviewed_at` 过期时守护**整轮跳过评估**（心跳写 `structure_review_required`）→ 到价提醒整体静默，排障先看这一项。

## 推送状态契约：设计跳过 ≠ 投递失败

- guard 直推 TG 的成功判据：`data/keylevel_guard.log` 里 `ALERT OK <SYM> rich_sent`。
- 事件分析链状态：`analyzed`／`failed`／`analyzing`／`pending_push`／**`skipped_not_goa`**。
- `auto_card` 对非 GO-A 打印 `⏸ 未推送：FinalVerdict不是完整GO-A可执行裁决` = 设计跳过：dispatcher 记 `skipped_not_goa`、`push_retry_required=false`；误记成 `failed_or_missing` 会让补投递计数无限空转。
- 读到旧 trigger 文件 `push_status: failed_or_missing` + 高 `push_retry_count` 时，先对一下同事件的 `data/analysis_dispatch_<event_id>.log` 是否本就是 NO-GO 跳过——别当投递故障重排查。

## 排障入口

- `data/keylevel_guard.log`：`TRIGGER <SYM> xN price=… tier:name`（穿越）／`ALERT OK|SKIP … rich_sent`（投递）。
- `data/.keylevel_guard_health.json`：`status`／`active_approved_levels`／`push_enabled_levels`／`structure_review_current`／`checked_at`。
- `data/trigger_<SYM>.json`：`level/price/ts/cooldown_until/analysis_status/push_status/push_retry_count/analysis_log`。
- `data/analysis_dispatch_<event_id>.log`：该次 `auto_card --quick` 的完整 stdout（裁决与「未推送」原因都在这里）。

## 验证清单

```bash
python -m py_compile scripts/pipeline_router.py scripts/auto_card.py scripts/keylevel_guard.py scripts/keylevel_read_trigger.py scripts/keylevels_collect.py scripts/keylevel_analysis_dispatcher.py scripts/btc_keylevel_guard_watchdog.py
python -m pytest tests/test_analysis_modes.py tests/test_pipeline_router.py tests/test_keylevel_contract.py -q
python scripts/keylevel_analysis_dispatcher.py BTCUSDT  # 无待处理事件应输出 WAIT
python -c "import json;h=json.load(open('data/.keylevel_guard_health.json',encoding='utf-8'));print(h['status'],h['active_approved_levels'],h['push_enabled_levels'],h['structure_review_current'])"  # 加位/静默位后核计数
python -c "import json; json.load(open('data/keylevels_config.json', encoding='utf-8'))"
git diff --check
```

验收重点：监控不判多空、不自动下单；默认 dispatcher 不推送；`WAIT/NO-GO` 不得保留可执行 entry/stop/target；Pine/副指标只提供计算和确认，Python `FinalVerdict` 是唯一最终裁决。
