"""契约 ↔ 定版指标源码 对齐回归。

契约是手写的，指标是另一份文件；两边一漂移，消费方就**静默丢字段**。
这里把 `scripts/tv_indicator_alignment_check.py` 的判定变成测试，
任何人改了 plot 标题/行动格行名而没同步契约，测试立刻红。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tv_indicator_contract as C  # noqa: E402


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "tv_indicator_alignment_check", ROOT / "scripts" / "tv_indicator_alignment_check.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_contract_version_is_current():
    assert C.CONTRACT_VERSION == "v15"
    assert C.CONTRACT_CURRENT == 22003
    assert C.SUPPORTED_CONTRACT_VERSIONS == (22002, 22003)
    assert C.DEGRADED is False


def test_main_indicator_exports_match_contract_exactly():
    chk = _load_checker()
    fields = chk.scan_plots(chk.MAIN_PINE.read_text(encoding="utf-8"))
    exported = {n for n, k in fields.items() if "data_window" in k or "price_scale" in k}
    assert exported - set(C.DW_MAIN) == set(), "源码导出、契约缺失 → 会静默丢字段"
    assert set(C.DW_MAIN) - set(fields) == set(), "契约有、源码已无 → 死字段"


def test_sub_indicator_exports_match_contract_exactly():
    chk = _load_checker()
    fields = chk.scan_plots(chk.SUB_PINE.read_text(encoding="utf-8"))
    exported = {n for n, k in fields.items() if "data_window" in k or "price_scale" in k}
    assert exported - set(C.DW_SUB) == set()
    assert set(C.DW_SUB) - set(fields) == set()


def test_action_grid_rows_and_order_match_contract():
    chk = _load_checker()
    main_rows, main_dynamic = chk.scan_rows(chk.MAIN_PINE.read_text(encoding="utf-8"))
    assert main_dynamic == 1, "主指标只有一个动态行标签（「风控」四态）"
    assert [r for r in main_rows if r in set(C.MAIN_ROW_LABELS)] == \
        [r for r in C.MAIN_ROW_LABELS if r != C.SVP_AUTHORIZATION_LABEL]

    sub_rows, _ = chk.scan_rows(chk.SUB_PINE.read_text(encoding="utf-8"))
    assert sub_rows == C.SUB_ROW_LABELS


def test_svp_authorization_literals_exist_in_indicator_source():
    chk = _load_checker()
    src = chk.MAIN_PINE.read_text(encoding="utf-8")
    for token in (C.SVP_AUTHORIZATION_LABEL, C.SVP_OBSERVATION_LABEL,
                  C.SVP_UNAUTHORIZED_LABEL, C.SVP_FORBIDDEN_VALUE):
        assert token in src, f"契约授权态 {token} 在指标源码里不存在"
