from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import render_v96


def test_non_crypto_timeframe_rows_show_haldro_not_applicable():
    assert render_v96._sub_tf_text_for_asset({}, {"asset_is_crypto": False}) == "不适用"
    assert render_v96._sub_tf_text_for_asset({"sub_composite": 11}, {"asset_is_crypto": False}) == "不适用"


def test_crypto_timeframe_rows_keep_haldro_data_path():
    assert render_v96._sub_tf_text_for_asset({}, {"asset_is_crypto": True}) == "待刷新"
