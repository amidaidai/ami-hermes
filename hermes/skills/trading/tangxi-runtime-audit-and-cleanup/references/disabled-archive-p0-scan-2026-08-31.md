# scripts/_disabled_20260829/ 归档区 P0 扫描方法

> 2026-08-31 审计发现 2 个隐藏 P0（cvd_analyzer + credential_store），写下此文件作为下次审计的快速定位手册。

## 背景

`scripts/_disabled_20260829/` 是 8/29 binance-only 迁移归档区，存 81 个脚本。当时决策是"归档而非删除"（用户偏好"不要的就删掉"时实际默认归档，理由：可回滚+防 cron 静默引用）。

**问题**：归档时只查了"是否有其它 live 脚本 import"，**没查 cron jobs.json 是否引用 + 没查 lazy import（在 try/except 内、函数体内延迟加载）**。这导致：
- `cvd_analyzer.py` 被 `orphan_integration.py:230,234` 延迟 import，auto_card 触发孤儿链才报 `ImportError`
- `credential_store.py` 被 `trading_system.py:294` 顶层 import，**任何引用 trading_system 的脚本加载即崩**（auto_card 走 try/except 兜底未直接暴露，但 source_snapshot() 调用路径全断）

## 3 步扫描方法

```bash
cd "D:/Hermes agent"

# 步骤 1：扫 live scripts 引用（_disabled 区反向）
echo "=== _disabled 被 live scripts 引用 ==="
for f in scripts/_disabled_20260829/*.py; do
  base=$(basename "$f" .py)
  refs=$(grep -rln "\\bfrom $base\\b\\|\\bimport $base\\b" scripts/ \
    --include="*.py" 2>/dev/null \
    | grep -v _disabled | grep -v _archive | grep -v __pycache__)
  if [ -n "$refs" ]; then
    echo "🔴 $base.py ← $(echo "$refs" | wc -l) refs"
    echo "$refs" | head -3
  fi
done

# 步骤 2：扫 cron 引用（jobs.json script 字段）
echo "=== _disabled 被 cron 引用 ==="
python -c "
import json
d = json.load(open(r'C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json'))
for j in d['jobs']:
    s = str(j.get('script',''))
    if any(name in s for name in ['cvd_analyzer','credential_store','ws_liquidation','macro_poly']):
        print(f\"🔴 cron: {j['name']} → {s}\")
"

# 步骤 3：扫 lazy import（try/except 内、函数体内）
echo "=== lazy import 模式风险 ==="
for f in scripts/_disabled_20260829/*.py; do
  base=$(basename "$f" .py)
  # 找任何出现模块名的 live 文件
  matches=$(grep -rln "$base" scripts/ --include="*.py" 2>/dev/null \
    | grep -v _disabled | grep -v _archive | head -5)
  if [ -n "$matches" ]; then
    echo "⚠ $base.py 在 live 中被提到（含注释/字符串/lazy import）:"
    echo "$matches" | sed 's/^/  /'
  fi
done
```

## 已知 case 表（2026-08-31 审计时点）

| 脚本 | 引用方 | 引用类型 | 表现 | 修复 |
|------|--------|---------|------|------|
| `cvd_analyzer.py` | `orphan_integration.py:230,234` | 函数体内 import | auto_card 触发孤儿链 → `ImportError: No module named 'cvd_analyzer'` | cp 回 `scripts/` |
| `credential_store.py` | `trading_system.py:294` | 顶层 import | `trading_system` 加载即崩 → `source_snapshot()` 任何调用路径全断；auto_card 走 try/except 兜底未直接暴露 | cp 回 `scripts/` |
| `ws_liquidation_daemon.py` | `liq_listener_btcusdt` cron | cron script | 必 `Script timed out after 3600s`（while True 常驻） | cron `enabled=false, state=disabled` + 留观文档 |
| `macro_poly_refresh.py` | `宏观Poly刷新` cron | cron script | 7/15 `ERROR: DXY missing` + script not found | cron `enabled=false, state=disabled` + 留观文档 |
| `tv_keepalive.py` | `TV Desktop保活` cron | cron script | 49d `Script not found` + `auto-disabled: enabled+paused contradiction` | cp 回 + 改 cron 4 字段（见 SKILL.md 修法） |

## 恢复铁律

1. **不要直接复制到 scripts/**——先看 `_disabled_20260829/<name>.py` 的 header 和 imports，确认它没有引入别的 _disabled 依赖（会形成依赖链）
2. **cp 后立即 `py_compile`**：`python -c "import py_compile; py_compile.compile('scripts/<name>.py', doraise=True)"`
3. **改引用方**：cron 改 4 字段（enabled/state/paused_at/paused_reason）；auto_card 不改（已经走 try/except）
4. **跑一次依赖它的 quick 路径**：
   ```bash
   timeout 60 python scripts/auto_card.py BTCUSDT --quick
   ```
   看卡内是否出现依赖模块的输出（如 `CVD✅ / 相关性✅ / 订单流✅`）。修复前一定缺，修复后一定有。
5. **jobs.json 必备份**：`shutil.copy2(p, p+'.bak.'+time.strftime('%Y%m%d%H%M%S'))`

## 为什么是 P0 而非 P1

P0 判定标准：**核心链路断 + auto_card 主流程无法完成**。
- cvd_analyzer 缺 → auto_card 在 `_advanced_orderflow` 块内 try/except 兜底，**主卡仍出**但孤儿链全失效 → 实际是 P0（订单流/相关性空缺）
- credential_store 缺 → `import trading_system` 直接崩，**任何引用 trading_system 的脚本**（含 auto_card / pipeline_router / system_data_bridge）全受影响
- ws_daemon cron → 必 timeout 烧 cron 调度资源，污染 last_status

P0 修复时长 ≤ 5 分钟（cp + py_compile + cron 4 字段）。
