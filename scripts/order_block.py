#!/usr/bin/env python3
"""Order Block识别 — 机构吸筹/派发K线检测"""
import json

def detect_obs(klines, lookback=100):
    """检测Order Block。
    
    Args:
        klines: list of [time, open, high, low, close, volume, ...]
        lookback: 回溯K线数
        
    Returns:
        list[dict]: [{type, price, zone_top, zone_bottom, strength(1-5), displacement_pct}]
    """
    k = klines[-lookback:] if len(klines) > lookback else klines
    obs = []
    n = len(k)
    
    for i in range(1, n - 1):
        o1, h1, l1, c1, v1 = float(k[i-1][1]), float(k[i-1][2]), float(k[i-1][3]), float(k[i-1][4]), float(k[i-1][5])
        o2, h2, l2, c2, v2 = float(k[i][1]), float(k[i][2]), float(k[i][3]), float(k[i][4]), float(k[i][5])
        
        # 均值成交量前3
        vol_ma = sum(float(k[j][5]) for j in range(max(0, i-3), i)) / min(i, 3)
        if vol_ma == 0:
            vol_ma = v2
        
        # 强阳线（涨幅>0.3%, 放量>1.5x均值）
        body2 = abs(c2 - o2)
        range2 = h2 - l2
        if range2 == 0:
            continue
        body_pct = body2 / o2 * 100
        vol_ratio = v2 / vol_ma if vol_ma > 0 else 1
        
        is_strong_bull = c2 > o2 and body_pct > 0.3 and vol_ratio > 1.5
        is_strong_bear = c2 < o2 and body_pct > 0.3 and vol_ratio > 1.5
        
        # 前一根K线
        prev_body_pct = abs(c1 - o1) / o1 * 100 if o1 > 0 else 0
        
        if is_strong_bull and prev_body_pct < 0.15:  # 下跌后强转阳
            # 前一根最低价 = 牛市OB
            displacement = body_pct
            obs.append({
                "type": "bullish",
                "price": round(l1, 2),
                "zone_top": round(l1 + (h1 - l1) * 0.382, 2),
                "zone_bottom": round(l1 - (h1 - l1) * 0.382, 2),
                "strength": min(int(displacement * 5), 5),
                "displacement_pct": round(displacement, 2),
            })
        
        elif is_strong_bear and prev_body_pct < 0.15:  # 上涨后强转阴
            # 前一根最高价 = 熊市OB
            displacement = body_pct
            obs.append({
                "type": "bearish",
                "price": round(h1, 2),
                "zone_top": round(h1 + (h1 - l1) * 0.382, 2),
                "zone_bottom": round(h1 - (h1 - l1) * 0.382, 2),
                "strength": min(int(displacement * 5), 5),
                "displacement_pct": round(displacement, 2),
            })
    
    # 去重(价格$10以内取最强的)
    deduped = []
    used_prices = set()
    for ob in sorted(obs, key=lambda x: x["strength"], reverse=True):
        price_key = round(ob["price"] / 10) * 10  # 取整到$10
        if price_key not in used_prices:
            used_prices.add(price_key)
            deduped.append(ob)
    
    return sorted(deduped, key=lambda x: x["price"])


def nearest_ob(obs, current_price, side=None):
    """找最近的OB。side: 'bullish'/'bearish'。"""
    if side:
        obs = [o for o in obs if o["type"] == side]
    if not obs:
        return None
    
    # 找最接近当前价的
    nearest = min(obs, key=lambda o: abs(o["price"] - current_price))
    return nearest


if __name__ == "__main__":
    # 测试
    test_klines = []
    base = 64250.0
    for i in range(30):
        if i == 5:
            # 强阳
            test_klines.append([i, base-80, base+20, base-100, base+10, 2000])
        elif i == 6:
            # 巨阳 + 放量
            test_klines.append([i, base+10, base+120, base-10, base+100, 5000])
        elif i == 7:
            # 调整
            test_klines.append([i, base+100, base+130, base+80, base+110, 1500])
        elif i == 15:
            # 强阴
            test_klines.append([i, base+50, base+80, base-30, base-20, 1800])
        elif i == 16:
            # 巨阴 + 放量
            test_klines.append([i, base-20, base+10, base-120, base-100, 4500])
        else:
            base += 2
            test_klines.append([i, base, base+30, base-20, base+10, 800])
    
    obs = detect_obs(test_klines)
    print(f"检测到 {len(obs)} 个OB:")
    for o in obs:
        print(f"  {o['type']}: {o['price']} 区间[{o['zone_bottom']}-{o['zone_top']}] 强度{o['strength']}/5")
    
    nearest = nearest_ob(obs, base)
    if nearest:
        print(f"\n最近OB: {nearest['type']} @ {nearest['price']} 强度{nearest['strength']}/5")
