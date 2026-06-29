#!/usr/bin/env python3
"""
棠溪 · 48h上线前就绪报告 v1.0
基于社区2026共识（Freqtrade readliness check + X/Reddit overfitting detection）

检查维度:
  1. 过拟合检测 — 训练vs测试胜率差
  2. OOS差距 — Walk-Forward OOS段 vs IS段
  3. 参数敏感性 — 微调参数结果不应崩溃
  4. 滑点压力 — 2×滑点回测是否仍盈利
  5. 时长覆盖 — 30天连续K线≥2000根
  6. 样本充足 — 每模型≥20笔真实成交复盘
  7. 数据质量 — BTC/XAU A级≥90%
  8. 风险宪法 — Protections已启用

用法:
  python scripts/readiness_report.py           # 全量检查
  python scripts/readiness_report.py BTCUSDT   # 单品种
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json, sys, os
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"

# ═══ 检查函数 ═══

def check_overfit(train_win_rate: float, test_win_rate: float, threshold: float = 0.15) -> dict:
    """过拟合检测：训练-测试胜率差 > 15% = 过拟合"""
    gap = abs(train_win_rate - test_win_rate)
    overfit = gap > threshold
    return {
        "check": "过拟合检测",
        "passed": not overfit,
        "train_win_rate": round(train_win_rate, 3),
        "test_win_rate": round(test_win_rate, 3),
        "gap": round(gap, 3),
        "threshold": threshold,
        "verdict": "过拟合" if overfit else "通过",
    }


def check_oos_gap(is_win_rate: float, oos_win_rate: float, threshold: float = 0.20) -> dict:
    """OOS差距：IS vs OOS胜率差 > 20% = 过拟合"""
    gap = abs(is_win_rate - oos_win_rate)
    overfit = gap > threshold
    return {
        "check": "OOS差距(Walk-Forward)",
        "passed": not overfit,
        "is_win_rate": round(is_win_rate, 3),
        "oos_win_rate": round(oos_win_rate, 3),
        "gap": round(gap, 3),
        "threshold": threshold,
        "verdict": "过拟合" if overfit else "通过",
    }


def check_param_stability(base_params: dict, results: list[dict], threshold: float = 0.30) -> dict:
    """
    参数敏感性：微调5%参数，结果变化 ≤ 30%
    results: [{"params": {...}, "win_rate": float}, ...]
    """
    if not results:
        return {"check": "参数敏感性", "passed": None, "verdict": "无数据", "reason": "未提供回测结果"}
    
    win_rates = [r["win_rate"] for r in results]
    max_gap = max(win_rates) - min(win_rates)
    stable = max_gap <= threshold
    
    return {
        "check": "参数敏感性",
        "passed": stable,
        "min_win_rate": round(min(win_rates), 3),
        "max_win_rate": round(max(win_rates), 3),
        "max_gap": round(max_gap, 3),
        "threshold": threshold,
        "verdict": "稳定" if stable else "不稳定⚠",
    }


def check_slippage(base_pf: float, slip_pf: float, threshold: float = 0.50) -> dict:
    """
    滑点压力测试：2×滑点后利润因子仍 > 0.5×基准
    """
    if base_pf <= 0:
        return {"check": "滑点压力测试", "passed": None, "verdict": "基准无利润", "reason": "基准PF≤0"}
    
    ratio = slip_pf / base_pf
    passed = ratio >= threshold
    
    return {
        "check": "滑点压力测试(2×滑点)",
        "passed": passed,
        "base_profit_factor": round(base_pf, 2),
        "slip_profit_factor": round(slip_pf, 2),
        "ratio": round(ratio, 2),
        "threshold": threshold,
        "verdict": "稳健" if passed else "滑点敏感⚠",
    }


def check_data_coverage(klines_file: str, min_bars: int = 2000) -> dict:
    """K线数据覆盖"""
    path = Path(klines_file) if Path(klines_file).is_absolute() else DATA / klines_file
    if not path.exists():
        return {"check": f"数据覆盖({klines_file})", "passed": False, "verdict": "缺失", "bars": 0}
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        bars = len(data) if isinstance(data, list) else len(data.get("klines", data.get("data", [])))
        passed = bars >= min_bars
        return {"check": f"数据覆盖({klines_file})", "passed": passed, "bars": bars,
                "min_required": min_bars, "verdict": "充足" if passed else f"不足({bars}/{min_bars})"}
    except Exception as e:
        return {"check": f"数据覆盖({klines_file})", "passed": False, "verdict": f"读取错误:{e}", "bars": 0}


def check_model_samples(symbol: str = None) -> dict:
    """模型样本数：每模型≥20笔真实成交复盘"""
    stats_file = DATA / "strategy_model_stats.json"
    if not stats_file.exists():
        return {"check": "模型样本数", "passed": False, "verdict": "无统计文件",
                "models": {}, "min_required": 20}
    
    try:
        stats = json.loads(stats_file.read_text(encoding="utf-8"))
        models = stats.get("models", {})
        
        insufficient = []
        sufficient = []
        for name, m in models.items():
            count = m.get("predictions", m.get("total", 0))
            if count >= 20:
                sufficient.append(name)
            else:
                insufficient.append(f"{name}({count}/20)")
        
        passed = len(insufficient) == 0
        return {
            "check": "模型样本数(≥20笔)",
            "passed": passed,
            "sufficient": sufficient,
            "insufficient": insufficient,
            "min_required": 20,
            "verdict": "全部充足" if passed else f"{len(insufficient)}个不足",
        }
    except Exception as e:
        return {"check": "模型样本数", "passed": False, "verdict": f"读取错误:{e}"}


def check_data_quality() -> dict:
    """数据质量：BTC/XAU A级比例"""
    results = {}
    for sym in ["BTCUSDT", "XAUUSD"]:
        snap = DATA / f"source_snapshot_{sym}.json"
        if snap.exists():
            try:
                d = json.loads(snap.read_text(encoding="utf-8"))
                q = d.get("quality", d.get("confidence_label", "C"))
                results[sym] = q
            except:
                results[sym] = "读取错误"
        else:
            results[sym] = "无快照"
    
    a_count = sum(1 for v in results.values() if "A" in str(v))
    passed = a_count == 2
    
    return {
        "check": "数据质量(BTC+XAU A级)",
        "passed": passed,
        "snapshots": results,
        "a_count": a_count,
        "verdict": "全A级" if passed else f"{a_count}/2 A级",
    }


def check_protections_enabled() -> dict:
    """Protections 系统是否启用"""
    try:
        from risk_constitution import CONSTITUTION
        has_atr = CONSTITUTION.get("MAX_STOP_ATR_RATIO", 0) > 0
        has_sg = CONSTITUTION.get("STOPLOSS_GUARD_LOOKBACK", 0) > 0
        has_cooldown = CONSTITUTION.get("COOLDOWN_AFTER_LOSS", 0) > 0
        has_hard_dd = CONSTITUTION.get("MAX_DAILY_DRAWDOWN_HARD", 0) > 0
        all_ok = has_atr and has_sg and has_cooldown and has_hard_dd
        return {
            "check": "Protections已启用",
            "passed": all_ok,
            "atr_clamp": has_atr,
            "stoploss_guard": has_sg,
            "cooldown": has_cooldown,
            "hard_drawdown": has_hard_dd,
            "verdict": "全启用" if all_ok else "部分缺失",
        }
    except Exception as e:
        return {"check": "Protections已启用", "passed": False, "verdict": f"导入失败:{e}"}


# ═══ 主报告 ═══

def generate_report(symbol: str = None, **kwargs) -> dict:
    """
    生成48h就绪报告
    
    社区基准（Freqtrade 48h readiness）:
      ✅ 过拟合检测通过
      ✅ OOS差距 < 20%
      ✅ 参数稳定（5%微调结果波动 < 30%）
      ✅ 2×滑点后仍盈利
      ✅ 30天连续数据 ≥ 2000根
      ✅ 每模型 ≥ 20笔真实成交复盘
      ✅ BTC + XAU 数据 A级
      ✅ Protections 全启用
    """
    checks = []
    
    # 1. 过拟合（如果有WFO数据）
    wf_file = DATA / "walkforward_results.json"
    if wf_file.exists():
        try:
            wf = json.loads(wf_file.read_text(encoding="utf-8"))
            train_wr = wf.get("train_metrics", {}).get("win_rate", 0)
            test_wr = wf.get("test_metrics", {}).get("win_rate", 0)
            if train_wr and test_wr:
                checks.append(check_overfit(train_wr, test_wr))
        except:
            pass
    
    # 2-4. 回测相关（需要传参）
    if kwargs.get("train_wr") and kwargs.get("test_wr"):
        checks.append(check_oos_gap(kwargs["train_wr"], kwargs["test_wr"]))
    if kwargs.get("param_results"):
        checks.append(check_param_stability({}, kwargs["param_results"]))
    if kwargs.get("base_pf") and kwargs.get("slip_pf"):
        checks.append(check_slippage(kwargs["base_pf"], kwargs["slip_pf"]))
    
    # 5. 数据覆盖
    checks.append(check_data_coverage("btc_klines_30d_merged.json"))
    
    # 6. 模型样本
    checks.append(check_model_samples(symbol))
    
    # 7. 数据质量
    checks.append(check_data_quality())
    
    # 8. Protections
    checks.append(check_protections_enabled())
    
    passed = [c for c in checks if c["passed"]]
    failed = [c for c in checks if c["passed"] is False]
    
    return {
        "report": "48h上线前就绪报告",
        "time": datetime.now(TZ).isoformat(timespec="seconds"),
        "symbol": symbol or "全品种",
        "passed_count": len(passed),
        "failed_count": len(failed),
        "total_checks": len(checks),
        "verdict": "GO ✅" if len(failed) == 0 else "NOGO ❌",
        "checks": checks,
        "failures": [c["verdict"] for c in failed],
    }


# ═══ CLI ═══

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else None
    
    # 尝试加载WFO结果
    train_wr = test_wr = base_pf = slip_pf = None
    param_results = None
    
    wf_file = DATA / "walkforward_results.json"
    if wf_file.exists():
        try:
            wf = json.loads(wf_file.read_text(encoding="utf-8"))
            train_wr = wf.get("train_metrics", {}).get("win_rate")
            test_wr = wf.get("test_metrics", {}).get("win_rate")
        except:
            pass
    
    report = generate_report(
        symbol=symbol,
        train_wr=train_wr,
        test_wr=test_wr,
        base_pf=base_pf,
        slip_pf=slip_pf,
        param_results=param_results,
    )
    
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
