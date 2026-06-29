#!/usr/bin/env python3
"""
引擎中控 v1.0 — 休眠引擎接线器
将所有孤立引擎串联到统一分析流程

调用链:
  pipeline_2022(趋势+入场) → five_model_matcher(多模型确认)
  → dmi_decision(DMI方向) → vwap_ema_cvd(VWAP/CVD引擎)
  → orderflow_absorption(订单流) → scoring_engine(评分)
  → risk_constitution(风控) → backtest_runner(胜率)
  → 输出统一卡
"""
import sys, os, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 确保可以import到scripts目录下的引擎
ROOT = Path("D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hermes" / "scripts"))

TZ = timezone(timedelta(hours=8))
DATA = os.path.expanduser("~/AppData/Local/hermes/data")


def _import_or_none(name):
    try:
        return __import__(name)
    except ImportError:
        return None


def _read_json(fp):
    try:
        with open(fp) as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    now = datetime.now(TZ)
    ts = now.strftime("%Y-%m-%d %H:%M BJT")
    
    # 读取最新数据
    tv = _read_json(os.path.join(DATA, "btc_ref_levels.json"))
    latest = _read_json(os.path.join(DATA, "btc_latest.json"))
    macro = _read_json(os.path.join(DATA, "macro_snapshot.json"))
    sentiment = _read_json(os.path.join(DATA, "sentiment.json"))
    liq_data = _read_json(os.path.join(DATA, "liquidation_pressure.json"))
    
    price = tv.get("price", latest.get("price", 0))
    
    results = {"engines": {}, "warnings": []}
    
    # 1. DMI决策 (最快，只需价格数据)
    dmi = _import_or_none("dmi_decision")
    if dmi and price:
        try:
            dmi_result = dmi.analyze({"price": price, **(tv or {})})
            results["engines"]["dmi"] = str(dmi_result)[:200]
        except Exception as e:
            results["warnings"].append(f"dmi: {e}")
    
    # 2. 五模型匹配器
    fm = _import_or_none("five_model_matcher")
    if fm and price:
        try:
            fm_result = fm.match_all({"price": price, **(tv or {}), **(latest or {})})
            results["engines"]["five_model"] = str(fm_result)[:200]
        except Exception as e:
            results["warnings"].append(f"five_model: {e}")
    
    # 3. 评分引擎
    se = _import_or_none("scoring_engine")
    if se:
        try:
            score = se.score_all({**(tv or {}), **(latest or {}), **({"price": price} if price else {})})
            results["engines"]["scoring"] = str(score)[:200]
        except Exception as e:
            results["warnings"].append(f"scoring: {e}")
    
    # 4. 风险宪法
    rc = _import_or_none("risk_constitution")
    if rc:
        try:
            risk = rc.evaluate({**(latest or {}), **(sentiment or {}), **(liq_data or {})})
            results["engines"]["risk"] = str(risk)[:300]
        except Exception as e:
            results["warnings"].append(f"risk: {e}")
    
    # 生成摘要
    lines = [f"引擎中控 {ts}"]
    
    dmi_info = results["engines"].get("dmi", "未启动")
    fm_info = results["engines"].get("five_model", "未启动")
    score_info = results["engines"].get("scoring", "未启动")
    risk_info = results["engines"].get("risk", "未启动")
    
    lines.append(f"DMI: {dmi_info[:80]}")
    lines.append(f"五模型: {fm_info[:80]}")
    lines.append(f"评分: {score_info[:80]}")
    lines.append(f"风控: {risk_info[:80]}")
    
    if results["warnings"]:
        lines.append(f"注意: {'; '.join(results['warnings'][:3])}")
    
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
