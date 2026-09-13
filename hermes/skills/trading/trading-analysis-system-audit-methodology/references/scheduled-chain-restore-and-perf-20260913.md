# 计划任务链恢复 · 重复探测的性能根因 · 人工输入型工具（2026-09-13 实录）

仓库 `D:/Hermes agent`，分支 main，提交 `418026b`（32 文件，未 push）。
本篇只记录**上一份 references 没覆盖**的部分（副本交接/降级落点/伪造默认值见
`parallel-fix-and-degradation-placement-20260913.md`）。

## 一、影子校准链：两条链并存时先定性再恢复

停摆症状：`data/shadow/decision_signals.jsonl` 每轮出卡都在写（1 MB / 358 条），
但 `decision_outcomes.jsonl` 停在 7-11（只有 15 条）。

先弄清同域其实有**两条**链，各自的写入物与消费者不同：

| 链 | 生产者 | 产物 | 调度 |
|:--|:--|:--|:--|
| A 卡片影子 | `auto_card` → `shadow_calibration.append_shadow_signal` | `data/shadow/decision_signals.jsonl` | 随出卡 |
| A 结果标注 | `shadow_outcome_labeler.py` → `label_outcome` | `data/shadow/decision_outcomes.jsonl` | `影子结果标注` cron（已 paused） |
| B 信号闭环 | `cron_signal_tick.py` → `signal_outcome` | 另一套存储 | `信号闭环·tick`（15 分，在跑） |

结论：A 是半活（只进不出，FinalVerdict 拿不到自校准数据），B 与 A 职责不同、不重复。
所以处理是**恢复 A 的标注器**，不是退役、也不是去合并两条链。

判据：先列出「写入物 → 消费者」，再决定恢复/退役；名字相似不代表重复。

## 二、性能根因：每条都重探传输模式

恢复前先手动跑一次（`HANGQING_NO_SEND=1 python scripts/shadow_outcome_labeler.py`）：
**280 秒超时未完成，一条都没标出来**。

单调用实测：

| 模式 | 结果 | 耗时 |
|:--|:--|:--|
| 直连（`ProxyHandler({})`） | URLError timed out | 12.04s |
| 走代理（环境 `HTTPS_PROXY`） | 200 | 0.44s |

旧代码 `for direct in (True, False)` → 每条信号先白等一次 12s；111 条待标 ≈ 22 分钟，
`*/15` 的 cron 永远跑不完。（该 cron 早先被 pause，很可能就是被这个拖死的。）

修法：

```python
_PROXY_MODE: list[bool | None] = [None]

def _fetch_json(url, direct):
    opener = (urllib.request.build_opener(urllib.request.ProxyHandler({})) if direct
              else urllib.request.build_opener())
    with opener.open(req, timeout=5 if direct else 10) as response:   # 直连短超时兜底
        payload = json.loads(response.read())
    _PROXY_MODE[0] = direct        # 成功即记下可用模式
    return payload

preferred = _PROXY_MODE[0]
order = (True, False) if preferred is None else (preferred, not preferred)
```

效果：首轮补标 **140 条（15 → 157）**；紧接着第二轮 **12 秒**完成。

注意两点：

- 保持 `_fetch_json(url, direct)` 的位置参数签名，既有测试是用 `def fail(url, direct)` 桩的。
- 测试要注意真实契约藏在被 mock 掉的那一层：桩必须自己写回 `_PROXY_MODE[0]`，
  否则断言「第二轮不再白试直连」会假失败（本轮先踩后修）。

## 三、恢复动作与回执

```bash
hermes cron resume 8fe56a00eb8b      # 影子结果标注
hermes cron run 8fe56a00eb8b         # 触发一次 → Ran now: succeeded
```

验证三件套（只看 `enabled=true` 不算恢复）：

- `hermes cron runs 8fe56a00eb8b` → `completed  job=…  source=direct`
- jobs.json 里 `last_status=ok`、`last_run_at` 已更新、`next_run_at` 正常
- 产物 `decision_outcomes.jsonl` 在增长

仍有意暂停、**本轮不动**的三个：`COT报告刷新` / `Deribit期权刷新` / `清算压力监控`。

## 四、人工对账工具：`scripts/risk_state_reconcile.py`

背景：`risk_state.json` 是 7-15 的模拟快照（`sim from monitor …`）且无生产者，
系统只能永久标「非真实额度 / 状态陈旧」。系统不该编余额，于是把「人对账」做成显式动作。

形状（可复用到其它「必须由人提供事实」的写操作）：

- `--balance` 必填且 `> 0`；否则 `return 2` + 明确拒绝理由（不进入流程）。
- 默认 dry-run；只有 `--write` 才原子写（temp + `os.replace`）。
- **合并而非序列化**：读原 JSON → 只覆盖自己拥有的字段 → 写回，
  于是 `allowed_risk_next_trade` / `last_unreviewed_trade` / `max_daily_loss` / `lock_trading`
  等非 dataclass 字段原样保留（序列化 dataclass 会把它们静默丢掉）。
- 日期盖章为**当天（北京时间）**，并写 `reconciled_at` / `reconciled_by=manual_cli`。
- 原文件是坏 JSON → `raise SystemExit` 拒绝覆盖，保留现场。
- 写完回读 `risk_state_status()` 打印状态，形成闭环证据。

本机实测：对真文件 dry-run **未改动**（`date` 仍 `2026-07-15`），并列出被保留的 6 个键。

## 五、加固与既有测试的取舍（本轮的实际决策）

子代理的硬拦截让 `test_core.py::TestTradeFrequencyCap`(2) +
`test_risk_constitution_v2.py`(3) 共 5 个**既有**用例失败。

决策顺序：

1. 先问「这些用例编码的是真实业务语义吗」——是（频率上限、体制除数、新闻/组合硬闸）。
2. 再看「改实现 vs 改用例」——若改用例，等于为了硬化风险层而砍掉风控频率语义，不划算。
3. 于是回到第 2 层问题：**硬拦截的落点错了**（见姊妹篇第二节），把落点改对后 5 个用例自然全绿。

实际操作：只重写了子代理自己新增的 `tests/test_risk_freshness_closure.py`，
把它从「断言 blocked」改为断言**可见降级契约**（`status=stale` + `usable=False` +
不回写文件 + 新鲜状态仍能正常算出仓位），既有用例一行未动。

另有一处提示：pytest 测试夹具里类型标注写死 `rr_a: float = 3.0` 会让
「传 None 验非法」的用例报 Pyright 错，放宽为 `object` 即可，别为了让类型检查闭嘴而删边界用例。

## 六、收尾形态（供下次对照）

- 回归：`1032 passed / 0 failed / 0 error`（JUnit 存 `outputs/audit_20260913/`）。
- 守卫：`indicator_source_audit` 通过、`tv_indicator_alignment_check` 完全对齐、
  `skill_drift_scan` LIVE 0。
- 提交：单个提交说明「修了什么/否掉了什么/边界在哪」，并在回复里明确
  「未 push / 未下单 / 未外发 TG / 未改 Pine / 未升格关键位」。
