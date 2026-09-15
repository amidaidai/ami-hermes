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
from typing import Any

from atomic_json import atomic_write_json
from chart_evidence import build_chart_evidence, normalize_timeframe, symbol_matches
from binance_public import fetch_futures

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


# ═══════════════════════════════════════════════════════════════════════════
# 交互式分析租约 — 「有人正在看图分析」这件事，后台任务必须看得见
# ═══════════════════════════════════════════════════════════════════════════
# tv_collection_lock 只序列化**后台任务彼此**。交互式分析（对话里直接读行动格 +
# 截图）不持锁，于是后台续航会在读图中途把图切走 —— 实测 2026-09-11 14:07 读 5m
# 时被 btc_tv_refresh 连抢两次，行动格整张读成空表。租约把「分析进行中」变成后台
# 任务可见的事实：有效期内后台切图任务 defer 到下一轮，而不是硬闯。
#
# 契约：租约只影响**后台切图任务的调度**，不改任何数据内容与裁决。
ANALYSIS_LEASE = ROOT / "data" / "tv_analysis_lease.json"
ANALYSIS_LEASE_DEFAULT_MINUTES = 10.0
ANALYSIS_LEASE_MAX_MINUTES = 30.0


def begin_analysis_lease(minutes: float = ANALYSIS_LEASE_DEFAULT_MINUTES, *,
                         note: str = "", symbol: str = "",
                         liveness: str = "ttl") -> dict:
    """声明「交互式分析进行中」。

    TTL 有上限（30 分钟）——分析脚本崩了也不会把后台续航永久锁死。

    liveness（2026-09-14 修）:
      - "ttl"（默认）：**只看 TTL，不看 pid 存活**。这是 CLI `start` / 交互式分析
        的正确语义——`python scripts/tv_analysis_lease.py start` 写完文件就退出，
        旧实现把 pid 记成这个短命进程，consumer 一查 psutil.pid_exists() 就是 False，
        于是租约被判「持有进程已退出」→ 后台任务照旧抢图。
      - "pid"：保留旧的存活性判定，适合真正常驻的持有者（守护进程自持租约）。
    """
    try:
        ttl = float(minutes)
    except (TypeError, ValueError):
        ttl = ANALYSIS_LEASE_DEFAULT_MINUTES
    ttl = max(0.5, min(ANALYSIS_LEASE_MAX_MINUTES, ttl))
    now = datetime.now(TZ)
    mode = "pid" if str(liveness).strip().lower() == "pid" else "ttl"
    payload = {
        "active": True,
        "started_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(minutes=ttl)).isoformat(timespec="seconds"),
        "minutes": ttl,
        "pid": os.getpid(),
        "liveness": mode,
        "note": str(note or "")[:200],
        "symbol": str(symbol or "").upper(),
    }
    try:
        atomic_write_json(ANALYSIS_LEASE, payload)
    except OSError:
        pass
    return payload


def end_analysis_lease() -> dict:
    """释放租约（幂等；不存在也算成功）。"""
    try:
        ANALYSIS_LEASE.unlink()
    except (FileNotFoundError, OSError):
        pass
    return {"active": False}


def read_analysis_lease() -> dict:
    try:
        data = json.loads(ANALYSIS_LEASE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _lease_holder_alive(pid) -> bool | None:
    """True=持有进程还在；False=已死；None=无法判断（保持 TTL 判定）。"""
    try:
        pid_i = int(pid)
    except (TypeError, ValueError):
        return False
    if pid_i <= 0:
        return False
    try:
        import psutil
        return bool(psutil.pid_exists(pid_i))
    except Exception:
        return None


def analysis_lease_status(now=None) -> dict:
    """租约状态。文件缺失 / active 非真 / 已过期 / （pid 模式）持有进程已死，一律视为「无分析」。

    2026-09-14：`liveness == "ttl"`（默认，CLI/交互式分析写入）**跳过 pid 存活判定**，
    只看 TTL。原因见 begin_analysis_lease 文档 —— CLI 进程写完即退，旧逻辑把
    有效租约误判为「持有进程已退出」，后台切图任务因此完全不退让。
    """
    data = read_analysis_lease()
    if not data or not data.get("active"):
        return {"active": False, "reason": "无分析租约"}
    try:
        expires = datetime.fromisoformat(str(data.get("expires_at") or ""))
    except ValueError:
        return {"active": False, "reason": "租约时间戳不可解析", "lease": data}
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=TZ)
    current = now or datetime.now(TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=TZ)
    remaining = (expires - current).total_seconds()
    if remaining <= 0:
        return {"active": False, "reason": "租约已过期", "lease": data,
                "remaining_seconds": round(remaining, 1)}
    ttl_only = str(data.get("liveness") or "ttl").strip().lower() != "pid"
    if not ttl_only:
        alive = _lease_holder_alive(data.get("pid"))
        if alive is False:
            return {
                "active": False,
                "reason": "租约持有进程已退出",
                "lease": data,
                "holder_pid": data.get("pid"),
                "remaining_seconds": round(remaining, 1),
            }
    return {
        "active": True,
        "reason": "交互式分析进行中",
        "remaining_seconds": round(remaining, 1),
        "expires_at": expires.isoformat(timespec="seconds"),
        "holder_pid": data.get("pid"),
        "note": data.get("note") or "",
        "symbol": data.get("symbol") or "",
        "lease": data,
    }


def analysis_in_progress() -> bool:
    """后台任务入口处的一个布尔判断：现在要不要让路。"""
    return bool(analysis_lease_status().get("active"))


class AnalysisLeaseActive(RuntimeError):
    """后台切图任务撞上交互式分析租约时抛出；调用方按「本轮让路」处理，不算失败。"""


# ═══ 图表归属（棘轮保护）— BTC / XAU 共用同一套规则 ═══
# 历史缺陷：BTC 侧只把「进入时看到什么」当用户图表。一旦某轮恢复失败（残留周期
# 留在采集用的 TF 上），下一轮就把残留认成用户图表，从此越跑越偏。XAU 侧已修，
# BTC 侧没跟上 —— 同一个 bug 的两份实现漂移。现在收敛到这一处。
CHART_OWNER = ROOT / "data" / "tv_chart_owner.json"


def load_chart_owner() -> dict:
    try:
        data = json.loads(CHART_OWNER.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def save_chart_owner(state: dict) -> None:
    try:
        CHART_OWNER.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(CHART_OWNER, state)
    except OSError:
        pass          # 状态文件写不了也不能阻断采集


def chart_owner_resolve_restore(our_symbol: str, current_symbol: str,
                                current_timeframe: str) -> dict:
    """决定采集结束后该把图表还给谁。

    - 进入时看到**非**本任务品种 → 那是用户的图表，记下来并作为归还目标
    - 进入时已在**本任务品种**上 → 优先用「待归还」记录修回来（打断棘轮）；
      没有待归还记录才认为用户真的在看该品种，保持不动
    """
    our = str(our_symbol or "").strip().upper()
    cur_symbol = str(current_symbol or "").strip()
    cur_timeframe = str(current_timeframe or "").strip()
    state = load_chart_owner()

    if cur_symbol and cur_symbol.upper() != our:
        state["user_symbol"] = cur_symbol
        state["user_timeframe"] = cur_timeframe
        state["pending_restore"] = {"symbol": cur_symbol, "resolution": cur_timeframe}
        state["captured_at"] = datetime.now(TZ).isoformat(timespec="seconds")
        save_chart_owner(state)
        return {"symbol": cur_symbol, "resolution": cur_timeframe}

    pending = state.get("pending_restore") or {}
    pending_symbol = str(pending.get("symbol") or "").strip()
    if pending_symbol and pending_symbol.upper() != our:
        # 上次没还回去 → 用记录修回来，不要顺着残留继续「恢复」成采集品种
        state["ratchet_break_at"] = datetime.now(TZ).isoformat(timespec="seconds")
        state["ratchet_break_from"] = cur_symbol
        save_chart_owner(state)
        return {"symbol": pending_symbol,
                "resolution": str(pending.get("resolution") or "")}

    remembered = str(state.get("user_symbol") or "").strip()
    if remembered and remembered.upper() != our:
        # pending 已被成功归还清掉，但图又被留在采集品种上（失败路径/杀进程）。
        # 记住的用户品种仍在，不能把残留当成「用户真的在看黄金」。
        state["pending_restore"] = {
            "symbol": remembered,
            "resolution": str(state.get("user_timeframe") or ""),
        }
        state["ratchet_break_at"] = datetime.now(TZ).isoformat(timespec="seconds")
        state["ratchet_break_from"] = cur_symbol
        save_chart_owner(state)
        return {
            "symbol": remembered,
            "resolution": str(state.get("user_timeframe") or ""),
        }

    # 用户真的在看本任务品种（或首次运行无记录）→ 保持原样
    return {"symbol": cur_symbol, "resolution": cur_timeframe}


def chart_owner_mark_restored() -> None:
    """归还成功后清掉「待归还」，并记一笔归还时间。"""
    state = load_chart_owner()
    if state.pop("pending_restore", None) is not None:
        state["restored_at"] = datetime.now(TZ).isoformat(timespec="seconds")
        save_chart_owner(state)


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
            merged.update(getattr(_TVC, "LEGACY_DW_ALIASES_MAIN", {}) or {})
            merged.update(getattr(_TVC, "LEGACY_DW_ALIASES_SUB", {}) or {})
            for src, dw in merged.items():
                table[dw] = src
                table[dw.split(" (")[0]] = src   # 允许不带括号后缀的短名
        except Exception:
            pass
        _CONTRACT_DW_LOOKUP = table
    return _CONTRACT_DW_LOOKUP


def _contract_sub_keys() -> frozenset:
    """契约里副指标（AggVol）的 canonical snake_case 键集合。

    用于「只从副研究采副字段」的白名单 —— 副研究不得写入任何主指标字段。
    """
    try:
        import tv_indicator_contract as _TVC
        keys = list(getattr(_TVC, "DW_ALIASES_SUB", {}) or {})
        keys += list(getattr(_TVC, "LEGACY_DW_ALIASES_SUB", {}) or {})
        return frozenset(keys)
    except Exception:
        return frozenset()


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
    sub_keys = _contract_sub_keys()
    for study in studies:
        if not isinstance(study, dict):
            continue
        values = study.get("values")
        if not isinstance(values, dict):
            continue
        is_main = _is_main_study(study)
        for key, val in values.items():
            if not isinstance(key, str):
                continue
            norm = key.lower().replace(" ", "_")
            # Evidence may only enter through the validated main-study decoder.
            # Generic aliases must not leak malformed or foreign packed flags.
            if norm.startswith("mcp_evidence_") or norm in (
                    "mcp_location_valid", "mcp_trigger_confirmed", "mcp_bar_closed"):
                continue
            _aliases = _contract_dw_aliases()
            _hit = _aliases.get(key) or _aliases.get(key.split(" (")[0])
            if is_main:
                indicators[norm] = val
                # v13：契约驱动的稳定别名（覆盖带括号/百分号/中文后缀的 DW 名）。
                # 必须跳过 evidence 前缀 —— 那是 _read_evidence() 专属，
                # 不能让通用别名把未校验的证据标志漏进缓存。
                if _hit and not _hit.startswith("mcp_evidence_"):
                    indicators[_hit] = val
            elif _hit in sub_keys and _is_sub_study(study):
                # 副研究（Volume Aggregated Spot & Futures / HALDRO）：
                # **只**接受契约 SUB 别名，主指标字段与证据标志一律不采 —— 主/副隔离不变。
                # 2026-09-12：此处此前是整段 `if not _is_main_study: continue`，
                # 把 AggVol 的 Composite / HALDRO Valid / CVD / LSR / Coverage
                # 全部丢掉，卡面长期显示「副指标待刷新」。setdefault 保证主研究优先。
                indicators.setdefault(_hit, val)
            # 旧的 startswith 链已删：MCP StructPack / Risk Pack / EMA Length /
            # CVD Method Code / OI Change % / HALDRO * 全部由上面的契约别名覆盖
            # （含「带公式说明的长标题」用 key.split(" (")[0] 命中的短名）。
            # 那是第 4 份手写白名单，正是本文件要终结的漂移来源。
    indicators.update(_read_evidence(data))
    return indicators


def _is_main_study(study):
    """Determine if a study is the main SVP indicator (not a sub-study)."""
    import re as _re
    name = study.get("name", "")
    return bool(name and _re.match(
        r"^SVP(?:$|[+\s])", name, _re.IGNORECASE))


def _is_sub_study(study):
    """是否为副指标（AggVol / HALDRO / Volume Aggregated）研究。

    副字段的来源必须是**具名的副指标研究**，不能是随便一个第三方指标 ——
    否则用户图上任何带 "Composite"/"CVD Value" 字段的研究都可能污染裁决输入。
    """
    import re as _re
    name = str(study.get("name") or "")
    return bool(_re.search(r"(?:AggVol|Aggregated|HALDRO)", name, _re.IGNORECASE))

def read_dmi_table(symbol=None, study_role: str = "main"):
    """读取行动格/决策表。symbol 给定时 --symbol 直读。

    study_role:
      "main"  - 仅返回主 SVP 研究的行动格（副研究不被合并，免止污染）
      "sub"   - 仅返回非主研究的行动格（独立供下游）
    "main" 为默认行为，确保主研究的核心行（结论/方向/路径/风控）不被
    次研究的同名行覆盖。
    "sub" 可由需要独立副表的下游模块使用。
    """
    args = ["data", "tables", "--study-filter", "SVP"]
    if symbol:
        args += ["--symbol", symbol]
    data = _tv_json(*args, timeout=15)
    if not data:
        return {}
    table = {}
    for study in data.get("studies", []):
        if not isinstance(study, dict):
            continue
        if study_role == "main":
            # 只读主 SVP 研究，跳过副研究免止污染
            if not _is_main_study(study):
                continue
        elif study_role == "sub":
            # 只读非主研究（副研究），主研究直接跳过
            if _is_main_study(study):
                continue
        for tbl in study.get("tables", []):
            for row in tbl.get("rows", []):
                if "|" in row:
                    key, val = row.split("|", 1)
                    table[key.strip()] = val.strip()
    return table


def risk_row_label(rows: dict) -> str:
    """Preserve authorization in the row key; mixed snapshots fail closed.

    Uses tv_indicator_contract RISK_ROW_VARIANTS for authoritative label identification.
    Scans in reverse order (most conservative first): 风控 > 风控·观察 > 风控·未授权 > 禁做·不出价.
    """
    from tv_indicator_contract import RISK_ROW_VARIANTS as _RISK_VARIANTS
    return next(
        (label for label in reversed(_RISK_VARIANTS) if label in (rows or {})),
        "",
)


def risk_row_value(rows: dict) -> str:
    """取最保守的风控行；标签与值必须成对消费。"""
    label = risk_row_label(rows)
    return (rows or {}).get(label, "")



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


def read_pine_boxes(symbol=None):
    """读取Pine绘制区域（FVG/OB等）；空结果必须保留为证据缺失。"""
    args = ["data", "boxes", "--study-filter", "SVP"]
    if symbol:
        args += ["--symbol", symbol]
    data = _tv_json(*args, timeout=15)
    if not data:
        return []
    rows = []
    for study in data.get("studies", []):
        # The CLI calls the normalized Pine box collection ``zones`` while
        # older adapters used ``boxes``.  Accept both without inventing a
        # FVG/OB label that the source did not provide.
        collection = study.get("boxes")
        if not isinstance(collection, list):
            collection = study.get("zones", [])
        for box in collection:
            if isinstance(box, dict):
                rows.append(box)
    return rows


def read_pine_labels(symbol=None):
    """读取Pine文字标签（BOS/MSS/流动性等）。"""
    args = ["data", "labels", "--study-filter", "SVP"]
    if symbol:
        args += ["--symbol", symbol]
    data = _tv_json(*args, timeout=15)
    if not data:
        return []
    rows = []
    for study in data.get("studies", []):
        for label in study.get("labels", []):
            if isinstance(label, dict):
                rows.append(label)
    return rows


def read_quote(symbol="BINANCE:BTCUSDT.P"):
    """读取实时报价并保持历史标量返回契约。"""
    payload = read_quote_payload(symbol)
    if isinstance(payload, dict):
        value = payload.get("last") or payload.get("close") or payload.get("price")
        parsed = _num(value)
        if parsed is not None and parsed > 0:
            return parsed
    return None


def read_quote_payload(symbol="BINANCE:BTCUSDT.P"):
    """读取完整报价栏；返回值必须来自同一次CLI响应。"""
    out, ok = _tv("quote", "--symbol", symbol, timeout=10)
    if not ok:
        return None
    try:
        payload = json.loads(out)
        if isinstance(payload, dict):
            return payload
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def read_binance_snapshot(symbol="BTCUSDT") -> dict[str, Any]:
    """Read independent Binance USD-M 24h/mark data for cross-validation."""
    ticker = fetch_futures("/fapi/v1/ticker/24hr", {"symbol": symbol}, timeout=8)
    premium = fetch_futures("/fapi/v1/premiumIndex", {"symbol": symbol}, timeout=8)
    if not isinstance(ticker, dict) or str(ticker.get("symbol", "")).upper() != str(symbol).upper():
        return {"status": "unavailable", "source": "binance_futures"}
    def num(value):
        return _num(value)
    return {
        "status": "live",
        "source": "binance_futures",
        "symbol": str(ticker.get("symbol")).upper(),
        "last_price": num(ticker.get("lastPrice")),
        "open": num(ticker.get("openPrice")),
        "high": num(ticker.get("highPrice")),
        "low": num(ticker.get("lowPrice")),
        "close_time_ms": ticker.get("closeTime"),
        "price_change_pct": num(ticker.get("priceChangePercent")),
        "mark_price": num((premium or {}).get("markPrice")),
        "index_price": num((premium or {}).get("indexPrice")),
        "funding_rate": num((premium or {}).get("lastFundingRate")),
        "next_funding_time_ms": (premium or {}).get("nextFundingTime"),
    }


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


def read_chart_state():
    """返回完整图表身份，不用请求参数猜测当前图。"""
    data = _tv_json("state", timeout=10)
    return data if isinstance(data, dict) else {}


def validate_chart_identity(state: dict, expected_symbol: str,
                            expected_timeframe: str = "") -> tuple[bool, list[str]]:
    """校验品种/周期；失败时调用方必须停止把数据标成实时。"""
    errors = []
    actual_symbol = state.get("symbol") or state.get("ticker")
    actual_tf = normalize_timeframe(state.get("resolution") or state.get("timeframe"))
    if not symbol_matches(actual_symbol, expected_symbol):
        errors.append("symbol_mismatch")
    if expected_timeframe and actual_tf != normalize_timeframe(expected_timeframe):
        errors.append("timeframe_mismatch")
    return not errors, errors


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


def load_cache(symbol=None):
    """加载已有缓存。非 BTC 只读专属文件，避免失败路径把黄金标到 BTC 主缓存。"""
    paths = []
    if symbol and _norm_symbol_for_cache(symbol) != _norm_symbol_for_cache("BINANCE:BTCUSDT.P"):
        paths.append(_symbol_cache_path(symbol))
    else:
        paths.append(CACHE)
        if symbol:
            paths.append(_symbol_cache_path(symbol))
    for path in paths:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    return {}


def quote_payload_matches_expected(payload, expect_symbol: str) -> bool:
    """报价身份必须跟采集目标一致；禁止用 BTC swap 合同卡死黄金。"""
    if not isinstance(payload, dict) or not expect_symbol:
        return False
    quote_sym = str(payload.get("symbol") or payload.get("ticker") or "")
    if not symbol_matches(quote_sym, expect_symbol):
        return False
    norm = _norm_symbol_for_cache(expect_symbol)
    last = _num(payload.get("last") or payload.get("close") or payload.get("price"))
    if "BTCUSDT" in norm:
        return (
            str(payload.get("exchange", "")).upper() == "BINANCE"
            and str(payload.get("type", "")).lower() == "swap"
            and last is not None
            and last > 1000
        )
    if "XAU" in norm:
        qtype = str(payload.get("type", "")).lower()
        exchange = str(payload.get("exchange", "")).upper()
        if exchange == "BINANCE" or qtype == "swap":
            return False
        return last is not None and 1000 < last < 10000
    return last is not None and last > 0


def _symbol_cache_path(symbol) -> Path:
    """按品种归一化出专属缓存路径（与 auto_card._tv_symbol_cache_path 同规则）。

    BINANCE:BTCUSDT.P → data/tv_live_BTCUSDT.json
    OANDA:XAUUSD      → data/tv_live_XAUUSD.json
    """
    raw = str(symbol or "").upper().split(":")[-1]
    if raw.endswith(".P"):
        raw = raw[:-2]
    key = "".join(ch for ch in raw if ch.isalnum())
    if key.endswith("PERP"):
        key = key[:-4]
    return CACHE.with_name(f"tv_live_{key}.json") if key else CACHE


def save_cache(data):
    """写入缓存。

    20260910 修复(P0)：tv_dmi_cache.json 是 **BTC 主缓存**（读取侧按 BTC 品种校验），
    但写入侧原先无条件覆盖它。带 expect_symbol 的调用（如 XAU 采集）不经过旧品种门禁，
    于是把 OANDA:XAUUSD 的数据整份写进 BTC 主缓存 —— 实测该文件里全是黄金价（4374），
    而 BTC 消费者读到后会把黄金当 BTC。现在非 BTC 品种改写各自的 tv_live_{KEY}.json。
    """
    if isinstance(data, dict) and data.get("symbol"):
        sym = _norm_symbol_for_cache(data.get("symbol"))
        canonical = _norm_symbol_for_cache("BINANCE:BTCUSDT.P")
        if sym and sym != canonical:
            atomic_write_json(_symbol_cache_path(data.get("symbol")), data)
            return
    atomic_write_json(CACHE, data)


def _collect_and_cache_locked(alert_mode=False, expect_symbol=None, expected_timeframe=""):
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
        old = load_cache(expect_symbol)
        if old:
            old["fresh"] = False
            old["stale"] = True
            return old
        return None
    chart_state = read_chart_state()
    if not chart_state:
        # Compatibility fallback for older CLI/test doubles.  This proves only
        # the symbol, never the timeframe or full chart evidence.
        fallback_symbol = read_state_symbol()
        if fallback_symbol:
            chart_state = {"symbol": fallback_symbol}
    if expect_symbol:
        identity_ok, identity_errors = validate_chart_identity(
            chart_state, expect_symbol, expected_timeframe)
        if not identity_ok and "symbol_mismatch" in identity_errors:
            # Some legacy CLI state responses contain only a transport shell;
            # retry the narrow symbol read before declaring a mismatch.
            fallback_symbol = read_state_symbol()
            if symbol_matches(fallback_symbol, expect_symbol):
                chart_state = {**chart_state, "symbol": fallback_symbol}
                identity_ok, identity_errors = validate_chart_identity(
                    chart_state, expect_symbol, expected_timeframe)
        if not identity_ok:
            old = load_cache(expect_symbol)
            if old:
                old["fresh"] = False
                old["stale"] = True
                old["stale_reason"] = "TV图表身份不匹配:" + ",".join(identity_errors)
                save_cache(old)
                return old
            return None
        # 自定义Pine在切品种后需要时间完成Data Window/行动格重算。
        time.sleep(3)
        refreshed_state = read_chart_state()
        refreshed_ok, _ = validate_chart_identity(
            refreshed_state, expect_symbol, expected_timeframe
        ) if refreshed_state else (False, [])
        if refreshed_state and (not expect_symbol or refreshed_ok):
            chart_state = refreshed_state
    read_sym = None

    indicators = read_indicators(read_sym)
    dmi = read_dmi_table(read_sym)
    lines = read_pine_lines(read_sym)
    boxes = read_pine_boxes(read_sym)
    labels = read_pine_labels(read_sym)
    # Empty tables/values are commonly a transient recalculation or chart
    # contention signal. Retry only while the real chart identity remains
    # correct; never turn another timeframe's data into a BTC cache.
    for _ in range(3):
        if dmi and indicators:
            break
        time.sleep(5)
        current_state = read_chart_state()
        identity_ok, _ = validate_chart_identity(
            current_state, expect_symbol or "BINANCE:BTCUSDT.P", expected_timeframe
        )
        if not identity_ok:
            break
        indicators = read_indicators(read_sym)
        dmi = read_dmi_table(read_sym)
        lines = read_pine_lines(read_sym)
        boxes = read_pine_boxes(read_sym)
        labels = read_pine_labels(read_sym)
    quote_payload = read_quote_payload(expect_symbol or "BINANCE:BTCUSDT.P")
    quote = None
    if isinstance(quote_payload, dict):
        quote = _num(quote_payload.get("last") or quote_payload.get("close") or quote_payload.get("price"))
    # Compatibility with legacy test doubles/adapters that only implement the
    # scalar read_quote contract.  The full payload remains preferred.
    if quote is None:
        quote = read_quote(expect_symbol or "BINANCE:BTCUSDT.P")
    quote_identity_ok = quote_payload_matches_expected(
        quote_payload, expect_symbol or "BINANCE:BTCUSDT.P"
    )
    if expect_symbol and isinstance(quote_payload, dict) and not quote_identity_ok:
        old = load_cache(expect_symbol)
        if old:
            old["fresh"] = False
            old["stale"] = True
            old["stale_reason"] = "TradingView报价身份不匹配"
            save_cache(old)
            return old
        return None
    expected_norm = _norm_symbol_for_cache(expect_symbol or "BINANCE:BTCUSDT.P")
    if "BTCUSDT" in expected_norm:
        binance_snapshot = read_binance_snapshot("BTCUSDT")
    else:
        binance_snapshot = {
            "status": "skipped",
            "source": "not_applicable",
            "reason": f"{expected_norm}不走加密合约交叉",
        }
    if isinstance(binance_snapshot, dict) and binance_snapshot.get("status") == "live":
        indicators["day_high"] = binance_snapshot.get("high")
        indicators["day_low"] = binance_snapshot.get("low")
        tv_price = float(quote or 0.0)
        bn_price = float(_num(binance_snapshot.get("last_price")) or 0.0)
        if tv_price and bn_price:
            delta_pct = (tv_price - bn_price) / bn_price * 100.0
            binance_snapshot["tv_price_delta_pct"] = delta_pct
            binance_snapshot["cross_status"] = "aligned" if abs(delta_pct) <= 0.25 else "divergent"
        else:
            binance_snapshot["cross_status"] = "unavailable"
    else:
        binance_snapshot = binance_snapshot or {"status": "unavailable"}

    if expect_symbol:
        # Final gate: the chart may be stolen while tables/quote are being
        # read. Revalidate both symbol and timeframe, not symbol alone.
        final_state = read_chart_state()
        final_ok, final_errors = validate_chart_identity(
            final_state or chart_state, expect_symbol, expected_timeframe
        )
        current = (final_state or chart_state).get("symbol") or read_state_symbol()
        if (not final_ok or not current or
                _norm_symbol_for_cache(current) != _norm_symbol_for_cache(expect_symbol)):
            old = load_cache(expect_symbol)
            if old:
                old["fresh"] = False
                old["stale"] = True
                old["stale_reason"] = "TV采集结束时图表身份变化:" + ",".join(final_errors)
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
    old_cache = load_cache(expect_symbol)
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
    # 使用契约权威 risk_row_label 识别合法动态行，保留原标签不越权
    # 既接受明确的 "风控"，也接受带授权后缀的 "风控·未授权" / "风控·观察"
    from tv_indicator_contract import risk_row_label as _risk_label
    detected_risk_label = _risk_label(dmi)
    if not detected_risk_label:
        # 兜底：仍检查硬编码集合（兼容旧缓存）
        required_action_rows = {"结论", "方向", "路径", "风控"}
        action_table_complete = required_action_rows.issubset(set(dmi))
    else:
        # 契约驱动：检测到的风控标签及其核心行必须均存在
        action_table_complete = all(
            k in dmi for k in ("结论", "方向", "路径", detected_risk_label)
        )
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
        "binance_cross_validation": binance_snapshot,
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
        "timeframe": chart_state.get("resolution") or chart_state.get("timeframe"),
        "chart_evidence": build_chart_evidence(
            state=chart_state, quote=quote_payload or quote, indicators=indicators,
            lines=lines, boxes=boxes, labels=labels,
            expected_symbol=expect_symbol or "BINANCE:BTCUSDT.P",
            expected_timeframe=expected_timeframe,
        ),
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


def collect_and_cache(alert_mode=False, expect_symbol=None, expected_timeframe=""):
    """Collect one complete chart read under the shared-chart lease."""
    with tv_collection_lock():
        return _collect_and_cache_locked(
            alert_mode=alert_mode, expect_symbol=expect_symbol,
            expected_timeframe=expected_timeframe)


if __name__ == "__main__":
    result = collect_and_cache(alert_mode="--alert" in sys.argv)
    if result is None:
        print("tv cache refresh failed: TradingView CDP unavailable")
        sys.exit(1)
