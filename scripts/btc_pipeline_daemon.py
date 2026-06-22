#!/usr/bin/env python3
"""BTC管线守护 — 每3分钟运行全流程管线+评分+截图"""
import json, os, sys, time, subprocess
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DIR = os.path.expanduser("~/AppData/Local/hermes/data")
SCRIPTS = os.path.expanduser("~/AppData/Local/hermes/scripts")
SCREENSHOT_DIR = os.path.expanduser("~/AppData/Local/hermes/data/screenshots")
os.makedirs(DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

PENDING = os.path.join(DIR, "btc_pending.txt")
PRIORITY = os.path.join(DIR, "btc_priority.txt")
SIGNALS_FILE = os.path.join(DIR, "btc_signals.json")
LATEST_FILE = os.path.join(DIR, "btc_latest.json")
TV_DATA_FILE = os.path.join(DIR, "btc_tv_data.json")
STATE_FILE = os.path.join(DIR, "btc_pipeline_state.json")
LOG_FILE = os.path.join(DIR, "btc_pipeline_daemon.log")

# ====== 配置 ======
PIPELINE_INTERVAL = 180       # 3分钟
SCREENSHOT_INTERVAL = 300     # 5分钟
ONESHOT_TRIGGER = True        # 首次立即运行

# ====== 工具 ======
def _read_json(fp, default=None):
    if default is None: default = {}
    try:
        with open(fp) as f:
            return json.load(f)
    except: return default

def _write_json(fp, data):
    with open(fp, "w") as f:
        json.dump(data, f, indent=2)

def _write_pending(msg, priority="normal"):
    tag = "⭐" if priority == "high" else ""
    with open(PENDING, "a") as f:
        f.write(f"{tag}{msg}\n---\n")
    if priority == "high":
        with open(PRIORITY, "a") as f:
            f.write(f"{msg}\nBREAK\n")

def now_ts():
    return time.time()

def log(msg):
    t = datetime.now(TZ).strftime("%H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{t}] {msg}\n")
    # Keep daemon stdout ASCII-only to avoid Windows console/cron mojibake.
    sys.stdout.write(f"[{t}] pipeline log\n")
    sys.stdout.flush()

# ====== 管线 ======
def update_state(state, key, value):
    state[key] = value
    state["last_update"] = datetime.now(TZ).strftime("%H:%M:%S")
    _write_json(STATE_FILE, state)

def run_module(module_name, data=None):
    """运行一个管线模块（通过subprocess调用python脚本）。"""
    script = os.path.join(SCRIPTS, module_name)
    if not os.path.exists(script):
        log(f"⚠ 模块不存在: {module_name}")
        return None
    
    try:
        if data:
            # 传入数据作为JSON参数
            input_json = json.dumps(data)
            result = subprocess.run(
                [sys.executable, script, input_json],
                capture_output=True, text=True, timeout=30,
            )
        else:
            result = subprocess.run(
                [sys.executable, script],
                capture_output=True, text=True, timeout=30,
            )
        return result.stdout.strip() if result.stdout else None
    except subprocess.TimeoutExpired:
        log(f"⚠ 模块超时: {module_name}")
        return None
    except Exception as e:
        log(f"⚠ 模块失败 {module_name}: {e}")
        return None

def run_pipeline_cycle():
    """完整管线循环。"""
    log("运行全流程管线...")
    
    # 1. 读取当前数据
    latest = _read_json(LATEST_FILE)
    tv = _read_json(TV_DATA_FILE)
    signals = _read_json(SIGNALS_FILE)
    price = latest.get("price", 0)
    
    if not price:
        log("⚠ 无价格数据，跳过管线")
        return None
    
    # 2. 获取15m K线
    import urllib.request
    klines = []
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=60"
        req = urllib.request.Request(url, headers={"User-Agent": "D/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            klines = json.loads(resp.read())
        log(f"✅ 获取 {len(klines)} 根15m K线")
    except Exception as e:
        log(f"⚠ K线获取失败: {e}")
        return None
    
    # 3. 关键位
    levels = {
        "VAH": tv.get("VAH", tv.get("vah", 0)),
        "VAL": tv.get("VAL", tv.get("val", 0)),
        "POC": tv.get("POC", tv.get("poc", 0)),
        "VWAP": tv.get("VWAP", tv.get("vwap", 0)),
    }
    
    # 4. 运行pipeline
    try:
        sys.path.insert(0, SCRIPTS)
        from pipeline_2022 import run_pipeline, pipeline_summary
        from fvg_detector import detect_fvg, update_fvg_status, best_fvg
        from order_block import detect_obs, nearest_ob as find_nearest_ob
        from scoring_engine_v2 import score_all, interpret as score_interpret
        from event_calendar import get_block_status
    except ImportError as e:
        log(f"⚠ 导入失败: {e}")
        return None
    
    # Pipeline
    pipe_result = run_pipeline(klines, levels, price)
    log(f"管线阶段: {pipe_result['stage']} · 得分 {pipe_result['score']}")
    
    # FVG
    fvgs = detect_fvg(klines[-50:])
    update_fvg_status(fvgs, price, klines[-50:])
    best = best_fvg(fvgs) if fvgs else None
    fvg_note = f"· {len(fvgs)}个FVG" + (f" · 最佳@{best['midpoint']}" if best else "")
    log(f"FVG: {len(fvgs)}个{fvg_note}")
    
    # OB
    obs = detect_obs(klines[-100:])
    nearest = find_nearest_ob(obs, price)
    ob_note = ""
    if nearest:
        ob_note = f" · OB {nearest['type']} @ {nearest['price']}"
    log(f"OB: {len(obs)}个{ob_note}")
    
    # 注入信号
    enriched = dict(signals)
    if best:
        enriched["fvg"] = {"exists": True, "midpoint": best["midpoint"], "type": best["type"]}
    if nearest:
        enriched["order_block"] = {"near": True, "detail": f"{nearest['type']}@{nearest['price']}"}
    enriched["three_source_align"] = {"aligned": pipe_result.get("score", 0) >= 4}
    
    # 评分
    scoring = score_all(enriched)
    log(f"评分: {scoring['total']}/{scoring['max_possible']} · {scoring['level']} · {len(scoring['converging_signals'])}信号汇聚")
    
    # 事件
    events = get_block_status()
    if events.get("blocked"):
        log(f"⚠ 事件阻塞: {events.get('reason', '')}")
    
    # 判定
    pipe_ready = pipe_result["stage"] == "entry_ready"
    high_score = scoring.get("high_probability", False) or pipe_result.get("score", 0) >= 5
    is_high_prob = pipe_ready or high_score
    
    # 生成推送
    card_lines = []
    card_lines.append(f"**管线 S→{pipe_result['stage']}** · 评分 {scoring['total']}/{scoring['max_possible']} {scoring['level']}")
    card_lines.append(f"现价 `{price:,.0f}`")
    if scoring.get("converging_signals"):
        card_lines.append(f"汇聚: {'·'.join(scoring['converging_signals'][:5])}")
    if best:
        card_lines.append(f"FVG {best['type']}: `{best['bottom']}`→`{best['top']}` 中点`{best['midpoint']}`")
    if nearest:
        card_lines.append(f"OB {nearest['type']}: `{nearest['price']}` 强度{nearest['strength']}/5")
    
    if pipe_ready:
        dir_str = pipe_result.get("direction", "").upper()
        card_lines.append(f"⭐ {dir_str} 入场就绪 @ `{pipe_result['entry_price']}` — 回测FVG")
        card_lines.append(f"确认数: {len(pipe_result['confirmations'])}")
        for c in pipe_result["confirmations"]:
            card_lines.append(f"  [{c['type']}]")
    elif pipe_result["stage"] == "wait_retest":
        card_lines.append(f"等待FVG回测 @ `{pipe_result['entry_price']}`")
    elif pipe_result["stage"] == "wait_sweep":
        card_lines.append("等待流动性扫荡触发")
    else:
        status = pipe_result.get("details", pipe_result.get("stage", "监控中"))
        card_lines.append(f"状态: {status}")
    
    if events.get("blocked"):
        card_lines.append(f"⚠ {events['reason']}")
    elif events.get("next_event"):
        card_lines.append(f"下个事件: {events['next_event']}")
    
    card = "\n".join(card_lines)
    
    # 推送
    _write_pending(card, priority="high" if is_high_prob else "normal")
    if is_high_prob:
        log("🚨 高概率信号 -> 已推送到pending")
    
    # 截图(如果高概率信号)
    screenshot_path = None
    if is_high_prob:
        try:
            log("📸 触发TV截图...")
            result = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, "tv_screenshot.py"), "BTCUSDT", "15"],
                capture_output=True, text=True, timeout=25,
            )
            for line in result.stdout.strip().split("\n"):
                if "✅" in line:
                    spath = line.replace("✅ ", "").strip()
                    if os.path.exists(spath):
                        screenshot_path = spath
                        log(f"✅ 截图: {spath}")
                    break
        except Exception as e:
            log(f"⚠ 截图失败: {e}")
    
    # 写状态
    state = _read_json(STATE_FILE)
    update_state(state, "last_pipeline", pipe_result["stage"])
    update_state(state, "last_score", scoring["total"])
    update_state(state, "last_level", scoring["level"])
    update_state(state, "high_probability", is_high_prob)
    update_state(state, "fvg_count", len(fvgs))
    update_state(state, "ob_count", len(obs))
    update_state(state, "price", price)
    update_state(state, "screenshot", screenshot_path or "")
    
    log(f"管线完成: {pipe_result['stage']} · {scoring['total']}pt · {scoring['level']}")
    return {"pipeline": pipe_result, "scoring": scoring, "screenshot": screenshot_path}


def main():
    log("🚀 BTC管线守护启动 · 间隔{PIPELINE_INTERVAL}s")
    
    last_pipeline = 0
    last_screenshot = 0
    cycle_count = 0
    
    if ONESHOT_TRIGGER:
        log("首次触发管线...")
        run_pipeline_cycle()
        last_pipeline = now_ts()
        last_screenshot = now_ts()
    
    while True:
        try:
            now = now_ts()
            
            # 管线循环 (每3分钟)
            if now - last_pipeline >= PIPELINE_INTERVAL:
                run_pipeline_cycle()
                last_pipeline = now
            
            # 定期截图 (每5分钟, 仅当有活跃信号)
            if now - last_screenshot >= SCREENSHOT_INTERVAL:
                state = _read_json(STATE_FILE)
                if state.get("high_probability") or state.get("last_score", 0) >= 6:
                    log("📸 定期截图...")
                    try:
                        result = subprocess.run(
                            [sys.executable, os.path.join(SCRIPTS, "tv_screenshot.py"), "BTCUSDT", "15"],
                            capture_output=True, text=True, timeout=25,
                        )
                        for line in result.stdout.strip().split("\n"):
                            if "✅" in line:
                                spath = line.replace("✅ ", "").strip()
                                if os.path.exists(spath):
                                    state = _read_json(STATE_FILE)
                                    state["screenshot"] = spath
                                    _write_json(STATE_FILE, state)
                                    log(f"✅ 截图: {spath}")
                                break
                    except Exception as e:
                        log(f"⚠ 截图失败: {e}")
                else:
                    log("无活跃信号，跳过截图")
                last_screenshot = now
            
            cycle_count += 1
            if cycle_count % 20 == 0:
                log(f"运行中 (管线{PIPELINE_INTERVAL}s · 截图{SCREENSHOT_INTERVAL}s)")
            
            time.sleep(10)  # 主循环10s
        
        except KeyboardInterrupt:
            log("停止")
            break
        except Exception as e:
            log(f"循环错误: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
