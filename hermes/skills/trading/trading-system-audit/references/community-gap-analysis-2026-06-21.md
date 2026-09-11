# v6.9.15b 全量审计 · 社区共识差距 + 系统缺陷

◷ 2026-06-21 · 11域扫描 · 6源联网 · 13条发现

## 社区共识对照表（已对齐/差距/缺失 · 更新至 2026-06-21 21:30）

| 共识项 | 棠溪状态 | 差距 |
|--------|---------|------|
| CVD 背离 = 假突破预警 | ✅ v6.9.2 | — |
| **CVD 趋势线突破 LEADING信号** | ✅ v2.1(2026-06-21) | — |
| Liquidity Sweep 灵魂 | ✅ 模板+评分 | — |
| Iceberg 吸收 + 扫止损 | ❌ | P2 缺失 |
| ATR×2 止损锚定结构 | ✅ v6.9.11 | — |
| 日限 3% / 周限 6% | ✅ v6.9.13 | — |
| 时间止损 4-6 根 | ✅ v6.9.13 | — |
| +1.5R 分批止盈 | ✅ v6.9.13 | — |
| Walk-Forward 验证 | 框架存在 | P2 未产出 |
| Pine v6 Footprint | ❌ | P2 缺失 |
| Freqtrade Protections | ✅ v2.0 | — |
| **动态回撤降级 5级渐进** | ✅ v2.1(2026-06-21) | — |
| 预测回验 ≥20 样本 | 23行 | P1 |
| CVD + Taker + Funding 三维 | ✅ BTC | — |
| XAU Kill Zone 时段 | ✅ session_filter | — |
| SMT 背离（关联品种确认） | `correlation_matrix.py` 存在 | P2 未接评分 |
| **Discord清理 → 电报唯一** | ✅ v6.9.16 | — |
| **Cron静默输出+话题统一416** | ✅ v6.9.16 | — |
| **MCP finance死服务** | 未删除 | P2 |

## v6.9.16 会话修复（2026-06-21 全社区联网审计）

### P0
1. **Watchdog第二次重启风暴 (20:57-21:24)** — Discord推送100%超时阻塞
   - 修复：清冷却 + Discord认证已从系统完全清除
2. **MCP finance死服务** — `finance` 和 `financekit` 重叠·`finance`无可见工具
   - 建议：删除 `finance` MCP服务器

### Cron统一
- 4个cron deliver从 `846` → `416`
- 持仓与信号v1.3: 有变化才输出·静默零刷屏
- TV信号监控wrapper v1.1: 零输出（内部已推Telegram）

### 恢复记录
```
d8798ba feat: CVD趋势线突破 + 动态回撤降级 v2.1
ca0a417 opt: cron静默优化 + 话题统一416 + 清理Discord残留
```

## 修复记录
   - 根因: get_cvd() 守卫只检查 endswith("USDT")，XAUUSD 匹配 → 误入 Binance klines
   - 修法: 加 "XAU" in symu
   - 文件: scripts/行情守望.py:235-236

2. TV 信号监控 cron 未注册
   - 根因: hermes/cron/tv_signal_monitor.yaml 存在但从未注册到 cron
   - 修法: hermes cron create + 创建 wrapper
   - 影响: v6.9.15 智能推送管线从未执行

3. Watchdog 下午重启风暴 (15:52-17:22)
   - 根因: 测试 NO_SEND 残留 + 网络抖动 + 代码频繁编辑
   - 状态: 手动重启后稳定，timeout 已优化为 6s×2

## P1 发现

4. 数据桥"未接" —— event_ban 嵌套函数导致 ImportError
   - system_data_bridge.py: event_ban() 定义在 _get_asset_class_simple() 内部
   - → ImportError → _HAS_BRIDGE = False 静默降级
   - 验证: 重启后 monitor.log 显示"数据桥已接"

5. BTC 完整卡 —— 假阳性
   - auto_card_BTCUSDT_full.md 存在 (78行 3747B)
   - 双卡系统工作正常: .md=极简 · _full.md=完整

6. prediction_log 仅 1 行 —— 无回验样本
   - 无法统计胜率、无法调权重

7. system_data_bridge.py 死代码
   - event_ban 内部 57 行嵌套重复函数 (get_dxy/get_basic_earnings_flag/asset_macro_enrich/_get_asset_class_simple)
   - 模块级已有正确版本，嵌套版死代码

## P2 发现

8. monitor_events 膨胀 (47,916 行)
9. 社区 Iceberg 吸收检测缺失
10. Pine v6 Footprint 未利用
11. Walk-Forward 框架未产出
12. monitor_state 旧时间戳残留
## v6.9.16 会话修复（2026-06-21 全社区联网审计）

### P0
1. **Watchdog第二次重启风暴 (20:57-21:24)** — Discord推送100%超时阻塞
   - 修复：清冷却 + Discord认证已从系统完全清除
2. **MCP finance死服务** — `finance` 和 `financekit` 重叠·`finance`无可见工具
   - 建议：删除 `finance` MCP服务器

### Cron统一
- 4个cron deliver从 `846` → `416`
- 持仓与信号v1.3: 有变化才输出·静默零刷屏
- TV信号监控wrapper v1.1: 零输出（内部已推Telegram）

### 恢复记录
```
d8798ba feat: CVD趋势线突破 + 动态回撤降级 v2.1
ca0a417 opt: cron静默优化 + 话题统一416 + 清理Discord残留
```

## 修复记录

```
229ee90 fix: P0/P1审计修复 v6.9.15b
  - XAU kline 400 守卫
  - TV 信号监控 cron 注册
  - event_ban 移出嵌套 → 数据桥已接
  - 删除 57 行嵌套死代码
```
