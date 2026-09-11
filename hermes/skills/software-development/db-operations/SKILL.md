---
name: db-operations
description: 通用数据库操作技能 — SQLite / PostgreSQL 数据库的建表、CRUD、迁移、查询优化。提供标准化的连接管理、索引建议、慢查询分析和数据导入导出模板。
category: software-development
---

# Database Operations

## SQLite（本地轻量，零配置）

### 连接与建表
```python
import sqlite3
conn = sqlite3.connect('data.db')
conn.row_factory = sqlite3.Row  # 列名访问
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT CHECK(side IN ('BUY','SELL')),
    price REAL,
    qty REAL,
    pnl REAL,
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP
)''')
conn.commit()
```

### 常用操作
```python
# 插入
c.execute('INSERT INTO trades VALUES (?,?,?,?,?,?,?,?)', data)
# 批量
c.executemany('INSERT INTO trades VALUES (?,?,?,?,?,?,?,?)', rows)
# 查询（参数化防注入）
c.execute('SELECT * FROM trades WHERE symbol=? AND side=?', ('BTCUSDT', 'BUY'))
rows = c.fetchall()
for row in rows: print(row['symbol'], row['price'])
# 更新
c.execute('UPDATE trades SET pnl=? WHERE id=?', (pnl, trade_id))
# 删除
c.execute('DELETE FROM trades WHERE id=?', (trade_id,))
```

### 实用查询
```python
# 分页
c.execute('SELECT * FROM trades ORDER BY opened_at DESC LIMIT ? OFFSET ?', (limit, offset))
# 聚合
c.execute('''SELECT symbol, COUNT(*) as cnt, SUM(pnl) as total_pnl
             FROM trades GROUP BY symbol ORDER BY total_pnl DESC''')
# 时间范围
c.execute('SELECT * FROM trades WHERE opened_at >= datetime("now", "-7 days")')
```

## PostgreSQL（生产级）

### 连接
```python
import psycopg2
conn = psycopg2.connect(
    host='localhost', port=5432,
    dbname='trading', user='postgres', password='****'
)
# 或用连接池
from psycopg2 import pool
pool = pool.SimpleConnectionPool(1, 10, ...)
conn = pool.getconn()
```

### 建表与索引
```sql
CREATE TABLE IF NOT EXISTS tick_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    price NUMERIC(20,8),
    volume NUMERIC(20,8),
    ts TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tick_symbol_ts ON tick_data(symbol, ts DESC);
```

### 高级查询
```sql
-- 窗口函数（滚动统计）
SELECT symbol, ts, price,
    AVG(price) OVER (PARTITION BY symbol ORDER BY ts ROWS 19 PRECEDING) as sma20
FROM tick_data;
-- CTE 递归查询（树形结构）
WITH RECURSIVE ...
```

## 索引建议速查
| 查询模式 | 索引策略 |
|---------|---------|
| WHERE symbol=? | 单列 B-tree |
| WHERE symbol=? AND time>? | 复合索引 (symbol, time DESC) |
| ORDER BY time DESC LIMIT N | time 上建索引 |
| GROUP BY symbol | 覆盖索引 |
| LIKE 'prefix%' | B-tree（前缀匹配） |

## 慢查询排查
```sql
-- PostgreSQL
SELECT query, calls, total_time, rows
FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;
-- SQLite
EXPLAIN QUERY PLAN SELECT ...;
```

## 数据导入导出
```python
# SQLite → CSV
import csv
c.execute('SELECT * FROM trades')
with open('trades.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow([d[0] for d in c.description])
    w.writerows(c.fetchall())
# CSV → SQLite（用 pandas 更简单）
import pandas as pd
df = pd.read_csv('data.csv')
df.to_sql('table_name', conn, if_exists='append', index=False)
```

## 参考文件

- `references/trading-journal.md` — 交易日志系统的完整 DB 设计、SQL 模式和 CLI 接口。

## 注意事项
- 永远使用参数化查询（`?` 占位符），不要拼接 SQL
- SQLite 不支持并发写，PostgreSQL 适合多连接场景
- 大量 INSERT 用 `executemany` 或事务批量提交
- 敏感信息（密码、连接串）不要硬编码，用环境变量
