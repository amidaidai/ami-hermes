# 关键位监控链路：旧触发残留 + 去重状态缺失陷阱（2026-08-29 实战，已修复）

## 链路
`keylevel_guard.py`（0.5s轮询）→ 写 `data/trigger_{symbol}.json` → `keylevel_read_trigger.py`（cron每2min）
读触发 → `keylevel_analysis_dispatcher.py` → `auto_card.py {symbol} --quick --push` → 推386。
去重 state 文件：`C:\Users\Administrator\AppData\Local\hermes\data\keylevel_agent_state.json`（脚本用 `os.path.expanduser("~/...")` 解析）。

## 症状（实测）
- `keylevel_read_trigger.py --no-dispatch` 反复输出**8小时前的旧事件**（如 `level=磁吸↓·周五伦低 price=78379.3 ts=2026-08-28T23:58:40`），而不是静默 `WAIT no-trigger`。
- 每2分钟的 cron 每次运行都重新上报同一旧事件 → 浪费 token、占用分析窗口，真正的新监控位触发时可能被旧事件抢占。

## 根因（两个叠加）
1. **trigger 文件残留旧位，且 `analysis_status` 字段缺失/为 None**：`split_trigger` 写触发时，旧版本可能只写 `triggered:true` 而无 `analysis_status`。`read_trigger` 的去重分支只识别精确字符串 `status=="analyzed"` / `== "analyzing"` / `== "failed"`，**`None` 不匹配任何分支** → 该事件永远被视为"待处理"，每次 cron 都重报。
2. **去重 state 文件缺失**：`read_trigger` 第66行 `last_done_ts = state.get(sym,{}).get(zone,"")`，若 state 文件不存在 → `state={}` → `last_done_ts=""` ≠ 旧事件的 ts → 无法用 `last_done_ts==ts_key` 拦截。

## 修复
1. **写入正确去重 state**（key = 触发事件名，value = 该事件的 ts），这样 `last_done_ts==ts_key` 才命中：
   ```python
   import json, os
   from pathlib import Path
   p = Path(os.path.expanduser('~/AppData/Local/hermes/data/keylevel_agent_state.json'))
   p.parent.mkdir(parents=True, exist_ok=True)
   state = {'BTCUSDT': {'磁吸↓·周五伦低': '2026-08-28T23:58:40.966222+08:00'}}
   p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
   ```
2. **验证**：`python scripts/keylevel_read_trigger.py --no-dispatch` → 应输出 `WAIT no-trigger`（而不是旧事件）。

## 关键坑：路径不一致（踩过）
- 用 git-bash `mkdir -p "$HOME/AppData/..."` 把文件写到了 `/c/Users/...`（bash 展开），但 Python `os.path.expanduser("~")` 在 Windows 展开为 `C:\Users\...` → **根本没写到脚本读取的路径**。
- 必须用 Python 脚本本身 `os.path.expanduser` 写入，验证路径用 `repr(p)` 打印确认。

## 预防
- 监控链路诊断顺序：① `state` 文件是否存在且含对应 zone，② trigger 文件 `analysis_status` 是否是合法值（None/analyzed/analyzing/failed），③ 现价 vs 监控位是否真的穿越过（没穿越不该有 trigger）。先查状态再查配置，别直接跑 cron。
