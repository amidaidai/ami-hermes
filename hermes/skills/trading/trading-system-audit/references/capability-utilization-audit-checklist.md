# 棠溪能力利用率审计清单 (v4.1 · 2026-06-22 更新)

当用户说"全方位优化""完美运用我的能力""全部修复"时，执行以下逐项检查。

## 审计清单（11项·逐项不可跳过）

### ① Pine指标数据桥 ✅ 已对齐
- [x] `fetch_tv_data.cjs` cron运行（偶有Node.js错误·有旧缓存兜底）
- [x] 输出JSON vwap/poc/vah/val 为BTC价位（非XAU脏数据）
- [x] 切换品种后重编译：`ui_open_panel("pine-editor")` → `pine_smart_compile()`
- [ ] P1: cron偶发error（Node.js环境/超时），旧缓存可兜底

### ② 三层确认(OB+FVG+Sweep) ✅ v4.1已回植
- [x] `triple_confirm_bonus` 参数传入 `compute_scores()` → 趋势分+0~3
- [ ] P2: 实际OB/FVG/Sweep检测函数需从 `triple_confirm.py` 调用后传入

### ③ CVD吸收/派发全链路 ✅ v4.1已实现
- [x] Python端 `cvd_absorb_buy` / `cvd_distribute_sell` 检测
- [x] 对齐Pine参数：CVD_ABSORB_LEN=12、ATR×0.8压缩、3×avgDelta阈值
- [x] 6态输出：顺多/顺空/顶背/底背/下方吸收/上方派发

### ④ Polymarket/宏观情绪桥 ⚠️ 部分修复
- [x] `macro_poly_refresh.py` 逻辑修复（event_ban不再误报）
- [ ] P1: cron last_status仍error（间歇性网络超时）
- [x] DXY可获取（100.89）

### ⑤ TV决策表直读 ✅ v4.1已接入
- [x] `fetch_tv_data.cjs` Step 6 抓取Pine tables
- [x] JSON输出含 `tv_grade` / `tv_treatment` 字段
- [x] Python引擎 `compute_scores(tv_grade=...)` 优先使用TV等级
- [ ] P1: cron环境下Pine tables JS执行失败（`tv_grade: None`），Python计算兜底

### ⑥ MTF VWAP入评分 ✅ v4.1已实现
- [x] 周VWAP(w_vwap)/月VWAP(m_vwap)在数据桥中
- [x] 趋势分：站周+月VWAP上方 +1
- [x] HTF过滤：w_vwap + EMA55 联合判断多空

### ⑦ KillZone匹配 ✅ v4.1已接入
- [x] `session_strategy.get_active_killzone()` 可导入
- [x] DMI引擎传入 `killzone_active` → 趋势分+1

### ⑧ jin10日历接入 ⚠️ 可用但未全接
- [x] `event_ban_live.py` 存在且可导入
- [ ] P2: 事件禁做仅在macro_poly_refresh中刷新缓存，未在告警引擎中实时检查

### ⑨ Cron健康 ⚠️ 3/11 error
- [ ] 日间维护：超时（>30s网络调用）
- [ ] BTC TV数据桥：`fetch_tv_data.cjs` Node.js错误
- [ ] 宏观+Poly：间歇性error（手动跑成功）
- [x] 其余8/11 ok

### ⑩ 推送A级门控 ✅ 已实施
- [x] 仅A级推送（趋势分≥8·全门控）
- [x] `if grade != "A": return 0`
- [x] B/C/X静默

### ⑪ TV截图规范 ✅ 已修正
- [x] `capture_screenshot(region="full")` — 全窗口含价格轴+CVD
- [x] MEDIA:路径直发Telegram群
- [x] 分析卡必须附带截图

## 本次修复记录（2026-06-22 · commits 72a7d55→0282fb7）

| # | 修复项 | 文件 |
|---|--------|------|
| 1 | TV指标XAU→BTC重编译 | Pine Ctrl+S |
| 2 | CVD吸收/派发全链路 | `dmi_decision.py` |
| 3 | 周/月VWAP入趋势分 | `dmi_decision.py` |
| 4 | KillZone接入引擎 | `btc_alert_watch_v3.py` |
| 5 | TV决策表直读(JS+Pine tables) | `fetch_tv_data.cjs` |
| 6 | Polymarket cron修复 | `macro_poly_refresh.py` |
| 7 | 持仓与信号cron激活 | cron update |
| 8 | 数据桥路径修正(BTCUSDT.P) | `btc_alert_watch_v3.py` |
| 9 | 三层确认参数接入 | `dmi_decision.py` |

## 新增参考文件
- `references/dmi-engine-integration-pattern.md` — DMI引擎三层对齐模式（Python复现+TV直读+动态桥）
