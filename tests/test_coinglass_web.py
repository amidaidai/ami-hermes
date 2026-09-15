"""CoinGlass 网页端读取器回归（scripts/coinglass_web.py）。

只锁死**离线可复现**的部分：TOTP、key1 推导、握手样本解密、聚合计算。
真网络请求不进单测（会随 CoinGlass 前端变更而红，且依赖代理）。
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from coinglass_web import (  # noqa: E402
    HEATMAP_PATH,
    aes_gzip_decrypt,
    liquidation_by_level,
    make_param_token,
    param_key_for_path,
    spot_price,
    top_liquidation_levels,
    totp,
)

# 2026-09-15 浏览器实测抓到的 (unix秒, TOTP) 样本
TOTP_SAMPLES = [(1789460662, "660967"), (1789460628, "763921")]

# 2026-09-15 浏览器实测抓到的握手样本：/api/index/v5/liqHeatMap 的 user 响应头
HANDSHAKE_HEADER = "xznBZErws7NJpmBGr0uOAcqpZNMsqseTDbcEg828Ml0WU2704sMLapML/yF37mr8"
HANDSHAKE_KEY2 = "e5765a38d03646dc"


def test_totp_matches_captured_samples():
    for ts, code in TOTP_SAMPLES:
        assert totp(ts) == code


def test_param_key_is_base64_of_first_12_path_chars():
    assert param_key_for_path(HEATMAP_PATH) == "L2FwaS9pbmRleC92"
    assert param_key_for_path("/api/futures/home/statistics") == "L2FwaS9mdXR1cmVz"


def test_handshake_header_decrypts_to_second_layer_key():
    assert aes_gzip_decrypt(HANDSHAKE_HEADER, param_key_for_path(HEATMAP_PATH)).decode() == HANDSHAKE_KEY2


def test_param_token_is_decryptable_and_carries_totp():
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    token = make_param_token(now=1789460662)
    # 前端用的是 enc.Utf8.parse(KEY) → 32 个 ASCII 字符当 AES-256 密钥
    dec = Cipher(algorithms.AES(b"1f68efd73f8d4921acc0dead41dd39bc"),
                 modes.ECB()).decryptor()
    raw = dec.update(base64.b64decode(token)) + dec.finalize()
    assert raw.startswith(b"1789460662,660967")


def _fixture_payload():
    """最小合成热力图：3 个价位桶 × 2 个时间桶。"""
    return {
        "instrument": {"exName": "Binance", "instrumentId": "BTCUSDT", "priceTick": 0.1},
        "y": [70000.0, 70100.0, 70200.0],
        "prices": [[1789463000, "77000", "77100", "76900", "77050", "123.0"]],
        "liq": [[0, 0, 100.0], [1, 0, 50.0], [1, 1, 300.0], [0, 2, 10.0]],
    }


def test_liquidation_aggregates_by_price_bin():
    levels = liquidation_by_level(_fixture_payload())
    assert levels == [(70050.0, 150.0), (70150.0, 300.0), (70250.0, 10.0)]


def test_spot_price_reads_last_close():
    assert spot_price(_fixture_payload()) == 77050.0


def test_top_levels_sorted_by_intensity_and_deduped_by_distance():
    picked = top_liquidation_levels(_fixture_payload(), top=3, min_gap_pct=0.0)
    assert [p["price"] for p in picked] == [70150.0, 70050.0, 70250.0]
    assert picked[0]["side"] == "下方"
    assert picked[0]["intensity"] == 300.0
    assert round(picked[0]["share_pct"], 2) == round(300 / 460 * 100, 2)
    assert all("intensity" in p and "distance_pct" in p for p in picked)
    # 不得把相对刻度写成美元
    assert not any("notional_usd" in p or "notional_musd" in p for p in picked)


def test_module_is_self_contained_no_secrets_no_pandas():
    """模块必须自包含：不读凭据文件、不依赖 pandas（去掉模块 docstring 后再断言）。"""
    src = (ROOT / "scripts" / "coinglass_web.py").read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]
    assert "secrets" not in body
    assert "credential_store" not in body
    assert "import pandas" not in body


def test_plaintext_endpoints_pass_through_unencrypted():
    """少数接口不加密（data 直接是明文对象），不得因此报错。"""
    from coinglass_web import _unwrap

    plain = [{"symbol": "BTC", "coinName": "Bitcoin"}]
    assert _unwrap("/api/v2/support/symbol", {"code": "0", "data": plain}, {}) == plain


def test_gated_symbol_error_surfaces_server_code():
    """非 BTC 品种匿名请求返回 code=40000 时，必须暴露服务端 code 而不是装作成功。"""
    from coinglass_web import _unwrap

    try:
        _unwrap("/api/index/v5/liqHeatMap", {"code": "40000", "msg": "40000"}, {})
    except ValueError as exc:
        assert "40000" in str(exc)
    else:
        raise AssertionError("门控响应必须抛错")
