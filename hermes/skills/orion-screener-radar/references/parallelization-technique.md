# Orion Radar Parallelization Technique

## Problem

v2.0 串行架构在 120s cron 超时内跑不完四层验证链：
- Step 1: fetch_orion("") → 15s
- Step 2: fetch_orion("hl") → 15s
- Step 3: 5 候选 × 6 串行 Binance API 调用 × 15s timeout → 最坏 450s
- Step 4: CoinGecko 串行 + 0.3s sleep → 10-20s
- 总计：最坏 ~500s，远超 120s 限制

## Solution: ThreadPoolExecutor 并行化

### 层级 1：两交易所并行拉取

```python
with ThreadPoolExecutor(max_workers=2) as pool:
    fut_bn = pool.submit(fetch_orion, "")
    fut_hl = pool.submit(fetch_orion, "hl")
    bn_tickers = fut_bn.result()
    hl_tickers = fut_hl.result()
```

### 层级 2：候选间并行 + 候选内并行

```python
# 3 个候选并行（外层）
with ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(_verify_one, enumerate(top)))

# 每个候选内部 6 个 API 调用并行（内层）
with ThreadPoolExecutor(max_workers=6) as pool:
    list(pool.map(lambda fn: fn(), [_fetch_24h, _fetch_oi, _fetch_oi_hist,
                                     _fetch_funding, _fetch_taker, _fetch_ls]))
```

### 层级 3：全局 deadline guard

```python
DEADLINE_SECONDS = 90  # cron 默认 120s，留 30s 余量

def time_left():
    return DEADLINE_SECONDS - (time.time() - _start)

# 剩余时间不足时自动跳过深层验证
if time_left() > 20 and HAS_KEYS:
    deep_verify(candidates)
else:
    log("跳过深度验证（时间不足）")
```

## 结果

| 指标 | v2.0 串行 | v2.1 并行 | 提升 |
|---|---|---|---|
| 总耗时 | 120s+ (超时) | 3.1s | 39x |
| 候选数 | 5 | 3 | 减少 40% |
| API per-call timeout | 15s | 8s | 减少 47% |
| Binance 调用 | 串行 30 次 | 并行 18 次 | 并行 6x |
| CoinGecko 调用 | 串行 + sleep | 并行无 sleep | 3x |

## 适用场景

此模式适用于任何 I/O-bound 的多源验证链：
- 多交易所 API 交叉验证
- 多数据源聚合查询
- cron 脚本超时优化

关键原则：I/O-bound 任务用 ThreadPoolExecutor（不是 ProcessPoolExecutor），
因为 GIL 在 I/O 等待时释放，线程切换开销远小于进程。
