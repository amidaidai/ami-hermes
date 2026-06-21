#!/usr/bin/env python3
"""
棠溪 · 风险宪法 v1.0
融合: trading-scanner (NadirAliOfficial) 风险宪法 + Kelly仓位 + 连续亏损熔断

宪法规则（融合 trading-scanner Risk Constitution）:
  1. 单笔最大风险 ≤ 3% 本金（自适应Kelly）
  2. 日回撤 ≥ 5% → 当天暂停交易
  3. 周回撤 ≥ 10% → 本周暂停交易
  4. 连续亏损 ≥ 3 笔 → 暂停扫描 + 人工复盘
  5. 新闻黑窗期：重大事件前60m + 后30m 禁做
  6. 未复盘交易 > 0 → 最高轻仓
  7. 事件禁做(volatility spike) → BTC>5%, XAU>1%
"""

import json, os, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass, field

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
DATA_DIR = ROOT / "data"

# ═══ 宪法常量（可调 · v2.0 社区2026共识值） ═══
# 源：Freqtrade Protections + X/Reddit 1%黄金标准 + NautilusTrader pre-trade
CONSTITUTION = {
    "MAX_RISK_PER_TRADE_PCT": 0.01,        # 单笔最大 1% 本金（社区2026共识：0.5-1%）
    "MAX_DAILY_DRAWDOWN_PCT": 0.05,        # 日回撤 5% 暂停（默认保守模式）
    "MAX_DAILY_DRAWDOWN_PCT_AGGRESSIVE": 0.05,  # 激进模式 5%
    "MAX_DAILY_DRAWDOWN_PCT_CONSERVATIVE": 0.02,  # 保守模式 2%（Reddit共识）
    "DRAWDOWN_MODE": "conservative",       # conservative(2%) / aggressive(5%)
    "MAX_WEEKLY_DRAWDOWN_PCT": 0.10,       # 周回撤 10% 暂停
    "MAX_CONSECUTIVE_LOSSES": 3,           # 连续亏损 3 笔暂停
    "NEWS_BLOCK_MINUTES_BEFORE": 60,       # 新闻前60m禁做
    "NEWS_BLOCK_MINUTES_AFTER": 30,        # 新闻后30m禁做
    "KELLY_FRACTION": 0.20,               # Kelly分数 (保守=0.20, v2.0更保守)
    "VOLATILITY_BAN_BTC": 0.05,            # BTC波动>5%禁做
    "VOLATILITY_BAN_XAU": 0.01,            # XAU波动>1%禁做
    "REQUIRED_RR_RATIO": 2.0,              # R:R底线 1:2
    "MIN_STOP_ATR_RATIO": 0.5,             # 止损 ≥ 0.5×ATR（下限）
    "MAX_STOP_ATR_RATIO": 2.5,             # 止损 ≤ 2.5×ATR（上限·v2.0新增·防风险过大）
    # Freqtrade-style Protections（v2.0 社区增强）
    "STOPLOSS_GUARD_LOOKBACK": 12,         # 止损后12根K线冷却（防复仇）
    "COOLDOWN_AFTER_LOSS": 3,              # 亏损后3根K线暂停
    "MAX_DAILY_DRAWDOWN_HARD": 0.10,       # 日回撤10%全停·不可恢复（社区共识）
    "MAX_WEEKLY_DRAWDOWN_HARD": 0.15,      # 周回撤15%全停（社区共识）
    # 交易频率与冷却
    "MAX_TRADES_PER_DAY": 10,              # 每日最大交易次数
    "TRADE_COOLDOWN_MINUTES": 15,          # 止损后冷却时间（分钟）
    # Volatility Targeting（3Commas 2025指南）
    "VOLATILITY_TARGET_BASE": 0.02,        # 基准波动率2%
    "VOLATILITY_TARGET_MIN_MULT": 0.3,     # 高波动最低仓位倍数（不减到0）
    "VOLATILITY_TARGET_MAX_MULT": 1.5,     # 低波动最大仓位倍数
    "BB_WIDTH_VOLATILE": 0.03,             # BB宽度>3%判定为高波动
    "BB_WIDTH_CALM": 0.01,                 # BB宽度<1%判定为低波动
}


@dataclass
class RiskState:
    """风险状态跟踪"""
    date: str = field(default_factory=lambda: datetime.now(TZ).strftime("%Y-%m-%d"))
    daily_realized_pnl: float = 0.0
    daily_starting_balance: float = 100.0
    weekly_realized_pnl: float = 0.0
    weekly_starting_balance: float = 100.0
    trades_count: int = 0
    loss_streak: int = 0
    max_loss_streak: int = 0
    unreviewed_trade_count: int = 0
    suspended: bool = False
    suspend_reason: str = ""
    # 社区建议增强: 交易频率 + 冷却
    trades_today: int = 0
    last_loss_time: Optional[str] = None  # ISO格式时间戳


def load_risk_state() -> RiskState:
    """从 risk_state.json 加载"""
    path = DATA_DIR / "risk_state.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return RiskState(**{k: v for k, v in data.items() if k in RiskState.__dataclass_fields__})
        except Exception:
            pass
    return RiskState()


def save_risk_state(state: RiskState):
    """保存到 risk_state.json"""
    path = DATA_DIR / "risk_state.json"
    path.write_text(json.dumps(state.__dict__, indent=2, ensure_ascii=False), encoding="utf-8")


def kelly_position_size(win_rate: float, avg_win_r: float, avg_loss_r: float,
                         account_balance: float, fraction: float = None) -> dict:
    """
    Kelly仓位计算
    
    Kelly公式: f* = (p * W - (1-p) * L) / (W * L)
    其中 p=胜率, W=平均盈利(R), L=平均亏损(|R|)
    
    返回 Kelly分数 和 建议风险金额
    """
    if fraction is None:
        fraction = CONSTITUTION["KELLY_FRACTION"]
    
    if win_rate <= 0 or avg_win_r <= 0 or avg_loss_r <= 0:
        # 无统计数据 → 默认保守
        return {
            "kelly_fraction": fraction,
            "kelly_raw": 0,
            "suggested_risk_pct": CONSTITUTION["MAX_RISK_PER_TRADE_PCT"],
            "suggested_risk_usd": round(account_balance * CONSTITUTION["MAX_RISK_PER_TRADE_PCT"], 2),
            "method": "保守默认·样本不足"
        }
    
    # Kelly公式
    L = abs(avg_loss_r)
    kelly_raw = (win_rate * avg_win_r - (1 - win_rate) * L) / (avg_win_r * L)
    kelly_safe = max(0, min(kelly_raw * fraction, CONSTITUTION["MAX_RISK_PER_TRADE_PCT"]))
    
    return {
        "kelly_fraction": fraction,
        "kelly_raw": round(kelly_raw, 3),
        "suggested_risk_pct": round(kelly_safe * 100, 2),
        "suggested_risk_usd": round(account_balance * kelly_safe, 2),
        "method": f"Kelly×{fraction}" if kelly_raw > 0 else "Kelly≤0·保守默认"
    }


def check_constitution(symbol: str,
                        risk_usd: float = 3.0,
                        account_balance: float = 100.0,
                        entry_price: Optional[float] = None,
                        stop_price: Optional[float] = None,
                        target1_price: Optional[float] = None,
                        atr_value: Optional[float] = None,
                        state: Optional[RiskState] = None,
                        volatility_24h_pct: float = 0.0,
                        has_major_news: bool = False) -> dict:
    """
    风险宪法检查 · 全维度
    
    Returns:
        {
            "allowed": bool,
            "reasons": [...],       # 允许/拒绝原因
            "violations": [...],    # 违规项
            "risk_tier": str,       # 常规/轻仓/半仓/禁止
            "max_risk_usd": float,
            "cooldown_minutes": int,
        }
    """
    if state is None:
        state = load_risk_state()
    
    reasons = []
    violations = []
    
    # ═══ 检查1: 单笔风险 ≤ 3% 本金 ═══
    risk_pct = risk_usd / account_balance if account_balance > 0 else 1.0
    if risk_pct > CONSTITUTION["MAX_RISK_PER_TRADE_PCT"] + 0.001:
        violations.append(f"单笔风险 {risk_pct:.1%} > {CONSTITUTION['MAX_RISK_PER_TRADE_PCT']:.0%} 上限")
    else:
        reasons.append(f"单笔风险 {risk_pct:.1%} ✓")
    
    # ═══ 检查2: R:R 底线 1:2 ═══
    if entry_price and stop_price and target1_price:
        risk = abs(entry_price - stop_price)
        reward = abs(target1_price - entry_price)
        if risk > 0:
            rr = reward / risk
            if rr < CONSTITUTION["REQUIRED_RR_RATIO"]:
                violations.append(f"R:R {rr:.1f}:1 < {CONSTITUTION['REQUIRED_RR_RATIO']}:1 底线")
            else:
                reasons.append(f"R:R {rr:.1f}:1 ✓")
    
    # ═══ 检查3: 止损夹层 — 0.5×ATR ≤ 止损距离 ≤ 2.5×ATR ═══
    if entry_price and stop_price and atr_value:
        stop_distance = abs(entry_price - stop_price)
        if stop_distance < CONSTITUTION["MIN_STOP_ATR_RATIO"] * atr_value:
            violations.append(f"止损{stop_distance:.0f} < {CONSTITUTION['MIN_STOP_ATR_RATIO']:.1f}×ATR{atr_value:.0f}·噪音止损风险")
        if stop_distance > CONSTITUTION["MAX_STOP_ATR_RATIO"] * atr_value:
            violations.append(f"止损{stop_distance:.0f} > {CONSTITUTION['MAX_STOP_ATR_RATIO']:.1f}×ATR{atr_value:.0f}·风险过大")
    
    # ═══ 检查4: 日回撤熔断 · P2-8 可配置模式 ═══
    if state and state.daily_starting_balance > 0:
        daily_drawdown = -state.daily_realized_pnl / state.daily_starting_balance
        # P2-8: 动态选择日回撤阈值 (conservative=2% / aggressive=5%)
        mode = CONSTITUTION.get("DRAWDOWN_MODE", "conservative")
        if mode == "aggressive":
            dd_limit = CONSTITUTION["MAX_DAILY_DRAWDOWN_PCT_AGGRESSIVE"]
        else:
            dd_limit = CONSTITUTION["MAX_DAILY_DRAWDOWN_PCT_CONSERVATIVE"]
        if daily_drawdown >= dd_limit:
            violations.append(f"日回撤 {daily_drawdown:.1%} ≥ {dd_limit:.0%} 熔断({mode}模式)")
    
    # ═══ 检查5: 周回撤 ≥ 10% → 暂停 ═══
    if state and state.weekly_starting_balance > 0:
        weekly_drawdown = -state.weekly_realized_pnl / state.weekly_starting_balance
        if weekly_drawdown >= CONSTITUTION["MAX_WEEKLY_DRAWDOWN_PCT"]:
            violations.append(f"周回撤 {weekly_drawdown:.1%} ≥ {CONSTITUTION['MAX_WEEKLY_DRAWDOWN_PCT']:.0%} 熔断")
    
    # ═══ 检查6: 连续亏损 ≥ 3 → 暂停 ═══
    if state and state.loss_streak >= CONSTITUTION["MAX_CONSECUTIVE_LOSSES"]:
        violations.append(f"连续 {state.loss_streak} 亏损 ≥ {CONSTITUTION['MAX_CONSECUTIVE_LOSSES']} 暂停")
    
    # ═══ 检查7: 波动率禁做 ═══
    if "BTC" in symbol or "ETH" in symbol:
        if volatility_24h_pct >= CONSTITUTION["VOLATILITY_BAN_BTC"]:
            violations.append(f"24h波动 {volatility_24h_pct:.1%} ≥ {CONSTITUTION['VOLATILITY_BAN_BTC']:.0%} BTC波动禁做")
    elif "XAU" in symbol.upper():
        if volatility_24h_pct >= CONSTITUTION["VOLATILITY_BAN_XAU"]:
            violations.append(f"24h波动 {volatility_24h_pct:.1%} ≥ {CONSTITUTION['VOLATILITY_BAN_XAU']:.0%} XAU波动禁做")
    
    # ═══ 检查8: 新闻黑窗期 ═══
    if has_major_news:
        violations.append(f"新闻黑窗期 · 前{CONSTITUTION['NEWS_BLOCK_MINUTES_BEFORE']}分+后{CONSTITUTION['NEWS_BLOCK_MINUTES_AFTER']}分禁做")
    
    # ═══ 检查9: 未复盘交易 → 轻仓 ═══
    if state and state.unreviewed_trade_count > 0:
        reasons.append(f"⚠ {state.unreviewed_trade_count}笔未复盘·最高轻仓")
    
    # ═══ 检查10: 交易频率上限（3Commas建议: max 10/day） ═══
    if state and state.trades_today >= CONSTITUTION["MAX_TRADES_PER_DAY"]:
        violations.append(f"今日已交易{state.trades_today}次 ≥ {CONSTITUTION['MAX_TRADES_PER_DAY']}次上限")
    
    # ═══ 检查11: 止损后冷却（3Commas建议: cooldown timer） ═══
    if state and state.last_loss_time:
        try:
            last_loss = datetime.fromisoformat(str(state.last_loss_time).replace("Z", "+00:00")).astimezone(TZ)
            cooldown_min = CONSTITUTION["TRADE_COOLDOWN_MINUTES"]
            elapsed = (datetime.now(TZ) - last_loss).total_seconds() / 60
            if elapsed < cooldown_min:
                remaining = cooldown_min - elapsed
                violations.append(f"止损冷却中·剩余{remaining:.0f}分")
        except (ValueError, TypeError):
            pass
    
    # ═══ 判定 ═══
    has_hard_violation = any(v for v in violations if "熔断" in v or "暂停" in v or "禁做" in v or "黑窗" in v or "上限" in v or "冷却" in v)
    
    if has_hard_violation:
        allowed = False
        risk_tier = "禁止"
        max_risk_usd = 0
    elif violations:
        allowed = True
        risk_tier = "轻仓"
        max_risk_usd = min(risk_usd, account_balance * 0.015)
    elif state and state.unreviewed_trade_count > 0:
        allowed = True
        risk_tier = "轻仓"
        max_risk_usd = min(risk_usd, account_balance * 0.02)
    else:
        allowed = True
        risk_tier = "常规"
        max_risk_usd = min(risk_usd, account_balance * CONSTITUTION["MAX_RISK_PER_TRADE_PCT"])
    
    reasons = [r for r in reasons if not r.startswith("⚠")]  # 清理警告
    
    return {
        "allowed": allowed,
        "reasons": reasons,
        "violations": violations,
        "risk_tier": risk_tier,
        "max_risk_usd": round(max_risk_usd, 2),
        "cooldown_minutes": 60 if has_hard_violation else 0,
    }


# ═══ Freqtrade-style Protections v2.0（社区2026共识） ═══

@dataclass
class Protections:
    """Freqtrade-style 自动防护层 — StoplossGuard + Cooldown + MaxDrawdown"""
    # StoplossGuard: 止损后N根K线内不重入同品种
    stoploss_guard: dict = field(default_factory=lambda: {})  # {symbol: last_stoploss_bar}
    stoploss_guard_lookback: int = 12  # 默认12根K线
    
    # CooldownPeriod: 亏损后N根K线暂停
    cooldown_active: bool = False
    cooldown_bars_remaining: int = 0
    cooldown_after_loss: int = 3  # 默认3根K线
    
    # MaxDrawdown: 硬上限熔断
    daily_drawdown_pct: float = 0.0
    max_daily_drawdown_hard: float = 0.10
    weekly_drawdown_pct: float = 0.0
    max_weekly_drawdown_hard: float = 0.15
    
    # State
    suspended: bool = False
    suspend_reason: str = ""
    
    def check_stoploss_guard(self, symbol: str, current_bar: int) -> tuple[bool, str]:
        """止损守卫：止损后N根K线内禁止同品种再入场"""
        last = self.stoploss_guard.get(symbol.upper())
        if last is not None and (current_bar - last) < self.stoploss_guard_lookback:
            remaining = self.stoploss_guard_lookback - (current_bar - last)
            return False, f"StoplossGuard: {symbol}止损后冷却中·还需{remaining}根K线"
        return True, ""
    
    def check_cooldown(self) -> tuple[bool, str]:
        """冷却检查：亏损后N根K线内暂停所有交易"""
        if self.cooldown_active and self.cooldown_bars_remaining > 0:
            return False, f"CooldownPeriod: 亏损冷却中·还需{self.cooldown_bars_remaining}根K线"
        return True, ""
    
    def check_max_drawdown(self) -> tuple[bool, str]:
        """最大回撤硬熔断"""
        if self.daily_drawdown_pct >= self.max_daily_drawdown_hard:
            return False, f"MaxDrawdown: 日回撤{self.daily_drawdown_pct:.1%} ≥ {self.max_daily_drawdown_hard:.0%}·全停"
        if self.weekly_drawdown_pct >= self.max_weekly_drawdown_hard:
            return False, f"MaxDrawdown: 周回撤{self.weekly_drawdown_pct:.1%} ≥ {self.max_weekly_drawdown_hard:.0%}·全停"
        return True, ""
    
    def on_stoploss(self, symbol: str, current_bar: int):
        """止损触发时记录"""
        self.stoploss_guard[symbol.upper()] = current_bar
    
    def on_loss(self, current_bar: int):
        """亏损触发时启动冷却"""
        self.cooldown_active = True
        self.cooldown_bars_remaining = self.cooldown_after_loss
        self.stoploss_guard["_last_loss_bar"] = current_bar
    
    def advance_bar(self):
        """每根新K线推进所有计时器"""
        if self.cooldown_active and self.cooldown_bars_remaining > 0:
            self.cooldown_bars_remaining -= 1
            if self.cooldown_bars_remaining <= 0:
                self.cooldown_active = False
    
    def to_dict(self) -> dict:
        """序列化为可 JSON 持久化的 dict"""
        return {
            "stoploss_guard": self.stoploss_guard,
            "stoploss_guard_lookback": self.stoploss_guard_lookback,
            "cooldown_active": self.cooldown_active,
            "cooldown_bars_remaining": self.cooldown_bars_remaining,
            "cooldown_after_loss": self.cooldown_after_loss,
            "daily_drawdown_pct": self.daily_drawdown_pct,
            "max_daily_drawdown_hard": self.max_daily_drawdown_hard,
            "weekly_drawdown_pct": self.weekly_drawdown_pct,
            "max_weekly_drawdown_hard": self.max_weekly_drawdown_hard,
            "suspended": self.suspended,
            "suspend_reason": self.suspend_reason,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Protections":
        """从 dict 恢复 Protections 实例"""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
    
    def check_all(self, symbol: str, current_bar: int) -> tuple[bool, list[str]]:
        """全量检查所有防护层，返回 (通过?, [违规原因])"""
        violations = []
        
        ok, reason = self.check_max_drawdown()
        if not ok:
            violations.append(reason)
            self.suspended = True
            self.suspend_reason = reason
            return False, violations
        
        ok, reason = self.check_cooldown()
        if not ok:
            violations.append(reason)
        
        ok2, reason2 = self.check_stoploss_guard(symbol, current_bar)
        if not ok2:
            violations.append(reason2)
        
        return len(violations) == 0, violations


def apply_protections(symbol: str, current_bar: int = None,
                      protections: Protections = None) -> dict:
    """便捷入口：Protections.check_all() 的 dict 返回"""
    if protections is None:
        return {"passed": True, "violations": [], "suspended": False, "reason": ""}
    
    if current_bar is None:
        from datetime import datetime
        current_bar = int(datetime.now().timestamp() // 300)  # 5m bar proxy
    
    passed, violations = protections.check_all(symbol, current_bar)
    
    return {
        "passed": passed,
        "violations": violations,
        "suspended": protections.suspended,
        "reason": protections.suspend_reason if protections.suspended else "",
    }


_PROTECTIONS_FILE = DATA_DIR / "protections_state.json"

def load_protections() -> Protections:
    """从磁盘加载 Protections 状态（监控重启不丢失）"""
    if _PROTECTIONS_FILE.exists():
        try:
            data = json.loads(_PROTECTIONS_FILE.read_text(encoding="utf-8"))
            return Protections.from_dict(data)
        except Exception:
            pass
    return Protections()


def save_protections(p: Protections):
    """持久化 Protections 状态到磁盘"""
    _PROTECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PROTECTIONS_FILE.write_text(json.dumps(p.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


# ═══ Volatility Targeting (3Commas 2025指南) ═══

def volatility_target_multiplier(current_volatility: float, base_volatility: float = None) -> dict:
    """
    波动率目标仓位调节器
    
    概念(3Commas): 高波动减仓·低波动加仓·保持每笔风险贡献相等
    公式: multiplier = base_vol / current_vol (clamped)
    
    Args:
        current_volatility: 当前波动率(如ATR%或BB宽度)
        base_volatility: 基准波动率, 默认2%
    
    Returns:
        {"multiplier": float, "adjusted_risk_pct": float, "regime": str, "reason": str}
    """
    if base_volatility is None:
        base_volatility = CONSTITUTION["VOLATILITY_TARGET_BASE"]
    
    if current_volatility <= 0:
        return {"multiplier": 1.0, "adjusted_risk_pct": 0.03, "regime": "未知", "reason": "波动率为0·默认仓位"}
    
    # 仓位倍数 = 基准波动 / 当前波动
    raw_mult = base_volatility / current_volatility
    min_mult = CONSTITUTION["VOLATILITY_TARGET_MIN_MULT"]
    max_mult = CONSTITUTION["VOLATILITY_TARGET_MAX_MULT"]
    multiplier = max(min_mult, min(max_mult, raw_mult))
    
    # 波动率体制
    if current_volatility >= CONSTITUTION["BB_WIDTH_VOLATILE"]:
        regime = "高波动"
    elif current_volatility <= CONSTITUTION["BB_WIDTH_CALM"]:
        regime = "低波动"
    else:
        regime = "正常"
    
    adjusted_risk = CONSTITUTION["MAX_RISK_PER_TRADE_PCT"] * multiplier
    
    return {
        "multiplier": round(multiplier, 2),
        "adjusted_risk_pct": round(adjusted_risk, 4),
        "regime": regime,
        "reason": f"{regime}({current_volatility:.2%}) → 仓位×{multiplier:.2f} 风险{adjusted_risk:.2%}",
    }


def real_time_volatility_filter(closes: list[float], period: int = 20) -> dict:
    """
    实时波动率过滤器 (3Commas建议: BB width作为实时波动代理)
    
    使用Bollinger Band宽度作为波动率代理:
    BB_width = (upper_band - lower_band) / middle_band
    
    Returns:
        {"bb_width": float, "volatility_regime": str, "should_reduce_size": bool, "should_delay_entry": bool}
    """
    n = len(closes)
    if n < period:
        return {"bb_width": 0.0, "volatility_regime": "数据不足", "should_reduce_size": False, "should_delay_entry": False}
    
    # 计算SMA和标准差
    recent = closes[-period:]
    sma = sum(recent) / period
    variance = sum((x - sma) ** 2 for x in recent) / period
    std = variance ** 0.5
    
    # BB宽度 = 2 * std / sma
    bb_width = (2 * std / sma) if sma > 0 else 0.0
    
    # 波动率体制判定
    if bb_width >= CONSTITUTION["BB_WIDTH_VOLATILE"]:
        regime = "高波动"
        should_reduce = True
        should_delay = True
    elif bb_width <= CONSTITUTION["BB_WIDTH_CALM"]:
        regime = "低波动"
        should_reduce = False
        should_delay = False
    else:
        regime = "正常"
        should_reduce = False
        should_delay = False
    
    # 获取仓位建议
    target = volatility_target_multiplier(bb_width)
    
    return {
        "bb_width": round(bb_width, 4),
        "volatility_regime": regime,
        "should_reduce_size": should_reduce,
        "should_delay_entry": should_delay,
        "position_multiplier": target["multiplier"],
        "adjusted_risk_pct": target["adjusted_risk_pct"],
        "reason": target["reason"],
    }


def adaptive_risk_usd(account_balance: float, atr_pct: float,
                      base_risk_pct: float = None,
                      max_risk_pct: float = 0.10,
                      max_risk_usd_abs: float = 10.0) -> dict:
    """自适应单笔风险金额：按 ATR 波动率缩放 risk_usd。

    把已有的 volatility_target_multiplier（高波动减仓·低波动加仓·风险贡献相等）
    接进实际仓位决策，替代写死的 risk_usd=2。

    单笔风险硬上限取「账户百分比」与「绝对上限」两者更小者：
    棠溪铁律单笔最大 `10U`，且本金 100 阶段 ≤ 10% 账户。

    Args:
        account_balance: 账户余额（USD）
        atr_pct: 当前 ATR 占价格百分比（如 0.02 = 2%）。0/缺失 → 回退基准。
        base_risk_pct: 基准单笔风险占比，默认 CONSTITUTION["MAX_RISK_PER_TRADE_PCT"]
        max_risk_pct: 单笔风险占账户比例上限（默认 10%）
        max_risk_usd_abs: 单笔风险绝对上限（默认 `10U`，棠溪铁律）

    Returns:
        {risk_usd, risk_pct, multiplier, regime, capped, reason}
    """
    if base_risk_pct is None:
        base_risk_pct = CONSTITUTION["MAX_RISK_PER_TRADE_PCT"]

    # 双重硬上限：账户百分比 与 绝对值，取更小者
    hard_cap = min(account_balance * max_risk_pct, max_risk_usd_abs)

    # ATR 缺失/为0：回退基准，倍数1.0，不崩
    if not atr_pct or atr_pct <= 0:
        raw_risk_usd = account_balance * base_risk_pct
        capped = raw_risk_usd > hard_cap
        return {
            "risk_usd": round(min(raw_risk_usd, hard_cap), 2),
            "risk_pct": base_risk_pct,
            "multiplier": 1.0,
            "regime": "未知",
            "capped": capped,
            "reason": "ATR缺失 → 基准仓位",
        }

    vt = volatility_target_multiplier(atr_pct)
    multiplier = vt["multiplier"]
    risk_pct = base_risk_pct * multiplier
    raw_risk_usd = account_balance * risk_pct

    capped = raw_risk_usd > hard_cap
    risk_usd = round(min(raw_risk_usd, hard_cap), 2)

    return {
        "risk_usd": risk_usd,
        "risk_pct": round(risk_pct, 4),
        "multiplier": multiplier,
        "regime": vt["regime"],
        "capped": capped,
        "reason": f"{vt['regime']}(ATR{atr_pct:.2%}) → 仓位×{multiplier:.2f} · 风险`{risk_usd}`U" + ("（触上限）" if capped else ""),
    }


# ═══ 动态回撤降级 v2.1（X社区2026机构共识·渐进式风控）═══
# 源：X/Twitter 2026 institutional consensus + Reddit r/algotrading
# 共识：纯固定1%不够 → 必须根据当前回撤层级自动降险
#   DD > 5-8% → 风险降至 0.5%/笔
#   DD > 10-12% → 风险降至 0.25%/笔
#   DD > 15-20% → 暂停所有新仓

def dynamic_drawdown_scaling(
    current_drawdown_pct: float,
    base_risk_pct: float = None,
) -> dict:
    """
    基于当前回撤的动态风险缩放。
    
    与 MaxDrawdown 硬熔断不同：这里是渐进式降级，而非一刀切停。
    
    Args:
        current_drawdown_pct: 当前回撤百分比（正数，如0.08=8%）
        base_risk_pct: 基准风险%，默认1%
        
    Returns:
        {
            "scaled_risk_pct": float,    # 缩放后风险%
            "tier": str,                  # 层级：full/half/quarter/paused
            "multiplier": float,          # 相对基准的倍数
            "threshold_breached": list,   # 触发的阈值
            "message": str,               # 人类可读描述
        }
    """
    if base_risk_pct is None:
        base_risk_pct = CONSTITUTION["MAX_RISK_PER_TRADE_PCT"]
    
    dd = abs(current_drawdown_pct)
    thresholds = []
    
    # 渐进式降级（社区共识）
    if dd >= 0.20:
        scaled = 0.0
        tier = "paused"
        thresholds.append("DD≥20%")
        msg = "回撤≥20% · 暂停所有新仓 · 等待恢复"
    elif dd >= 0.15:
        scaled = base_risk_pct * 0.10
        tier = "micro"
        thresholds.append("DD≥15%")
        msg = f"回撤{dd:.1%}≥15% · 降至{scaled:.2%} · 基本暂停"
    elif dd >= 0.12:
        scaled = base_risk_pct * 0.25
        tier = "quarter"
        thresholds.append("DD≥12%")
        msg = f"回撤{dd:.1%}≥12% · 降至{scaled:.2%}(1/4仓)"
    elif dd >= 0.08:
        scaled = base_risk_pct * 0.50
        tier = "half"
        thresholds.append("DD≥8%")
        msg = f"回撤{dd:.1%}≥8% · 降至{scaled:.2%}(1/2仓)"
    elif dd >= 0.05:
        scaled = base_risk_pct * 0.75
        tier = "reduced"
        thresholds.append("DD≥5%")
        msg = f"回撤{dd:.1%}≥5% · 降至{scaled:.2%}(3/4仓)"
    else:
        scaled = base_risk_pct
        tier = "full"
        msg = f"回撤{dd:.1%}<5% · 维持全仓{scaled:.2%}"
    
    multiplier = scaled / base_risk_pct if base_risk_pct > 0 else 1.0
    
    return {
        "scaled_risk_pct": round(scaled, 5),
        "tier": tier,
        "multiplier": round(multiplier, 3),
        "threshold_breached": thresholds,
        "message": msg,
    }


def combined_risk_check(
    account_balance: float,
    atr_pct: float,
    current_drawdown_pct: float,
    max_risk_usd_abs: float = 10.0,
) -> dict:
    """
    组合风险检查：波动率自适应 + 回撤降级 = 最终单笔风险。
    
    优先级：回撤降级分母 → 波动率自适应分子 → 硬上限兜底。
    
    Returns: 最终 risk_usd + 各层详情
    """
    # 层1：回撤降级
    dd = dynamic_drawdown_scaling(current_drawdown_pct)
    
    # 层2：波动率自适应
    vol = adaptive_risk_usd(account_balance, atr_pct)
    
    # 组合：用回撤降级后的风险% × 波动率倍数
    combined_risk_pct = dd["scaled_risk_pct"] * vol["multiplier"]
    raw_risk_usd = account_balance * combined_risk_pct
    
    # 层3：硬上限
    hard_cap = min(account_balance * 0.10, max_risk_usd_abs)
    final_risk_usd = min(raw_risk_usd, hard_cap)
    capped = raw_risk_usd > hard_cap
    
    return {
        "risk_usd": round(final_risk_usd, 2),
        "risk_pct": round(combined_risk_pct, 5),
        "drawdown_tier": dd["tier"],
        "drawdown_mult": dd["multiplier"],
        "volatility_mult": vol["multiplier"],
        "volatility_regime": vol["regime"],
        "capped": capped,
        "reason": (
            f"回撤{dd['tier']}(×{dd['multiplier']})"
            f" · 波动{vol['regime']}(×{vol['multiplier']})"
            f" · 风险`{final_risk_usd}`U"
            + ("（触上限）" if capped else "")
        ),
    }


# ═══ CLI ═══
if __name__ == "__main__":
    # Demo
    state = RiskState(
        date="2026-06-18",
        daily_realized_pnl=0.0,
        daily_starting_balance=67.52,
        trades_count=0,
        loss_streak=0,
        unreviewed_trade_count=1,
    )
    
    result = check_constitution(
        symbol="BTCUSDT",
        risk_usd=3.0,
        account_balance=67.52,
        entry_price=64050,
        stop_price=64510,
        target1_price=63670,
        atr_value=450,
        state=state,
        volatility_24h_pct=0.029,  # 2.9%
    )
    
    kelly = kelly_position_size(win_rate=0.833, avg_win_r=2.0, avg_loss_r=1.0,
                                  account_balance=67.52)
    
    print("═" * 50)
    print("风险宪法检查")
    print("═" * 50)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\n═" * 50)
    print("Kelly仓位建议")
    print("═" * 50)
    print(json.dumps(kelly, indent=2, ensure_ascii=False))
