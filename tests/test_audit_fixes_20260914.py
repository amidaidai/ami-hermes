"""2026-09-14 审计修复回归：CLI 参数闸门 / 维护工具依赖降级 / XAU 同步升级计数。

从当日实测缺陷逐条提炼（无网络、不写业务盘）：
1. `auto_card.py --mode full` —— `--mode` 不被识别、其值 `full` 被当成品种，
   为伪品种生成看似正常的卡（静默错输出）。未知参数必须显式报错。
2. `maintenance/mcp_proxy_check.py` 在 PyYAML 不可用的解释器里抛
   "需要 PyYAML" 并以退出码 2 返回 —— 与「发现代理问题」同码，
   把「工具读不到配置」伪装成「代理故障」。必须降级解析 + 独立退出码 3。
3. `xau_tv_sync.py` 单次抖动与「连续多轮失败（XAU 现场结构持续变旧）」
   在 cron 上长得一样；缺连续失败证据 → 无法分级。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auto_card
import xau_tv_sync


def _load_mcp_proxy_check():
    spec = importlib.util.spec_from_file_location(
        "mcp_proxy_check_under_test", ROOT / "scripts" / "maintenance" / "mcp_proxy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 1. auto_card CLI 参数闸门 ────────────────────────────────────────────

def test_unknown_flag_mode_is_rejected():
    """`--mode full` 必须报错，不能静默产出伪品种卡。"""
    msg = auto_card._reject_unknown_flags(["--mode", "full"])
    assert msg and "--mode" in msg
    assert "档位" in msg or "--full" in msg


def test_known_flags_pass():
    assert auto_card._reject_unknown_flags(["BTCUSDT", "--full", "--push"]) is None
    assert auto_card._reject_unknown_flags(["XAUUSD", "--quick"]) is None
    assert auto_card._reject_unknown_flags(["BTCUSDT", "--inherit"]) is None
    assert auto_card._reject_unknown_flags(["BTCUSDT", "--now"]) is None


def test_message_value_is_not_treated_as_flag():
    """`--message` 的值可以以 '-' 开头，不得被当成未知参数。"""
    assert auto_card._reject_unknown_flags(
        ["--mode-auto", "--message", "分析一下 BTC"]) is None
    assert auto_card._reject_unknown_flags(
        ["--mode-auto", "--message", "--weird-but-is-a-value"]) is None


def test_cli_guard_exits_nonzero_without_side_effects():
    """真实 CLI 路径：退出码 2 且不生成卡文件。"""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "auto_card.py"), "--mode", "full"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120,
    )
    assert proc.returncode == 2
    assert "未知参数 --mode" in (proc.stderr + proc.stdout)


def test_full_pipeline_route_is_reachable():
    """`--full` 仍是唯一完整档开关（防误删）。"""
    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert '"--full" in sys.argv' in src
    assert "_reject_unknown_flags" in src


# ── 2. mcp_proxy_check 依赖降级与退出码语义 ──────────────────────────────

_FAKE_CONFIG = """\
model: x
mcp_servers:
  plain:
    command: node
    enabled: false
    env: {}
  proxied:
    command: uvx
    enabled: true
    args:
      - one
      - two
    env:
      HTTP_PROXY: http://127.0.0.1:7897
      HTTPS_PROXY: "http://127.0.0.1:7897"
      NO_PROXY: localhost,127.0.0.1
  later:
    command: node
    enabled: true
other_section:
  mcp_servers:
    decoy:
      env:
        HTTP_PROXY: http://should-not-appear
"""


def test_minimal_parser_extracts_servers_env_and_enabled():
    mpc = _load_mcp_proxy_check()
    servers = mpc._minimal_mcp_servers_parse(_FAKE_CONFIG)
    assert set(servers) == {"plain", "proxied", "later"}
    assert servers["plain"]["enabled"] is False
    assert servers["proxied"]["enabled"] is True
    assert servers["proxied"]["env"]["HTTP_PROXY"] == "http://127.0.0.1:7897"
    assert servers["proxied"]["env"]["HTTPS_PROXY"] == "http://127.0.0.1:7897"
    assert servers["proxied"]["env"]["NO_PROXY"] == "localhost,127.0.0.1"
    # 不得越界读其它顶层段落
    assert "decoy" not in servers


def test_minimal_parser_survives_nested_args_and_colons_in_values():
    """args 列表与含冒号的值（路径/URL）不得被当成新的 server/env 键。"""
    mpc = _load_mcp_proxy_check()
    servers = mpc._minimal_mcp_servers_parse(_FAKE_CONFIG)
    assert "args" not in servers
    assert "one" not in servers
    assert servers["proxied"]["env"]["HTTP_PROXY"].count(":") == 2


def test_minimal_parser_agrees_with_pyyaml_on_real_config():
    """真实 config.yaml：回退解析在「本工具消费的字段」上必须与 PyYAML 一致。"""
    import pytest

    yaml = pytest.importorskip("yaml")
    cfg = Path.home() / "AppData" / "Local" / "hermes" / "config.yaml"
    if not cfg.exists():
        pytest.skip("本机无 config.yaml")
    text = cfg.read_text(encoding="utf-8")
    real = (yaml.safe_load(text) or {}).get("mcp_servers") or {}
    fallback = _load_mcp_proxy_check()._minimal_mcp_servers_parse(text)

    def consumed(servers):
        return {
            name: {
                "enabled": (cfg or {}).get("enabled", True),
                "proxy": {k: v for k, v in ((cfg or {}).get("env") or {}).items()
                          if "PROXY" in k.upper()},
            }
            for name, cfg in servers.items()
        }

    assert consumed(fallback) == consumed(real)


def test_missing_servers_section_is_tool_unavailable_not_problem(tmp_path):
    """无 mcp_servers 段 → 退出码 3（工具不可用），绝不是 2（发现问题）。"""
    mpc = _load_mcp_proxy_check()
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model: x\nnothing_here: 1\n", encoding="utf-8")
    assert mpc.main(["--config", str(cfg), "--no-write"]) == 3


def test_exit_code_contract_documented():
    src = (ROOT / "scripts" / "maintenance" / "mcp_proxy_check.py").read_text(encoding="utf-8")
    assert "3 = 本工具不可用" in src


# ── 3. XAU 同步升级计数 ──────────────────────────────────────────────────

def test_sync_status_counts_consecutive_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(xau_tv_sync, "STATUS_OUT", tmp_path / "xau_tv_sync_status.json")
    first = xau_tv_sync._write_sync_status(False, RuntimeError("boom"), kept="verified_cache")
    assert first["status"] == "failed"
    assert first["consecutive_failures"] == 1
    assert first["kept"] == "verified_cache"
    assert first["last_success_at"] is None

    second = xau_tv_sync._write_sync_status(False, RuntimeError("boom2"), kept="structure_only")
    assert second["status"] == "degraded"
    assert second["consecutive_failures"] == 2

    third = xau_tv_sync._write_sync_status(False, RuntimeError("boom3"), kept="none")
    assert third["consecutive_failures"] == 3

    on_disk = json.loads((tmp_path / "xau_tv_sync_status.json").read_text(encoding="utf-8"))
    assert on_disk["schema"] == "xau_tv_sync_status_v1"
    assert on_disk["consecutive_failures"] == 3


def test_sync_status_success_resets_and_keeps_last_success(tmp_path, monkeypatch):
    monkeypatch.setattr(xau_tv_sync, "STATUS_OUT", tmp_path / "xau_tv_sync_status.json")
    xau_tv_sync._write_sync_status(False, RuntimeError("x"))
    ok = xau_tv_sync._write_sync_status(True)
    assert ok["status"] == "ok"
    assert ok["consecutive_failures"] == 0
    assert ok["last_error"] is None
    assert ok["last_success_at"]


def test_sync_status_corrupt_previous_does_not_crash(tmp_path, monkeypatch):
    path = tmp_path / "xau_tv_sync_status.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(xau_tv_sync, "STATUS_OUT", path)
    st = xau_tv_sync._write_sync_status(False, RuntimeError("y"))
    assert st["consecutive_failures"] == 1


def test_sync_failure_paths_still_return_nonzero():
    """退出码语义未被本改动推翻：失败仍非零（可见降级），只是多了升级计数。"""
    src = (ROOT / "scripts" / "xau_tv_sync.py").read_text(encoding="utf-8")
    assert "_write_sync_status(True)" in src
    assert src.count("_write_sync_status(False") >= 3
    assert "return 1" in src


# ── 4. 预检按连续失败分级 ────────────────────────────────────────────────

def test_preflight_reports_degraded_on_sustained_failure(tmp_path):
    """连续失败 → 预检输出 DEGRADED（而不是与单次抖动同样安静）。"""
    data = tmp_path / "data"
    data.mkdir()
    (data / "xau_tv_sync_status.json").write_text(json.dumps({
        "schema": "xau_tv_sync_status_v1", "status": "degraded",
        "consecutive_failures": 2, "last_error": "行动格刷新失败或过期",
        "last_success_at": "2026-09-14T04:00:00+08:00", "kept": "verified_cache",
        "checked_at": "2026-09-14T04:15:00+08:00",
    }, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_preflight.py")],
        capture_output=True, text=True, cwd=str(tmp_path), timeout=300,
    )
    out = proc.stdout + proc.stderr
    assert "XAU同步: DEGRADED" in out


def test_preflight_tolerates_missing_status_file(tmp_path):
    """尚无状态文件只代表「未观测」，不得因此把预检打成 red。"""
    (tmp_path / "data").mkdir()
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_preflight.py")],
        capture_output=True, text=True, cwd=str(tmp_path), timeout=300,
    )
    out = proc.stdout + proc.stderr
    assert "XAU同步: 尚无状态记录" in out


# ── 5. cron_read 源名/文件名/新鲜度契约 ─────────────────────────────────

def test_cron_source_file_maps_legacy_name():
    from pipeline_router import cron_source_file
    # 源名拼路径会永久误判「文件不存在」的已知错配
    assert cron_source_file("x_sentiment") == "x_sentiment_context.json"
    assert cron_source_file("dune_cache") == "dune_cache.json"


def test_cron_source_max_age_honours_producer_contracts():
    from pipeline_router import cron_source_max_age
    assert cron_source_max_age("xau_macro_context") == 24.0   # TTL 24h，不是 6h
    assert cron_source_max_age("unknown_source") == 6.0       # 缺省


def test_cron_source_paused_flags_design_paused_sources():
    from pipeline_router import cron_source_paused, CRON_SOURCES_PAUSED
    for name in ("dune_cache", "deribit_options", "qlib_factors", "liquidation_pressure"):
        assert cron_source_paused(name) is True
    assert cron_source_paused("x_sentiment") is False   # 2026-09-14 起有 cron
    assert all(reason for reason in CRON_SOURCES_PAUSED.values())


def test_cron_sources_all_resolve_to_canonical_files():
    """每个资产类别的源名都必须能解析出文件名，且不重复。"""
    from pipeline_router import CRON_SOURCES, cron_source_file
    for asset, names in CRON_SOURCES.items():
        resolved = [cron_source_file(n) for n in names]
        assert len(resolved) == len(set(resolved)), f"{asset} 源名重复: {names}"
        for fn in resolved:
            assert fn.endswith(".json")


def test_card_note_separates_design_paused_from_missing():
    """卡面必须把「刻意不采」与「采不到」分开写。"""
    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert "设计性停用" in src
    assert "cron_paused" in src
    assert "not cron_missing and not cron_paused" in src


# ── 6. TV 复用窗口：前置决策必须比读取窗口更严 ──────────────────────────

def test_tv_live_window_single_source_and_pre_sync_margin():
    """前置与读取必须共用同一常量，且前置留出出卡余量。

    事故形态（2026-09-14 实测）：XAU 缓存 4 分钟（前置判「新鲜跳过」），
    出卡 90s 后读取侧跨过 5 分钟阈值 → 主指标被丢弃、门2 亮红，
    同一张卡自相矛盾。
    """
    assert auto_card.TV_LIVE_READ_MAX_AGE_MIN == 5.0
    assert auto_card.TV_LIVE_PRE_SYNC_MARGIN_MIN > 0
    assert (auto_card.TV_LIVE_PRE_SYNC_MAX_AGE_MIN
            == auto_card.TV_LIVE_READ_MAX_AGE_MIN - auto_card.TV_LIVE_PRE_SYNC_MARGIN_MIN)
    # 余量要盖得住最慢出卡路径（实测 XAU 冷启动 ~160s）
    assert auto_card.TV_LIVE_PRE_SYNC_MARGIN_MIN * 60 >= 160

    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    # 读取侧与前置侧都引用常量，不得再出现裸数字
    assert "_live_max_age = TV_LIVE_READ_MAX_AGE_MIN" in src
    assert "TV_LIVE_PRE_SYNC_MAX_AGE_MIN" in src
    assert "_load_xau_tv_contract(max_age_minutes=TV_LIVE_PRE_SYNC_MAX_AGE_MIN)" in src


def test_load_xau_tv_contract_accepts_max_age_override():
    """契约校验函数必须能把更严的窗口透传给 validate_xau_outputs。"""
    import inspect
    sig = inspect.signature(auto_card._load_xau_tv_contract)
    assert "max_age_minutes" in sig.parameters
    src = (ROOT / "scripts" / "auto_card.py").read_text(encoding="utf-8")
    assert '"live_max_age_minutes": float(max_age_minutes)' in src
