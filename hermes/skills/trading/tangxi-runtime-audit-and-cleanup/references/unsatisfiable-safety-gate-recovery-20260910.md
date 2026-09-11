# 不可满足的安全闸 → 监控静默停摆 5 天（2026-09-10 实战）

## 症状

- 看门狗每 2 分钟跑一次，日志一直 `AUTO-RENEW skipped error=structure_review_required`
- 紧接着 `DEGRADED: keylevels_config 当前无有效批准关键位`，exit 2
- 守护进程心跳停在 3.5 天前
- 用户侧表现：**到价提醒不响了**（但没人会主动发现“应该响而没响”）

## 取证链

```
approval_renewal.valid_until      = 2026-09-05T16:13:56   ← 5 天前过期
auto_approval_policy.structure_reviewed_at = 2026-09-04   ← 超过 24h 上限
max_structure_age_hours           = 24
```

关键代码（两道闸必须同时成立）：

```python
def structure_review_is_current(config, now_epoch):
    max_hours = float(policy["max_structure_age_hours"])
    reviewed  = parse(policy["structure_reviewed_at"] or policy["authorized_at"])
    return now <= reviewed + max_hours * 3600      # ← 闸 A

def active_approved_level_count(config=None):
    if not structure_review_is_current(config):    # ← 闸 A 不过则全部归零
        return 0
    return sum(1 for lv in levels if level_is_active(lv))   # ← 闸 B
```

而自动续期只动闸 B：

```python
for level in levels:
    if expires <= threshold:
        level["valid_until"] = new_until           # ← 只刷这个没用
```

**根因：`structure_reviewed_at` 没有生产者。**

```bash
grep -rn "structure_reviewed_at" --include=*.py --include=*.json .
# 结果：只有 keylevel_guard.py / watchdog 在读，tests/ 在写，config 里是死值
# → 无任何生产脚本 → 闸 A 在首次复核 24h 后永久为假
```

## 修法：给闸補一个真生产者（不是回写字段）

```python
NAME_TO_SVP = {                      # 批准位名称 → 当前 SVP Data Window 字段
    "价值区·VAH": "vah_price", "价值区·VAL": "val_price",
    "价值区·POC": "poc_price", "价值区·nPOC": "npoc_price",
    "价值区·M-VWAP": "m_vwap_price", "价值区·DO": "do_price",
}
MAX_DRIFT_PCT = 2.5     # 同名价值区漂移上限
MAX_BAND_PCT  = 10.0    # 无同名读数时的价格带

def review(config, snapshot):
    # 0. 先校验快照品种！共享缓存可能装着别的品种（见 tradingview-state-integrity）
    if snapshot_symbol 不匹配 config 的品种:
        return {"ok": False, "symbol_mismatch": True}

    for level in levels:
        svp_key = NAME_TO_SVP.get(level["name"])
        current = snapshot["indicators"].get(svp_key) if svp_key else None
        if current:                                     # 同名读数 → 漂移判定
            if abs(approved - current) / current * 100 > MAX_DRIFT_PCT:
                invalid.append(...)
        else:                                           # 无同名 → 价格带判定
            if abs(approved - price) / price * 100 > MAX_BAND_PCT:
                invalid.append(...)

    ok = checked >= MIN_VALID and len(invalid) == 0       # ★ 全数通过才盖章
```

**盖章逻辑（关键：只降不升）**：

```python
def apply_review(config_path, result, now, force=False):
    if not result["ok"]:
        return {"stamped": False}                  # 不通过 → 不动配置
    if 距上次盖章 < MIN_STAMP_INTERVAL_MIN(30):
        return {"stamped": False}                  # 频控，避免每 2 分钟写盘
    policy["structure_reviewed_at"] = now.isoformat()
    policy["structure_review_method"] = result["method"]   # 留下“怎么审的”证据
    policy["structure_review_valid"]  = result["valid"]
```

## 阈值设计教训

先用「valid >= MIN_VALID（8 个里 ≥ 6 个）」→ 测试挂：某个位漂了 20% 仍然放行，
意味着看门狗会把**已失效的那个也一起续期** → 监控一个假价 → 发假警报。

改成「**任一失效即不盖章**」（`valid == checked and checked >= MIN_VALID`）。
理由是：盖章是**批量**动作（一次给全部位续期），所以“部分成立”不能被当作“可以盖章”。
宁可让闸落下、要求人工重新批准，也不放行已知失效的位。

## 验收清单

- [ ] 复核通过 → `structure_reviewed_at` 被更新（读回确认）
- [ ] 复核不通过 → 配置**未被修改**（读回确认）
- [ ] 品种不匹配（如缓存里是黄金）→ 拒绝且报 `symbol_mismatch`，不得得出“漂移 1600%”的假结论
- [ ] 频控：30 分钟内重复调用不重复写盘
- [ ] 看门狗完整跑一次：`STRUCTURE-REVIEW ok` → `AUTO-RENEW` → `status: ok`
- [ ] `.keylevel_guard_health.json` 里 `active_approved_levels > 0`
- [ ] 守护进程重启后心跳恢复新鲜
