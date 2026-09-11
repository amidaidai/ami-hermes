# 关键区到价提醒 — no_agent 零token监控

## 适用场景
用户要求"到这个价格/区间提醒我"时，用 no_agent cron 而非 agent cron。

## 优势
- 零token消耗 — 脚本直接检查价格，不跑LLM
- 只触发时推送 — 不在区间时静默退出，无输出=无推送
- 防重复 — 状态文件记录上次是否已提醒，避免每次3分钟都刷

## 模式

### 脚本模板
```python
#!/usr/bin/env python3
"""{品种} {区间名}到价提醒"""
import json, urllib.request, sys, os, time

SYM = "{SYMBOL}"
ZONE_LOW = {lower}
ZONE_HIGH = {upper}

STATE_FILE = os.path.join(os.path.dirname(__file__), "{state_file}")

def get_price():
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={SYM}"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return float(json.loads(r.read())["price"])

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except: return {"last_alerted": False}

def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f)

price = get_price()

if ZONE_LOW <= price <= ZONE_HIGH:
    state = load_state()
    if not state.get("last_alerted"):
        print(f"🔔 {SYM} {price} 进入关键区 {ZONE_LOW}~{ZONE_HIGH}")
        save_state({"last_alerted": True, "price": price, "time": time.time()})
else:
    save_state({"last_alerted": False})
```

### Cron设置
```
cronjob(action='create',
    no_agent=True,
    script='{script_name}.py',
    schedule='3m',
    name='{中文名}',
    deliver='origin')
```

### 注意事项
- 脚本放 `~/.hermes/scripts/`（cron相对路径解析目录）
- 状态文件放同目录，自动防重复推送
- 价格离开区间时自动重置 `last_alerted=false`，重新进入可再次提醒
- 仅依赖 stdlib urllib，零三方依赖
- Binance `api/v3/ticker/price` 免费无认证