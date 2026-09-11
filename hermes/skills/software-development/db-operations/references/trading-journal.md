# 交易日志数据库参考模式

本参考文件记录了交易日志系统的数据库设计（创建于 2026-06-15 会话）。

## 适用场景

当用户需要一个轻量级交易日志系统来记录开仓/平仓、生成复盘报告时，使用此模式。

## 核心表结构

```sql
-- 交易主表
CREATE TABLE trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,               -- BTCUSDT, ETHUSDT 等
    side        TEXT NOT NULL CHECK(side IN ('BUY','SELL','LONG','SHORT')),
    entry_price REAL,
    exit_price  REAL,
    qty         REAL NOT NULL,
    pnl         REAL,                         -- 正=盈利，负=亏损
    market      TEXT DEFAULT 'spot' CHECK(market IN ('spot','futures')),
    opened_at   TIMESTAMP DEFAULT (datetime('now','localtime')),
    closed_at   TIMESTAMP,
    reason      TEXT,                         -- 开/平仓理由
    screenshot  TEXT,                         -- 截图路径
    tags        TEXT,                         -- 标签（逗号分隔）
    created_at  TIMESTAMP DEFAULT (datetime('now','localtime'))
);

-- 分析记录表（保留每次分析的快照）
CREATE TABLE analysis_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol        TEXT NOT NULL,
    timeframe     TEXT,
    analysis_type TEXT,                       -- 'execution_card', 'screener' 等
    result_summary TEXT,                      -- 分析结论摘要
    decision      TEXT,                       -- '做多', '做空', '等待', 'X'
    screenshot    TEXT,
    created_at    TIMESTAMP DEFAULT (datetime('now','localtime'))
);

-- 索引
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_opened ON trades(opened_at);
CREATE INDEX idx_analysis_symbol ON analysis_log(symbol);
CREATE INDEX idx_analysis_created ON analysis_log(created_at);
```

## 关键 SQL 模式

### 胜率统计
```sql
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate,
    SUM(pnl) as total_pnl,
    ROUND(AVG(CASE WHEN pnl > 0 THEN pnl END), 2) as avg_win,
    ROUND(AVG(CASE WHEN pnl < 0 THEN ABS(pnl) END), 2) as avg_loss
FROM trades 
WHERE closed_at IS NOT NULL 
  AND closed_at >= datetime('now', '-30 days', 'localtime');
```

### 品种盈亏排名
```sql
SELECT symbol,
    COUNT(*) as trades,
    SUM(pnl) as total_pnl,
    ROUND(AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as win_rate
FROM trades WHERE pnl IS NOT NULL
GROUP BY symbol ORDER BY total_pnl DESC;
```

### 未平仓持仓
```sql
SELECT * FROM trades 
WHERE closed_at IS NULL 
ORDER BY opened_at DESC;
```

## CLI 接口模式

将数据库封装为 Python CLI 是最实用的接口模式：

```python
python journal.py add BTCUSDT BUY 68500 0.001 "理由"
python journal.py close 1 69500        # 平仓（自动计算 PnL）
python journal.py close 1 69500 10.0   # 平仓（指定 PnL）
python journal.py open                  # 当前持仓
python journal.py trades                # 近期交易
python journal.py report 1              # 今日复盘
python journal.py report 30             # 30 天复盘
```

核心模式：
- `add_trade()` → INSERT 返回 trade_id
- `close_trade()` → UPDATE 计算 PnL
- `get_open_trades()` → SELECT WHERE closed_at IS NULL
- `generate_report()` → 聚合查询 + 统计计算

## 注意事项

- 使用 WAL 模式（`PRAGMA journal_mode=WAL`）提高并发读性能
- SQLite 不适合高频写入（多个并发写），适合个人交易日志场景
- PnL 可以用 Python 计算（简化版）或从交易所直接读取
- 建议在日常交易中使用 journal.py 的 CLI 接口，不让 SQL 暴露在外
