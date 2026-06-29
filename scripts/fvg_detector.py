#!/usr/bin/env python3
"""FVG检测模块 — 三烛不重叠Fair Value Gap识别"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json

def detect_fvg(klines, lookback=50):
    """检测FVG缺口。
    
    Args:
        klines: list of [time, open, high, low, close, volume, ...]
        lookback: 回溯K线数
        
    Returns:
        list[dict]: FVG列表 [{type, top, bottom, midpoint, gap_size, start_idx, confirmed}]
    """
    fvgs = []
    k = klines[-lookback:] if len(klines) > lookback else klines
    n = len(k)
    
    for i in range(n - 2):
        # 三烛: i, i+1, i+2
        h1, l1 = float(k[i][2]), float(k[i][3])
        h2, l2 = float(k[i+1][2]), float(k[i+1][3])
        h3, l3 = float(k[i+2][2]), float(k[i+2][3])
        
        # 牛市FVG: candle1.high < candle3.low (向上跳空)
        if h1 < l3:
            gap_size = l3 - h1
            fvgs.append({
                "type": "bullish",
                "top": l3,
                "bottom": h1,
                "midpoint": round((h1 + l3) / 2, 2),
                "gap_size": round(gap_size, 2),
                "start_idx": i,
                "signal_candle": i + 1,  # 第二根确认
                "confirmed": False,
            })
        
        # 熊市FVG: candle1.low > candle3.high (向下跳空)
        if l1 > h3:
            gap_size = l1 - h3
            fvgs.append({
                "type": "bearish",
                "top": l1,
                "bottom": h3,
                "midpoint": round((l1 + h3) / 2, 2),
                "gap_size": round(gap_size, 2),
                "start_idx": i,
                "signal_candle": i + 1,
                "confirmed": False,
            })
    
    return fvgs


def update_fvg_status(fvgs, current_price, klines):
    """更新FVG确认状态。"""
    for fvg in fvgs:
        mid = fvg["midpoint"]
        gap_size = fvg["gap_size"]
        bottom, top = fvg["bottom"], fvg["top"]
        
        if fvg["type"] == "bullish":
            # 价格回测FVG区间或50%线 = 待确认
            if bottom <= current_price <= top:
                fvg["confirmed"] = True
                fvg["status"] = "retested"
            elif current_price > top + gap_size:
                fvg["status"] = "gap_up_expanded"
            elif current_price < bottom:
                fvg["status"] = "gap_filled"
            else:
                fvg["status"] = "pending"
        else:  # bearish
            if bottom <= current_price <= top:
                fvg["confirmed"] = True
                fvg["status"] = "retested"
            elif current_price < bottom - gap_size:
                fvg["status"] = "gap_down_expanded"
            elif current_price > top:
                fvg["status"] = "gap_filled"
            else:
                fvg["status"] = "pending"
    
    return fvgs


def best_fvg(fvgs):
    """返回最佳FVG（间隙最大且未确认/已回测的）。"""
    active = [f for f in fvgs if f.get("status") in ("pending", "retested")]
    if not active:
        return None
    active.sort(key=lambda x: x["gap_size"], reverse=True)
    return active[0]


if __name__ == "__main__":
    # 测试: 模拟15m K线
    test_klines = []
    base = 64200.0
    for i in range(30):
        # 制造一个跳空缺口
        if i == 10:
            test_klines.append([i, base, base+20, base-10, base+5, 100])
        elif i == 11:
            test_klines.append([i, base+80, base+90, base+70, base+85, 200])
        elif i == 12:
            test_klines.append([i, base+60, base+70, base+55, base+65, 150])
        else:
            base += 5
            test_klines.append([i, base, base+30, base-20, base+10, 100])
    
    fvgs = detect_fvg(test_klines)
    print(f"检测到 {len(fvgs)} 个FVG:")
    for f in fvgs:
        print(f"  {f['type']}: {f['bottom']}->{f['top']} 中点{f['midpoint']} 间隙{f['gap_size']}")
    
    updated = update_fvg_status(fvgs, base + 15, test_klines)
    print("\n更新状态后:")
    for f in updated:
        print(f"  {f['type']} @ {f['midpoint']}: {f.get('status', 'unknown')}")
    
    best = best_fvg(fvgs)
    if best:
        print(f"\n最佳FVG: {best['type']} @ {best['midpoint']} 间隙{best['gap_size']}")
