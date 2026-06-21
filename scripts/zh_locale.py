#!/usr/bin/env python3
"""
系统进化 v7.5 · 中文本地化 + TV截图 + 话题路由 + 每日学习

用法:
  from zh_locale import T, CARD_ZH, ALERT_ZH
  print(T("买入信号", "BTCUSDT"))  # → 中文标注
"""

# ═══════════════ 中文本地化字典 ═══════════════

# 方向/状态
DIR_ZH = {"long": "做多", "short": "做空", "wait": "观望"}
STATUS_ZH = {"A做多": "A做多", "A做空": "A做空", "B等待": "B等待", "X禁做": "X禁做", "C等待": "C等待"}

# 市场阶段
PHASE_ZH = {
    "Trend": "趋势", "Breakout": "突破", "Reversal": "反转",
    "Consolidation": "盘整", "Range": "区间", "Pullback": "回撤"
}

# 技术术语（保留英文缩写，补充中文说明）
TECH_ZH = {
    "VWAP": "量价均值", "EMA": "指数均线", "CVD": "累积成交量差",
    "ATR": "平均真实波幅", "RSI": "相对强弱", "MACD": "异同均线",
    "POC": "成交量控制点", "VAH": "价值区上沿", "VAL": "价值区下沿",
    "DMI": "方向运动", "FVG": "公允价值缺口", "OB": "订单块",
    "BSL": "买方流动性", "SSL": "卖方流动性",
    "SMT": "聪明钱陷阱", "MSS": "市场结构转变",
}

# 分析卡标签
CARD_LABELS = {
    "price": "现价", "high": "最高", "low": "最低", "open": "开盘", "close": "收盘",
    "volume": "量", "change": "涨跌", "range": "振幅",
    "support": "支撑", "resistance": "阻力", "level": "关键位",
    "entry": "入场", "stop": "止损", "target": "止盈", "exit": "出场",
    "risk": "风险", "reward": "回报", "R:R": "盈亏比",
    "direction": "方向", "bias": "偏", "confidence": "置信度",
    "funding": "资金费率", "premium": "溢价",
}

# Kill Zone 中文
KILL_ZONE_ZH = {
    "Asia Kill Zone 活跃": "亚洲盘活跃",
    "London Kill Zone 活跃": "伦敦盘活跃",
    "NY AM Kill Zone 活跃": "纽约上午盘活跃",
    "NY PM Kill Zone 活跃": "纽约下午盘活跃",
    "非Kill Zone · 低流动性": "非主盘·低流动性",
    "非Kill Zone": "非主盘",
}

# 策略描述
STRATEGY_ZH = {
    "crypto_entry": (
        "加密现货vs永续无分裂 · CVD/Taker顺向 · Funding/OI无拥堵 · "
        "突破接受需无背离 · 扫荡后出现Displacement确认"
    ),
    "xau_entry": (
        "London/NY Kill Zone优先 · DXY/美债不反向 · "
        "扫荡后出现Displacement确认 · 结构位+EMA排列+量确认"
    ),
    "crypto_risk": "Funding/OI拥堵降仓 · 逐仓优先 · 强制止损不撤",
    "crypto_exit": "复核CVD/Taker/OI续航 · +1.5R移保本 · Funding异常立即降仓",
    "xau_exit": "复核Kill Zone是否结束 · DXY/美债是否反向 · 扫荡点是否被重新接受",
}

# 时间框架标签
TF_LABELS = {
    "1m": "1分钟", "5m": "5分钟", "15m": "15分钟",
    "1h": "1小时", "4h": "4小时", "1d": "日线", "1w": "周线",
}

# 品种标签
SYMBOL_ZH = {
    "BTCUSDT": "比特币",
    "XAUUSD": "黄金",
    "ETHUSDT": "以太坊",
    "SOLUSDT": "Solana",
}

def T(key: str, *args) -> str:
    """翻译单个标签。"""
    for d in [DIR_ZH, CARD_LABELS, KILL_ZONE_ZH, TECH_ZH, SYMBOL_ZH, TF_LABELS]:
        if key in d:
            return d[key]
    return key

def asset_name(symbol: str) -> str:
    """品种中文名。"""
    return SYMBOL_ZH.get(symbol, symbol)

def timeframe_cn(tf: str) -> str:
    """时间框架中文。"""
    return TF_LABELS.get(tf, tf)

def direction_cn(d: str) -> str:
    """方向中文。"""
    return DIR_ZH.get(d, d)

def kill_zone_cn(en: str) -> str:
    """Kill Zone中文。"""
    for key, cn in KILL_ZONE_ZH.items():
        if key in en:
            return cn
    return en
