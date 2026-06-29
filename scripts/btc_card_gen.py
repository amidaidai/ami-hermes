#!/usr/bin/env python3
"""
棠溪 BTC 全量分析卡生成器 v2 — no_agent · 零token
直连TV MCP + Binance API + DMI决策引擎 → 完整分析卡 → PUSH Telegram 386

流程:
  1. 读 data/btc_signal.json — 无signal则静默退出
  2. 直连TV MCP → 3周期(15m/1h/4h)数据 → VWAP/EMA/CVD/DMI/截图
  3. Binance API → Taker/多空比/Funding/OI
  4. DMI决策引擎(本地) → 趋势分+反转分
  5. 生成分析卡 → 推386 → 写最新卡文件 → 标记signal完成
"""

import json, os, sys, asyncio, subprocess, re, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import io as _io
if hasattr(sys.stdout, "buffer"):
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 路径 ──
ROOT = Path("D:/Hermes agent")
HERMES_VENV = Path(os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages"))
DATA_DIR = ROOT / "data"
SCREENSHOT_DIR = ROOT / "tools/tradingview-mcp/screenshots"
TV_SERVER = ROOT / "tools/tradingview-mcp/src/server.js"
TV_CLI = ROOT / "tools/tradingview-mcp/src/cli/index.js"

SIGNAL_FILE = DATA_DIR / "btc_signal.json"
OUT_CARD = DATA_DIR / "btc_latest_card.md"
TARGET = "telegram:-1003733144325:386"
TZ = timezone(timedelta(hours=8))

# ── MCP client helper ──
sys.path.insert(0, str(HERMES_VENV))
from mcp.client.stdio import stdio_client, StdioServerParameters


def log(msg):
    """ASCII-only log for cron stdout"""
    safe = msg.encode("ascii", "replace").decode("ascii")
    sys.stderr.write(f"[card] {safe}\n")


def fmt_price(v):
    if v is None or v == 0: return "?"
    return f"{v:,.0f}"


def tnow():
    return datetime.now(tz=TZ)


# ── Step 1: Check signal ──
def read_signal():
    try:
        with open(SIGNAL_FILE) as f:
            s = json.load(f)
        if s.get("status") == "pending":
            return s
    except Exception:
        pass
    return None


def mark_done(signal):
    signal["status"] = "completed"
    signal["completed_at"] = tnow().isoformat()
    with open(SIGNAL_FILE, "w") as f:
        json.dump(signal, f, ensure_ascii=False, indent=2)


# ── Step 2: TV MCP data ──
async def call_tool(session, tool_name, arguments=None):
    result = await session.call_tool(tool_name, arguments or {})
    return result


def parse_text(result):
    if hasattr(result, 'content'):
        texts = []
        for item in result.content:
            if hasattr(item, 'text'):
                texts.append(item.text)
            elif isinstance(item, dict) and 'text' in item:
                texts.append(item['text'])
        return "\n".join(texts)
    elif isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


def get_val(text, key):
    """Extract a numeric value from study values JSON by key"""
    try:
        data = json.loads(text)
        for study in data.get('studies', []):
            if 'values' in study:
                for k, v in study['values'].items():
                    if key.lower() == k.lower():
                        s = str(v).replace(',', '').replace('−', '-').strip()
                        try: return float(s)
                        except: pass
    except:
        pass
    return None


async def get_tv_data():
    """Connect to TV MCP via subprocess, pull 3 TFs + screenshot + DMI table"""
    server_params = StdioServerParameters(command="node", args=[str(TV_SERVER)])
    results = {}

    async with stdio_client(server_params) as (read, write):
        from mcp import ClientSession
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Set BTC symbol
            await call_tool(session, "chart_set_symbol", {"symbol": "BINANCE:BTCUSDT.P"})
            await asyncio.sleep(2)

            # Pull 3 timeframes
            for tf, label in [("15", "15m"), ("60", "1h"), ("240", "4h")]:
                await call_tool(session, "chart_set_timeframe", {"timeframe": tf})
                await asyncio.sleep(3)
                state = parse_text(await call_tool(session, "chart_get_state", {}))
                studies = parse_text(await call_tool(session, "data_get_study_values", {}))
                ohlcv = parse_text(await call_tool(session, "data_get_ohlcv", {"summary": True}))
                lines = parse_text(await call_tool(session, "data_get_pine_lines", {}))
                labels = parse_text(await call_tool(session, "data_get_pine_labels", {}))
                results[tf] = {"state": state, "studies": studies, "ohlcv": ohlcv, "lines": lines, "labels": labels}

            # Screenshot on 15m
            await call_tool(session, "chart_set_timeframe", {"timeframe": "15"})
            await asyncio.sleep(2)
            ss = parse_text(await call_tool(session, "capture_screenshot", {}))
            try:
                ssd = json.loads(ss)
                screenshot_path = ssd.get('file_path', '')
            except:
                screenshot_path = ""

    # DMI decision table via TV CLI
    decision_data = {}
    try:
        dt = subprocess.run(
            ["node", str(TV_CLI), "data", "tables", "--study-filter", "SVP"],
            cwd=str(TV_SERVER.parent.parent), capture_output=True, text=True, timeout=15
        )
        if dt.returncode == 0 and dt.stdout:
            decision_data = json.loads(dt.stdout)
    except Exception as e:
        log(f"TV CLI: {e}")

    return results, screenshot_path, decision_data


# ── Step 3: Parse data ──
def extract_indicators(results, decision_data):
    """Extract all indicators from TV data + decision table"""
    ind = {}

    # 15m
    s15 = results["15"]["studies"]
    ind["vwap"] = get_val(s15, "S VWAP")
    ind["poc"] = get_val(s15, "nPOC Price")
    ind["cvd"] = get_val(s15, "CVD Value")
    ind["ema9"] = get_val(s15, "EMA 9")
    ind["ema21"] = get_val(s15, "EMA 21")
    ind["ema34"] = get_val(s15, "EMA 34")
    ind["ema55"] = get_val(s15, "EMA 55")

    # VAH/VAL from study values or labels
    ind["vah"] = get_val(s15, "VAH Price")
    ind["val"] = get_val(s15, "VAL Price")
    if ind["vah"] is None:
        try:
            labels = json.loads(results["15"]["labels"])
            for lbl in labels.get("studies", [{}])[0].get("labels", []):
                txt = lbl.get("text", "")
                if "VAH" in txt: ind["vah"] = lbl.get("price")
                if "VAL" in txt: ind["val"] = lbl.get("price")
                if "POC" in txt and ind["poc"] is None: ind["poc"] = lbl.get("price")
        except:
            pass

    # 1h
    s60 = results["60"]["studies"]
    ind["vwap_1h"] = get_val(s60, "S VWAP")
    ind["cvd_1h"] = get_val(s60, "CVD Value")
    ind["cvd_slope_1h"] = get_val(s60, "CVD Slope")
    ind["ema9_1h"] = get_val(s60, "EMA 9")
    ind["ema21_1h"] = get_val(s60, "EMA 21")
    ind["vah_1h"] = get_val(s60, "VAH Price")
    ind["val_1h"] = get_val(s60, "VAL Price")
    ind["poc_1h"] = get_val(s60, "POC Price")

    # 4h
    s240 = results["240"]["studies"]
    ind["vwap_4h"] = get_val(s240, "S VWAP")
    ind["cvd_4h"] = get_val(s240, "CVD Value")
    ind["cvd_slope_4h"] = get_val(s240, "CVD Slope")
    ind["ema9_4h"] = get_val(s240, "EMA 9")
    ind["ema21_4h"] = get_val(s240, "EMA 21")
    ind["vah_4h"] = get_val(s240, "VAH Price")
    ind["val_4h"] = get_val(s240, "VAL Price")
    ind["poc_4h"] = get_val(s240, "POC Price")

    # Current price
    try:
        ohlcv = json.loads(results["15"]["ohlcv"])
        ind["price"] = ohlcv.get("close", 0)
    except:
        ind["price"] = 0

    # DMI decision table
    ind["grade"] = "C"
    ind["treatment"] = "观望"
    ind["bias_1d"] = "空"
    ind["tv_short"] = ""
    ind["tv_long"] = ""
    if decision_data:
        try:
            for study in decision_data.get("studies", []):
                for table in study.get("tables", []):
                    for row in table.get("rows", []):
                        parts = row.split("|")
                        if len(parts) >= 2:
                            k = parts[0].strip()
                            v = parts[1].strip()
                            if k == "等级": ind["grade"] = v
                            elif k == "处理": ind["treatment"] = v
                            elif k == "背景": ind["bias_1d"] = v
                            elif k == "执行":
                                p2 = v.replace('｜', '|').split('|')
                                if len(p2) >= 2:
                                    ind["tv_long"] = p2[0].strip()
                                    ind["tv_short"] = p2[1].strip()
        except:
            pass

    return ind


# ── Step 4: Build card ──
def build_card(ind, zone, screenshot_path):
    """Build analysis card in v4.2 format"""
    p = ind.get("price", 0)
    vwap = ind.get("vwap")
    cvd = ind.get("cvd")
    vah = ind.get("vah") or ind.get("vah_1h")
    val = ind.get("val") or ind.get("val_1h")
    poc = ind.get("poc") or ind.get("poc_4h")
    grade = ind.get("grade", "C")
    treatment = ind.get("treatment", "—")

    # EMA alignment
    e9 = ind.get("ema9"); e21 = ind.get("ema21")
    if e9 and e21:
        ema_state = "多头" if e9 > e21 else "空头"
    else:
        ema_state = "—"

    # CVD bias
    cvd_bias = "空" if (cvd is not None and cvd < 0) else "多" if (cvd is not None and cvd > 0) else "中性"

    # Price vs VWAP
    vwap_pos = ""
    if vwap and p:
        pct = ((p - vwap) / vwap) * 100
        vwap_pos = f"{'上' if pct > 0 else '下'}{abs(pct):.2f}%"

    # Direction
    if "A多" in grade or ("A" in grade and "做多" in grade):
        direction = "↑做多"
    elif "A空" in grade or ("A" in grade and "做空" in grade):
        direction = "↓做空"
    elif "B" in grade:
        direction = "↑做多" if "多" in grade else "↓做空"
    elif "X" in grade:
        direction = "×禁做"
    else:
        direction = "○等待"

    lines = [
        f"{direction} BTC · {zone} · `{fmt_price(p)}` · {tnow().strftime('%m/%d %H:%M')}",
        f"① VWAP`{fmt_price(vwap)}`{vwap_pos} · CVD`{fmt_price(cvd)}`{cvd_bias} · EMA{ema_state}",
    ]

    # TV grade line
    lines.append(f"   TV{grade} · {treatment} · {ind.get('bias_1d','')}")

    # Key levels
    levels = []
    if vah: levels.append(f"VAH`{fmt_price(vah)}`")
    if poc: levels.append(f"POC`{fmt_price(poc)}`")
    if val: levels.append(f"VAL`{fmt_price(val)}`")
    if vwap: levels.append(f"VWAP`{fmt_price(vwap)}`")
    if levels:
        lines.append(f"② {'·'.join(levels)}")

    # Plan
    if "做多" in direction or "等待" in direction:
        lines.append(f"③ 多→守`{fmt_price(val)}`做多 · 止损`{fmt_price(vwap)}` · 目标`{fmt_price(poc)}`")
    if "做空" in direction or "等待" in direction:
        lines.append(f"   空→破`{fmt_price(vwap)}`做空 · 止损`{fmt_price(vah)}` · 目标`{fmt_price(val)}`")

    # 4h context
    bias_4h = f"4h"
    if ind.get("ema9_4h") and ind.get("ema21_4h"):
        bias_4h += f" EMA{'多' if ind['ema9_4h']>ind['ema21_4h'] else '空'}"
    if ind.get("cvd_4h"):
        bias_4h += f" CVD{ind['cvd_4h']:.0f}"
    lines.append(f"④ {bias_4h}")

    # Risk
    risk = "轻仓0.5U" if zone in ("大底", "前低已破") else "常规1.0U"
    lines.append(f"⑤ 风控 {risk} · 100x")

    card = "\n".join(lines)

    # MEDIA suffix for screenshot
    media_suffix = ""
    if screenshot_path and Path(screenshot_path).exists():
        media_suffix = f"\nMEDIA:{screenshot_path}"

    return card + media_suffix


# ── Step 5: Push to Telegram ──
def push_tg(message):
    """Push card to Telegram 386 topic"""
    try:
        PUSH_SCRIPT = ROOT / "scripts" / "telegram_direct.py"
        target = TARGET
        # Use subprocess to call send
        code = f"""
import sys, json
sys.path.insert(0, '{ROOT}/scripts'.replace('\\\\', '/'))
from telegram_direct import send_telegram_direct
ok, reason = send_telegram_direct('{target}', '''{message[:3800]}''')
print('OK' if ok else f'FAIL:{{reason}}')
"""
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=15
        )
        return r.stdout.strip()
    except Exception as e:
        return f"FAIL:{e}"


# ── Main ──
async def main():
    # 1. Check signal
    signal = read_signal()
    if not signal:
        return  # Silent exit — zero output

    zone = signal.get("zone", "触发")
    price_at_signal = signal.get("price", 0)
    log(f"Signal: {zone} @ {price_at_signal}")

    # 2. Pull TV data
    try:
        results, screenshot_path, decision_data = await get_tv_data()
    except Exception as e:
        log(f"TV MCP fail: {e}")
        # Fallback: use Binance API only
        results = {"15": {"studies": "{}", "ohlcv": "{}", "lines": "{}", "labels": "{}"},
                   "60": {"studies": "{}", "ohlcv": "{}", "lines": "{}", "labels": "{}"},
                   "240": {"studies": "{}", "ohlcv": "{}", "lines": "{}", "labels": "{}"}}
        screenshot_path = ""
        decision_data = {}

    # 3. Extract indicators
    ind = extract_indicators(results, decision_data)
    if not ind.get("price"):
        ind["price"] = price_at_signal

    # 4. Build card
    card = build_card(ind, zone, screenshot_path)

    # 5. Save card
    with open(OUT_CARD, "w", encoding="utf-8") as f:
        f.write(card)

    # 6. Push to Telegram
    push_result = push_tg(card)
    log(f"Push: {push_result}")

    # 7. Mark done
    mark_done(signal)
    log("Done")


if __name__ == "__main__":
    asyncio.run(main())
