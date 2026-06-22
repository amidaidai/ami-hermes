#!/usr/bin/env python3
"""BTC alert pusher v5 — direct Telegram send, ASCII-only stdout."""
import os, re, sys

from telegram_direct import send_telegram_direct

DIR = os.path.expanduser("~/AppData/Local/hermes/data")
PENDING = os.path.join(DIR, "btc_pending.txt")
TARGET = "telegram:-1003733144325:386"
MAX_TELEGRAM_CHARS = 3900


def log_ascii(message: str) -> None:
    """Write ASCII-only diagnostics. Normal success stays silent for no_agent cron."""
    safe = message.encode("ascii", "replace").decode("ascii")
    sys.stdout.write(safe.rstrip() + "\n")
    sys.stdout.flush()


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def truncate_file(path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.truncate(0)


def telegram_chunks(text: str) -> list[str]:
    chunks = []
    current = []
    current_len = 0
    for line in text.splitlines():
        add_len = len(line) + 1
        if current and current_len + add_len > MAX_TELEGRAM_CHARS:
            chunks.append("\n".join(current).rstrip())
            current = [line]
            current_len = add_len
        else:
            current.append(line)
            current_len += add_len
    if current:
        chunks.append("\n".join(current).rstrip())
    return [c for c in chunks if c.strip()]

# ===== 推送类型 → 方向标注 =====
DIRECTION_MAP = {
    "站回VWAP": "方向→做多",
    "站回VAL": "方向→做多",
    "破VAL": "方向→做空 ⚠",
    "VWAP测试": "方向→等待确认",
    "破VAH": "方向→做多",
    "Sweep": "方向→待确认",
}

def _infer_direction(text: str, alert_type: str = "") -> str:
    """根据推送内容推断方向。v3: 支持新告警格式 ↑↓○ 前缀。"""
    direction = ""
    # v3: 如果行首已有方向标记，直接使用
    if text.startswith("↑") or "↑做多" in text[:10]:
        return "↑做多"
    if text.startswith("↓") or "↓做空" in text[:10]:
        return "↓做空"
    if text.startswith("○") or "○等待" in text[:10]:
        return "○等待"
    
    if "VWAP+B2" in text or "VWAP-B2" in text:
        direction = "↑做多" if "+B2" in text else "↓做空"
    elif "站回VWAP" in text or "站回VAL" in text:
        direction = "↑做多"
    elif "破VAL" in text:
        direction = "↓做空"
    elif "破VAH" in text:
        direction = "↑做多"
    elif "VWAP测试" in text:
        direction = "○等待"
    elif "CVD" in text:
        if "多背离" in text:
            direction = "↑做多(背离)"
        elif "空背离" in text:
            direction = "↓做空(背离)"
        else:
            direction = "○监测"
    elif "扫荡" in text or "Sweep" in text:
        direction = "○回收确认"
    elif "Silver" in text or "银弹" in text:
        direction = "★银弹窗口"
    elif "KillZone" in text:
        direction = "○时段活跃"
    elif "吸收" in text:
        direction = "○机构行为"
    elif "管线" in text:
        if "entry_ready" in text or "入场" in text:
            direction = "⭐入场就绪"
        elif "wait" in text:
            direction = "○等待触发"
        else:
            direction = "○监测中"
    return direction


def _clean_line(line: str) -> str | None:
    """清理单行：去分隔符，保留 emoji。"""
    stripped = line.strip()
    if re.match(r'^[-_*]{3,}$', stripped):
        return None
    if stripped == "---":
        return None
    if stripped.startswith('"""') and stripped.endswith('"""'):
        return None
    if not stripped:
        return None
    return stripped


# ===== 每条告警首行匹配规则 (v3.0: 多因子扩展) =====
_ALERT_HEADER_RE = re.compile(
    r'^(?:[🟡🔴🟢🟠📊🔮🎯💧⭐★◆🔼🔽⏺️]+?\s*)?'  # 可选 emoji 前缀
    r'[↑↓○]'  # 方向标记 (v3格式)
    r'|'
    r'^[★⭐]?'  # 高胜率标记
    r'('
    r'VWAP[+-]B2|站回VWAP|站回VAL|站回VAH|'
    r'破VAL|破VAH|VWAP测试|'
    r'CVD[多空]背离|CVD强[买卖]|'
    r'Taker碾压|EMA完美|'
    r'Sweep|Silver|银弹|KillZone|'
    r'管线|信号|告警|监测'
    r')'
)


def _is_alert_header(line: str) -> bool:
    """判断是否为新告警的首行（含 emoji + 关键词）。"""
    return bool(_ALERT_HEADER_RE.match(line.strip()))


def _split_blocks(lines: list) -> list:
    """将行按告警首行分割成段。"""
    blocks = []
    current = []
    for line in lines:
        if _is_alert_header(line) and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _add_direction(cleaned_lines: list) -> str:
    """在每条告警首行前加上方向标注。"""
    if not cleaned_lines:
        return ""
    
    result = []
    for block in _split_blocks(cleaned_lines):
        if not block:
            continue
        
        full_text = " ".join(block)
        direction = _infer_direction(full_text)
        
        if direction and block:
            # 方向标注替换原首行
            block[0] = f"{direction} {block[0]}"
        
        result.extend(block)
    
    return "\n".join(result)


def clean_pending(content: str) -> str:
    """清理 pending, 去分隔线, 加方向标注。"""
    if not content or not content.strip():
        return ""
    
    lines = content.strip().split("\n")
    cleaned = []
    
    for line in lines:
        cl = _clean_line(line)
        if cl:
            cleaned.append(cl)
    
    # 去首尾空
    while cleaned and cleaned[0].strip() == "":
        cleaned.pop(0)
    while cleaned and cleaned[-1].strip() == "":
        cleaned.pop()
    
    # 加方向标注
    result = _add_direction(cleaned)
    
    if result and not result.endswith("\n"):
        result += "\n"
    
    return result


def fix_markdown_balance(text: str) -> str:
    """修复不成对的 ** 和 `。"""
    double_star = text.count("**")
    if double_star % 2 != 0:
        text += "**"
    lines = text.split("\n")
    fixed = []
    in_block = False
    for line in lines:
        if line.strip().startswith("```"):
            in_block = not in_block
            fixed.append(line)
            continue
        if not in_block:
            ticks = line.count("`")
            if line.count("```") == 0 and ticks % 2 != 0:
                line += "`"
        fixed.append(line)
    return "\n".join(fixed)


if __name__ == "__main__":
    if not os.path.exists(PENDING):
        sys.exit(0)

    size = os.path.getsize(PENDING)
    if size == 0:
        sys.exit(0)

    raw = read_text(PENDING)

    if not raw.strip():
        truncate_file(PENDING)
        sys.exit(0)

    cleaned = clean_pending(raw)
    if not cleaned:
        truncate_file(PENDING)
        sys.exit(0)

    cleaned = fix_markdown_balance(cleaned)
    chunks = telegram_chunks(cleaned)
    if not chunks:
        truncate_file(PENDING)
        sys.exit(0)

    for idx, chunk in enumerate(chunks, start=1):
        ok, reason = send_telegram_direct(TARGET, chunk)
        if not ok:
            log_ascii(f"ERROR btc_push_cron send failed chunk={idx}/{len(chunks)} reason={reason}")
            sys.exit(1)

    truncate_file(PENDING)
    sys.exit(0)
