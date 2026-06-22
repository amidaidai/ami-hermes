#!/usr/bin/env python3
"""BTC全流程管线集成 — 串联FVG·评分·事件·OB·截图→分析卡"""
import json, os, sys, subprocess
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DIR = os.path.expanduser("~/AppData/Local/hermes/data")
SCRIPTS = os.path.expanduser("~/AppData/Local/hermes/scripts")
os.makedirs(DIR, exist_ok=True)

PENDING = os.path.join(DIR, "btc_pending.txt")
SIGNALS_FILE = os.path.join(DIR, "btc_signals.json")
LATEST_FILE = os.path.join(DIR, "btc_latest.json")
TV_DATA_FILE = os.path.join(DIR, "btc_tv_data.json")
MACRO_FILE = os.path.join(DIR, "btc_macro.json")
SCREENSHOT_DIR = os.path.expanduser("~/AppData/Local/hermes/data/screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def _read_json(fp):
    try:
        with open(fp) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_pending(msg, priority="normal"):
    tag = "⭐" if priority == "high" else ""
    with open(PENDING, "a") as f:
        f.write(f"{tag}{msg}\n---\n")


def _import_or_none(module_name):
    """安全导入模块。"""
    try:
        return __import__(module_name)
    except ImportError:
        return None


def fetch_binance_klines(symbol="BTCUSDT", interval="15m", limit=60):
    """从Binance获取K线数据。"""
    import urllib.request
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "D/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())
    except Exception:
        return _read_json(os.path.join(DIR, "btc_klines_cache.json"))


def take_tv_screenshot(symbol="BTCUSDT", tf="15"):
    """调用TV截图脚本。返回截图路径或None。"""
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "tv_screenshot.py"), symbol, tf],
            capture_output=True, text=True, timeout=25,
        )
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if "✅" in line or line.endswith(".png") or ".png" in line:
                # 提取路径
                path = line.replace("✅ ", "").strip()
                if os.path.exists(path):
                    return path
        return None
    except Exception:
        return None


def run_full_pipeline(klines, current_price=None):
    """全流程：6模块串联 → 评分 → 分析卡。"""
    result = {
        "timestamp": datetime.now(TZ).strftime("%H:%M:%S"),
        "pipeline": {},
        "scoring": {},
        "events": {},
        "fvg": [],
        "obs": [],
        "analysis_card": "",
        "key_levels": {},
    }
    
    # 1. 读取现有数据
    latest = _read_json(LATEST_FILE)
    tv = _read_json(TV_DATA_FILE)
    signals = _read_json(SIGNALS_FILE)
    
    if current_price is None:
        current_price = latest.get("price", tv.get("price", 0))
        if not current_price:
            current_price = float(klines[-1][4]) if klines else 0
    
    # 2. 关键位
    levels = {
        "VAH": tv.get("VAH", tv.get("vah", 0)),
        "VAL": tv.get("VAL", tv.get("val", 0)),
        "POC": tv.get("POC", tv.get("poc", 0)),
        "VWAP": tv.get("VWAP", tv.get("vwap", 0)),
        "HOD": tv.get("day_high", 0),
        "LOD": tv.get("day_low", 0),
    }
    result["key_levels"] = {k: v for k, v in levels.items() if v}
    
    # 3. 2022模型管线
    pipeline_m = _import_or_none("pipeline_2022")
    if pipeline_m:
        try:
            pipe_result = pipeline_m.run_pipeline(klines, levels, current_price)
            result["pipeline"] = pipe_result
        except Exception as e:
            result["pipeline"] = {"error": str(e)}
    
    # 4. FVG检测
    fvg_m = _import_or_none("fvg_detector")
    if fvg_m:
        try:
            fvgs = fvg_m.detect_fvg(klines[-50:])
            fvg_m.update_fvg_status(fvgs, current_price, klines[-50:])
            result["fvg"] = fvgs[:5]
        except Exception as e:
            result["fvg_error"] = str(e)
    
    # 5. OB检测
    ob_m = _import_or_none("order_block")
    if ob_m:
        try:
            obs = ob_m.detect_obs(klines[-100:])
            result["obs"] = obs[:5]
            nearest = ob_m.nearest_ob(obs, current_price)
            if nearest:
                result["nearest_ob"] = nearest
        except Exception as e:
            result["ob_error"] = str(e)
    
    # 6. 多因子评分
    score_m = _import_or_none("scoring_engine_v2")
    if score_m:
        try:
            # 注入管线数据到signals
            enriched = dict(signals)
            if result["pipeline"].get("stage") == "entry_ready":
                enriched["fvg"] = {"exists": True}
            if result.get("fvg"):
                enriched["fvg"] = {"exists": True}
            if result.get("nearest_ob"):
                enriched["order_block"] = {"near": True, "detail": f"{result['nearest_ob']['type']} @ {result['nearest_ob']['price']}"}
            
            scoring = score_m.score_all(enriched)
            result["scoring"] = scoring
        except Exception as e:
            result["scoring_error"] = str(e)
    
    # 7. 事件日历
    event_m = _import_or_none("event_calendar")
    if event_m:
        try:
            events = event_m.get_block_status()
            result["events"] = events
        except Exception as e:
            result["events"] = {"blocked": False, "error": str(e)}
    
    # 8. 生成分析卡
    card = generate_analysis_card(result, current_price, latest, tv)
    result["analysis_card"] = card
    
    return result


def _num(*values, default=0.0):
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _bias_text(price, latest, tv, pipe):
    vwap = _num(tv.get("vwap"), tv.get("VWAP"), latest.get("vwap"))
    poc = _num(tv.get("poc"), tv.get("POC"))
    vah = _num(tv.get("vah"), tv.get("VAH"))
    val = _num(tv.get("val"), tv.get("VAL"))
    cvd = _num(tv.get("cvd"), tv.get("CVD"))
    cvd_slope = _num(tv.get("cvd_slope"), tv.get("CVD_slope"))
    taker = _num(latest.get("taker_ratio"), latest.get("taker_buy_sell_ratio"), default=1.0)
    ls = _num(latest.get("ls_ratio"), latest.get("long_short_ratio"), default=1.0)

    if pipe.get("direction"):
        raw = str(pipe.get("direction", "")).lower()
        if "long" in raw or "bull" in raw or raw == "buy":
            return "偏多", "2022管线给多头方向"
        if "short" in raw or "bear" in raw or raw == "sell":
            return "偏空", "2022管线给空头方向"

    above_core = price > max(vwap, poc) if vwap and poc else price > vwap
    near_vah = bool(vah and abs(price - vah) <= 180)
    near_val = bool(val and abs(price - val) <= 180)

    if above_core and taker > 1.05 and cvd_slope < 0 and near_vah:
        return "偏多等待", "价在VWAP/POC上方，Taker转买；但CVD仍负，必须看VAH接受"
    if above_core and taker > 1.05:
        return "偏多", "价站VWAP/POC上方，Taker买方增强"
    if not above_core and cvd < 0 and cvd_slope < 0:
        return "偏空", "价失VWAP/POC且CVD顺空"
    if near_val and cvd < 0:
        return "偏空等待", "贴近VAL，卖压未解除，等破位或回收确认"
    if ls > 1.6 and cvd < 0:
        return "等待偏空", "多空比拥挤但CVD负，防多头被动出清"
    return "等待", "核心位内震荡，缺少放量确认"


def generate_analysis_card(result, price, latest, tv):
    """生成棠溪格式分析卡（短版·含管线状态）。"""
    pipe = result.get("pipeline", {})
    pipe_stage = pipe.get("stage", "idle")
    pipe_detail = pipe.get("details", "")
    
    scoring = result.get("scoring", {})
    score_total = scoring.get("total", "?")
    score_max = scoring.get("max_possible", 20)
    score_level = scoring.get("level", "低")
    converging = scoring.get("converging_signals", [])
    
    fvg_count = len(result.get("fvg", []))
    ob_count = len(result.get("obs", []))
    
    events = result.get("events", {})
    blocked = events.get("blocked", False)
    
    # 决定方向
    bias, bias_reason = _bias_text(price, latest, tv, pipe)
    direction = bias
    
    # 生成卡
    lines = []
    lines.append(f"**① 品种：BTCUSDT · BINANCE**")
    lines.append(f"**② 主方向：{bias}** — {bias_reason}")
    lines.append(f"**③ 管线：S→{pipe_stage}** — {pipe_detail or '等待'}")
    lines.append(f"**④ 现价：`{price:,.0f}` · {fvg_count}个FVG · {ob_count}个OB**")
    lines.append(f"**⑤ 状态：{direction} · 评分{score_total}/{score_max} · {score_level}**")
    if converging:
        lines.append(f"**⑥ 汇聚：{len(converging)}信号** — {'·'.join(converging[:5])}")
    if blocked:
        lines.append(f"**⚠ 事件阻塞** — {events.get('reason', '')}")
    lines.append(f"**⑦ 决策：**")
    
    if pipe_stage == "entry_ready":
        lines.append(f"⭐ 2022模型管线就绪 — {pipe.get('direction', '')}方向入场 @ `{pipe.get('entry_price', '')}`")
    elif pipe.get("signal_type"):
        lines.append(f"信号：{pipe['signal_type']}")
    elif "偏多" in bias:
        lines.append("★最值得看：VAH接受。15m收上VAH且CVD斜率止跌，才追多；VAH拒绝就不追。")
    elif "偏空" in bias:
        lines.append("★最值得看：VWAP/POC失守。15m收回核心位下方且CVD继续负，才顺空。")
    else:
        lines.append("★最值得看：等扫荡或FVG回测，不预入场。")
    
    if events.get("next_event"):
        lines.append(f"**事件: {events['next_event']}**")
    
    # CVD/多空比/Taker
    cvd = _num(latest.get("cvd"), tv.get("cvd"), tv.get("CVD"))
    cvd_slope = _num(tv.get("cvd_slope"), tv.get("CVD_slope"))
    ls = _num(latest.get("ls_ratio"), latest.get("long_short_ratio"), default=1.0)
    taker = _num(latest.get("taker_ratio"), latest.get("taker_buy_sell_ratio"), latest.get("taker_volume", {}).get("buy_sell_ratio"), default=1.0)
    lines.append(f"CVD `{cvd:+.0f}` · 斜率 `{cvd_slope:+.0f}` · 多空比 `{ls:.2f}` · Taker `{taker:.2f}`")
    
    return "\n".join(lines)


def push_analysis(klines=None, timeframes=None):
    """完整推一条分析到pending。"""
    if klines is None:
        klines = fetch_binance_klines()
    if timeframes is None:
        timeframes = {"15m": klines}
    
    for tf, klines_data in timeframes.items():
        result = run_full_pipeline(klines_data)
        
        card = result["analysis_card"]
        scoring = result.get("scoring", {})
        
        # pipeline得分
        pipe_score = result["pipeline"].get("score", 0)
        is_high_prob = scoring.get("high_probability", False) or pipe_score >= 5
        
        # 生成推送消息
        msg = card
        if result.get("fvg"):
            best_fvg = result["fvg"][0]
            msg += f"\n📌 FVG {best_fvg['type']}: `{best_fvg['bottom']}`→`{best_fvg['top']}` 中点`{best_fvg['midpoint']}`"
        
        if result.get("nearest_ob"):
            ob = result["nearest_ob"]
            msg += f"\n📌 OB {ob['type']}: `{ob['price']}` 强度{ob['strength']}/5"
        
        # 截图（不依赖MCP工具的静默尝试）
        # 截图由守护cron独立处理，这里只生产文本
        _write_pending(msg, priority="high" if is_high_prob else "normal")
        
        # 写scoring结果到signals文件供复盘用
        signals_data = _read_json(SIGNALS_FILE)
        signals_data["pipeline_score"] = pipe_score
        signals_data["scoring_total"] = scoring.get("total", 0)
        signals_data["converging_signals"] = scoring.get("converging_signals", [])
        signals_data["stage"] = result["pipeline"].get("stage", "idle")
        try:
            with open(SIGNALS_FILE, "w") as f:
                json.dump(signals_data, f, indent=2)
        except Exception:
            pass
    
    return True


if __name__ == "__main__":
    klines = fetch_binance_klines()
    if klines:
        result = run_full_pipeline(klines)
        print(result["analysis_card"])
        print(f"\n管线阶段: {result['pipeline'].get('stage', 'unknown')}")
        if result.get("fvg"):
            print(f"FVG: {len(result['fvg'])}个")
        if result.get("nearest_ob"):
            print(f"最近OB: {result['nearest_ob']}")
        print(f"汇聚评分: {result['scoring'].get('total', '?')}/{result['scoring'].get('max_possible', 20)}")
    else:
        print("❌ 无法获取K线数据")
