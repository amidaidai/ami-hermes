"""凭据守卫的回归测试（2026-09-13）。

锁死两类行为：
  1. 「说明性占位符」文件必须被判为未配置（事故复现：oanda_token.txt）；
  2. 「中文注释 + 真 key」与「.json 结构化凭据」**不得**被误杀 —— 误杀的代价
     是让本来可用的数据源静默失效，比漏判更糟。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from credential_store import is_placeholder, secret_status  # noqa: E402


def test_comment_only_file_is_placeholder():
    """整份只有注释 → 未配置（不是一个 token）。"""
    text = "# 获取方式：登录 OANDA\n# Format: <token>\n\n"
    ok, reason = is_placeholder(text, "oanda_token.txt")
    assert ok
    assert "注释" in reason


def test_placeholder_marker_is_detected():
    """PLACEHOLDER_/TODO/YOUR_ 这类标记必须命中。"""
    for marker in ("PLACEHOLDER_REPLACE_WITH_REAL_TOKEN", "TODO", "CHANGEME",
                   "YOUR_API_KEY_HERE", "<your-token>"):
        ok, _ = is_placeholder(f"# 说明\n{marker}\n", "x.txt")
        assert ok, marker


def test_real_oanda_placeholder_file_is_rejected():
    """真实事故文件的形态：7 行注释 + 一行 PLACEHOLDER_*。"""
    text = (
        "# OANDA personal token\n"
        "# Format: <32-hex-char-token>\n"
        "# 获取方式：登录 developer.oanda.com → 我的账户 → 管理 API 访问\n"
        "# 缺少此文件则 XAU 五周期 OHLCV 走 TwelveData 降级\n"
        "# 当前降级路径：金十报价 + TV 切图\n"
        "PLACEHOLDER_REPLACE_WITH_REAL_TOKEN\n"
    )
    ok, reason = is_placeholder(text, "oanda_token.txt")
    assert ok
    assert "PLACEHOLDER" in reason.upper() or "占位" in reason


def test_chinese_comment_with_real_key_is_usable():
    """中文注释 + 真 key —— 必须仍然可用（防误杀）。"""
    text = "# 我的 FMP 密钥\n# 从 site.financialmodelingprep.com 获取\nabc123def456ghi789jkl012mno345pq\n"
    ok, reason = is_placeholder(text, "fmp_api_key.txt")
    assert not ok, f"误杀真凭据: {reason}"


def test_json_credential_with_chinese_is_usable():
    """.json 结构化凭据含中文描述 —— 不做中文启发式判定（防误杀）。"""
    text = '{\n  "brave": {"key": "BSAxxxxxxxxxxxxxxxxxxxx", "note": "网页搜索"},\n  "exa": {"key": "5d11200b-957b", "note": "AI 搜索"}\n}\n'
    ok, reason = is_placeholder(text, "search_apis.json")
    assert not ok, f"误杀 json 凭据: {reason}"


def test_empty_is_placeholder():
    assert is_placeholder("", "x.txt")[0]
    assert is_placeholder("   \n\n", "x.txt")[0]


def test_secret_status_reports_state_without_leaking_value():
    st = secret_status("oanda_token.txt")
    assert st["usable"] is False
    assert "reason" in st and st["reason"]
    # 状态里绝不能出现凭据内容
    assert "PLACEHOLDER_REPLACE" not in str(st)
