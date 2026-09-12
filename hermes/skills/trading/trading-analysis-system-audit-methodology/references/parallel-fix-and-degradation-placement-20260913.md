# 并行修复代理交接 · 降级落点 · 伪造默认值（2026-09-13 实录）

仓库 `D:/Hermes agent`，分支 main。本轮从「审计多份互相矛盾的历史报告」推进到「全面修复+回归」。
所有路径相对仓库根；未 commit / 未 push / 未下单 / 未外发 TG。

## 一、并行修复代理的实际结局

派了 4 个只读→可写修复代理（数据源、影子+风控、XAU 证据、看门狗）+ 1 个归档清单代理，
按文件边界分工。结果：**5 个全部以 API 配额报错结束**，但都已改过盘上文件。

| 现象 | 证据 |
|:--|:--|
| 「完成」是假的 | 完成摘要写着 `API call failed after 3 retries: HTTP 429: The usage limit has been reached`，`exit_reason=max_iterations` |
| 留下半成品 | 自己的新用例失败（`test_archive_manifest.py` 2 项、`test_xau_ohlcv_evidence_integrity.py` 1 项） |
| 改坏既有契约 | `risk_constitution.py` 的硬拦截让 `test_core.py::TestTradeFrequencyCap`(2) 与 `test_risk_constitution_v2.py`(3) 失败 |

**收工时全量回归只有 1018 passed / 8 failed**，逐条修完后 **1023 passed / 0 failed**。
只跑新用例会完全漏掉那 5 个被改坏的旧契约 —— 这是必须跑全量的直接理由。

处理原则：子代理的**意图**可留（如「风险状态陈旧必须可见」），**落点**要重审（见第二节）；
它没写完的测试要么补完要么删掉。

## 二、降级落点：为什么否掉「风险状态硬拦截」

子代理版本（被回退）：

```python
status = risk_state_status(state)
if not status["usable"]:
    return {"allowed": False, ...}          # check_constitution 内
```

**为什么不能这么写**（追踪到消费方才看清）：`decision_loop.py:443`
`if risk and not bool(risk.get("allowed", False)): hard.append("risk_constitution")`
→ 进入 `hard` 阻断 → FinalVerdict 永久 NO-GO。

而 `data/risk_state.json` 当前是：

```json
{"date": "2026-07-15", "daily_starting_balance": 67.52,
 "last_unreviewed_trade": {"note": "sim from monitor VAH回收 for closed-loop test"}}
```

即**历史遗留的模拟快照**，且全仓检索 `save_risk_state` 只有 `trading_system.py`（未在 cron 中）会写 →
**没有生产者会把它刷新回健康**。加硬拦截 = 系统被永久锁死，不是 fail-closed 而是 fail-forever。

最终设计（保留可见性、不加硬闸门）：

- `risk_constitution.py` 新增 `risk_state_status()`：`fresh / stale / missing / invalid` + `usable`；
  `RiskState.date` 默认空串、起始余额默认 `0.0`（不再凭空造 `100.0`）；
  `load_risk_state()` 读坏 JSON 时置 `state_error` 而不是静默回退默认值。
- 读取**不回写**文件（测试断言 `path.read_bytes() == before`）。
- `auto_card.py` 把状态作为 `role="risk_context"` 一行推进来源矩阵 → 只产生 warning、不产生 hard blocker：
  `status` 映射 `fresh→live / stale→stale_cache / missing|invalid→unavailable`，
  且 `entered_final_verdict=False`。

判据可复用：**若该来源当前没有生产者能把它刷新回健康，就不能新增硬拦截。**

## 三、伪造默认值：宏观快照

`scripts/multi_source_collector.py::macro_overview()` 原实现：

```python
vix_val = result.get("vix", {}).get("price", 20)   # 取不到就是 20
spx_chg = result.get("spx", {}).get("change_pct", 0)  # 取不到就是 0
...
result["sentiment"] = sentiment   # 于是固定输出「中性」
result["vix_level"] = vix_val
```

配合 `auto_card.py` 的 `print(f"  📊 宏观: ... VIX {macro.get('vix_level','?')} | SPX {...:+.1f}%")`，
全源失败时控制台照旧显示「中性 | VIX 20 | SPX +0.0%」，而来源矩阵同期报「本轮未采到有效字段」。

修法：

- 只对**真实取到**的字段做判定；两个都取不到 → 不写 `sentiment` / `vix_level`。
- 只在这一轮确实取到东西时才写 `timestamp`（外层 `_cached`/`_source_status` 依赖语义时间戳
  才能报 `live`；此前无时间戳导致宏观**永远**被标 `unavailable`，这是在制造反向误报）。
- 打印改为带来源状态：取不到就打印「本轮未采到有效字段」，不再输出默认数。

扫描式样（下次直接跑）：`\.get\([^)]*,\s*[0-9]`、`or 100\.0`、`change_pct, 0`、`:\+\.1f}%`。

## 四、看门狗误报（报警疲劳）

`data_freshness_watchdog.py` 的 `WATCH_FILES` 里盯着 `keylevels_structure_review.json`，
但那个文件按设计只有 `{ok, valid, checked, method, stamped, stamp_reason}`，**没有时间戳**
→ 每轮必报「显式时间戳缺失」。真实时间戳在 `keylevels_config.json` 的嵌套键
`auto_approval_policy.structure_reviewed_at`（实测 `2026-09-13T01:52:58+08:00`，由守护自动续）。

修法：给 `WATCH_FILES` 加 `payload_path`（嵌套键路径），`_best_existing`/`_payload_health`/
新增的 `_nested_health` 均支持；改指真正的键后实跑 `healthy=True / 9 项 / 0 异常`。

另外两处：

- 现役文件缺失原为 `continue` 静默跳过 → 改为 `status="missing"` 计入异常。
- 外发改为显式 `report --send` + `HANGQING_NO_SEND` 兜底；默认路径**不 import 任何发送模块**
  （测试用 `patch.object(watch.importlib, "import_module", side_effect=assert)` 锁死）。
  确认脚本无外发依赖后，才把调度从 `28 8,12,16,20 * * *` 收紧到 `*/15 * * * *`。

## 五、执行卡与 R:R（本会话内本人完成）

- 两张卡共用 `render_tv_card.final_is_executable`：GO-A + `executable is True` + 等级/方向匹配 +
  有限正数三件套 + 几何正确 + 声明 R:R 与三件套实算 R:R **双双 ≥2**。
- `render_v96` 的 `execution_rr` 改为「优先 FinalVerdict 的 `rr`，缺失才由三件套推算」；
  删除「缺 `rr` 就回落 `rr_a`」这条会拿旧计划冒充当前风险预算的路径。
- 结论行区分「缺失/非法」（不写 R:R不足）与「有值但 <2」（写 R:R不足）。
- 失效价取 canonical `stop`，不再显示传入的旧计划 `inv_line`。
- 「数据A」→「价格共识A（非全源健康度）」，避免用价格一致性冒充整体源健康度。

## 六、XAU 每层证据（实跑验证过的形态）

`data/xau_tv_state.json` 现在每周期带：

```
evidence: {source, symbol, timeframe, bar_open_time, bar_close_time,
           next_bar_open_time, observed_at, closed, closure_basis, same_source_as_chart}
volume_kind: broker_tick_volume | unavailable
ohlcv_evidence[tf]: {status: verified|rejected, reason}
```

要点：切图前后各读一次 `chart_get_state`，品种或周期不符即 `rejected`；
`xau_ohlcv_source._clean()` 的白名单要带上 `evidence/volume/volume_kind`，
否则证据在对外口径那一步被丢掉（消费者按 key 取值 → 加 key 是增量安全的）。

**不要用固定振幅阈值判真假**：本轮实跑 1D 2.81% / 4h 1.16% / 1h 0.26% / 15m 0.08% / 5m 0.07%，
微幅区间本身就是黄金 5m/15m 的正常形态（历史上曾把这种「四层 0.01%」误判为退化）。

验证方式：TV 当时在 `OANDA:XAUUSD 5m`，直接跑 `xau_tv_sync.py`（`XAU_TV_NO_PUSH=1`
`TANGXI_ENABLE_AUTOMATED_TG=0`），走 API 不可用→逐周期切图的安全网路径，
结果五周期全 `verified` 并原子发布。**不为验证把共享图表切走。**

## 七、自查：我自己写错过的断言

本轮我先提交过一份综合审计报告，随后发现其中数条不成立，已整篇撤回：

- 写「主指标 13 行里只有 6 行」→ 实际主 13 行、副 6 行（把主副行数记混）。
- 写「uv 3.12 仍缺包」→ 实测 Hermes venv / uv 3.11 / uv 3.12 六项依赖均可导入。
- 写「不会产生误导性建议」→ 绝对化健康断言，没有证据能支撑。
- 把上一轮已存在的改动算作本轮新增。
- 引用了并不存在的截图路径。

教训（写入交付格式）：报告里每条断言要么带本轮工具输出，要么标「未验证」；
不写「全面健康 / 不会误导」这类无法取证的全称句。
