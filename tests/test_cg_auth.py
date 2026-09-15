"""CoinGecko 认证契约回归（2026-09-14）。

背景：仓库 8 处把 Demo key（`CG-`）当 Pro key 发 `x-cg-pro-api-key`，
实测每次 HTTP 400/10010 → 上层读成「源不可用」，cg_pro 步因此被退役。
这里锁死三件事：
  1) header 映射正确（demo / pro / 空）；
  2) 全仓不得再手写这两个 header（唯一出口 = scripts/cg_auth.py）；
  3) 旧的坏用法字符串不再出现。
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cg_auth import auth_headers, credential_kind, PUBLIC_BASE  # noqa: E402


def test_demo_key_uses_demo_header_not_pro_header():
    h = auth_headers("CG-tku1234567890abcdefghij")
    assert h == {"x-cg-demo-api-key": "CG-tku1234567890abcdefghij"}
    assert "x-cg-pro-api-key" not in h


def test_pro_shaped_key_uses_pro_header():
    h = auth_headers("CGproKeyWithoutDashPrefix000000")
    assert h == {"x-cg-pro-api-key": "CGproKeyWithoutDashPrefix000000"}


def test_empty_or_placeholder_key_sends_no_auth_header():
    for value in (None, "", "   ", "\n"):
        assert auth_headers(value) == {}, repr(value)


def test_credential_kind_never_echoes_the_key():
    key = "CG-supersecret-demo-key"
    assert credential_kind(key) == "Demo key"
    assert key not in credential_kind(key)


def test_public_base_is_the_host_these_headers_belong_to():
    assert PUBLIC_BASE == "https://api.coingecko.com/api/v3"


def test_no_module_hardcodes_coingecko_auth_headers():
    """唯一出口规则：除 cg_auth.py 外任何脚本再手写 header 即变红。"""
    offenders = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        if path.name == "cg_auth.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in ('"x-cg-pro-api-key"', '"x-cg-demo-api-key"', "'x-cg-pro-api-key'", "'x-cg-demo-api-key'"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert offenders == [], f"手写 CG 认证头：{offenders}"


def test_legacy_broken_pattern_is_gone():
    text = (ROOT / "scripts" / "multi_source_collector.py").read_text(encoding="utf-8")
    assert 'headers={"x-cg-pro-api-key": CG_KEY} if CG_KEY else None' not in text


def test_cg_top_coins_survives_null_24h_change(monkeypatch):
    """markets 端点会给部分币返回 price_change_percentage_24h=null。

    旧码 `c.get(..., 0)` 兜不住「值为 null」，alt 均值求和直接 TypeError，
    整个 cg_top 源被吞成 request_failed（与认证头错误叠加，让 cg_pro 看似彻底不可用）。
    """
    import multi_source_collector as m  # noqa: E402

    rows = [
        {"symbol": "btc", "name": "Bitcoin", "current_price": 78000, "market_cap": 1,
         "price_change_percentage_24h": 1.0},
        {"symbol": "new", "name": "FreshlyListed", "current_price": 1, "market_cap": 1,
         "price_change_percentage_24h": None},
    ]
    monkeypatch.setattr(m, "_fetch", lambda *a, **k: rows)
    monkeypatch.setattr(m, "_cached", lambda key, fetcher, ttl=300, cache_when=None: fetcher())

    out = m.cg_top_coins(2)
    assert out["coin_count"] == 2
    assert out["btc_change_24h"] == 1.0
    assert out["avg_alt_change_24h"] == 0  # 唯一的 alt 是 None → 剔除 → 空集 → 0
    assert out["rotation"] == "同步"


def test_cg_top_coins_survives_btc_null_change(monkeypatch):
    import multi_source_collector as m  # noqa: E402

    rows = [{"symbol": "btc", "name": "Bitcoin", "current_price": 78000, "market_cap": 1,
             "price_change_percentage_24h": None}]
    monkeypatch.setattr(m, "_fetch", lambda *a, **k: rows)
    monkeypatch.setattr(m, "_cached", lambda key, fetcher, ttl=300, cache_when=None: fetcher())

    out = m.cg_top_coins(1)
    assert out["btc_change_24h"] == 0.0
    assert out["rotation"] in {"同步", "BTC主导", "山寨季"}
