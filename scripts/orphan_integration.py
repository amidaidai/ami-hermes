#!/usr/bin/env python3
"""
棠溪 · 孤儿脚本集成适配层 v1.0
================================================

将 6 个独立"孤儿"脚本的公共函数封装为统一接口，
供 auto_card.py 调用，用于分析卡的数据增强。

孤儿脚本清单:
    1. meta_labeler.py          — Meta-Labeling 执行门控闸门
    2. orderflow_absorption.py  — 订单流吸收/消耗检测
    3. cvd_analyzer.py          — CVD 共振分级（CVD+VWAP）
    4. fvg_detector.py          — ICT 三烛 Fair Value Gap 检测
    5. order_block.py           — 机构 Order Block 识别
    6. correlation_matrix.py    — 多资产相关性风险乘数

统一接口:
    run_orphan_checks(symbol, price, direction, klines=None) -> dict

数据来源标注:
    所有返回字段均附 `_source` 标签，便于分析卡追踪出处。

作者: 棠溪集成层
版本: 1.0
"""

from __future__ import annotations
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

# ── 标准输出编码修复 ──
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 路径常量 ──
ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
SCRIPTS = ROOT / "scripts"
TZ = timezone(timedelta(hours=8))

# ── 将 scripts/ 加入导入路径 ──
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# ── 日志 ──
logger = logging.getLogger("orphan_integration")


# ════════════════════════════════════════════════════════════
#  内部工具
# ════════════════════════════════════════════════════════════

def _safe_call(func, *args, default: Any = None, label: str = "", **kwargs) -> Any:
    """通用安全调用包装器：任何异常都返回 default，不中断主流程。"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"[{label}] 调用失败: {e}")
        return default


def _ensure_data_dir() -> None:
    """确保 data/ 目录存在"""
    DATA.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════════
#  1. Meta-Labeling 执行门控
#     数据来源: 孤儿·meta_labeler v1.0
# ════════════════════════════════════════════════════════════

def run_meta_label_gate(
    symbol: str,
    price: float,
    direction: str = "long",
    signal: Optional[dict] = None,
) -> dict:
    """
    调用 meta_labeler.check_meta_label() 执行门控闸门。

    Args:
        symbol: 交易对（用于标注）
        price: 当前价格
        direction: 交易方向 long/short
        signal: MetaLabeler 支持的特征字典；
                为 None 时根据 price/direction 构造最小信号。

    Returns:
        {
            "execute": bool,
            "confidence": float,
            "reason": str,
            "_source": "孤儿·meta_labeler v1.0"
        }
    """
    source_tag = "孤儿·meta_labeler v1.0"

    if signal is None:
        signal = {
            "model_score": 7,
            "data_quality": "B",
            "cvd_direction": "中性",
            "direction": direction,
            "session": "off",
            "loss_streak": 0,
        }

    try:
        from meta_labeler import check_meta_label
        result = check_meta_label(signal)
        result["_source"] = source_tag
        return result
    except Exception as e:
        logger.warning(f"[{source_tag}] 门控调用失败: {e}")
        return {
            "execute": True,
            "confidence": 0.5,
            "reason": f"门控调用失败({e})·默认放行",
            "_source": source_tag,
            "_error": str(e),
        }


# ════════════════════════════════════════════════════════════
#  2. 订单流吸收检测
#     数据来源: 孤儿·orderflow_absorption v1.0
# ════════════════════════════════════════════════════════════

def run_absorption(
    symbol: str,
    price: float,
    cvd_direction: str = "?",
    cvd_quality: str = "C",
    price_change_5m_pct: float = 0.0,
    volume_ratio: float = 1.0,
    key_level_proximity: float = 1.0,
) -> dict:
    """
    调用 orderflow_absorption.detect_absorption() 检测订单流吸收。

    Args:
        symbol: 交易对
        price: 当前价格
        cvd_direction: CVD 方向 ("买"/"卖"/"?")
        cvd_quality: CVD 质量 ("A"/"B"/"C")
        price_change_5m_pct: 5分钟价格变化率
        volume_ratio: 量比 (当前/均值)
        key_level_proximity: 距关键位 ATR 倍数

    Returns:
        {
            "absorption_detected": bool,
            "pattern": str,
            "stop_run_risk": str,
            "direction_bias": str,
            "confidence": int,
            "signals": list[str],
            "summary": str,
            "_source": "孤儿·orderflow_absorption v1.0"
        }
    """
    source_tag = "孤儿·orderflow_absorption v1.0"

    try:
        from orderflow_absorption import detect_absorption
        result = detect_absorption(
            symbol=symbol,
            current_price=price,
            cvd_direction=cvd_direction,
            cvd_quality=cvd_quality,
            price_change_5m_pct=price_change_5m_pct,
            volume_ratio=volume_ratio,
            key_level_proximity=key_level_proximity,
        )
        result["_source"] = source_tag
        return result
    except Exception as e:
        logger.warning(f"[{source_tag}] 吸收检测失败: {e}")
        return {
            "absorption_detected": False,
            "pattern": "未知",
            "stop_run_risk": "无",
            "direction_bias": "中性",
            "confidence": 0,
            "signals": [],
            "summary": f"吸收检测调用失败({e})·默认无信号",
            "_source": source_tag,
            "_error": str(e),
        }


# ════════════════════════════════════════════════════════════
#  3. CVD 共振分级
#     数据来源: 孤儿·cvd_analyzer v1.0
# ════════════════════════════════════════════════════════════

def run_cvd_confluence(
    price: float,
    vwap: float = 0.0,
    cvd_result: Optional[Any] = None,
) -> dict:
    """
    调用 cvd_analyzer.check_cvd_confluence() 检测 CVD+VWAP 共振。

    Args:
        price: 当前价格
        vwap: VWAP 价格
        cvd_result: CVDResult 对象；为 None 时构造最小默认值。

    Returns:
        {
            "confluence": bool,
            "direction": str,
            "confidence": float,
            "reason": str,
            "cvd_signal": str,
            "cvd_confidence": float,
            "_source": "孤儿·cvd_analyzer v1.0"
        }
    """
    source_tag = "孤儿·cvd_analyzer v1.0"

    try:
        from cvd_analyzer import check_cvd_confluence, CVDResult

        if cvd_result is None:
            # 构造最小默认 CVDResult（无信号状态）
            from cvd_analyzer import SignalType
            cvd_result = CVDResult(
                signal=SignalType.NONE,
                confidence=0.0,
                cvd_value=0.0,
                cvd_slope=0.0,
                price_trend="中性",
                cvd_trend="中性",
                description="无CVD数据·默认无信号",
            )

        result = check_cvd_confluence(cvd_result, vwap, price)
        result["_source"] = source_tag
        return result
    except Exception as e:
        logger.warning(f"[{source_tag}] CVD共振检测失败: {e}")
        return {
            "confluence": False,
            "direction": "中性",
            "confidence": 0.0,
            "reason": f"CVD共振调用失败({e})·默认无共振",
            "cvd_signal": "无信号",
            "cvd_confidence": 0.0,
            "_source": source_tag,
            "_error": str(e),
        }


# ════════════════════════════════════════════════════════════
#  4. FVG 检测
#     数据来源: 孤儿·fvg_detector v1.0
# ════════════════════════════════════════════════════════════

def run_fvg_detection(
    klines: Optional[list] = None,
    direction: str = "long",
    lookback: int = 120,
    timeframe: str = "4h",
) -> dict:
    """
    调用 fvg_detector.detect_fvg() + best_fvg() 检测 Fair Value Gap。

    Args:
        klines: K线数据 list of [time, open, high, low, close, volume, ...]
        direction: 交易方向 long/short
        lookback: 回溯K线数
        timeframe: K线周期标注

    Returns:
        {
            "fvgs": list[dict],
            "best_fvg": dict | None,
            "count": int,
            "_source": "孤儿·fvg_detector v1.0"
        }
    """
    source_tag = "孤儿·fvg_detector v1.0"

    try:
        from fvg_detector import detect_fvg, best_fvg, update_fvg_status

        if not klines or len(klines) < 3:
            return {
                "fvgs": [],
                "best_fvg": None,
                "count": 0,
                "_source": source_tag,
                "_note": "K线数据不足·跳过FVG检测",
            }

        fvgs = detect_fvg(klines, lookback=lookback, timeframe=timeframe)
        # 更新状态（需要当前价，从最后一根K线取）
        last_close = float(klines[-1][4]) if klines else 0.0
        fvgs = update_fvg_status(fvgs, last_close, klines)
        best = best_fvg(fvgs, direction=direction, structural_only=True)

        return {
            "fvgs": fvgs,
            "best_fvg": best,
            "count": len(fvgs),
            "_source": source_tag,
        }
    except Exception as e:
        logger.warning(f"[{source_tag}] FVG检测失败: {e}")
        return {
            "fvgs": [],
            "best_fvg": None,
            "count": 0,
            "_source": source_tag,
            "_error": str(e),
        }


# ════════════════════════════════════════════════════════════
#  5. Order Block 检测
#     数据来源: 孤儿·order_block v1.0
# ════════════════════════════════════════════════════════════

def run_ob_detection(
    klines: Optional[list] = None,
    price: float = 0.0,
    direction: str = "long",
    lookback: int = 100,
) -> dict:
    """
    调用 order_block.detect_obs() + nearest_ob() 检测 Order Block。

    Args:
        klines: K线数据
        price: 当前价格（用于找最近OB）
        direction: 交易方向 long/short
        lookback: 回溯K线数

    Returns:
        {
            "obs": list[dict],
            "nearest_ob": dict | None,
            "count": int,
            "_source": "孤儿·order_block v1.0"
        }
    """
    source_tag = "孤儿·order_block v1.0"

    try:
        from order_block import detect_obs, nearest_ob

        if not klines or len(klines) < 3:
            return {
                "obs": [],
                "nearest_ob": None,
                "count": 0,
                "_source": source_tag,
                "_note": "K线数据不足·跳过OB检测",
            }

        obs = detect_obs(klines, lookback=lookback)

        # 根据方向筛选对应类型的 OB
        side = "bullish" if direction in ("long", "bullish") else "bearish"
        nearest = nearest_ob(obs, price, side=side)

        return {
            "obs": obs,
            "nearest_ob": nearest,
            "count": len(obs),
            "_source": source_tag,
        }
    except Exception as e:
        logger.warning(f"[{source_tag}] OB检测失败: {e}")
        return {
            "obs": [],
            "nearest_ob": None,
            "count": 0,
            "_source": source_tag,
            "_error": str(e),
        }


# ════════════════════════════════════════════════════════════
#  6. 多资产风险乘数
#     数据来源: 孤儿·correlation_matrix v1.0
# ════════════════════════════════════════════════════════════

def run_correlation_multiplier(
    positions: Optional[dict[str, float]] = None,
) -> dict:
    """
    调用 correlation_matrix.multi_asset_risk_multiplier() 计算风险乘数。

    Args:
        positions: {"BTCUSDT": risk_usd, "XAUUSD": risk_usd, ...}
                  为 None 时使用默认最小仓位。

    Returns:
        {
            "multiplier": float,
            "correlation_state": dict | None,
            "_source": "孤儿·correlation_matrix v1.0"
        }
    """
    source_tag = "孤儿·correlation_matrix v1.0"

    if positions is None:
        positions = {"BTCUSDT": 1.0, "XAUUSD": 1.0}

    try:
        from correlation_matrix import multi_asset_risk_multiplier, compute_correlation

        multiplier = multi_asset_risk_multiplier(positions)
        corr_state = _safe_call(compute_correlation, label="compute_correlation", default=None)

        return {
            "multiplier": multiplier,
            "correlation_state": corr_state,
            "_source": source_tag,
        }
    except Exception as e:
        logger.warning(f"[{source_tag}] 相关性计算失败: {e}")
        return {
            "multiplier": 1.0,
            "correlation_state": None,
            "_source": source_tag,
            "_error": str(e),
        }


# ════════════════════════════════════════════════════════════
#  统一接口: run_orphan_checks
# ════════════════════════════════════════════════════════════

def run_orphan_checks(
    symbol: str,
    price: float,
    direction: str = "long",
    klines: Optional[list] = None,
    vwap: float = 0.0,
    cvd_result: Optional[Any] = None,
    positions: Optional[dict[str, float]] = None,
    meta_signal: Optional[dict] = None,
    cvd_direction: str = "?",
    cvd_quality: str = "C",
    price_change_5m_pct: float = 0.0,
    volume_ratio: float = 1.0,
    key_level_proximity: float = 1.0,
) -> dict:
    """
    统一接口：运行全部 6 个孤儿脚本检查，返回结果字典。

    每个子调用均独立 try/except 包裹，单个脚本失败不影响其他。

    Args:
        symbol:        交易对 (如 "BTCUSDT")
        price:         当前价格
        direction:     交易方向 "long" / "short"
        klines:        K线数据 (OHLCV格式)，为 None 时 FVG/OB 跳过
        vwap:          VWAP 价格，用于 CVD 共振检测
        cvd_result:    CVDResult 对象，为 None 时用默认值
        positions:     多资产仓位 dict，用于风险乘数
        meta_signal:   自定义 MetaLabeler 信号字典
        cvd_direction: CVD 方向 ("买"/"卖"/"?")
        cvd_quality:   CVD 质量 ("A"/"B"/"C")
        price_change_5m_pct:  5分钟价格变化率
        volume_ratio:  量比
        key_level_proximity: 距关键位 ATR 倍数

    Returns:
        {
            "meta_label":       dict,   # 门控结果
            "absorption":       dict,   # 订单流吸收
            "cvd_confluence":   dict,   # CVD共振
            "fvg":              dict,   # FVG检测
            "ob":               dict,   # Order Block
            "corr_multiplier":  float,  # 风险乘数
            "_meta": {                  # 运行元数据
                "symbol": str,
                "price": float,
                "direction": str,
                "timestamp": str,
                "version": "1.0",
            }
        }
    """
    timestamp = datetime.now(TZ).isoformat(timespec="seconds")

    # ── 1. Meta-Labeling 门控 ──
    meta_label = run_meta_label_gate(
        symbol=symbol,
        price=price,
        direction=direction,
        signal=meta_signal,
    )

    # ── 2. 订单流吸收 ──
    absorption = run_absorption(
        symbol=symbol,
        price=price,
        cvd_direction=cvd_direction,
        cvd_quality=cvd_quality,
        price_change_5m_pct=price_change_5m_pct,
        volume_ratio=volume_ratio,
        key_level_proximity=key_level_proximity,
    )

    # ── 3. CVD 共振 ──
    cvd_confluence = run_cvd_confluence(
        price=price,
        vwap=vwap,
        cvd_result=cvd_result,
    )

    # ── 4. FVG 检测 ──
    fvg = run_fvg_detection(
        klines=klines,
        direction=direction,
    )

    # ── 5. Order Block 检测 ──
    ob = run_ob_detection(
        klines=klines,
        price=price,
        direction=direction,
    )

    # ── 6. 多资产风险乘数 ──
    corr_result = run_correlation_multiplier(positions=positions)
    corr_multiplier = corr_result.get("multiplier", 1.0)

    # ── 汇总结果 ──
    result = {
        "meta_label": meta_label,
        "absorption": absorption,
        "cvd_confluence": cvd_confluence,
        "fvg": fvg,
        "ob": ob,
        "corr_multiplier": corr_multiplier,
        "_meta": {
            "symbol": symbol,
            "price": price,
            "direction": direction,
            "timestamp": timestamp,
            "version": "1.0",
            "source": "棠溪·孤儿脚本集成适配层",
        },
    }

    # ── 写入分析卡数据文件（便于交叉验证） ──
    _save_orphan_signals(symbol, result)

    return result


# ════════════════════════════════════════════════════════════
#  持久化: 写入 data/orphan_signals_{symbol}.json
# ════════════════════════════════════════════════════════════

def _save_orphan_signals(symbol: str, result: dict) -> Optional[Path]:
    """
    将孤儿脚本运行结果写入 data/orphan_signals_{symbol}.json。
    用于交叉验证和事后分析。

    Returns:
        写入的文件路径，失败返回 None。
    """
    try:
        _ensure_data_dir()
        filepath = DATA / f"orphan_signals_{symbol}.json"
        # 使用自定义序列化，处理可能的非 JSON 序列化对象（如 CVDResult）
        payload = json.dumps(result, indent=2, ensure_ascii=False, default=str)
        filepath.write_text(payload, encoding="utf-8")
        logger.info(f"孤儿信号已保存: {filepath}")
        return filepath
    except Exception as e:
        logger.warning(f"保存孤儿信号失败: {e}")
        return None


# ════════════════════════════════════════════════════════════
#  CLI 自测
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="棠溪·孤儿脚本集成适配层自测")
    parser.add_argument("--symbol", default="BTCUSDT", help="交易对")
    parser.add_argument("--price", type=float, default=64450.0, help="当前价格")
    parser.add_argument("--direction", default="long", choices=["long", "short"], help="交易方向")
    parser.add_argument("--vwap", type=float, default=64000.0, help="VWAP价格")
    args = parser.parse_args()

    print(f"═══ 孤儿脚本集成自测 ═══")
    print(f"标的: {args.symbol}  价格: {args.price}  方向: {args.direction}")
    print()

    result = run_orphan_checks(
        symbol=args.symbol,
        price=args.price,
        direction=args.direction,
        vwap=args.vwap,
        klines=None,  # 自测无K线数据
    )

    # 打印摘要
    print(f"【Meta-Label】执行={result['meta_label'].get('execute')} 置信={result['meta_label'].get('confidence')} 原因={result['meta_label'].get('reason')}")
    print(f"【Absorption】检测={result['absorption'].get('absorption_detected')} 模式={result['absorption'].get('pattern')} 偏空={result['absorption'].get('direction_bias')}")
    print(f"【CVD Confluence】共振={result['cvd_confluence'].get('confluence')} 方向={result['cvd_confluence'].get('direction')} 原因={result['cvd_confluence'].get('reason')}")
    print(f"【FVG】数量={result['fvg'].get('count')} 最佳={result['fvg'].get('best_fvg')}")
    print(f"【OB】数量={result['ob'].get('count')} 最近={result['ob'].get('nearest_ob')}")
    print(f"【Corr Multiplier】{result['corr_multiplier']}")
    print()
    print(f"数据来源: {result['_meta']['source']} v{result['_meta']['version']}")
    print(f"时间戳: {result['_meta']['timestamp']}")

    # 检查文件是否写入
    saved_file = DATA / f"orphan_signals_{args.symbol}.json"
    if saved_file.exists():
        print(f"\n✅ 分析卡数据已写入: {saved_file}")
    else:
        print(f"\n⚠️ 分析卡数据未写入")
