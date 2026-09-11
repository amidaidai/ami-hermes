#!/usr/bin/env python
"""黄金入场监控 v2 — 双源·日志·冷却·状态自升级
no_agent模式，零token消耗。
用法：cronjob(action='create', no_agent=True, script='gold_monitor.py', schedule='5m', deliver='origin')
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gold_monitor_state.json')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'gold_monitor_events.jsonl')
LOG_FILE = os.path.abspath(LOG_FILE)

BUY_ZONE_LOW = 4315
BUY_ZONE_HIGH = 4323
BREAKOUT_LEVEL = 4330
BREAKDOWN_LEVEL = 4287
COOLDOWN_SECONDS = 600
FUTURES_PREMIUM = 20
MAX_SOURCE_SPREAD = 5
STATE_MAX_AGE = 7 * 86400

PHASES = {
    0: {'name': '初始等待', 'cond': [
        {'id': 'A', 'range': (BUY_ZONE_LOW, BUY_ZONE_HIGH), 'label': '回踩POC做多区间', 'next': 1},
        {'id': 'B', 'min': BREAKOUT_LEVEL, 'label': '突破4330', 'next': 2},
        {'id': 'C', 'max': BREAKDOWN_LEVEL, 'label': '跌破4287结构破坏', 'next': 3},
    ]},
    1: {'name': '回踩确认等待', 'cond': [
        {'id': '1A', 'range': (4315, 4325), 'label': '回踩POC确认做多', 'next': 4, 'needs_confirm': True},
        {'id': '1B', 'min': 4340, 'label': '回踩失败·向上突破', 'next': 2},
        {'id': '1C', 'max': 4300, 'label': '回踩下破转弱', 'next': 3},
    ]},
    2: {'name': '突破后确认', 'cond': [
        {'id': '2A', 'range': (4320, 4330), 'label': '突破后回踩POC确认', 'next': 4, 'needs_confirm': True},
        {'id': '2B', 'min': 4341, 'label': '继续上攻Band2', 'next': 5},
        {'id': '2C', 'max': 4315, 'label': '假突破回撤', 'next': 0},
    ]},
    3: {'name': '空头确认', 'cond': [
        {'id': '3A', 'range': (4260, 4287), 'label': '反弹测试做空区', 'next': 6, 'needs_confirm': True},
        {'id': '3B', 'max': 4255, 'label': '继续下跌破开盘', 'next': 7},
        {'id': '3C', 'min': 4300, 'label': '结构恢复·空失败', 'next': 0},
    ]},
    4: {'name': '持仓做多', 'cond': [
        {'id': '4A', 'min': 4341, 'label': '到达Band2目标', 'next': 5},
        {'id': '4B', 'max': 4305, 'label': '止损线·离场', 'next': 0},
    ]},
    5: {'name': '目标区', 'cond': [
        {'id': '5A', 'min': 4364, 'label': '到达4364目标', 'next': 0},
        {'id': '5B', 'max': 4320, 'label': '回撤过深·平仓', 'next': 0},
    ]},
    6: {'name': '持仓做空', 'cond': [
        {'id': '6A', 'max': 4257, 'label': '到达VAL目标', 'next': 7},
        {'id': '6B', 'min': 4300, 'label': '空头止损·离场', 'next': 0},
    ]},
    7: {'name': '空头目标区', 'cond': [
        {'id': '7A', 'max': 4219, 'label': '到达前低目标', 'next': 0},
        {'id': '7B', 'min': 4280, 'label': '反弹过深·平仓', 'next': 0},
    ]},
}

def now_ts(): return time.time()
def now_str(): return datetime.now().astimezone().isoformat()

def fetch_json(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {'_error': str(e)}

def load_state():
    default = {'phase': 0, 'cooldowns': {}, 'alerts': []}
    if not os.path.exists(STATE_FILE):
        return default
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        state.setdefault('phase', 0); state.setdefault('cooldowns', {}); state.setdefault('alerts', [])
        return state
    except: return default

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=2)

def clean_state(state):
    cutoff = now_ts() - STATE_MAX_AGE
    state['cooldowns'] = {k: v for k, v in state['cooldowns'].items() if v > cutoff}
    state['alerts'] = [a for a in state['alerts'] if a.get('t', 0) > cutoff]

def log_event(event):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except: pass

def get_prices():
    errors = []; spot_primary = spot_secondary = None; volume = 0
    d1 = fetch_json('https://api.gold-api.com/price/XAU')
    if d1 and '_error' not in d1: spot_primary = d1.get('price')
    else: errors.append(f'gold-api: {d1.get("_error", "no data")}')
    d2 = fetch_json('https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=5d')
    if d2 and '_error' not in d2:
        try:
            r = d2['chart']['result'][0]
            fp = r['meta'].get('regularMarketPrice')
            if fp: spot_secondary = fp - FUTURES_PREMIUM
            vols = r.get('indicators',{}).get('quote',[{}])[0].get('volume',[])
            if vols: volume = vols[-1] or 0
        except: pass
    else: errors.append(f'Yahoo: {d2.get("_error", "no data")}')
    return spot_primary, spot_secondary, volume, errors

def resolve_price(sp, ss, errors):
    if sp and ss:
        spread = abs(sp - ss)
        if spread <= MAX_SOURCE_SPREAD: return round((sp+ss)/2,2), 'A', f'gold-api+GC=F(差${spread:.1f})'
        else: return round(sp,2), 'B', f'gold-api(主)·Yahoo偏差${spread:.1f}'
    if sp: return round(sp,2), 'C', 'gold-api单源'
    if ss: return round(ss,2), 'C', 'Yahoo估算单源'
    return None, 'X', f'全源不可用: {"; ".join(errors[:2])}'

def check_conditions(phase, price, state):
    pi = PHASES.get(phase, PHASES[0]); now = now_ts(); triggered = []
    for c in pi['cond']:
        match = False
        if 'range' in c: lo, hi = c['range']; match = lo <= price <= hi
        if 'min' in c and price >= c['min']: match = True
        if 'max' in c and price <= c['max']: match = True
        if not match: continue
        key = f'{phase}_{c["id"]}'
        if now - state['cooldowns'].get(key, 0) < COOLDOWN_SECONDS: continue
        triggered.append((c, key))
    return triggered, pi

def build_message(triggered, pi, price, quality, sn, vol, phase):
    lines = []; first = True; np = None
    for c, key in triggered:
        if first:
            lines.append(f'🔔 黄金信号 [{pi["name"]}]')
            lines.append(f'')
            lines.append(f'现货：`${price:.2f}` · {sn}')
            if vol: lines.append(f'日量：{vol:,}')
            lines.append(f'数据质量：{quality}级')
            lines.append('')
            first = False
        lines.append(f'▶ {c["label"]}')
        n = c.get('next')
        if n is not None and n != phase:
            lines.append(f'  监控升级：阶段{phase}→阶段{n}')
            np = n
    return '\n'.join(lines), np

def main():
    state = load_state(); clean_state(state); phase = state.get('phase', 0)
    sp, ss, vol, errs = get_prices()
    price, qual, sn = resolve_price(sp, ss, errs)
    if price is None:
        log_event({'t':now_str(),'type':'error','price':None,'phase':phase,'errors':errs})
        return
    triggered, pi = check_conditions(phase, price, state)
    if not triggered: return
    for c, key in triggered: state['cooldowns'][key] = now_ts()
    msg, np = build_message(triggered, pi, price, qual, sn, vol, phase)
    if np is not None:
        state['phase'] = np
        state['cooldowns'] = {k:v for k,v in state['cooldowns'].items() if not k.startswith(f'{phase}_')}
    log_event({'t':now_str(),'type':'trigger','price':price,'phase':phase,
        'triggers':[{'id':c['id'],'label':c['label']} for c,_ in triggered],
        'new_phase':np,'quality':qual,'source':sn})
    state['alerts'] = [a for a in (state.get('alerts') or []) if a.get('t',0) > now_ts() - 86400]
    state['alerts'].append({'t':now_ts(),'phase':phase,'triggers':[c['id'] for c,_ in triggered],'price':price})
    state['alerts'] = state['alerts'][-20:]
    save_state(state)
    print(msg)

if __name__ == '__main__':
    main()
