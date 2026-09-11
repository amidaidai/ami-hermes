---
name: data-analysis-tools
description: 数据分析技能 — 基于 pandas/numpy/scipy 的数据清洗、统计摘要、时间序列分析、相关性分析、可视化报告生成。适用于交易回测数据、市场数据、日志数据的批量分析场景。
category: data-science
---

# Data Analysis Tools

> 核心库：pandas, numpy, scipy, matplotlib, seaborn, plotly

## 数据导入
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# CSV
df = pd.read_csv('trades.csv', parse_dates=['opened_at'])
# JSON
df = pd.read_json('data.json')
# SQLite
df = pd.read_sql('SELECT * FROM trades', conn)
# Excel
df = pd.read_excel('data.xlsx', sheet_name='Sheet1')
```

## 数据清洗
```python
# 查看基本信息
df.info()
df.describe()
df.isnull().sum()

# 缺失值处理
df.dropna(subset=['price'])                    # 删除
df.fillna({'pnl': 0})                          # 填充
df['sma20'] = df['close'].rolling(20).mean()   # 滚动填充

# 异常值
q1, q3 = df['price'].quantile([0.25, 0.75])
iqr = q3 - q1
df_clean = df[(df['price'] >= q1 - 1.5*iqr) & (df['price'] <= q3 + 1.5*iqr)]

# 类型转换
df['price'] = df['price'].astype(float)
df['ts'] = pd.to_datetime(df['ts'])
df.set_index('ts', inplace=True)
```

## 时间序列分析
```python
# 重采样（OHLCV 聚合）
ohlc = df['close'].resample('1H').ohlc()
volume = df['volume'].resample('1H').sum()

# 滚动窗口
df['sma20'] = df['close'].rolling(20).mean()
df['sma50'] = df['close'].rolling(50).mean()
df['std20'] = df['close'].rolling(20).std()
df['upper'] = df['sma20'] + 2 * df['std20']
df['lower'] = df['sma20'] - 2 * df['std20']

# 日收益率
df['return'] = df['close'].pct_change()
df['log_return'] = np.log(df['close'] / df['close'].shift(1))
```

## 统计分析
```python
# 描述统计
summary = df.groupby('symbol')['pnl'].agg(['count', 'sum', 'mean', 'std'])
summary['win_rate'] = df[df['pnl'] > 0].groupby('symbol').size() / df.groupby('symbol').size()
summary['profit_factor'] = (
    df[df['pnl'] > 0].groupby('symbol')['pnl'].sum() /
    abs(df[df['pnl'] < 0].groupby('symbol')['pnl'].sum())
)

# 相关性
corr = df[['close', 'volume', 'rsi']].corr()
# 滚动相关性
df['corr'] = df['close'].rolling(30).corr(df['volume'])
```

## 可视化模板
```python
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# K 线简化版
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={'height_ratios': [3, 1]})
ax1.plot(df.index, df['close'], label='Close', color='#2962FF')
ax1.plot(df.index, df['sma20'], label='SMA20', alpha=0.7)
ax1.fill_between(df.index, df['upper'], df['lower'], alpha=0.1)
ax1.legend()

ax2.bar(df.index, df['volume'], color=np.where(df['close'].diff() > 0, '#26A69A', '#EF5350'), alpha=0.5)
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
plt.tight_layout()
plt.savefig('chart.png', dpi=150, bbox_inches='tight')
```

## 业绩评估指标
```python
def perf_metrics(df):
    trades = df[df['pnl'].notna()]
    total_return = trades['pnl'].sum()
    win_rate = (trades['pnl'] > 0).mean()
    avg_win = trades[trades['pnl'] > 0]['pnl'].mean()
    avg_loss = abs(trades[trades['pnl'] < 0]['pnl'].mean())
    profit_factor = avg_win / avg_loss if avg_loss != 0 else float('inf')
    sharpe = trades['pnl'].mean() / trades['pnl'].std() * np.sqrt(252) if trades['pnl'].std() != 0 else 0
    max_dd = (trades['pnl'].cumsum().cummax() - trades['pnl'].cumsum()).max()
    return {'total_return': total_return, 'win_rate': win_rate,
            'profit_factor': profit_factor, 'sharpe': sharpe, 'max_dd': max_dd}
```

## 常用快捷方式
```python
# 快速查看 unique 值分布
df['symbol'].value_counts()

# 按条件筛选
df[(df['symbol'] == 'BTCUSDT') & (df['pnl'] > 0)].head()

# 透视表
pd.pivot_table(df, values='pnl', index='symbol', columns='side', aggfunc='sum')

# 导出
df.to_csv('analysis.csv', index=False)
df.to_excel('analysis.xlsx', sheet_name='Results')
```

## 注意事项
- 处理金融时间序列时注意时区（UTC vs 本地）
- 大量数据（>1M rows）考虑用 `polars` 替代 pandas
- matplotlib 中文字体问题：`plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']`
