#!/usr/bin/env python3
"""棠溪统一凭据读取器：环境变量优先，本地 hermes/secrets 次之。

2026-09-13 加固：识别并拒绝「占位符/说明性注释」文件。

背景事故：`hermes/secrets/oanda_token.txt` 实际是一份**说明性占位符**
（7 行注释 + 一行 `PLACEHOLDER_...`），但 `trading_system.py::oanda_spot_price`
直接 `read_text().strip()` 把它当成真 token 去拼 URL，于是在本机抛
`InvalidURL: URL can't contain control characters`，被 `except Exception: return None`
静默吞掉 —— 表现成「OANDA 不可用」，真实原因是「从未配置」。
两者对排查的含义完全不同，必须在读取层就区分开。

判据（保守，宁可漏判也不误伤真凭据）：
  a) 逐行跳过注释行（`#` / `//` / `;`）与空行后，没有任何剩余内容；
  b) 剩余首行形如 PLACEHOLDER / TODO / CHANGEME / YOUR_ / <...>；
  c) 内容含 CJK 字符 —— 真实 API key/token 一律 ASCII，含中文说明即文档。
命中任一 → 视为未配置，返回空串。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

SECRETS_DIR = Path(__file__).resolve().parents[1] / "hermes" / "secrets"

_COMMENT_PREFIXES = ("#", "//", ";")
_PLACEHOLDER_RE = re.compile(r"^(PLACEHOLDER|TODO|CHANGEME|CHANGE_ME|YOUR[_A-Z]*|<.*>|XXX+)",
                             re.IGNORECASE)
_CJK_RE = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]")
# 一行里若存在较长的 ASCII 字母数字串，就认为它是「承载凭据的行」而非纯说明散文
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{8,}")


def is_placeholder(value: str, filename: str = "") -> tuple[bool, str]:
    """判断一段凭据内容是否其实是「说明/占位符」。返回 (是否, 原因)。"""
    if not value or not value.strip():
        return True, "空内容"
    lines = [ln.strip() for ln in value.splitlines()]
    meaningful = [ln for ln in lines if ln and not ln.startswith(_COMMENT_PREFIXES)]
    if not meaningful:
        return True, "整份文件只有注释/空行"
    head = meaningful[0]
    m = _PLACEHOLDER_RE.match(head)
    if m:
        # 只报标记类型，绝不回显内容本身 —— 万一是真凭据被误判，
        # 也不能把它写进日志/诊断输出（本模块承诺「不记录、不回显」）。
        return True, f"含占位标记类型 {m.group(1).upper()}"
    # 结构化格式（.json 等）本就含描述性文字，不做中文启发式判定
    if filename.lower().endswith((".json",)):
        return False, ""
    # 只在「有效行」里查中文，且该行没有长 ASCII 串（即不像承载凭据的行）时才判为占位
    for ln in meaningful:
        if _CJK_RE.search(ln) and not _ASCII_TOKEN_RE.search(ln):
            return True, "有效行是中文说明文字（真实 key 应为 ASCII 串）"
    return False, ""


def read_secret_raw(filename: str, *env_names: str) -> str:
    """不做占位符判定的原始读取（逃生口，仅供明确的诊断/迁移脚本使用）。"""
    for name in env_names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    try:
        return (SECRETS_DIR / filename).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def extract_value(raw: str, filename: str = "") -> str:
    """从「注释 + 值」形态的文件里提取真正的凭据值。

    规则（沿用系统既有语义，2026-09-13 统一到这里）：
      · 只有注释/空行 → 空串；
      · `.json` 等结构化格式 → 原样返回（由调用方自行解析）；
      · 有注释行 → 返回第一条有效行（注释后那行就是值）；
      · 没有注释行且有效行多于一条 → 原样返回（可能是多行凭据，如 PEM）。
    把带注释的整份内容当成 token 会污染 Authorization 头 —— 所以必须剥注释。
    """
    lines = [ln.strip() for ln in raw.splitlines()]
    meaningful = [ln for ln in lines if ln and not ln.startswith(_COMMENT_PREFIXES)]
    if not meaningful:
        return ""
    if filename.lower().endswith(".json"):
        return raw
    has_comment = any(ln and ln.startswith(_COMMENT_PREFIXES) for ln in lines)
    if has_comment or len(meaningful) == 1:
        return meaningful[0]
    return "\n".join(meaningful)


def read_secret_file(path) -> str:
    """按**显式路径**读取并做占位符守卫。

    给「自带 SECRETS 目录常量」的模块（xau_ohlcv_source / multi_source_collector）
    委托用 —— 它们各自持有可被测试 monkeypatch 的目录变量，
    所以必须按路径读取，而不能走本模块固定的 SECRETS_DIR。
    """
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if not raw:
        return ""
    placeholder, _reason = is_placeholder(raw, p.name)
    if placeholder:
        return ""
    return extract_value(raw, p.name)


def read_secret(filename: str, *env_names: str) -> str:
    """读取凭据，不记录、不回显；环境变量优先于本地秘密文件。

    占位符/说明性文件一律返回空串（**环境变量仍然无条件优先**，
    所以用环境变量注入真实凭据的路径不受影响）。
    """
    for name in env_names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    raw = read_secret_raw(filename)
    if not raw:
        return ""
    placeholder, _reason = is_placeholder(raw, filename)
    if placeholder:
        return ""
    return extract_value(raw, filename)


def secret_status(filename: str, *env_names: str) -> dict:
    """给审计/诊断用的凭据状态（不回显凭据本身）。"""
    raw = read_secret_raw(filename, *env_names)
    if not raw:
        return {"file": filename, "state": "missing", "reason": "文件不存在或为空", "usable": False}
    from_env = any(os.environ.get(n, "").strip() for n in env_names)
    placeholder, reason = is_placeholder(raw, filename)
    return {
        "file": filename,
        "state": "from_env" if from_env else "from_file",
        "reason": reason or "ok",
        "usable": not placeholder,
        "length": len(raw),
    }
