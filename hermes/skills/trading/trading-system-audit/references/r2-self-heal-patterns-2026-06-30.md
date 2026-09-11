# R2 自愈修复模式 · 2026-06-30

## 1. 行情守望重启模式

**触发条件**: `monitor_heartbeat.json` 心跳停滞 > 2h + PID 已死

**诊断**: 心跳文件年龄 > 2h + 进程不存在 = 旧进程自然死亡。残留锁文件使本地启动失败。

**修复**:
```bash
# Step 1: 清除锁和旧心跳
rm -f data/monitor.lock data/monitor_heartbeat.json

# Step 2: 后台启动
cd "D:/Hermes agent"
python scripts/行情守望.py -s BTCUSDT XAUUSD
# (用 terminal(background=true) 启动而非 foreground)
```

**验证**:
```bash
sleep 15
cat data/monitor_heartbeat.json | python -c "import sys,json; d=json.load(sys.stdin); print(f'status={d[\"status\"]} symbol={d.get(\"symbol\",\"?\")} ts={d[\"time\"][:19]}')"
```
应为 `status=running symbol=XAUUSD ts=...`

---

## 2. Deribit 期权子进程超时 + 缓存降级

**问题**: `options_chain.py` 中 `_fetch_deribit()` 调 `subprocess.run([..., "deribit_options.py", "--line"], timeout=15)`。BTC 环境 15s 不够 → 超时 → 返回空 → 卡片无期权行。

**修法**: 双保险 (timeout 提高 + 缓存降级):
```python
def _fetch_deribit() -> dict:
    # 1. 先读缓存 (data/deribit.json < 10min)
    cache_path = ROOT / "data" / "deribit.json"
    cache_fresh = {}
    if cache_path.exists() and (now - cache_mtime) < 600:
        # 解析缓存中的 BTCOI/ETHOI 行
        ...

    # 2. 实时获取 (25s timeout, 比15s宽松)
    try:
        r = subprocess.run(..., timeout=25, ...)
        if r.stdout.strip():
            return _parse_deribit_line(r.stdout)
    except subprocess.TimeoutExpired:
        if cache_fresh:
            return cache_fresh  # 超时但缓存可用 → 降级但不空
    except Exception:
        pass
    return cache_fresh  # 最差返回缓存 (哪怕是空的)
```

**验证**: `python -c "from options_chain import options_card_line; print(repr(options_card_line('BTC')))"` 应在 2-5s 内返回（不超时）。

---

## 3. Protections TypedDict len() 错误

**问题**: `risk_constitution.py` 的 `Protections` 是 TypedDict，不支持 `len()`。`json.dumps` 正常但 `len(p)` 抛 `TypeError`。

**修法**: 用 `type(p).__name__` 替代 `len(p)`:
```python
# 错误
log(f"protections_state: {len(p)} keys")
# 正确
log(f"protections_state: OK ({type(p).__name__})")
```

---

## 4. sentiment_search 模块缺失 → Web 搜索 stub 回退

**问题**: `auto_card.py` 的 `Step 4: 市场热点` 中 `from sentiment_search import sentiment_line` 模块不存在 → `ModuleNotFoundError`。

**修法**: 创建 70 行 stub 模块，两级回退:
- `hermes_tools.web_search` (execute_code 沙箱内可用)
- Google RSS (`urllib.request`，any env)

**核心代码**:
```python
def sentiment_line(symbol: str) -> str:
    try:
        from hermes_tools import web_search
        r = web_search(query=f"{kw} news today 2026", limit=3)
        titles = [i["title"][:35] for i in r["data"]["web"][:3]]
        return f"📡 {sym}热点：{'|'.join(titles)}·{ts}"
    except ImportError:
        # urllib RSS fallback
        ...
    except Exception:
        return f"📡 {sym}热点：搜索暂不可用·{ts}"
```

---

## 5. R2 桥接模块集成模式

| 模块 | 功能 | 管线路由步骤 | 注入点 |
|------|------|-------------|--------|
| `jin10_gold_bridge.py` | 金十黄金宏观 (报价+日历+快讯) | gold_macro | auto_card Step 2 前 |
| `cot_bridge.py` | COT 持仓摘要 | gold_macro | auto_card Step 2 后 |
| `forex_rate.py` | 外汇利差 (央行利率+利差计算) | forex_rate | auto_card Step 5 后 |
| `options_chain.py` | 期权链 (Deribit+yfinance+cache) | options_chain | auto_card Step 5 后 |

**注入铁律**:
- 所有注入用 `try/except` 包裹，不因桥接失败中断出卡
- 品种条件用 `if 'XAU' in symbol.upper()` 等硬匹配过滤非触发品种
- 输出写入 `engine_data[key]` 供渲染层消费

---

## 6. Git 锁定模式

**铁律**: 用户说"锁定" = `git commit` + `git push` 到远端。

**操作**:
```bash
git add scripts/<new_files>
git commit -m "<描述>"
git push origin main
```

**注意**: 
- `??` (untracked) 和 ` M` (unstaged) 在 `git reset --hard` 下丢失
- `git push` 后才真正远端备份
