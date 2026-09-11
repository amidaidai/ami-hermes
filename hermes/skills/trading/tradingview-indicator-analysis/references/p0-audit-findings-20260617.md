# P0/P1/P2 审计发现与修复 · 2026-06-17

## P0 致命

### 1. 推送位信死循环（已修复）
- **问题**：`智能更新结构.py` 生成的监控位 `level_confidence.score` 基础分 66-74（missing 固定包含 "TradingView成交量复核" 和 "订单流确认"），`MIN_WARNING_LEVEL_SCORE=75` 导致高优先级位永不被推送
- **修复**：`行情守望.py` `MIN_WARNING_LEVEL_SCORE` 75→70，`live_level_confidence` 触发时通过 CVD 配合上浮+4 可推到≥70
- **文件**：`scripts/行情守望.py` L55-57

### 2. 零真实成交闭环
- **问题**：`trade_reviews.jsonl` 仅 1 条测试记录，`strategy_model_stats.json` 显示 1/20 样本，"未标注模型"
- **状态**：框架已就绪，`清理守护.py` 已集成，`trading_system.py` 模型治理框架就位。需跑 10-20 笔真实小仓交易（≤3U/笔）

## P1 重要

### 3. push() 无重试（已修复）
- **问题**：`行情守望.py` L238-244 的 `subprocess.run` 无重试，Windows 网络闪断丢告警
- **修复**：3 次重试，间隔 2s，失败日志完整
- **文件**：`scripts/行情守望.py` L238-255

### 4. 信号巡检只推送第一条事件（已修复）
- **问题**：`信号巡检.py` L342-347 只 `print(render_event(new_events[0]))`，其余标记 notified 后丢弃
- **修复**：改为 `for evt in new_events: print(render_event(evt, levels))`
- **文件**：`scripts/信号巡检.py` L343-348

### 5. XAU 数据质量分不一致（已修复）
- **问题**：`source_snapshot.json` 判 B 级（~78%），`monitor_levels.json` 的 `smart_update.quality` 判 C 级（~55%）
- **修复**：`智能更新结构.py` 写入前交叉验证 `source_snapshot.json`，不一致时覆写
- **文件**：`scripts/智能更新结构.py` L115-127

### 6. 维护结果被健康发现隐藏（已修复）
- **问题**：`信号巡检.py` L351 `if maintenance and not findings:` 导致有巡检问题时维护结果被吞
- **修复**：移除 `and not findings` 条件
- **文件**：`scripts/信号巡检.py` L362

## P2 清理

### 7. old_* 死函数（已修复）
- **问题**：`行情守望.py` 内 ~120 行 `old_lab/old_seq/zh_priority/zh_rule/old_display_name/old_display_plan/old_situation_text` 已无调用
- **修复**：全部删除，`monitor_display.py` 已完全接管显示层

### 8. monitor_events.json 膨胀（已修复）
- **问题**：6128 行持续增长，`notified: true` 条目不清除
- **修复**：新建 `scripts/清理守护.py`，7 天清理 + 1000 条上限

### 9. source_snapshots/ 文件爆炸（已修复）
- **问题**：日增 ~3000 文件
- **修复**：`清理守护.py` 实现 7 天保留 + 8-30 天 zip 归档 + 30 天删除

### 10. v9.9 维护链串行阻塞（已修复）
- **问题**：`模型统计.py`→`安全审计.py`→`系统体检.py` 串行，中间超时则后续不执行
- **修复**：`模型统计.py`+`安全审计.py` 用 `ThreadPoolExecutor(max_workers=2)` 并行，完成后跑 `系统体检.py`
- **文件**：`scripts/信号巡检.py` L270-286

### 11. 清理守护集成（已修复）
- **修复**：`清理守护.py` 集成进信号巡检 v9.9 维护链末尾
- **文件**：`scripts/信号巡检.py` L283

## 模型扩展

### 12. 5 类→31 类模型体系（已完成）
- **修复**：`trading_system.py` 新增 `ALL_MODELS`（31 类）+ `MODEL_CATEGORIES`（8 大类）+ `model_by_id/model_by_type_tag/list_models_by_category` 查询函数
- **8 大类别**：成交量/市场画像(6)、ICT/SMC(8)、市场结构(4)、Wyckoff(4)、斐波那契/谐波(3)、缺口理论(2)、经典形态(3)、订单流(1)
- **监控兼容**：`行情守望.py` `condition_ready` 新增 order_block/breaker_block/FVG/BOS/CHoCH/CVD 等 7 种触发类型

## 自启动配置

### 13. 行情守望开机自启动（已完成）
- **方案**：Windows 任务计划 `schtasks /create /tn HW_Monitor /tr "python D:\Hermes agent\scripts\行情守望.py" /sc onstart /delay 0001:00 /f`
- **辅助脚本**：`scripts/install_hw_monitor.bat`、`scripts/安装行情守望自启动.ps1`
- **锁机制**：`行情守望.py` PID 单实例锁防止重复启动

## 搜索 API 诊断

### 14. web_search 路由问题（已诊断，需手动重启）
- **根因**：Hermes 守护进程启动时读 `config.yaml` 到进程内存缓存，`hermes config set` 只写磁盘不通知重载
- **现状**：`web.search_backend = ddgs`、`web.extract_backend = tavily` 已正确写入 config.yaml，`web_extract` 已切到 tavily，`web_search` 需守护进程重启方可生效
- **修复命令**：关闭 Hermes 桌面/TUI 后重新启动，或在当前会话手动 `/new`
- **ddgs 可用性**：已验证 — ddgs 包已安装，DuckDuckGo 免费无限 2000/月限额
