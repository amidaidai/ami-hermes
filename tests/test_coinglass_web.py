"""CoinGlass 网页端读取器回归（scripts/coinglass_web.py）。

只锁死**离线可复现**的部分：TOTP、key1 推导、握手样本解密、聚合计算。
真网络请求不进单测（会随 CoinGlass 前端变更而红，且依赖代理）。
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from coinglass_web import (  # noqa: E402
    CACHE_MAX_AGE_S,
    HEATMAP_PATH,
    aes_gzip_decrypt,
    liquidation_band_text,
    liquidation_by_level,
    make_param_token,
    param_key_for_path,
    refresh_cache,
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


# ── 响应头 v 分支的 key1 派生（2026-09-16 换代）─────────────────────────────
# 旧实现只覆盖 v=1（路径分支），而实测 20 次请求 v 全落在 55/66/77 上
# → 恒报「响应不是 gzip 密文：协议可能已变更」。这里把四条分支全部离线锁死。


def test_response_key1_covers_every_known_v_branch():
    from coinglass_web import FIXED_KEY_MATERIAL, HEATMAP_PATH, param_key_for_path, response_key1

    assert response_key1({"v": "1"}, HEATMAP_PATH, "1789000000000") == param_key_for_path(HEATMAP_PATH)
    assert response_key1({"v": "1"}, HEATMAP_PATH, "") == "L2FwaS9pbmRleC92"   # 旧口径不变
    for v in ("0", "2"):
        assert response_key1({"v": v}, HEATMAP_PATH, "1789000000000") == "MTc4OTAwMDAwMDAw"[:16]
    for v, material in FIXED_KEY_MATERIAL.items():
        assert len(material) == 16
        key1 = response_key1({"v": v}, HEATMAP_PATH, "")
        assert key1 == base64.b64encode(material.encode()).decode()[:16]
        assert len(key1) == 16
    # 三个固定支必须互不相同，否则说明还原时抄重了
    assert len({response_key1({"v": v}, HEATMAP_PATH, "") for v in FIXED_KEY_MATERIAL}) == 3
    # 未知 v：显式失败，不许静默降级成某个分支
    try:
        response_key1({"v": "99"}, HEATMAP_PATH, "")
    except ValueError as exc:
        assert "99" in str(exc)
    else:
        raise AssertionError("未知 v 必须抛错")


@pytest.mark.parametrize("v", ["1", "0", "2", "55", "66", "77"])
def test_full_two_layer_response_roundtrip_for_every_v_branch(v):
    """离线往返：key1(按 v)解 user 头 → key2 → 解 body.data → JSON。

    这是换代回归的主闸门：任一支的 key 派生写错，该参数化用例就会红。
    """
    import gzip
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from coinglass_web import HEATMAP_PATH, _unwrap, response_key1

    def encrypt(key16: str, plain: bytes) -> str:
        """按生产同口径加密：AES-ECB(key=16 字符串的 UTF-8 字节) + PKCS7 + gzip。"""
        body = gzip.compress(plain)
        pad = 16 - len(body) % 16
        body += bytes([pad]) * pad
        enc = Cipher(algorithms.AES(key16.encode()), modes.ECB()).encryptor()
        return base64.b64encode(enc.update(body) + enc.finalize()).decode()

    key2 = "0123456789abcdef"
    payload = {"liq": [[1, 2, 3]], "instrument": "BTCUSDT"}
    cache_ts = "1789000000000"
    key1 = response_key1({"v": v}, HEATMAP_PATH, cache_ts)
    user_header = encrypt(key1, key2.encode())
    data_field = encrypt(key2, json.dumps(payload).encode())
    out = _unwrap(HEATMAP_PATH, {"code": "0", "data": data_field},
                  {"v": v, "user": user_header}, cache_ts)
    assert out == payload


# ── 缓存层（卡面渲染路径）2026-09-15 ─────────────────────────────────────────


def _write_band_cache(path, top, spot, *, status="live", age_s=0.0):
    import json
    import time

    path.write_text(json.dumps({
        "source": "coinglass_web", "symbol": "Binance_BTCUSDT", "status": status,
        "fetched_at": time.time() - age_s, "error": None, "spot": spot, "top": top,
        "intensity_note": "强度为 CoinGlass 相对刻度，非 USD",
    }, ensure_ascii=False), encoding="utf-8")


def test_band_text_marks_missing_and_stale_cache(tmp_path):
    """没有缓存 / 缓存过期都必须可见降级，不得照抄旧价位。"""
    assert liquidation_band_text("BTCUSDT", cache_path=str(tmp_path / "none.json")) == "清算带 不可用"
    p = tmp_path / "c.json"
    _write_band_cache(p, [], 77000, age_s=CACHE_MAX_AGE_S + 60)
    assert liquidation_band_text("BTCUSDT", cache_path=str(p)) == "清算带 陈旧(需刷新)"


def test_band_text_picks_nearest_above_and_below(tmp_path):
    """卡面要的是「摸到哪儿会撞清算」，取距离最近的上/下，而不是强度榜前二。"""
    p = tmp_path / "c.json"
    top = [
        {"price": 79680.0, "intensity": 9.0, "share_pct": 2.5, "side": "上方", "distance_pct": 3.52},
        {"price": 77492.0, "intensity": 1.0, "share_pct": 1.9, "side": "上方", "distance_pct": 0.68},
        {"price": 75303.0, "intensity": 1.0, "share_pct": 1.6, "side": "下方", "distance_pct": -2.19},
    ]
    _write_band_cache(p, top, 76969.0)
    assert liquidation_band_text("BTCUSDT", cache_path=str(p)) == \
        "清算带 上77,492(+0.68%)/下75,303(-2.19%)"


def test_band_text_is_empty_for_non_btc(tmp_path):
    """CoinGlass 匿名只覆盖 BTC —— 其它品种不占位，也不拿 BTC 数据冒充。"""
    p = tmp_path / "c.json"
    _write_band_cache(p, [], 3000)
    assert liquidation_band_text("ETHUSDT", cache_path=str(p)) == ""
    assert liquidation_band_text("XAUUSD", cache_path=str(p)) == ""


def test_refresh_cache_persists_status_spot_and_top(tmp_path, monkeypatch):
    import json
    import time

    def fake_fetch(symbol="Binance_BTCUSDT", interval=5, limit=288, timeout=30):
        return {"source": "coinglass_web", "symbol": symbol, "fetched_at": int(time.time()),
                "status": "live", "data": _fixture_payload(), "error": None}

    monkeypatch.setattr("coinglass_web.fetch_heatmap", fake_fetch)
    p = tmp_path / "c.json"
    rec = refresh_cache("Binance_BTCUSDT", cache_path=str(p))
    assert rec["status"] == "live"
    assert rec["spot"] == 77050.0
    assert 1 <= len(rec["top"]) <= 8
    assert all(x["side"] == "下方" for x in rec["top"])   # fixture 价位全在现价下方
    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert on_disk["spot"] == 77050.0 and on_disk["status"] == "live"


def test_refresh_cache_records_failure_state(tmp_path, monkeypatch):
    import json

    def fake_fetch(*_a, **_k):
        return {"source": "coinglass_web", "symbol": "Binance_BTCUSDT", "fetched_at": 1,
                "status": "unavailable", "data": None, "error": "ValueError: 接口返回异常"}

    monkeypatch.setattr("coinglass_web.fetch_heatmap", fake_fetch)
    p = tmp_path / "c.json"
    rec = refresh_cache(cache_path=str(p))
    assert rec["status"] == "unavailable" and rec["top"] == []
    assert json.loads(p.read_text(encoding="utf-8"))["status"] == "unavailable"
