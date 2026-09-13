# XAU TV 读取链四层根因 + 四轮生产实测（2026-09-13）

> 场景：XAU full 卡反复出现「TV五层 ⚠️ / TV缓存不可用」类红灯，同一日经四轮生产实跑逐层剥离，
> 最终第四轮（13:51 卡）达成组合验收：`♻缓存新鲜跳过 + ✅前置刷新 + 注入成功 + TV五层 ✅ + 7/8`。
> 修复 commits：`cc2cbf4`（阈值，上午）+ `3439cfb`（读取链三处 + DMI 防御，下午）。

## 四层根因

| 层 | 问题 | 症状（哪轮暴露） | 修复 |
|:--|:--|:--|:--|
| ① | `xau_tv_sync` 新鲜度阈值 10min < cron 间隔 15min（`*/15`） | 每周期尾部 5 分钟必判「行动格过期」，门 tv_live 误红 | 10→13（=间隔−2，对齐 btc_tv_refresh 18/20 模式）（13:34 前，cc2cbf4） |
| ② | 读取侧 `_tv_cache_status`（auto_card，live_paths / structure_paths 两处调用）默认 max_age=10，与前置 13 不一致 | 前置判「新鲜→跳过刷新」，读取判「过期→拒用」，**同卡自相矛盾**（门2 reason「缓存过期 10分钟」）（13:42 轮） | 调用处传 `_live_max_age = 13 if _is_gold_asset else 10` |
| ③ | XAU 读取链包含 BTC 专属 `tv_live.json` / `tv_dmi_cache.json` | 门2 reason 串充斥「品种不匹配 BINANCE:BTCUSDT.P」噪声 | gold 资产 `live_paths` / `structure_paths` 只留专属 `tv_live_XAUUSD.json`（`symbol_live_path`） |
| ④ | 修③时把 `if not tv_raw:` 改为 `if not tv_raw and ≠gold:`，XAU+None 掉进 `else` 分支的 `tv_raw.get()` | `⚠ TV DMI跳过: 'NoneType' object has no attribute 'get'`（13:44 轮，**自引入回归**） | 改 `elif tv_raw:`（无 tv_raw 时 tv_dmi_data 保持空 `{}`） |

## 四轮实测时间线（收敛过程）

| 轮 | 时间（BJT） | 结果 | 暴露层 |
|:--|:--|:--|:--|
| 1 | 13:34 | 7/8，但订单流 N/A、门2「品种不匹配」噪声 | ①已修，③未修 |
| 2 | 13:42 | 门2「缓存过期 10分钟」拒用（11min 数据）→ 前置却说新鲜跳过 | ② |
| 3 | 13:44 | `TV DMI跳过 NoneType` 异常（修②③后自引入） | ④ |
| 4 | 13:51 | **♻跳过 + ✅前置刷新 + 注入成功 + TV五层 ✅ + 7/8**；门2 红灯=「TV禁做/结构冲突: X」（真实行动格 X，非链路问题） | 收敛 ✅ |

## 诊断命令序列（可复用）

```bash
cd "D:/Hermes agent"
# 1) 数据新鲜度（对比卡运行时刻，判断「卡读到的数据多旧」）
stat -c '%y' data/tv_live_XAUUSD.json data/xau_tv_state.json | cut -c12-19
# 2) TV 现场健康 + 当前图（可能被其他任务/卡切走，注意 symbol+resolution）
#    mcp__tradingview__tv_health_check → cdp_connected / api_available / 当前 symbol
# 3) 手动同步（排除卡内联/并发干扰；前台跑约 55s，输出正常即成功）
python scripts/xau_tv_sync.py
# 4) 卡日志关键词过滤（验证组合验收标志）
python scripts/auto_card.py XAUUSD --mode-auto --message "分析一下黄金" 2>&1 \
  | grep -E "♻|前置|注入|TV DMI|CVD|完成|TV现场"
```

## 关键判读规则（防误报）

- **门2 红灯 reason 分类**：含「缓存过期 / 品种不匹配」= 链路问题（查 ①②③）；`TV禁做/结构冲突: X` = 真实数据判定（行动格 X 禁做），**不是故障**。
- **「♻ 跳过重复切图」是正常路径**：前置判定缓存新鲜即跳过刷新（按需刷新设计），不是「没刷新」。
- **同卡自相矛盾 = 阈值不一致信号**：前置与读取对同一数据判定相反时，先 grep 两处阈值再谈其他。
- **缓存 age 显示**：「缓存过期 N分钟」的 N 是 age 不是阈值（reason 引用 age），判定用 `<= max_age_minutes`。

## 实施纪律（本轮事故沉淀）

1. 改 if 条件必须全链检查 else/elif 落点（④ 是自引入回归，靠下一轮实跑才捕获）。
2. 一处阈值修复 → `grep -n` 同一数据全部校验点一起对齐（改一个 = 必查全部）。
3. patch 后 read-back + `py_compile`；跨函数签名的改动逐行核对（本轮 3 次模糊匹配误伤）。
4. 多段流水线修复必须生产实跑收尾——单测只证明所覆盖合同，不证明链路收敛。
