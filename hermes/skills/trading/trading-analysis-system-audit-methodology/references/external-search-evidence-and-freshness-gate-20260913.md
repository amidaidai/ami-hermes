# 外部检索证据 · 新鲜度闸门 · 测试全局状态隔离（2026-09-13 实录）

本文是 SKILL.md 中「外部检索与代理侧证据」「载荷字段名/类型冲突」「全量回归的环境干扰」三节的证据底稿。

## 一、x_search 的 degraded / 无引用形态（可复现）

同一个工具、同一台机器，**带日期过滤**时结果不可信：

| 调用形态 | 返回 | 内容 |
|---|---|---|
| `x_search(query)` | `degraded=false`，`inline_citations` 8 条 | 现价 77,000-77,300、支撑 76.0-76.5k、阻力 78.3k —— 与 Binance 实价一致 |
| `x_search(query, from_date, to_date)` | `degraded=true`，`degraded_reason="no citations returned despite filters"`，引用为空 | 阻力 **112,000-114,000**、支撑 98,000-103,000 —— 当时现价 **77,207** |

判定与处理：

1. 采用前先看 `degraded` 与 `inline_citations` 长度；`degraded=true` 或引用为空 → **整条丢弃**。
2. 即便 `degraded=false`，也要把引用里的关键位与 Binance/TV 现价做**量级常识核对**
   （数量级差 40% 的「阻力」不可能是当前市场的阻力）。
3. 检索结果是**仅情绪**证据：可以进「情绪/催化剂」行，不得改写方向、仓位、Entry/Stop/Target。

## 二、「客观部分脚本刷新 + 叙述按需」的分工实现

需求：X 情绪要真，但脚本抓不到社交平台（也不该为此硬造采集器）。落地形状：

- 脚本 `x_sentiment_refresh.py`：只刷客观可复现部分（恐贪 alternative.me、BTC/ETH 市占与总市值 CoinGecko `/global`、热门 `/search/trending`），
  原子写 `data/x_sentiment_context.json`；**不 import 任何外发模块**。
- agent 侧：检索到的叙述经 `--x-note "…"` 写回**同一文件**的 `x_note` 子对象，自带 `ts` 与 `label: 仅情绪·不改裁决`。
- 不带 `--x-note` 时**保留**已有叙述（`refresh_status.x_note = kept_previous`），绝不清空别人写的内容。
- 子项取不到 → 保留旧值 + `stale_cache:<异常名>`；**全部子项失败才 return 2**（部分降级不算事故，避免 cron 噪声）。
- 消费方按语义时间戳判龄：超过 6h 打印「本轮不采用（旧值不展示）」，并注册 `stale_cache`；
  不再出现「✅ + 两个月前的恐贪」。

副产品：该文件里的市占顺带从 6 月的 56.33% 换成真实值（CoinGecko `/global` 端点一直可用，只是**没有任何调用者**，
所以子缓存永远停在 6 月 —— 「没人调用的分支永远不刷新」）。

## 三、载荷键名与类型冲突（`unhashable type: 'dict'`）

真实崩溃点：`scripts/source_health.py:93`

```python
explicit = contract.get("status") if contract else data.get("_source_status") or data.get("source_status")
explicit_status = str(explicit) if explicit in VALID_STATES else None   # ← explicit 是 dict 时抛 TypeError
```

触发：新增刷新器把逐子项状态写成 `source_status: {fear_greed: "live", …}`（dict）。
后果：`_register_source_record` 抛 `unhashable type: 'dict'` 被外层 `except` 吞掉，
该源从可采信直接掉成 `unavailable`，而打印语句仍显示「✅」。

两侧修法：

```python
# ① 检查器：只采信合法类型
explicit_status = explicit if isinstance(explicit, str) and explicit in VALID_STATES else None
# ② 写入方：换用不冲突的键名，并清理历史遗留
context["refresh_status"] = status
if not isinstance(context.get("source_status"), str):
    context.pop("source_status", None)
```

复盘判据：`TypeError/unhashable` 出现在**状态判定**里而不是采集器里 → 先查键名与类型冲突。

## 四、全量回归假红：修法（不只是诊断）

诊断（SKILL.md 已写）：单跑通过、全量失败 → 先怀疑共享状态。修法是**用例侧隔离**：

```python
# tests/test_keylevel_contract.py —— 续航用例不该受真实分析租约影响
import tv_data_bridge as _bridge

@pytest.fixture(autouse=True)
def _no_active_analysis_lease(monkeypatch):
    monkeypatch.setattr(_bridge, "analysis_lease_status", lambda *a, **k: {"active": False})
```

注意：`btc_tv_refresh.main()` 是**函数内 import**（`from tv_data_bridge import analysis_lease_status`），
所以必须把补丁打在 `tv_data_bridge` 模块上，而不是 `refresh.analysis_lease_status`。

```python
# tests/test_binance_public.py —— 模块级冷却表/缓存必须逐用例复位
@pytest.fixture(autouse=True)
def _isolate_module_state(monkeypatch):
    monkeypatch.setattr(bp, "_HOST_DOWN_UNTIL", {})
    monkeypatch.setattr(bp, "_ORION_CACHE", {})
    monkeypatch.setattr(bp, "_ORION_CACHE_AT", 0.0)
    monkeypatch.setattr(bp, "_FAPI_HEALTH", None)

def test_module_host_cooldown_state_starts_clean():
    assert bp._HOST_DOWN_UNTIL == {}, "host 冷却表未隔离"
```

验收（必须复现原失败条件，不能只跑一遍绿）：

| 验收项 | 结果 |
|---|---|
| 故意持有活跃租约（`remaining_seconds≈360`）跑全量 | 1046 passed ← 原先会红的条件 |
| 常规全量连跑 3 次 | 三次全绿，不再飘 |
| 跑完全量后原始模块全局残留 | `_HOST_DOWN_UNTIL={}`、`_ORION_CACHE=[]`、`_FAPI_HEALTH=None` |

诚实边界：**泄漏源没有稳定复现**（现在整轮跑完、单跑疑似上游文件，全局都干净），
推测是某次真实网络请求临时失败触发的瞬时标记（本机 Binance 直连本就有 12s 超时毛病）。
因此落点选的是**进程级隔离**（不管上游谁失败都不影响本文件），而不是「假装找到了元凶」。

## 五、同轮档位审计数字（供下次对照）

`BTCUSDT` 实测：L1=4 步? 不 —— `route_pipeline` 对 quick/standard 返回**同一个 3 步列表**，
L3=15 步；L3 完成度随修复推进：**11/15 →（宏观端点修复）12/15 →（X 情绪恢复）13/15**，
剩余两项为 CoinGecko Pro（部分可用，用户选择先不动）与 Cron 缓存 5 源（生产者有意退役）。
quick 档卡面 `市占—（未采到）`，full 档 `市占58.7%`。
