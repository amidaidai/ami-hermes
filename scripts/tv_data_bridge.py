#!/usr/bin/env python3
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -*- coding: utf-8 -*-
"""
TV数据桥 v1.0 — 行情守望内嵌TV数据采集。

用法:
  python tv_data_bridge.py              # 更新cache，无输出（正常）
  python tv_data_bridge.py --alert      # 等级A/X时输出一行（供警报）

CLI依赖: tools/tradingview-mcp/src/cli/index.js (tv命令)
TV需以CDP模式运行 (端口9222)，否则fallback到已有cache。

采集: tv values + tv data tables + tv data lines + tv quote
缓存: data/tv_dmi_cache.json
"""

import subprocess, json, re, sys, os, time, threading
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta

from atomic_json import atomic_write_json

TZ = timezone(timedelta(hours=8))
ROOT = Path(os.environ.get("HERMES_ROOT", "D:/Hermes agent"))
TV_CLI = ROOT / "tools" / "tradingview-mcp" / "src" / "cli" / "index.js"
CACHE = ROOT / "data" / "tv_dmi_cache.json"
TV_LOCK = ROOT / "data" / ".tv_collection.lock"
TV_LOCK_STALE_SECONDS = 300
_LOCK_LOCAL = threading.local()


@contextmanager
def tv_collection_lock(timeout: float = 30.0):
    """Serialize shared TradingView chart mutations across BTC/XAU jobs."""
    depth = getattr(_LOCK_LOCAL, "depth", 0)
    if depth:
        _LOCK_LOCAL.depth = depth + 1
        try:
            yield
        finally:
            _LOCK_LOCAL.depth -= 1
        return
    deadline = time.monotonic() + timeout
    acquired = False
    while time.monotonic() < deadline:
        try:
            TV_LOCK.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(TV_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n".encode())
            os.close(fd)
            acquired = True
            break
        except FileExistsError:
            try:
                owner_alive = False
                owner = ""
                try:
                    owner = TV_LOCK.read_text(encoding="utf-8").strip().splitlines()[0]
                    if owner.isdigit() and int(owner) != os.getpid():
                        os.kill(int(owner), 0)
                        owner_alive = True
                except (FileNotFoundError, IndexError, OSError, ValueError, SystemError):
                    owner_alive = False
                stale = time.time() - TV_LOCK.stat().st_mtime > TV_LOCK_STALE_SECONDS
                if not owner_alive and (stale or owner):
                    TV_LOCK.unlink()
                    continue
            except OSError:
                pass
            time.sleep(0.1)
    if not acquired:
        raise TimeoutError("TradingView shared chart lock timeout")
    _LOCK_LOCAL.depth = 1
    try:
        yield
    finally:
        _LOCK_LOCAL.depth = 0
        try:
            TV_LOCK.unlink()
        except FileNotFoundError:
            pass


def _norm_symbol_for_cache(symbol: str) -> str:
    """归一化品种标识，供跨缓存品种门禁比对。"""
    s = str(symbol or "").upper()
    # 交易所前缀不属于品种身份；兼容NASDAQ/BATS/CME/NYMEX等所有市场。
    s = s.split(":")[-1]
    s = s.replace(".P", "")
    return s

# ═══ 报警阈值 ═══
ALERT_GRADES = {"A多", "A空", "X"}  # 只有这三个等级触发警报


def _tv(*args, timeout=15):
    """调用 tv CLI。返回(stdout, success)。"""
    try:
        cp = subprocess.run(
            ["node", str(TV_CLI)] + list(args),
            cwd=str(ROOT / "tools" / "tradingview-mcp"),
            capture_output=True, text=True, timeout=timeout
        )
        return cp.stdout.strip(), cp.returncode == 0
    except subprocess.TimeoutExpired:
        return "", False
    except FileNotFoundError:
        return "", False


def _tv_json(*args, timeout=15):
    """调用 tv CLI 并解析JSON。"""
    out, ok = _tv(*args, timeout=timeout)
    if not ok or not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    return data if data.get("success", False) else None


def _num(v):
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)):
            return float(v)
        text = str(v).replace("−", "-").replace(",", "")
        text = text.replace("\u202f", "").replace("\u00a0", "").replace(" ", "").strip()
        match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))([KMBkmb])?", text)
        if not match:
            return None
        value = float(match.group(1))
        multiplier = {"K": 1_000.0, "M": 1_000_000.0, "B": 1_000_000_000.0}.get(
            (match.group(2) or "").upper(), 1.0
        )
        return value * multiplier
    except ValueError:
        return None


def tv_available():
    """检查TV是否可连接。"""
    data = _tv_json("status", timeout=5)
    return bool(data and data.get("cdp_connected"))


EVIDENCE_VERSION = 20260905


def _evidence_integer(value):
    """Exact Data Window integer; K/M/B/T display rounding loses flag digits."""
    from decimal import Decimal, InvalidOperation

    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip().replace("−", "-")
    # TradingView can group digits with commas or narrow/no-break spaces.
    if not re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:[,\u202f\u00a0][0-9]{3})+)(?:\.0+)?", text):
        return None
    try:
        number = Decimal(text.replace(",", "").replace("\u202f", "").replace("\u00a0", ""))
        return int(number) if 0 <= number < 2 ** 53 else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def _read_evidence(data):
    """Decode only an unambiguous main SVP source; never borrow chart identity."""
    studies = data.get("studies")
    if not isinstance(studies, list):
        return {}
    main = [s for s in studies if isinstance(s, dict)
            and isinstance(s.get("name"), str)
            and re.match(r"^SVP(?:$|[+\s])", s["name"], re.IGNORECASE)]
    if len(main) != 1 or not isinstance(main[0].get("values"), dict):
        return {}
    study = main[0]
    fields = {}
    for title, value in study["values"].items():
        if not isinstance(title, str):
            continue
        match = re.fullmatch(r"MCP Evidence (Pack|Bar Time|Close Time)(?: \([^\n]*\))?", title)
        if match:
            field = match.group(1)
            if field in fields:
                return {}  # Ambiguous titles must not be last-write-wins.
            fields[field] = _evidence_integer(value)
    pack = fields.get("Pack")
    if pack is None:
        return {}
    version, digits = divmod(pack, 10000)
    direction, digits = divmod(digits, 1000)
    location, digits = divmod(digits, 100)
    trigger, closed = divmod(digits, 10)
    if version != EVIDENCE_VERSION or direction not in (0, 1, 2) or any(
            flag not in (0, 1) for flag in (location, trigger, closed)):
        return {}
    result = {
        "mcp_evidence_version": version,
        "mcp_evidence_direction": direction - 1,
        "mcp_location_valid": bool(location),
        "mcp_trigger_confirmed": bool(trigger),
        "mcp_bar_closed": bool(closed),
    }
    bar, close = fields.get("Bar Time"), fields.get("Close Time")
    if bar and close and close > bar:
        result["mcp_evidence_bar_time"] = bar
        result["mcp_evidence_close_time"] = close
    # Current values transport omits all three. Do not use the requested symbol,
    # a separate state read, or the study display name as evidence identity.
    symbol = data.get("symbol")
    if isinstance(symbol, str) and symbol.strip() and symbol.strip().upper() not in (
            "0", "UNKNOWN", "NULL", "NONE", "N/A"):
        result["mcp_evidence_symbol"] = symbol
    timeframe = data.get("timeframe", data.get("resolution"))
    if not isinstance(timeframe, bool) and isinstance(timeframe, (str, int)) and re.fullmatch(
            r"(?:[1-9][0-9]*[SDWM]?|[DWM])", str(timeframe)):
        result["mcp_evidence_timeframe"] = str(timeframe)
    study_id = study.get("id")
    if isinstance(study_id, str) and study_id.strip() and study_id.strip().upper() not in (
            "0", "UNKNOWN", "NULL", "NONE", "N/A"):
        result["mcp_evidence_study_id"] = study_id
    return result


_CONTRACT_DW_LOOKUP = None


def _contract_dw_aliases():
    """DW 原名 → 内部 snake_case 键，取自 scripts/tv_indicator_contract.py。

    契约缺失时返回空表：宁可少几个别名，也不能让指标读取整体失败。
    """
    global _CONTRACT_DW_LOOKUP
    if _CONTRACT_DW_LOOKUP is None:
        table = {}
        try:
            import tv_indicator_contract as _TVC
            merged = {}
            merged.update(getattr(_TVC, "DW_ALIASES_MAIN", {}) or {})
            merged.update(getattr(_TVC, "DW_ALIASES_SUB", {}) or {})
            merged.update(getattr(_TVC, "LEGACY_DW_ALIASES_SUB", {}) or {})
            for src, dw in merged.items():
                table[dw] = src
                table[dw.split(" (")[0]] = src   # 允许不带括号后缀的短名
        except Exception:
            pass
        _CONTRACT_DW_LOOKUP = table
    return _CONTRACT_DW_LOOKUP


def read_indicators(symbol=None):
    """读取指标值：VWAP/EMA/CVD/POC/VAH/VAL等。

    symbol 给定时 --symbol 直读目标品种，避免图表停在别的品种污染。
    """
    args = ["values"]
    if symbol:
        args += ["--symbol", symbol]
    data = _tv_json(*args, timeout=15)
    if not isinstance(data, dict):
        return {}
    indicators = {}
    studies = data.get("studies")
    if not isinstance(studies, list):
        return {}
    for study in studies:
        if not isinstance(study, dict) or not isinstance(study.get("values"), dict):
            continue
        for key, val in study["values"].items():
            if not isinstance(key, str):
                continue
            norm = key.lower().replace(" ", "_")
            # Evidence may only enter through the validated main-study decoder.
            # Generic aliases must not leak malformed or foreign packed flags.
            if norm.startswith("mcp_evidence_") or norm in (
                    "mcp_location_valid", "mcp_trigger_confirmed", "mcp_bar_closed"):
                continue
            indicators[norm] = val
            # v13：契约驱动的稳定别名（覆盖带括号/百分号/中文后缀的 DW 名）。
            # 必须跳过 evidence 前缀 —— 那是 _read_evidence() 专属，
            # 不能让通用别名把未校验的证据标志漏进缓存。
            _aliases = _contract_dw_aliases()
            _hit = _aliases.get(key) or _aliases.get(key.split(" (")[0])
            if _hit and not _hit.startswith("mcp_evidence_"):
                indicators[_hit] = val
            # 带公式说明的 Data Window 标题需要稳定别名，避免下游无法命中。
            if key.startswith("MCP StructPack"):
                indicators["mcp_struct_pack"] = val
            elif key.startswith("MCP Risk Pack"):
                indicators["mcp_risk_pack"] = val
            elif key.startswith("MCP EMA Length "):
                indicators[key.lower().replace(" ", "_")] = val
            elif key.startswith("MCP CVD Method Code"):
                indicators["mcp_cvd_method_code"] = val
            elif key == "OI Change % (Normalized)":
                indicators["oi_change_pct_normalized"] = val
            elif key == "HALDRO Risk Code":
                indicators["haldro_risk_code"] = val
            elif key == "HALDRO Valid Code":
                indicators["haldro_valid_code"] = val
    indicators.update(_read_evidence(data))
    return indicators


def read_dmi_table(symbol=None):
    """读取行动格/决策表。symbol 给定时 --symbol 直读。"""
    args = ["data", "tables", "--study-filter", "SVP"]
    if symbol:
        args += ["--symbol", symbol]
    data = _tv_json(*args, timeout=15)
    if not data:
        return {}
    table = {}
    for study in data.get("studies", []):
        for tbl in study.get("tables", []):
            for row in tbl.get("rows", []):
                if "|" in row:
                    key, val = row.split("|", 1)
                    table[key.strip()] = val.strip()
    return table


def read_pine_lines(symbol=None):
    """读取Pine绘制线（关键位）。symbol 给定时 --symbol 直读。"""
    args = ["data", "lines", "--study-filter", "SVP"]
    if symbol:
        args += ["--symbol", symbol]
    data = _tv_json(*args, timeout=15)
    if not data:
        return []
    levels = []
    for study in data.get("studies", []):
        for price in study.get("horizontal_levels", []):
            levels.append({"label": "level", "price": price})
    return levels


def read_quote(symbol="BINANCE:BTCUSDT.P"):
    """读取实时报价。"""
    out, ok = _tv("quote", "--symbol", symbol, timeout=10)
    if not ok:
        return None
    try:
        payload = json.loads(out)
        if isinstance(payload, dict):
            value = payload.get("last") or payload.get("close") or payload.get("price")
            parsed = _num(value)
            if parsed is not None and parsed > 0:
                return parsed
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    try:
        parsed = _num(out.strip().split()[-1])
        return parsed if parsed and parsed > 0 else None
    except (IndexError, TypeError, ValueError):
        return None


def read_state_symbol():
    """v9.6 修复 XAU/BTC 缓存交叉污染：读 chart_get_state 真实 symbol。

    旧实现硬编码 symbol=BINANCE:BTCUSDT.P，导致当前图表停在 OANDA:XAUUSD
    时，XAU 的 POC/VAH/VAL 被错标成 BTC symbol 写进 tv_dmi_cache.json，
    auto_card BTC 分支直接采信 → BTC 卡被 XAU 价位污染（P0 复发）。
    """
    data = _tv_json("state", timeout=10)
    if not data:
        return None
    sym = data.get("symbol") or data.get("ticker") or ""
    return sym.strip() or None


def ensure_expected_symbol(expect_symbol: str, attempts: int = 5) -> bool:
    """先切到目标品种，再用chart state验证；禁止给当前图数据强贴目标symbol。"""
    if not expect_symbol:
        return True
    _out, ok = _tv("symbol", expect_symbol, timeout=20)
    if not ok:
        return False
    expected = _norm_symbol_for_cache(expect_symbol)
    for _ in range(max(1, attempts)):
        current = read_state_symbol()
        if current and _norm_symbol_for_cache(current) == expected:
            return True
        time.sleep(1)
    return False


def load_cache():
    """加载已有缓存。"""
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except:
            pass
    return {}


def save_cache(data):
    """写入缓存。"""
    atomic_write_json(CACHE, data)


def _collect_and_cache_locked(alert_mode=False, expect_symbol=None):
    """
    采集TV数据 → 写缓存。

    alert_mode=True: 仅在等级为A多/A空/X时输出一行。
    alert_mode=False: 静默写入，零stdout。
    expect_symbol: 期望品种（如 "BINANCE:BTCUSDT.P"）。传入时通过 --symbol
        直读目标品种，彻底绕开"图表当前停在别的品种"导致的交叉污染，
        不再依赖全局图表状态。读不到目标品种有效数据时回退旧缓存并标 stale。
    """
    if not tv_available():
        return None

    # CLI values/data 的 --symbol 在部分TradingView版本中不会切换图表，却会让
    # 下游误以为读到了目标品种。必须先真实切图并校验state，再读当前图。
    if expect_symbol and not ensure_expected_symbol(expect_symbol):
        old = load_cache()
        if old:
            old["fresh"] = False
            old["stale"] = True
            return old
        return None
    if expect_symbol:
        # 自定义Pine在切品种后需要时间完成Data Window/行动格重算。
        time.sleep(3)
    read_sym = None

    indicators = read_indicators(read_sym)
    dmi = read_dmi_table(read_sym)
    lines = read_pine_lines(read_sym)
    quote = read_quote(expect_symbol or "BINANCE:BTCUSDT.P")

    if expect_symbol:
        current = read_state_symbol()
        if not current or _norm_symbol_for_cache(current) != _norm_symbol_for_cache(expect_symbol):
            old = load_cache()
            if old:
                old["fresh"] = False
                old["stale"] = True
                return old
            return None

    # 品种门禁（兼容无 expect_symbol 的旧路径：仍读全局图表状态比对）
    if not expect_symbol:
        real_symbol = read_state_symbol()
        if real_symbol and _norm_symbol_for_cache(real_symbol) != _norm_symbol_for_cache("BINANCE:BTCUSDT.P"):
            old = load_cache()
            if old:
                old.setdefault("stale", True)
                save_cache(old)
                return old
            return None

    grade = dmi.get("等级", dmi.get("grade", "?"))
    old_cache = load_cache()
    old_grade = old_cache.get("grade", "")

    # A chart can return generic Volume/Plot values while the required SVP
    # study is absent or still recalculating.  Do not stamp that partial read
    # as fresh TV authority.  Keep an old cache only as explicitly stale data.
    main_indicator_keys = {
        "poc_price", "vah_price", "val_price", "s_vwap", "mcp_side_code",
        "mcp_grade_code", "mcp_setup_score", "mcp_entry_price",
    }
    has_main_indicator = bool(main_indicator_keys.intersection(indicators))
    if not dmi and not has_main_indicator:
        if old_cache:
            old_cache["fresh"] = False
            old_cache["stale"] = True
            old_cache["stale_reason"] = "SVP主指标行动格/Data Window缺失"
            save_cache(old_cache)
            return old_cache
        return None
    required_action_rows = {"结论", "方向", "路径", "风控"}
    action_table_complete = required_action_rows.issubset(set(dmi))
    if not action_table_complete or quote is None:
        reason = "SVP行动格核心行或真实报价缺失"
        if old_cache:
            old_cache["fresh"] = False
            old_cache["stale"] = True
            old_cache["stale_reason"] = reason
            save_cache(old_cache)
            return old_cache
        return None

    # 构建缓存
    poc = _num(indicators.get("poc_price"))
    vah = _num(indicators.get("vah_price"))
    val = _num(indicators.get("val_price"))
    action_grid = {}
    for lvl in lines:
        lbl = str(lvl.get("label", "")).upper()
        p = lvl.get("price")
        if "POC" in lbl and poc is None: poc = p
        elif "VAH" in lbl and vah is None: vah = p
        elif "VAL" in lbl and val is None: val = p
    for k, v in dmi.items():
        kc = str(k).strip()
        if kc in ("结论", "方向", "进场", "止损", "目标", "核对", "磁吸↑", "磁吸↓"):
            action_grid[kc] = str(v).strip()

    # 直读失败时回退旧缓存并标 stale，避免下游误用空/错数据
    if not indicators and not dmi and old_cache:
        old_cache.setdefault("stale", True)
        save_cache(old_cache)
        return old_cache

    cache = {
        "timestamp": datetime.now(TZ).isoformat(),
        "symbol": expect_symbol or read_state_symbol() or "UNKNOWN",
        "fresh": True,
        "stale": False,
        "grade": grade,
        "last_price": quote,
        "decision_table": dmi,
        "indicators": indicators,
        "key_levels": lines,
        "source": "tv_data_bridge",
        "poc": poc,
        "vah": vah,
        "val": val,
        "action_grid": action_grid,
        "identity_valid": True,
        "action_table_complete": action_table_complete,
        "source_quality": "A",
        "source_quality_reason": "symbol/timeframe gate and core action rows passed",
    }
    save_cache(cache)

    # 警报模式：仅等级变化(A/X)时输出
    if alert_mode and grade in ALERT_GRADES:
        if grade != old_grade or old_cache.get("source") != "tv_data_bridge":
            treatment = dmi.get("处理", dmi.get("treatment", "?"))
            cvd_state = dmi.get("CVD", dmi.get("cvd", "?"))
            position = dmi.get("位置", dmi.get("position", "?"))
            price_str = f" `{quote}`" if quote else ""
            print(f"🚨 TV DMI: {grade} · {treatment} · CVD{cvd_state} · {position}{price_str}")

    return cache


def collect_and_cache(alert_mode=False, expect_symbol=None):
    """Collect one complete chart read under the shared-chart lease."""
    with tv_collection_lock():
        return _collect_and_cache_locked(alert_mode=alert_mode, expect_symbol=expect_symbol)


if __name__ == "__main__":
    result = collect_and_cache(alert_mode="--alert" in sys.argv)
    if result is None:
        print("tv cache refresh failed: TradingView CDP unavailable")
        sys.exit(1)
