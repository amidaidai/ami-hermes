# 运行态审计补充：全任务暂停、假新鲜与守护心跳

## 全任务同时暂停

当`jobs.json`仍有大量任务但`hermes cron list`显示0 active时，先统计：总数、enabled、paused、last_status、共同paused_at。若全部在同一时间暂停，优先判断为维护操作未恢复，而非21个脚本同时故障。

恢复顺序：

1. `hermes cron status`确认gateway/ticker存活；
2. 手工运行上次`last_status=error`的任务；
3. 修复并验证退出码；
4. 批量`hermes cron resume ID`；
5. 复核active数量、next_run与真实下一轮last_status；
6. 运行数据新鲜度审计。

## 假新鲜数据

mtime新不代表数据有效。以下内容必须判异常：

- 清算结果全部`api_error/no_data`；
- 行情快照只有error对象；
- symbol与目标品种不一致；
- `fresh=true`同时`stale=true`；
- Data Window缺少权限码却被标为完整聚合。

采集器全失败时不得写“市场常态”。应返回非零、保留最后有效快照，并让看门狗报告质量失败。

## 守护进程心跳

心跳写在价格采集成功之后会把“数据源故障”伪装成“进程死亡”，导致看门狗反复重启。优先修复行情端点多源回退；更完整的实现应在心跳中分开记录：

```json
{"process_alive": true, "data_ok": false, "last_data_at": "..."}
```

看门狗负责进程存活，数据新鲜度模块负责`data_ok/last_data_at`，两类故障不要混为一谈。

## 免费行情域名回退

Binance主域TLS失败时，现货价格/K线可回退：

```text
https://data-api.binance.vision/api/v3/ticker/price
https://data-api.binance.vision/api/v3/klines
```

回退响应必须验证类型和非空。Futures OI不能用现货接口伪造；没有第二OI源时应明确降级，不得把0当真实值。
