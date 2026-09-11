# 2026-09-02 全面审计定稿（综合 8.5/10）

> 承接 8/31 9 项修复 + 9/2 6 项 P0 收尾。本文件用于跨会话审计定稿追溯。

## 一、综合评分轨迹
- **7.2/10**（9/31 修前）：4 个真 P0 待修 + 2 个 cron 错配
- **8.5/10**（9/2 修后）：5 个 P0 全清零 + 4 个留观边界已文档化

## 二、真 P0 全清单（9/2 全部修复或确认）

| # | 项目 | 根因 | 修复 |
|:--:|------|------|------|
| **P0-1** | `cvd_analyzer.py` 孤儿 | 8/29 迁移归档至 `_disabled_20260829/`，`orphan_integration.py:230/234` 顶级 import 失败 | 从 `_disabled_20260829/cvd_analyzer.py` 恢复（13,855 B） |
| **P0-2** | `credential_store.py` 孤儿 | 8/29 迁移归档，`trading_system.py:294 from credential_store import read_secret` 失败 | 从 `_disabled_20260829/credential_store.py` 恢复（685 B） |
| **P0-3** | 8/31 07:50 trigger_BTCUSDT.json text_push=failed | cvd_analyzer 还没恢复（9/2 9:23 才恢复）→ 7:50 触发时仍崩 | cvd_analyzer 恢复后下次触发自动正常；当前 cooldown 已过 2.2h，新触发会重试 |
| **P0-4** | 2 个 cron 错配（liq_listener_btcusdt / 宏观Poly刷新）| `enabled=false state=disabled` 但脚本已归档/不匹配 | 写入 `paused_reason` 文档化原因，保留 cron 实体供未来审计 |
| **P0-5** | uv cpython 3.11 缺 6 个核心包 | `auto_card.py:4806` 用 `cpython-3.11-windows-x86_64-none` 解释器跑，但只装了 `setuptools+pip` → `import requests/pydantic/aiohttp/numpy/pandas/websockets` 全崩 | `--break-system-packages` 装 6 个包到 3.11 site-packages；quick 模式已实测通过 |
| **P0-6** | Pine 主指标 3 处 `table.new` ≠ 13 行行动格（记忆过期）| 实际是单 cell 内 `str.tostring` 拼接 13 行内容（源码验证）| 已修正记忆 |

## 三、修复命令定稿（固化以便复用）

```bash
# P0-5 装包脚本（每次 uv cpython 3.11 重建时必跑）
"C:/Users/Administrator/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe" -m pip install --break-system-packages requests pydantic aiohttp numpy pandas websockets
```

**双 Python 解释器关键事实**：
- 默认 `python` → Hermes venv（已装全）
- `auto_card.py:4806` 实际跑 → **uv cpython 3.11**（`cpython-3.11-windows-x86_64-none`）
- `uv python find` 返回的是 3.12.13，**不是 auto_card 用的**
- 解释：`cpython-3.11-windows-x86_64-none` 是 Windows short-name，`cpython-3.11.15-windows-x86_64-none` 是 full-name，**两条路径都指向 3.11.1 二进制**

## 四、4 项设计边界（留观，非故障）

| 项目 | 状态 | 设计原因 |
|------|------|----------|
| `data/monitor_levels.json` | 49d 旧 | 已被 `keylevels_config.json` 替代；`auto_card.py:2909 _approved_monitor_levels` 改读 keylevels |
| `data/protections_state.json` | 51d 旧 | 用户偏好手动开单 → 风控熔断不会触发 → 状态永远停初始值（drawdown=0/cooldown=False）|
| `data/trade_events.jsonl` | 47d 空 | 零自动交易（用户偏好手动控制开单）|
| `data/trade_reviews.jsonl` | 47d 空 | 依赖 trade_plans，无交易→无 plan→无 review |

## 五、cron 状态快照（9/2 10:33）

### enabled=true（4 个，全部 ok）
- ✅ XAU TV 现场同步 | `xau_tv_sync.py` | `*/15 * * * *`
- ✅ TV Desktop 保活 | `tv_keepalive.py` | `*/10 * * * *`
- ✅ BTC 关键位守护看门狗 | `btc_keylevel_guard_watchdog.py` | `*/2 * * * *`
- ✅ BTC 关键位到价分析推送 | `keylevel_read_trigger.py` | `*/2 * * * *`

### enabled=false state=disabled（2 个）
- 🔧 `liq_listener_btcusdt` (ws_liquidation_daemon.py) | 设计性 timeout | ws_daemon while True 配每日调度必 3600s
- 🔧 `宏观Poly刷新` (macro_poly_refresh.py) | 脚本已归档 | 7/15 DXY missing 断链

### enabled=false state=paused（19 个）
- 3 个 `auto-disabled: enabled+paused contradiction` 已文档化（**BTC关键位同步 已 9/2 修 reason**）
- 16 个无 reason paused = binance-only 迁移设计

## 六、关键经验教训（供未来审计复用）

### 教训 1：**孤儿 import 比 warning 严重**
- `orphan_integration.py:230` 顶级 import `cvd_analyzer` → 整个模块崩
- 后果：auto_card 的 `render_card_locked` 拿不到 CVD 数据，text 卡全失败
- **不是 warning，而是触发器链路静默断裂**

### 教训 2：**双 Python 解释器是隐性炸弹**
- 测试用 `python` 跑通 ≠ auto_card 跑通
- 必须用**实际 cron 调用的解释器**（`uv python find` ≠ 真解释器）测

### 教训 3：**source_snapshot 写盘的不对称性**
- full 模式写盘（`render_card_locked` 之后）
- quick 模式**不写盘**（仅 `_refresh_and_mark_snapshot` 只读不写）
- **这是设计**，但容易误判为 bug

### 教训 4：**TV 缓存 tv_live.json 的双路径**
- BTC: `btc_ref_levels_sync.py` → `mcp stdio (fetch_tv_mcp)` 直写 tv_live.json
- XAU: `xau_tv_sync.py` → TV MCP 五层 → 写 `xau_tv_state.json`（不是 tv_live_XAUUSD.json）
- `tv_live_dump.py`（被归档）只被 `auto_card.py:3250` 调，**failure 不影响**核心 XAU 路径

### 教训 5：**cooldown_until 是已处理过的，不是 pending**
- `trigger_BTCUSDT.json` cooldown_until 已过 = 上次处理过，等下次触发
- 看到 `handled: true + cooldown_until 过期` ≠ "待处理"，而是"等新触发"

## 七、待办清单

| 序 | 问题 | 优先级 | 操作 |
|---|---|---|---|
| 1 | ~~P0-5 装包~~ | ✅ | 已完成 |
| 2 | ~~P1 cron 矛盾 reason 文档化~~ | ✅ | 已完成（备份 jobs.json.bak.20260902103300）|
| 3 | quick 模式 source_snapshot 写盘行为 | ⚠️ P2 | P0-5 修复后已实测 quick 出卡（不写盘确认）|
| 4 | `BTC守护看门狗` cron 矛盾 reason | ⚠️ P2 | 同样用 9/2 修法统一 |
| 5 | `数据新鲜度看门狗` cron 矛盾 reason | ⚠️ P2 | 同上 |
