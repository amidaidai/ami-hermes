#!/usr/bin/env python3
"""
棠溪 · Dry-run 渐进上线模式 v1.0
社区2026共识（Freqtrade): 仿真→小规模→全量，共3阶段

阶段:
  1. Dry-run (0-2周): 全程仿真，不产生真实订单，只记录信号和复盘
  2. Micro-lot (2-4周): 最小仓位（0.001 BTC），验证实盘执行质量
  3. Full-scale (4周+): 按宪法正常仓位，完整自动执行

状态跟踪: data/dryrun_state.json
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from enum import Enum

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
DRYRUN_FILE = DATA / "dryrun_state.json"


class DryRunPhase(Enum):
    DRYRUN = "dryrun"        # 纯仿真
    MICRO = "micro"          # 最小仓位实盘
    FULL = "full"            # 全量


class DryRunState:
    def __init__(self):
        self.phase: DryRunPhase = DryRunPhase.DRYRUN
        self.started_at: str = datetime.now(TZ).isoformat(timespec="seconds")
        self.sim_trades: int = 0
        self.sim_wins: int = 0
        self.sim_total_r: float = 0.0
        self.phase2_started: str = ""
        self.micro_trades: int = 0
        self.micro_wins: int = 0
        self.micro_total_r: float = 0.0
        self.promoted_to_full: bool = False
    
    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "started_at": self.started_at,
            "sim_trades": self.sim_trades,
            "sim_wins": self.sim_wins,
            "sim_total_r": self.sim_total_r,
            "phase2_started": self.phase2_started,
            "micro_trades": self.micro_trades,
            "micro_wins": self.micro_wins,
            "micro_total_r": self.micro_total_r,
            "promoted_to_full": self.promoted_to_full,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "DryRunState":
        s = cls()
        s.phase = DryRunPhase(d.get("phase", "dryrun"))
        s.started_at = d.get("started_at", "")
        s.sim_trades = d.get("sim_trades", 0)
        s.sim_wins = d.get("sim_wins", 0)
        s.sim_total_r = d.get("sim_total_r", 0.0)
        s.phase2_started = d.get("phase2_started", "")
        s.micro_trades = d.get("micro_trades", 0)
        s.micro_wins = d.get("micro_wins", 0)
        s.micro_total_r = d.get("micro_total_r", 0.0)
        s.promoted_to_full = d.get("promoted_to_full", False)
        return s
    
    @property
    def sim_win_rate(self) -> float:
        return self.sim_wins / max(self.sim_trades, 1)
    
    @property
    def micro_win_rate(self) -> float:
        return self.micro_wins / max(self.micro_trades, 1)
    
    @property
    def real_risk_multiplier(self) -> float:
        """当前阶段的风险倍数"""
        if self.phase == DryRunPhase.DRYRUN:
            return 0.0  # 不产生真实订单
        elif self.phase == DryRunPhase.MICRO:
            return 0.02  # 2%正常仓位
        return 1.0


def load_dryrun_state() -> DryRunState:
    if DRYRUN_FILE.exists():
        try:
            return DryRunState.from_dict(json.loads(DRYRUN_FILE.read_text(encoding="utf-8")))
        except:
            pass
    return DryRunState()


def save_dryrun_state(state: DryRunState):
    DRYRUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    DRYRUN_FILE.write_text(json.dumps(state.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def check_promotion(state: DryRunState) -> dict:
    """
    检查是否满足晋升条件
    
    Phase 1 → 2: 仿真≥20笔 + 胜率≥40% + 平均R>0
    Phase 2 → 3: 微仓≥10笔 + 胜率≥35% + 平均R>0 + 滑点可接受
    """
    result = {"can_promote": False, "reason": "", "next_phase": None}
    
    if state.phase == DryRunPhase.DRYRUN:
        if state.sim_trades >= 20 and state.sim_win_rate >= 0.40 and state.sim_total_r > -3:
            result["can_promote"] = True
            result["next_phase"] = "micro"
            result["reason"] = f"仿真{state.sim_trades}笔 胜率{state.sim_win_rate:.0%} R={state.sim_total_r:+.1f} → 可晋升微仓"
        else:
            result["reason"] = f"仿真{state.sim_trades}/20笔 胜率{state.sim_win_rate:.0%} 还需积累"
    
    elif state.phase == DryRunPhase.MICRO:
        if state.micro_trades >= 10 and state.micro_win_rate >= 0.35 and state.micro_total_r > -2:
            result["can_promote"] = True
            result["next_phase"] = "full"
            result["reason"] = f"微仓{state.micro_trades}笔 胜率{state.micro_win_rate:.0%} R={state.micro_total_r:+.1f} → 可晋升全量"
        else:
            result["reason"] = f"微仓{state.micro_trades}/10笔 胜率{state.micro_win_rate:.0%} 还需积累"
    
    elif state.phase == DryRunPhase.FULL:
        result["reason"] = "已在全量模式"
    
    return result


def promote_phase(state: DryRunState) -> dict:
    """执行晋升"""
    check = check_promotion(state)
    if not check["can_promote"]:
        return {"promoted": False, "reason": check["reason"]}
    
    next_phase = check["next_phase"]
    if next_phase == "micro":
        state.phase = DryRunPhase.MICRO
        state.phase2_started = datetime.now(TZ).isoformat(timespec="seconds")
    elif next_phase == "full":
        state.phase = DryRunPhase.FULL
        state.promoted_to_full = True
    
    save_dryrun_state(state)
    return {"promoted": True, "new_phase": state.phase.value, "reason": check["reason"]}


def dryrun_status_report() -> str:
    """可读状态报告"""
    state = load_dryrun_state()
    check = check_promotion(state)
    
    lines = [
        f"阶段: {state.phase.value} · 风险倍数: {state.real_risk_multiplier:.0%}",
        f"仿真: {state.sim_trades}笔 胜率{state.sim_win_rate:.0%} R={state.sim_total_r:+.1f}",
    ]
    
    if state.phase in (DryRunPhase.MICRO, DryRunPhase.FULL):
        lines.append(f"微仓: {state.micro_trades}笔 胜率{state.micro_win_rate:.0%} R={state.micro_total_r:+.1f}")
    
    lines.append(f"晋升: {check['reason']}")
    return "\n".join(lines)


# ═══ CLI ═══
if __name__ == "__main__":
    import sys
    
    if "--promote" in sys.argv:
        state = load_dryrun_state()
        result = promote_phase(state)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif "--status" in sys.argv:
        print(dryrun_status_report())
    elif "--sim" in sys.argv:
        # 记录一笔仿真交易
        state = load_dryrun_state()
        win = "--win" in sys.argv
        r_val = float(sys.argv[sys.argv.index("--r") + 1]) if "--r" in sys.argv else 0.0
        state.sim_trades += 1
        if win:
            state.sim_wins += 1
        state.sim_total_r += r_val
        save_dryrun_state(state)
        print(f"仿真+1 {'✅赢' if win else '❌亏'} R={r_val:+.1f} 总{state.sim_trades}笔")
    elif "--micro" in sys.argv:
        state = load_dryrun_state()
        win = "--win" in sys.argv
        r_val = float(sys.argv[sys.argv.index("--r") + 1]) if "--r" in sys.argv else 0.0
        state.micro_trades += 1
        if win:
            state.micro_wins += 1
        state.micro_total_r += r_val
        save_dryrun_state(state)
        print(f"微仓+1 {'✅赢' if win else '❌亏'} R={r_val:+.1f} 总{state.micro_trades}笔")
    else:
        print(dryrun_status_report())
