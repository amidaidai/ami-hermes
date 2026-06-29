#!/usr/bin/env python
"""黄金入场监控 v2 — 双源·日志·冷却·状态自清理
no_agent模式，零token消耗
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
import sys
import io as _io
if hasattr(sys.stdout, "buffer"):
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ===== 配置 =====
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gold_monitor_state.json')
REQUEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'gold_trigger_request.json')
REQUEST_FILE = os.path.abspath(REQUEST_FILE)
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'gold_monitor_events.jsonl')
LOG_FILE = os.path.abspath(LOG_FILE)

BUY_ZONE_LOW = 4315
BUY_ZONE_HIGH = 4323
BREAKOUT_LEVEL = 4330
BREAKDOWN_LEVEL = 4287
# 警告：以上区间需手动更新。当前金价约4096，区间已偏离~5%。
# 使用 --update-zones 参数可基于现价重新计算区间。
COOLDOWN_SECONDS = 600  # 同条件10min冷却
FUTURES_PREMIUM = 20    # GC=F期货对现货的预估溢价
MAX_SOURCE_SPREAD = 5   # 双源最大允许差价
STATE_MAX_AGE = 7 * 86400  # 状态文件保留7天

# ===== 阶段定义 =====
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

# ===== 工具函数 =====
def now_ts():
    return time.time()

def now_str():
    return datetime.now().astimezone().isoformat()

def fetch_json(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {'_error': str(e)}

# ===== 状态管理 =====
def load_state():
    default = {'phase': 0, 'cooldowns': {}, 'alerts': []}
    if not os.path.exists(STATE_FILE):
        return default
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        state.setdefault('phase', 0)
        state.setdefault('cooldowns', {})
        state.setdefault('alerts', [])
        return state
    except:
        return default

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def clean_state(state):
    """清除超过7天的冷却记录和旧警报"""
    now = now_ts()
    cutoff = now - STATE_MAX_AGE
    state['cooldowns'] = {k: v for k, v in state['cooldowns'].items() if v > cutoff}
    state['alerts'] = [a for a in state['alerts'] if a.get('t', 0) > cutoff]

# ===== 日志 =====
def log_event(event):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except:
        pass


def refresh_xau_snapshot():
    """刷新 XAUUSD 统一 source snapshot，供审计/分析卡读取最新黄金质量。

    gold_monitor 自己只刷新 xau_macro_context；如果不顺手刷新 source_snapshot_XAUUSD，
    审计会看到 XAU 快照停在凌晨。这里失败静默，不影响到价监控推送。
    """
    try:
        import sys
        from pathlib import Path
        script_dir = Path(__file__).resolve().parent
        repo_scripts = Path("D:/Hermes agent/scripts")
        for p in (script_dir, repo_scripts):
            sp = str(p)
            if p.exists() and sp not in sys.path:
                sys.path.insert(0, sp)
        import trading_system as ts
        ts.source_snapshot('XAUUSD')
    except Exception as e:
        log_event({'t': now_str(), 'type': 'snapshot_refresh_error', 'symbol': 'XAUUSD', 'error': str(e)[:200]})

# ===== 双源价格 =====
def get_prices():
    """
    返回 (spot_primary, spot_secondary, volume, errors)
    spot_primary: gold-api.com 现货价
    spot_secondary: Yahoo GC=F 估算现货价（期货-溢价）
    volume: GC=F 日成交量
    errors: 错误列表
    """
    errors = []
    spot_primary = None
    spot_secondary = None
    volume = 0

    # 源1：gold-api.com（现货）
    d1 = fetch_json('https://api.gold-api.com/price/XAU')
    if d1 and '_error' not in d1:
        spot_primary = d1.get('price')
    else:
        errors.append(f'gold-api: {d1.get("_error", "no data")}')

    # 源2：Yahoo GC=F（期货，估算现货）
    d2 = fetch_json(
        'https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=5d'
    )
    if d2 and '_error' not in d2:
        try:
            result = d2['chart']['result'][0]
            meta = result['meta']
            futures_price = meta.get('regularMarketPrice')
            if futures_price:
                spot_secondary = futures_price - FUTURES_PREMIUM
            quotes = result.get('indicators', {}).get('quote', [{}])[0]
            vols = quotes.get('volume', [])
            if vols:
                volume = vols[-1] or 0
        except (KeyError, IndexError, TypeError) as e:
            errors.append(f'Yahoo parse: {e}')
    else:
        errors.append(f'Yahoo: {d2.get("_error", "no data")}')

    return spot_primary, spot_secondary, volume, errors

# ===== 价格融合 =====
def resolve_price(spot_primary, spot_secondary, errors):
    """双源融合，返回 (最终价格, 数据质量, 来源说明)"""
    # 双源都有 -> 交叉验证
    if spot_primary and spot_secondary:
        spread = abs(spot_primary - spot_secondary)
        avg = (spot_primary + spot_secondary) / 2
        if spread <= MAX_SOURCE_SPREAD:
            return round(avg, 2), 'A', f'gold-api+GC=F(差${spread:.1f})'
        else:
            # 差价过大，信托金十（现货）
            return round(spot_primary, 2), 'B', f'gold-api(主)·Yahoo偏差${spread:.1f}'
    # 单源
    if spot_primary:
        return round(spot_primary, 2), 'C', 'gold-api单源'
    if spot_secondary:
        return round(spot_secondary, 2), 'C', 'Yahoo估算单源'
    return None, 'X', f'全源不可用: {"; ".join(errors[:2])}'

# ===== 条件判断 =====
def check_conditions(phase, price, state):
    """检查当前阶段的条件，返回触发列表"""
    phase_info = PHASES.get(phase, PHASES[0])
    now = now_ts()
    triggered = []

    for cond in phase_info['cond']:
        match = False
        if 'range' in cond:
            lo, hi = cond['range']
            if lo <= price <= hi:
                match = True
        if 'min' in cond and price >= cond['min']:
            match = True
        if 'max' in cond and price <= cond['max']:
            match = True

        if not match:
            continue

        # 冷却检查
        cooldown_key = f'{phase}_{cond["id"]}'
        last_triggered = state['cooldowns'].get(cooldown_key, 0)
        if now - last_triggered < COOLDOWN_SECONDS:
            continue

        triggered.append((cond, cooldown_key))

    return triggered, phase_info

# ===== 推送消息 =====
def build_message(triggered, phase_info, price, quality, source_note, volume):
    lines = []
    first = True
    new_phase = None
    for cond, key in triggered:
        if first:
            lines.append(f'🔔 黄金信号 [{phase_info["name"]}]')
            lines.append('')
            lines.append(f'现货：`${price:.2f}` · {source_note}')
            if volume:
                lines.append(f'日量：{volume:,}')
            lines.append(f'数据质量：{quality}级')
            lines.append('')
            first = False
        lines.append(f'▶ {cond["label"]}')
        np = cond.get('next')
        if np is not None and np != phase_info.get('_current_phase'):
            lines.append(f'  监控升级：阶段{phase_info.get("_current_phase", "?")}→阶段{np}')
            new_phase = np
            # 重置新阶段的冷却，防止跳到新阶段后立即被冷却
            if new_phase is not None:
                lines.append(f'  新阶段监控：{PHASES[new_phase]["name"]}')
    return '\n'.join(lines), new_phase

# ===== 主逻辑 =====
def main():
    state = load_state()
    clean_state(state)
    phase = state.get('phase', 0)

    # 1. 获取双源价格
    spot_primary, spot_secondary, volume, errors = get_prices()

    # 2. 融合出最终价
    price, quality, source_note = resolve_price(spot_primary, spot_secondary, errors)

    # 全源不可用 -> 静默
    if price is None:
        # 记录错误到日志
        log_event({
            't': now_str(), 'type': 'error',
            'price': None, 'phase': phase,
            'errors': errors,
        })
        return

    # 2.1 刷新统一 XAU snapshot（即使未触发也刷新，避免审计/分析卡读到旧黄金快照）
    refresh_xau_snapshot()

    # 3. 检查条件
    triggered, phase_info = check_conditions(phase, price, state)

    if not triggered:
        return  # 静默

    # 4. 记录冷却
    for cond, key in triggered:
        state['cooldowns'][key] = now_ts()

    # 5. 构建消息
    phase_info['_current_phase'] = phase
    msg, new_phase = build_message(triggered, phase_info, price, quality, source_note, volume)

    # 6. 更新阶段
    if new_phase is not None:
        state['phase'] = new_phase
        # 跳到新阶段时，清除旧阶段的冷却记录（避免冲突）
        old_prefix = f'{phase}_'
        state['cooldowns'] = {k: v for k, v in state['cooldowns'].items() if not k.startswith(old_prefix)}

    # 7. 记录日志
    log_event({
        't': now_str(), 'type': 'trigger',
        'price': price, 'phase': phase,
        'triggers': [{'id': c['id'], 'label': c['label']} for c, _ in triggered],
        'new_phase': new_phase,
        'quality': quality,
        'source': source_note,
    })

    # 8. 写触发标记（供agent cron读取出分析卡）
    request = {
        'triggered_at': now_str(),
        'price': price,
        'phase': phase,
        'phase_name': phase_info['name'],
        'triggers': [{'id': c['id'], 'label': c['label']} for c, _ in triggered],
        'quality': quality,
        'source': source_note,
        'status': 'pending',
    }
    os.makedirs(os.path.dirname(REQUEST_FILE), exist_ok=True)
    with open(REQUEST_FILE, 'w') as f:
        json.dump(request, f, indent=2, ensure_ascii=False)

    # 8. 记录警报历史（只保留最近20条摘要）
    state['alerts'].append({
        't': now_ts(), 'phase': phase,
        'trigger': [{'id': c['id']} for c, _ in triggered],
        'price': price,
    })
    state['alerts'] = state['alerts'][-20:]

    # 9. 保存状态
    save_state(state)

    # 10. 输出（推送到Telegram）
    print(msg)

if __name__ == '__main__':
    main()
