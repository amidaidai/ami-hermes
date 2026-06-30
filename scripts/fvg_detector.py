#!/usr/bin/env python3
"""FVG检测模块 — ICT三烛Fair Value Gap识别。

棠溪规则：FVG用于中线结构，默认检测4h/D；15m/5m只作执行回测参考。
TV MCP通常读不到Pine里的box/rectangle，因此必须从OHLCV手算，不把pine_lines里的水平线误判成FVG。
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _k_float(candle, idx):
    return float(candle[idx])


def _round_price(value, decimals=8):
    # 保留足够精度，避免山寨币/外汇被round(..., 2)截断；展示层再格式化。
    return round(float(value), decimals)


def detect_fvg(klines, lookback=120, timeframe="4h", min_gap_atr=0.0, require_displacement=False, displacement_body_mult=1.2):
    """检测FVG缺口。

    Args:
        klines: list of [time, open, high, low, close, volume, ...]
        lookback: 回溯K线数。中线4h/D建议100-180。
        timeframe: FVG所属周期；用于输出和后续裁决。默认4h。
        min_gap_atr: 最小缺口尺寸，按近似ATR倍数过滤。0=不过滤。
        require_displacement: 是否要求中间K为位移K。正式结构可开启；默认关闭避免漏识别。
        displacement_body_mult: 中间K实体 >= 平均实体*N 才算位移。

    Returns:
        list[dict]: FVG列表 [{type, top, bottom, midpoint, gap_size, start_idx, timeframe, structural}]
    """
    if not klines or len(klines) < 3:
        return []
    fvgs = []
    k = klines[-lookback:] if len(klines) > lookback else klines
    n = len(k)

    ranges = [max(_k_float(c, 2) - _k_float(c, 3), 0.0) for c in k]
    atr_proxy = sum(ranges) / len(ranges) if ranges else 0.0
    bodies = [abs(_k_float(c, 4) - _k_float(c, 1)) for c in k]
    avg_body = sum(bodies) / len(bodies) if bodies else 0.0
    structural = str(timeframe).lower() in ("4h", "240", "d", "1d", "day", "w", "1w")

    for i in range(n - 2):
        # 三烛: i, i+1, i+2；ICT FVG只比较第1与第3根，第二根是位移/推动K。
        h1, l1 = _k_float(k[i], 2), _k_float(k[i], 3)
        h2, l2 = _k_float(k[i + 1], 2), _k_float(k[i + 1], 3)
        h3, l3 = _k_float(k[i + 2], 2), _k_float(k[i + 2], 3)
        o2, c2 = _k_float(k[i + 1], 1), _k_float(k[i + 1], 4)
        body2 = abs(c2 - o2)
        if require_displacement and avg_body > 0 and body2 < avg_body * displacement_body_mult:
            continue

        # 看涨FVG: candle1.high < candle3.low；缺口区间 C1.HIGH → C3.LOW
        if h1 < l3:
            gap_size = l3 - h1
            if min_gap_atr and atr_proxy and gap_size < atr_proxy * min_gap_atr:
                pass
            else:
                fvgs.append({
                    "type": "bullish",
                    "side": "long",
                    "top": _round_price(l3),
                    "bottom": _round_price(h1),
                    "midpoint": _round_price((h1 + l3) / 2),
                    "ce": _round_price((h1 + l3) / 2),
                    "gap_size": _round_price(gap_size),
                    "gap_atr": _round_price(gap_size / atr_proxy, 4) if atr_proxy else None,
                    "start_idx": i,
                    "signal_candle": i + 1,
                    "timeframe": timeframe,
                    "structural": structural,
                    "confirmed": False,
                })

        # 看跌FVG: candle1.low > candle3.high；缺口区间 C3.HIGH → C1.LOW
        if l1 > h3:
            gap_size = l1 - h3
            if min_gap_atr and atr_proxy and gap_size < atr_proxy * min_gap_atr:
                pass
            else:
                fvgs.append({
                    "type": "bearish",
                    "side": "short",
                    "top": _round_price(l1),
                    "bottom": _round_price(h3),
                    "midpoint": _round_price((l1 + h3) / 2),
                    "ce": _round_price((l1 + h3) / 2),
                    "gap_size": _round_price(gap_size),
                    "gap_atr": _round_price(gap_size / atr_proxy, 4) if atr_proxy else None,
                    "start_idx": i,
                    "signal_candle": i + 1,
                    "timeframe": timeframe,
                    "structural": structural,
                    "confirmed": False,
                })

    return fvgs


def update_fvg_status(fvgs, current_price, klines=None):
    """更新FVG状态。以当前价判断是否回测/失效；若传入后续K线，可判断是否已被完整填补。"""
    price = float(current_price) if current_price is not None else None
    for fvg in fvgs:
        bottom, top = float(fvg["bottom"]), float(fvg["top"])
        fvg["confirmed"] = False
        fvg["mitigated"] = False
        fvg["invalidated"] = False

        # 当前价在缺口内=正在回测；CE用于精确执行。
        if price is not None and bottom <= price <= top:
            fvg["confirmed"] = True
            fvg["status"] = "retested"
        elif fvg["type"] == "bullish":
            if price is not None and price < bottom:
                fvg["mitigated"] = True
                fvg["invalidated"] = True
                fvg["status"] = "filled_or_broken"
            elif price is not None and price > top:
                fvg["status"] = "unfilled_below_price"
            else:
                fvg["status"] = "pending"
        else:
            if price is not None and price > top:
                fvg["mitigated"] = True
                fvg["invalidated"] = True
                fvg["status"] = "filled_or_broken"
            elif price is not None and price < bottom:
                fvg["status"] = "unfilled_above_price"
            else:
                fvg["status"] = "pending"
    return fvgs


def best_fvg(fvgs, direction=None, structural_only=True):
    """返回最佳FVG。

    默认只取结构性(4h/D/W) FVG，避免15m/5m短噪声冒充中线结构。
    direction: long/short 可选，用于匹配交易方向。
    """
    active_status = {"pending", "retested", "unfilled_below_price", "unfilled_above_price"}
    active = [f for f in fvgs if f.get("status", "pending") in active_status]
    if structural_only:
        active = [f for f in active if f.get("structural")]
    if direction in ("long", "bullish"):
        active = [f for f in active if f.get("type") == "bullish"]
    elif direction in ("short", "bearish"):
        active = [f for f in active if f.get("type") == "bearish"]
    if not active:
        return None
    # 优先已回测/接近价位，其次更大gap_atr。
    active.sort(key=lambda x: (x.get("status") == "retested", x.get("gap_atr") or 0, x.get("gap_size") or 0), reverse=True)
    return active[0]


if __name__ == "__main__":
    # 简单自测：模拟4h中线FVG
    test_klines = []
    base = 64200.0
    for i in range(30):
        if i == 10:
            test_klines.append([i, base, base + 20, base - 10, base + 5, 100])
        elif i == 11:
            test_klines.append([i, base + 80, base + 90, base + 70, base + 85, 200])
        elif i == 12:
            test_klines.append([i, base + 60, base + 70, base + 55, base + 65, 150])
        else:
            base += 5
            test_klines.append([i, base, base + 30, base - 20, base + 10, 100])

    fvgs = detect_fvg(test_klines, timeframe="4h")
    print(f"检测到 {len(fvgs)} 个FVG:")
    for f in fvgs:
        print(f"  {f['timeframe']} {f['type']}: {f['bottom']}->{f['top']} CE{f['ce']} 间隙{f['gap_size']} 状态{f.get('status','pending')}")

    updated = update_fvg_status(fvgs, base + 15, test_klines)
    best = best_fvg(updated, structural_only=True)
    if best:
        print(f"最佳中线FVG: {best['timeframe']} {best['type']} @ {best['bottom']}-{best['top']} CE{best['ce']} {best.get('status')}")
