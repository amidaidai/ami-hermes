#!/usr/bin/env python3
"""Dump live TV data to cache for auto_card injection."""
import json
from datetime import datetime, timezone, timedelta
data={
 'timestamp': datetime.now(timezone(timedelta(hours=8))).isoformat(),
 'symbol': 'BINANCE:BTCUSDT.P',
 'fresh': True,
 'action_grid': {
  '结论': 'B空 轻仓',
  '方向': '偏空 · 走弱 · 折价 ⚡纽 扫9/2',
  '进场': '反抽DO 59550.2',
  '止损': '—',
  '目标': '↓上周 低 58030.0',
  '核对': 'HTF✓ EMA✓ CVD✓ 位置✓ 位移✓ 溢折✓ ADR✓ OI⚠多平',
  '磁吸↑': '--',
  '磁吸↓': '上周 低 58030.0 分60 距4.0ATR',
 },
 'poc': 59656.53,
 'vah': 60164.95,
 'val': 59360.94,
 'week_high': 60543.3,
 'week_low': 58888,
 'prev_week_low': 58030,
 'lines': [60758.3, 60543.3, 60325, 60164.95, 59656.53, 59550.2, 59360.94, 58988, 58850, 58030],
}
with open('data/tv_dmi_cache.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('tv_dmi_cache.json refreshed: POC', data['poc'], 'VAH', data['vah'], 'VAL', data['val'])
