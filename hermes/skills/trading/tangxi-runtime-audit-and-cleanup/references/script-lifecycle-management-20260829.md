---
# 脚本生存性评估清单

## 2026-08-29 审计结果

**145 个脚本** → **41 保留** / **83 归档** / **21 待评估**

---

## 保留脚本 (41 个) - 有实际引用或输出

```
auto_card.py                 # 主入口
pipeline_router.py           # 多资产路由
go_nogo_gate.py              # 7 问下单硬闸门
render_v96.py                # 驾驶舱渲染
data_gatherer.py             # 多源采集
multi_source_collector.py    # CG Pro 速率
multi_model_engine.py        # 核心引擎 v2.1
model_checklist.py           # 模型核对清单
session_strategy.py          # Session 策略
triple_confirm.py            # 三层确认
macro_filter.py              # 宏观过滤
cot_collector.py             # CFTC COT 持仓
deribit_options.py           # Deribit 期权
etf_flow_collector.py        # ETF 净流
dune_collector.py            # Dune 链上
orion_screener_radar.py      # Orion 雷达
xau_tv_sync.py               # XAU TV 同步
gold_monitor.py              # XAU 监控
btc_monitor.py               # BTC 监控
btc_daemon.py                # BTC 守护进程
btc_watchdog.py              # BTC 看门狗
btc_zone_alert.py            # BTC 区间告警
btc_push_386.py            # BTC 推送
btc_card_gen.py              # BTC 卡生成
x_sentiment_collector.py     # X 情绪采集
liquidation_collector.py     # 清算压力
stablecoin_collector.py      # 稳定币供应
qlib_factors.py              # QLib 因子
trade_exec_bridge.py         # 交易执行桥接
data_freshness_watchdog.py   # 数据新鲜度
tv_data_bridge.py            # TV 数据桥
tv_levels_collector.py       # TV 水平位采集
tv_live_dump.py              # TV 实时转储
macro_poly_refresh.py        # 宏观+Poly 缓存
黄金宏观.py                # 黄金宏观背景
spot_price.py                # 现货价格
btc_ref_levels_sync.py       # BTC 关键位同步
render_tv_card.py            # TV 卡渲染
fetch_tv_mcp.py              # TV MCP 接口
keylevel_guard.py            # 关键位守护
btc_keylevel_guard_watchdog.py
keylevel_read_trigger.py
keylevel_analysis_dispatcher.py
keylevels_collect.py
btc_keylevel_read_trigger.py
btc_keylevel_rest_guard.py
btc_keylevel_ws_guard.py
btc_keylevel_sentinel.py
btc_keylevel_aggregator.py
signal_confluence.py         # 作战室融合信号
telegram_reliable.py         # TG 可靠推送
system_data_bridge.py        # 数据桥接
adversarial_analyst.py       # 对抗分析
topic_router.py              # 主题路由
risk_constitution.py         # 风险构成
risk_constitution_v2.py
scoring_engine.py            # 评分引擎
multi_model_engine.py        # 多模型
model_router.py              # 模型路由
meta_labeler.py              # 元标签
orderflow_absorption.py      # 订单流吸收
order_block.py               # 订单块
options_chain.py             # 期权链
polymarket_bridge.py         # Polymarket 桥接
orphan_integration.py        # 孤儿集成
session_strategy.py          # 会话策略
shadow_calibration.py        # 阴影校准
sentiment_search.py         # 情绪搜索
signal_validators.py         # 信号验证
smart_monitor.py             # 智能监控
runtime_core_checks.py       # 运行时核心检查
```

---

## 已归档脚本 (83 个) - 无实际引用，搬至 `scripts/_disabled_YYYYMMDD/`

**归档命令**：
```bash
mkdir -p scripts/_disabled_20260829
mv scripts/{alert_dedup,auto_review,...}/*.py scripts/_disabled_20260829/
find scripts/_disabled_20260829 -name "*.pyc" -delete
```

**归档理由**：
- 无 `import` 引用
- 无 cron 任务调用
- 无 auto_card.py 依赖
- data/ 输出文件 >30 天未更新
- 49 天未被任何系统触碰

---

## 评估方法 (evaluate_script.py)

```python
"""
评估脚本生存性

输入: scripts/ 目录下所有 .py 文件
输出: KEEP / DELETE / REVIEW 三类
"""
import os, re
from collections import defaultdict

def evaluate_script(script_path: str, scripts_dir: str) -> str:
    """
    返回: 'KEEP', 'DELETE', 'REVIEW'
    """
    # 1. 读取内容
    with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 2. 检查引用
    import_refs = len(re.findall(r'^from\s+(\w+)', content, re.M))
    cron_refs = check_cron_jobs(script_name)  # grep jobs.json
    auto_card_refs = script_name in open('auto_card.py').read()
    data_refs = check_data_file_refs(script_name)  # 最近 30 天 data/ 更新
    
    age_days = (os.path.getmtime(script_path) - os.path.getmtime('/now')) / 86400
    
    if import_refs > 0 or cron_refs > 0 or auto_card_refs or data_refs:
        return 'KEEP'
    elif age_days > 30:
        return 'DELETE'
    else:
        return 'REVIEW'

def check_cron_jobs(script_name: str) -> int:
    """返回 jobs.json 中引用次数"""
    with open('cron/jobs.json') as f:
        jobs = json.load(f)['jobs']
    return sum(1 for j in jobs if script_name in j.get('script', ''))

def check_data_file_refs(script_name: str) -> bool:
    """检查 script 是否产出 data/ 最近 30 天的文件"""
    for f in os.listdir('data'):
        if script_name.replace('_', '') in f.replace('_', ''):
            if os.path.getmtime(f'data/{f}') > (time.time() - 30*86400):
                return True
    return False
```

---

## 关键决策参考

| 脚本 | 决策 | 理由 |
|------|------|------|
| `signal_confluence.py` | DELETE | 无 import，旧数据产出 49 天，一无所事 |
| `tv_data_bridge.py` | DELETE | 产出 tv_dmi_cache.json，无人读 |
| `btc_levels_read.py` | DELETE | 产出 tv_live/tv_dmi，无人读 |
| `cot_collector.py` | DELETE | 产出 cot_data.json 6 天，系统不读取 |
| `p0_refresh_all.py` | DELETE | auto_card 已 import，但脚本已被废弃的多源收集代替 |
| `xau_tv_sync.py` | KEEP | cron 驱动，XAU 卡核心依赖 |
| `btc_ref_levels_sync.py` | KEEP | cron 驱动，BTC 关键位核心 |
| `keylevel_guard.py` | KEEP | 心跳文件产出，自动推送依赖 |
| `btc_daemon.py` | KEEP | BTC 多因子评分 + TG:386 推送 |