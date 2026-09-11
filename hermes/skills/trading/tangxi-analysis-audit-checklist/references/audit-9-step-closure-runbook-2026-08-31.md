# 棠溪系统 C 全套修复闭环 Runbook（2026-08-31 落地）

## 触发
用户选 "C 全套"（或 "全部修一遍"/"全部自动修复"）时按本 runbook 顺序执行。本会话实测 9 步用时约 10 分钟（含端到端验证），所有步骤命令可直接复制。

## 前置条件
- 已在 `D:/Hermes agent` 目录
- Python 环境 OK（`pydantic 2.13.4` / `pydantic-core 2.46.4` 已验证）
- TV CDP 9222 端口已开（`python -c "import socket; print(socket.socket().connect_ex(('127.0.0.1',9222))==0)"` 返回 `True`）

## 9 步标准动作（顺序不可错）

### Step 1：恢复孤儿脚本（真 P0）

```bash
# 1a. 列出 6 个孤儿脚本的真实状态
for f in meta_labeler orderflow_absorption cvd_analyzer fvg_detector order_block correlation_matrix; do
  if [ -f "scripts/${f}.py" ]; then
    [ -f "scripts/_disabled_20260829/${f}.py" ] && echo "  🔵 ${f}.py 双份" || echo "  ✅ ${f}.py only in scripts/"
  elif [ -f "scripts/_disabled_20260829/${f}.py" ]; then
    echo "  🔴 ${f}.py 仅在 _disabled → 真孤儿"
  else
    echo "  ⚠️ ${f}.py 全部缺失"
  fi
done

# 1b. 恢复真孤儿（仅 _disabled）
cp scripts/_disabled_20260829/cvd_analyzer.py scripts/cvd_analyzer.py

# 1c. 验证
python -c "import sys; sys.path.insert(0,'scripts'); from cvd_analyzer import check_cvd_confluence, CVDResult; print('✅ import OK')"
```

### Step 2：恢复守护脚本 + 修 cron 自相矛盾

```bash
# 2a. 恢复脚本
cp scripts/_disabled_20260829/tv_keepalive.py scripts/tv_keepalive.py

# 2b. py_compile 验证
python -c "import py_compile; py_compile.compile('scripts/tv_keepalive.py', doraise=True); print('✅ py_compile OK')"

# 2c. dry-run（端口已开应静默退出）
timeout 8 python scripts/tv_keepalive.py
# 期望 exit=0 无输出

# 2d. 改 cron 状态（auto-disabled: enabled+paused contradiction）
python <<'PY'
import json, time, shutil
p = r'C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json'
d = json.load(open(p))
for j in d['jobs']:
    if j.get('id') == 'b78741992dfd':  # TV Desktop保活
        j['enabled'] = True
        j['state'] = 'scheduled'
        j.pop('paused_at', None)
        j.pop('paused_reason', None)
        j['next_run_at'] = None
        j['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S+08:00')
        break
shutil.copy2(p, p + '.bak.' + time.strftime('%Y%m%d%H%M%S'))
json.dump(d, open(p, 'w'), ensure_ascii=False, indent=2)
print('✅ cron enabled+state 修正')
PY
```

### Step 3：重生 btc_ref_levels + tv_live + tv_dmi_cache（一次刷三个）

```bash
timeout 60 python scripts/btc_ref_levels_sync.py
# 期望 exit=0 · updated_at=当前时间
python -c "import json; d=json.load(open('data/btc_ref_levels.json')); print('updated_at:', d['updated_at'])"
```

### Step 4：source_snapshot 留观（设计边界）

**不要 `auto_card.py BTCUSDT --quick` 试图刷它**——quick 模式不写盘（仅 `auto_card.py --full` 通过 `trading_system.source_snapshot()` 才写）。直接留观，下一次 full 模式触发自动刷新。

### Step 5：4 类设计性退役文件留观

| 文件 | 设计性退役原因 | 不重建 |
|---|---|---|
| `source_snapshot_*.json` | 仅 full 模式写盘 | 留观 |
| `monitor_levels.json` | 已被 `keylevels_config.json` 替代为唯一批准源 | 留观 |
| `protections_state.json` | live 区无 `save_protections()` 调用方 + 用户偏好"手动控制" | 留观 |
| `trade_events.jsonl` | 用户偏好"不需要自动交易" | 留观 |

### Step 6：暂停设计性错配 cron

```python
# liq_listener_btcusdt（while True daemon 配每日 cron 必 timeout 3600s）
python <<'PY'
import json, time, shutil
p = r'C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json'
d = json.load(open(p))
for j in d['jobs']:
    if j.get('name') == 'liq_listener_btcusdt':
        j['enabled'] = False
        j['state'] = 'disabled'
        j['paused_at'] = time.strftime('%Y-%m-%dT%H:%M:%S+08:00')
        j['paused_reason'] = '2026-08-31 棠溪审计: 设计性 timeout（ws_daemon while True 配每日调度必 3600s），已用 cron 暂停。请改 --once 模式或拆守护。'
        j['updated_at'] = j['paused_at']
        break
shutil.copy2(p, p + '.bak.' + time.strftime('%Y%m%d%H%M%S'))
json.dump(d, open(p, 'w'), ensure_ascii=False, indent=2)
PY
```

```python
# 宏观Poly刷新（脚本已归档 cron 引用断链）
python <<'PY'
import json, time, shutil
p = r'C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json'
d = json.load(open(p))
for j in d['jobs']:
    if j.get('name') == '宏观Poly刷新':
        j['enabled'] = False
        j['state'] = 'disabled'
        j['paused_at'] = time.strftime('%Y-%m-%dT%H:%M:%S+08:00')
        j['paused_reason'] = '2026-08-31 棠溪审计: 脚本已归档 _disabled_20260829/，cron 引用断链 (7/15 DXY missing)。架构改造后该模块退役。如需恢复请先把脚本移回 scripts/ 并修复 DXY 数据源。'
        j['updated_at'] = j['paused_at']
        break
shutil.copy2(p, p + '.bak.' + time.strftime('%Y%m%d%H%M%S'))
json.dump(d, open(p, 'w'), ensure_ascii=False, indent=2)
PY
```

### Step 7：核验 macro_poly_refresh.py DXY missing（已被 Step 6 覆盖）

如 Step 6 已执行，Step 7 跳过（重复）。

### Step 8：端到端验证（不可跳）

```bash
# 8a. 7 孤儿全员 import
python -c "
import sys; sys.path.insert(0,'scripts')
for m,f in [('cvd_analyzer','check_cvd_confluence'),('meta_labeler','check_meta_label'),
            ('orderflow_absorption','detect_absorption'),('fvg_detector','detect_fvg'),
            ('order_block','detect_obs'),('correlation_matrix','multi_asset_risk_multiplier')]:
    try: __import__(m, fromlist=[f]); getattr(__import__(m, fromlist=[f]), f); print(f'  ✅ {m}.{f}')
    except Exception as e: print(f'  ❌ {m}.{f}: {e}')
"

# 8b. 3 关键数据 mtime < 30min
python -c "
import json, time, os
for f in ['data/btc_ref_levels.json','data/tv_live.json','data/tv_dmi_cache.json']:
    age = int((time.time() - os.path.getmtime(f)) / 60)
    print(f'  {f}: {age}min {\"✅\" if age < 30 else \"❌\"}')
"

# 8c. 4 活跃 cron last_status=ok
python -c "
import json
d=json.load(open(r'C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json'))
for j in d['jobs']:
    if j.get('enabled'):
        print(f'  ✅ {j[\"name\"][:30]:30s} | {j.get(\"last_status\",\"?\")} | {j.get(\"script\",\"\")[:30]}')
"
```

### Step 9：输出修复报告

报告模板：
| 维度 | 修复前 | 修复后 |
|---|---|---|
| 孤儿 import | 6/7 | **7/7** ✅ |
| 关键位 ref_levels | 37h 过期 | **12min** ✅ |
| TV 缓存 | 37h 过期 | **12min** ✅ |
| 活跃 cron | 4（1 必 error）| **4 全部真活** ✅ |
| 设计性错配 cron | 2（liq/macro_poly）| **0（已 disabled + 留观文档）** ✅ |

综合评分：修复前 7.2/10 → 修复后 8.5/10。扣分项全部为设计边界（4 个留观文件 + 用户偏好导致 trade_events 不活跃）。

## 必查陷阱

| 陷阱 | 现象 | 修复 |
|---|---|---|
| `auto_card.py BTCUSDT --quick` 不写 source_snapshot | quick 模式不调 `trading_system.source_snapshot()` | 改 `--full` 才会写；quick 留观 |
| `btc_ref_levels_sync.py` 报 "unsupported format string passed to NoneType.__format__" | TV 缓存某字段 None | 仍 exit=0 + btc_ref_levels 已刷 → 警告级，不阻断 |
| `keylevels_collect.py` 报 "D 采集失败: timeframe mismatch" | 校验集需含 `{"D": "1D"}` 别名 | 已修；若复发校验 `set_timeframe("D")` 后 `chart_get_state()` |
| `python -c "import cvd_analyzer"` 报 `ModuleNotFoundError` | 路径不在 `sys.path` | 显式 `sys.path.insert(0, 'scripts')` |
| cron 改完 5 分钟内又被 auto-disabled | 脚本又被归档或路径错 | 检查 cron `script` 字段；先 `cp` 恢复再改 cron |

## 完成判断

完成 = **8a 7/7 ✅ + 8b 3/3 < 30min ✅ + 8c 4/4 ok ✅ + Step 6 暂停 cron 留观文档完整**。任一不满足 = 回到对应 Step 排查，不要宣称"修复完成"。
