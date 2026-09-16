# 路由契约 vs 实际消费方：漂移审计

> 同目录另见 `external-audit-verification.md`：用户贴来一份**外部审计**（GPT／顾问／别的 agent）问「是不是」时的逐条取证流程（判定分「为真／不复现／无法溯源」三类，真假都列）与影响面校准。

> **2026-09-16 补充（阈值口径漂移，同类局部）**：定时作业常有**两个不同用途的阈值**，混用就是假失败源。
> 实测 `btc_tv_refresh`：**触发口径 12 分**（本轮要不要去刷，需 < cron 20 分）与**合同口径 30 分**（下游能容忍的最大年龄）被混用 → 拿触发口径判「让路算不算失败」，于是 12:07/13:27/16:07 三轮缓存 1054s/1056s/1053s（≈17.5 分，**远在 30 分合同内**）全被记成 cron 失败，还把 `audit_preflight` 的 `Cron策略` 拖成 FAIL。修后新增独立的 `five_tf_contract_status()`（30 分）作让路判据：`age ≤ 24 分(0.8×合同) 且连续让路 < 3 轮` → exit 0；超限 / 连续 3 轮 / 年龄读不到 → exit 1。
> **审计问法**：`grep -n "max_age_minutes\|max_age_hours" scripts/<job>.py` —— 看让路/失败分支用的是哪个值、是否等于下游合同默认值；两数不同即 P1。
> **子进程「静默 rc=0 不发布」**：失败分支全部 `return 1` 的采集器却出现 rc=0 无产物 = 进程级静默退出，读代码定性不了。处置：把 rc + 诊断文件最后阶段打进失败消息（`run_collector() -> (rc, stage)`），先围起来——下一次复发时证据自然落进 cron 的 error 字段。

## 适用

回答「某步骤覆盖了哪些数据源」「完成度为什么老是 X/N」「某个维度是不是停采了」时。

## 铁律

1. **声明清单 ≠ 事实。** `scripts/pipeline_router.CRON_SOURCES` 只声明「应该读什么」；事实 = 有新鲜产出文件的采集器 + 在跑的 cron。报覆盖前先把两者对齐。
2. **残留源名会永久卡死完成度闸门。** `auto_card.py` 的 cron_read 规则是「清单里存在任一 `CRON_SOURCES_PAUSED` 源 → 这一步整步不计完成」。于是一个已退役的源名留在清单里，会让该步永远拿不到 ✅，脚注还会写「XX 采集 cron 已停用」——而真实情况可能是采集仍在跑。
3. **替代源可能根本不在该步骤里。** 同一个数据维度可以走卡面渲染路径而非采集步骤（例：清算走 `render_v96._liquidation_line` 直读 `liquidation_flow.json` / `coinglass_liq.json`，不在 cron_read 清单内）。审计时分别问「谁产出」和「谁消费」，不能只看步骤清单。
4. **换源三处一起改：** `CRON_SOURCES` + `CRON_SOURCE_FILES`（源名 ≠ 文件名，如 `x_sentiment` → `x_sentiment_context.json`）+ `CRON_SOURCE_MAX_AGE`（各源 TTL 不同，拿错阈值 = 每轮永久误报）。只改一处 = 留下一个无声的错。
5. **停用要有意为之且标注。** `CRON_SOURCES_PAUSED` 把「刻意不采」与「本该采到却没采到」分开记账，卡面两类不得混写。
6. **不信注释。** 步数/阶段数从代码常量现算（`CRYPTO_FULL_PIPELINE`、`route_pipeline`），docstring 里的旧数字（如退役步后仍写 fifteen-stage）不算证据。

## 复算命令

```bash
cd "D:/Hermes agent"

# 1) 档位×资产步数矩阵（现算，不抄文档）
python -c "import sys;sys.path.insert(0,'scripts');import pipeline_router as R;\
[print(s, m, len(R.route_pipeline(s,m)), R.route_pipeline(s,m)) \
 for s in ['BINANCE:BTCUSDT','OANDA:XAUUSD','EURUSD','AAPL','ES1!','SPX500'] \
 for m in ['quick','standard','full','monitor']]"

# 2) 某步骤的源清单真实状态（停用?/文件名?/阈值?）
python -c "import sys;sys.path.insert(0,'scripts');import pipeline_router as R;\
[print(n,'paused' if R.cron_source_paused(n) else 'live',R.cron_source_file(n),f'{R.cron_source_max_age(n):g}h') \
 for n in R.cron_sources('BTCUSDT')]"

# 3) 谁真正消费这个文件（找卡面/引擎消费方，而不是步骤清单）
grep -rn "liquidation_flow" scripts/ | grep -v pipeline_router

# 4) 运行态与数据新鲜度一批看完
python scripts/audit_preflight.py    # 退出码 0 = 就绪；逐行看 TV/缓存/关键位/cron/依赖

# 5) 改完契约后的回归（CRON_SOURCES 无测试锁定时先 grep 确认）
grep -rn "liquidation_pressure\|CRON_SOURCES" tests/ | head
python -m pytest -q tests/test_pipeline_router.py tests/test_analysis_modes.py
```

## 判定

| 观察 | 含义 | 动作 |
|---|---|---|
| 源在 `CRON_SOURCES`、但有新鲜产出 + cron 在跑 | 正常 | 照常记账 |
| 源在 `CRON_SOURCES`、标 `PAUSED`、无产出 | 刻意停用 | 保留并标「刻意不采」，不要机械恢复 |
| 源在 `CRON_SOURCES`、标 `PAUSED`、但已有活跃替代源 | **漂移** | 把清单项换成活跃源，或注明该维度走卡面路径 |
| 源有新鲜产出、却不在任何步骤/消费者里 | 孤儿采集 | 要么接进管线，要么停 cron |

## 已知实例（棠溪）

- `liquidation_pressure`（旧 `liquidation_collector.py`，OI×价挤压估算）已退役，但长期留在 crypto 的 `CRON_SOURCES` 里；活跃清算栈是 `liquidation_refresh`（cron 清算双源刷新 */10）→ `liquidation_flow.json` + `coinglass_liq.json`，落点在卡面 ③ 多源表「清算」行。
- 黄金/外汇/股票/期货的 `cron_read` 清单首页永远是 `cot_data`（COT cron 已停用），取证时不要把它读成故障。
