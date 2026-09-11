# 棠溪 TG 推送实际清单（2026-07-08 审计后状态）

## 已推 846 的任务（脚本内 push_tg_rich）
| 脚本 | 内容 | 备注 |
|:---|:---|:---|
| orion_screener_radar.py | Orion全市场雷达 | 加24h%/仓位系数 |
| x_sentiment_context.py | X情绪LLM快照 | 加共振候选表/恐惧贪婪分层 |
| btc_ref_levels_sync.py | BTC关键位 | 成功也推（关键位+偏离%+振幅+决策） |
| daily_trade_review_reminder.py | 每日复盘提醒 | 26笔待复盘 |
| monitor/btc_watchdog.py | BTC守护看门狗 | 告警表 |
| monitor/market_watchdog.py | 行情守望看门狗 | 告警表 |
| repo-maintenance/daily_ops_bundle.py | 每日运维聚合 | 管道表 |
| liquidation_collector.py | 清算压力 | 加价格变化%/爆仓决策 |
| dune_collector.py | Dune链上 | BTC流入USD/CEX各所/链上结论 |
| deribit_options.py | Deribit期权 | C/Pγ区/MaxPain磁吸 |
| cot_collector.py | CFTC COT | 机构多空净持仓详表 |
| stablecoin_collector.py | 稳定币 | 各币占比/资金流信号 |
| qlib_factors.py | 量化因子 | 三维归类(动量/趋势/量能) |
| x_sentiment_collector.py | X情绪数据 | 恐惧贪婪分层/热门币 |
| macro_poly_refresh.py | 宏观+Poly | DXY/VIX/SPX/美债/金银/风险情绪 |
| xau_tv_sync.py | XAU TV五层 | 5m/15m/1h/4h 高低收+4h位置 |
| data_freshness_watchdog.py | 数据新鲜度 | 过期文件告警表 |
| trade_exec_bridge.py | 交易执行桥 | 结构化事件表 |

## 通道文件
- `scripts/telegram_reliable.py` — `push_tg_rich(target, text)` 统一入口（RichMarkdown）
- `scripts/telegram_direct.py` — 386 通道，`send_telegram_direct` 默认 RichMarkdown
- `scripts/tg_table_card.py` — **死代码**（图片表生成器，用户禁用）

## 验证命令速查
```bash
# 1. 找出所有推TG脚本
grep -rlnE "telegram|push_tg|send_telegram|telegram_reliable" scripts/ --include=*.py

# 2. 找出所有topic
grep -rhoE "telegram:-1003733144325:[0-9]+" scripts/ --include=*.py | sort -u

# 3. 语法全检
python -c "import ast; [ast.parse(open('scripts/'+f).read()) for f in ['a.py','b.py']]; print('OK')"

# 4. 验证386默认RichMarkdown(单测)
python -c "
import sys; sys.path.insert(0,'scripts')
import telegram_reliable as tr
calls={}
tr._post_json=lambda m,p,t,to:(calls.update({'m':m,'r':'rich_message' in p}) or (True,'ok'))
tr.send_telegram_reliable('telegram:-1003733144325:386','| a | b |\n|:----|:----|')
print(calls)  # {'m':'sendRichMessage','r':True}
"
```

## Git 提交记录（本次改造）
- `0db55b5` 7任务统一RichMarkdown + cron Deliver改local
- `776b2b4` 决策精细度升级(BTC关键位/Orion/X情绪)
- `da407d4` 全量11 collector接TG做厚 + 386默认RichMarkdown + COT缓存命中也推详表
