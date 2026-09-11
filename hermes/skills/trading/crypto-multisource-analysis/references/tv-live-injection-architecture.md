# TV实时数据注入架构 v9.6

2026年6月29日落地。解决了auto_card D周期"待刷新"的根因。

## 问题

auto_card的klines dict中D周期无数据 → 渲染器显示"待刷新 | 待刷新 | 缺现场数据，降级参考"。TV MCP只能在agent上下文中调用，auto_card运行在terminal上下文中无法直连TV。

## 双缓存架构

| 缓存文件 | 写入者 | 内容 | 频率 |
|---------|--------|------|------|
| `data/tv_live.json` | agent上下文(手动dump) | 完整POC/VAH/VAL/action_grid/fresh | 按需 |
| `data/tv_dmi_cache.json` | cron tv_data_bridge.py | grade/decision_table/key_levels/indicators | 每5min |

**auto_card读取优先级**：tv_live.json → tv_dmi_cache.json。优先选有`fresh=true`且`poc`不为None的。

## auto_card注入逻辑

`hermes/scripts/auto_card.py` 中TV DMI段之后新增注入块：

```python
# v9.6: TV实时数据注入 — 优先读tv_live.json(agent现场) → 回退tv_dmi_cache.json(cron)
live_path = ROOT / "data" / "tv_live.json"
cache_path2 = ROOT / "data" / "tv_dmi_cache.json"
c2 = None
for p in [live_path, cache_path2]:
    if p.exists():
        c2 = json.loads(p.read_text())
        if c2.get("fresh") and c2.get("poc"):
            break
        c2 = None
if c2 and c2.get("fresh") and c2.get("poc"):
    klines = engine_data.setdefault("klines", {})
    poc = c2.get("poc"); vah = c2.get("vah"); val = c2.get("val")
    ag = c2.get("action_grid", {})
    direction = ag.get("方向", "待判")
    # D周期：TV现场数据
    klines["D"] = {
        "close": poc, "high": vah or poc, "low": val or poc,
        "poc": poc, "vah": vah, "val": val,
        "direction": direction,
        "description": f"TV现场 POC {poc:.0f} | VAH {vah:.0f} VAL {val:.0f} | {direction}",
    }
    # 4h/1h/15m/5m：注入POC/VAH/VAL字段
    for tf in ["4h", "1h", "15m", "5m"]:
        if tf in klines:
            k = klines[tf]
            k["poc"] = poc; k["vah"] = vah; k["val"] = val
            if "待" in str(k.get("description", "")):
                k["description"] = f"TV注入 POC{poc:.0f} VAH{vah:.0f} VAL{val:.0f}"
    # 注入到merged供render使用
    merged = engine_data.setdefault("merged", {})
    merged["vah"] = vah; merged["val"] = val; merged["poc"] = poc
    print(f"📡 TV实时注入: POC{poc:.0f} VAH{vah:.0f} VAL{val:.0f} → {len(klines)}周期")
```

## agent上下文手动dump

`scripts/tv_live_dump.py` 从TV MCP live数据写入tv_live.json：

```python
data = {
    'timestamp': datetime.now(TZ).isoformat(),
    'symbol': 'BINANCE:BTCUSDT.P',
    'fresh': True,
    'action_grid': {
        '结论': 'B空 轻仓', '方向': '偏空 · 走弱 · 折价',
        '进场': '反抽DO 59550.2', '止损': '—', '目标': '↓上周 低 58030.0',
        '核对': 'HTF✓ EMA✓ CVD✓ 位置✓ 位移✓ ADR✓ OI⚠多平',
        '磁吸↑': '--', '磁吸↓': '上周 低 58030.0',
    },
    'poc': 59656.53, 'vah': 60164.95, 'val': 59360.94,
}
```

## tv_data_bridge.py v9.6升级

cron写入的tv_dmi_cache.json现在额外包含：

```python
cache = {
    "fresh": True,
    "poc": poc,    # 从Pine labels解析
    "vah": vah,    # 从Pine labels解析
    "val": val,    # 从Pine labels解析
    "action_grid": action_grid,  # 从decision_table提取
    # ...原有字段不变
}
```

## 效果对比

| 之前 | 之后 |
|---|---|
| `| D \| 待刷新 \| 待刷新 \| 缺现场数据，降级参考 |` | `| D \| TV现场 POC 59657 \| VAH 60165 VAL 59361 \| 偏空·走弱·折价 |` |

## Pitfalls

- tv_live.json会被tv_data_bridge.py cron覆盖。依赖auto_card的优先读取顺序解决冲突。
- 如果TV MCP在agent上下文中未dump tv_live.json，auto_card回退到tv_dmi_cache.json（cron写入）。
- tv_dmi_cache.json由cron的Node.js CLI写入，其POC/VAH/VAL依赖CLI输出中包含这些标签。如果CLI版本不输出POC标签，这些字段为None，auto_card跳过注入。
