# 强制闸门的“假绿”模式

> 通用规律 + 一个已实测的实例。遇到任何“多门闸门 / 多源体检”类模块，先套下面的表结构和回读流程。

## 规律

1. **强制拦截门的输入位是 opt-in 的。** 门要拦你，必须先被告知“现在该拦”。那个信号常常不是业务字段，而是一个**专用布尔键**（如 `_banned_live`）。
2. **你不传 → 门走 `else` 分支 → 报绿。** 而不是报错、也不是报“未知”。因为门的作者假设编排器一定会传。
3. **业务语义相近的键不会被读取。** 把事件写进 `meta["events"]` 看起来天经地义，但只要门读的是 `engine_data["_banned_live"]`，`events` 就是个装饰字段。

结论：**凡是有“该拦却没拦”可能的门，喂完输入必须回读它。** 回读成本一次函数调用；漏读的代价是在该拦的窗口里给出可执行结论。

## 实例：GO/NO-GO 八门闸门（`scripts/go_nogo_gate.py`）

入口：`check_gate(symbol, engine_data, meta)`；卡面：`gate_report_card(result, symbol)`——**两个位置参数**，少传 `symbol` 直接 TypeError。

### 逐门依赖

| 门 | 读的键 | 缺了会怎样 |
|---|---|---|
| data_freshness | `meta.data_grade`（只有 A/A-/B 算新鲜）+ `engine_data._snapshot_age_h` | 默认 `"C"` / `24` → **红** |
| tv_live | `engine_data._tv_pine` / `_tv_live_status={"usable":bool}` / `_tv_direct_verified` / `_tv_main` / `_tv_override` | 全缺 → 「缺少现场数据」红 |
| rr_ratio | `meta.rr_a`（或 `rr1`）；`engine_data._final_verdict.rr` 有值时覆盖 | 无主推（WAIT）时**应当红**，不是 bug |
| **event_window** | `engine_data._banned_live` / `_ban_reason` / `_kill_zone` | **← 缺则假绿** |
| protections | `meta.protections_status` / `meta.protections_snapshot_stale` | 「未完整检测」黄 |
| wfo_samples | 影子样本接入情况 | 通常黄，不拦截 |
| dual_indicator | 主副指标是否已读 | 通常黄 |
| portfolio_exposure | 持仓数据 | 通常黄 |

**`event_window` 是唯一会假绿的门。** 它完全不看 `meta["events"]`。实测：把 5★ 利率决议与 4★ 数据写进 `meta["events"]`，门照旧输出

```
green · 无事件禁做·非主窗口
```

——在重大事件窗里放行。修法是显式补两个键：

```python
engine_data["_banned_live"] = True
engine_data["_ban_reason"] = "FOMC/重大数据窗口·只观察不进场"
engine_data["_kill_zone"] = "美盘事件窗"
```

### 回读配方

```python
import sys; sys.path.insert(0, "scripts")
import go_nogo_gate as g

engine_data = {
    "_snapshot_age_h": 0.15,
    "_tv_pine": {"main": {"结论": "..."}},
    "_tv_live_status": {"usable": True, "reason": "<来源·时间·fresh标志>"},
    "_tv_direct_verified": True,
    "_tv_main": {"grade": "C"},
    "_tv_override": {"tv_grade": "C", "tv_active": True},
    "_banned_live": True,
    "_ban_reason": "FOMC/重大数据窗口·只观察不进场",
    "_kill_zone": "美盘事件窗",
    "_final_verdict": {"state": "WAIT"},
}
meta = {
    "data_grade": "A",
    "status": "C",
    "protections_status": "通过",
    "protections_snapshot_stale": False,
}

r = g.check_gate("BTCUSDT", engine_data, meta)
for name, d in r["gates"].items():
    print(name, d["status"], d["reason"])
print(g.gate_report_card(r, "BTCUSDT"))
```

**验收标准**：事件窗内有事件时，`event_window` 必须是 `red`。回读看到 `green · 无事件禁做` 就是没传对，回去补键，不要出报告。

### 其他常见“噪声结论”

同一家族的模块还有两个会误导的默认输出，报告前要过滤：

- **黄灯不等于通过**：`未接入 / 未评估 / 未完整检测` 是缺数据，报告里要写明缺什么，不能计作已检查。
- **风控模块的假违规**：`evaluate_risk` 在无入场价/无止损时会吐出「单笔风险 100.0% > 1% 上限」这类条目——那是缺输入算出来的。只报模块自己声明的状态降级（如 `risk_state_status.status="stale"`），并把它写成**可见降级而非硬拦截**：方向结论照给，只是不给仓位建议。
