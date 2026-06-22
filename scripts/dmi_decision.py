#!/usr/bin/env python3
"""
棠溪 · DMI 决策引擎 v1.1
对标 SVP+ICT+VWAP+EMA+CVD 指标中的 DMI Strategy Table 评分逻辑

趋势分 0-10 · 反转分 0-10 · A/B/C/X 四级
v1.1: +CVD吸收/派发 +TV决策表直读 +KillZone +三层确认 +周月VWAP
"""
import math
from typing import Optional


def rma(series: list[float], length: int) -> list[float]:
    """Wilder's RMA (Running Moving Average): RMA_t = (RMA_{t-1}*(N-1) + val_t)/N"""
    out = [0.0] * len(series)
    if length <= 0 or len(series) == 0:
        return out
    sma = sum(series[:length]) / length
    out[length - 1] = sma
    alpha = 1.0 / length
    for i in range(length, len(series)):
        out[i] = out[i - 1] + alpha * (series[i] - out[i - 1])
    return out


def compute_dmi(highs: list[float], lows: list[float], closes: list[float],
                di_len: int = 10, adx_smooth: int = 10) -> dict:
    """Compute DMI (ADX, DI+, DI-)."""
    n = len(highs)
    if n < di_len + 1:
        return {"adx": 50.0, "di_plus": 50.0, "di_minus": 50.0,
                "trending": False, "bull": False, "bear": False, "hot": False}

    tr_list, plus_dm_list, minus_dm_list = [], [], []
    for i in range(n):
        h, l = highs[i], lows[i]
        prev_c = closes[i - 1] if i > 0 else closes[i]
        tr_list.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
        up_move = h - highs[i - 1] if i > 0 else 0
        down_move = lows[i - 1] - l if i > 0 else 0
        plus_dm_list.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm_list.append(down_move if down_move > up_move and down_move > 0 else 0.0)

    tr_rma = rma(tr_list, di_len)
    plus_rma = rma(plus_dm_list, di_len)
    minus_rma = rma(minus_dm_list, di_len)

    di_plus_list = [100.0 * plus_rma[i] / (tr_rma[i] if tr_rma[i] > 0 else 1.0) for i in range(n)]
    di_minus_list = [100.0 * minus_rma[i] / (tr_rma[i] if tr_rma[i] > 0 else 1.0) for i in range(n)]
    dx_list = [100.0 * abs(di_plus_list[i] - di_minus_list[i]) /
               (di_plus_list[i] + di_minus_list[i] if (di_plus_list[i] + di_minus_list[i]) > 0 else 1.0)
               for i in range(n)]
    adx_list = rma(dx_list, adx_smooth)

    latest_adx = adx_list[-1] if adx_list[-1] > 0 else 50.0
    latest_dip, latest_dim = di_plus_list[-1], di_minus_list[-1]
    prev_adx = adx_list[-2] if n >= 2 else latest_adx
    gap = abs(latest_dip - latest_dim)

    balance = latest_adx < 20.0 or gap <= 3.0
    bull = latest_dip > latest_dim and not balance
    bear = latest_dim > latest_dip and not balance
    hot = latest_adx >= 40.0
    adx_rising = latest_adx > prev_adx

    bull_path = bull and adx_rising and latest_adx >= 20.0
    bear_path = bear and adx_rising and latest_adx >= 20.0
    bull_confirm = bull_path or (bull and not (latest_adx < prev_adx))
    bear_confirm = bear_path or (bear and not (latest_adx < prev_adx))
    trend_weak = balance or latest_adx < prev_adx

    return {
        "adx": round(latest_adx, 1), "di_plus": round(latest_dip, 1),
        "di_minus": round(latest_dim, 1), "gap": round(gap, 1),
        "balance": balance, "bull": bull, "bear": bear, "hot": hot,
        "adx_rising": adx_rising, "bull_confirm": bull_confirm,
        "bear_confirm": bear_confirm, "trend_weak": trend_weak,
    }


def compute_atr(highs: list[float], lows: list[float], closes: list[float],
                length: int = 14) -> float:
    n = len(highs)
    if n < 2: return 0.0
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
               abs(lows[i] - closes[i - 1])) for i in range(1, n)]
    if not trs: return 0.0
    alpha = 1.0 / length
    atr = sum(trs[:length]) / length if len(trs) >= length else sum(trs) / len(trs)
    for i in range(length, len(trs)):
        atr = atr + alpha * (trs[i] - atr)
    return atr


def f_near_level(price: float, level: Optional[float], atr: float, mult: float) -> bool:
    if level is None or atr <= 0: return False
    return abs(price - level) <= atr * mult


def compute_scores(data: dict, dmi: dict, atr: float, ohlcv_bars: list[dict],
                   tv_grade: str = "", killzone_active: bool = False,
                   triple_confirm_bonus: int = 0) -> dict:
    """
    Compute trend score and reversal score.

    tv_grade: from TV decision table (overrides Python grade).
    killzone_active: bonus for KillZone window alignment.
    triple_confirm_bonus: 0-3 from OB/FVG/Sweep.
    """
    price = data.get("price", 0)
    vwap = data.get("vwap", 0)
    vah = data.get("vah", 0)
    val = data.get("val", 0); poc = data.get("poc", 0)
    b1h = data.get("band1_high", 0); b1l = data.get("band1_low", 0)
    ema9 = data.get("ema9", 0); ema21 = data.get("ema21", 0)
    ema34 = data.get("ema34", 0); ema55 = data.get("ema55", 0)
    cvd = data.get("cvd", 0); cvd_slope = data.get("cvd_slope", 0)
    w_vwap = data.get("w_vwap", 0); m_vwap = data.get("m_vwap", 0)

    # ── Position ──
    price_above_s = vwap > 0 and price >= vwap
    price_below_s = vwap > 0 and price < vwap
    price_above_vah = vah > 0 and price > vah
    price_below_val = val > 0 and price < val
    price_in_va = vah > 0 and val > 0 and price <= vah and price >= val
    vwap_extended_up = vwap > 0 and atr > 0 and price > vwap + atr * 1.5
    vwap_extended_dn = vwap > 0 and atr > 0 and price < vwap - atr * 1.5

    # ── MTF VWAP position ──
    price_above_w = w_vwap > 0 and price > w_vwap
    price_above_m = m_vwap > 0 and price > m_vwap
    price_below_m = m_vwap > 0 and price < m_vwap

    # ── EMA ──
    ema_fast_bull = ema9 >= ema21 if (ema9 and ema21) else False
    ema_slow_bull = ema34 >= ema55 if (ema34 and ema55) else False
    ema_bull = ema_fast_bull and ema_slow_bull
    ema_bear = (not ema_fast_bull) and (not ema_slow_bull)

    # ── CVD ──
    cvd_rising, cvd_falling = cvd_slope > 0, cvd_slope < 0
    cvd_bull_confirm = cvd_bear_confirm = False
    cvd_bull_div = cvd_bear_div = False
    cvd_absorb_buy = cvd_distribute_sell = False
    cvd_long_ok = cvd_short_ok = True

    if ohlcv_bars and len(ohlcv_bars) >= 20:
        closes_bars = [b.get("close", 0) for b in ohlcv_bars]
        highs_bars = [b.get("high", 0) for b in ohlcv_bars]
        lows_bars = [b.get("low", 0) for b in ohlcv_bars]

        if len(closes_bars) >= 5:
            price_up_5 = closes_bars[-1] > closes_bars[-5]
            cvd_bull_confirm = cvd_rising and price_up_5
            cvd_bear_confirm = cvd_falling and not price_up_5

        if len(highs_bars) >= 20 and cvd != 0:
            if highs_bars[-1] >= max(highs_bars[:-1]) and cvd < 0:
                cvd_bear_div = True
            if lows_bars[-1] <= min(lows_bars[:-1]) and cvd > 0:
                cvd_bull_div = True

        cvd_long_ok = cvd_bull_confirm or cvd_bull_div or not cvd_falling
        cvd_short_ok = cvd_bear_confirm or cvd_bear_div or not cvd_rising

        # ── CVD Absorption/Distribution (full, from Pine indicator) ──
        if len(ohlcv_bars) >= 12 and atr > 0 and cvd != 0:
            recent_12 = ohlcv_bars[-12:]
            price_range = max(b["high"] for b in recent_12) - min(b["low"] for b in recent_12)
            cvd_move_abs = abs(cvd)
            # Estimate average delta per bar
            avg_delta = sum(abs(b.get("close", 0) - b.get("open", 0)) for b in recent_12) / 12
            if avg_delta > 0:
                # Absorption: price compressed + CVD strongly negative + price near upper half
                cvd_absorb_buy = (price_range <= atr * 0.8 and
                                  cvd < -avg_delta * 3 and
                                  price >= min(b["low"] for b in recent_12) + price_range * 0.45)
                # Distribution: price compressed + CVD strongly positive + price near lower half
                cvd_distribute_sell = (price_range <= atr * 0.8 and
                                       cvd > avg_delta * 3 and
                                       price <= min(b["low"] for b in recent_12) + price_range * 0.55)

    cvd_state = ("上方派发" if cvd_distribute_sell else "下方吸收" if cvd_absorb_buy else
                 "顶背离" if cvd_bear_div else "底背离" if cvd_bull_div else
                 "顺多确认" if cvd_bull_confirm else "顺空确认" if cvd_bear_confirm else
                 "买盘回升" if cvd_rising else "卖盘回落" if cvd_falling else "中性")

    # ── Volume ──
    rel_vol, close_pos = 1.0, 0.5
    if ohlcv_bars:
        volumes = [b.get("volume", 0) for b in ohlcv_bars[-20:]]
        if volumes:
            vol_ma = sum(volumes) / len(volumes) if volumes else 1.0
            rel_vol = volumes[-1] / vol_ma if vol_ma > 0 else 1.0
            last_bar = ohlcv_bars[-1]
            bar_range = max(last_bar.get("high", 0) - last_bar.get("low", 0), 1.0)
            close_pos = (last_bar.get("close", 0) - last_bar.get("low", 0)) / bar_range if bar_range > 0 else 0.5
    vol_high = rel_vol >= 1.5
    vol_low = rel_vol <= 0.7
    close_near_high = close_pos >= 0.70
    close_near_low = close_pos <= 0.30

    # ── HTF (Weekly/Monthly VWAP + EMA) ──
    htf_bull = (vwap > 0 and w_vwap > 0 and price >= vwap and
                price_above_w and ema9 >= ema55 if (ema9 and ema55) else False)
    htf_bear = (vwap > 0 and w_vwap > 0 and price < vwap and
                not price_above_w and ema9 < ema55 if (ema9 and ema55) else False)
    htf_allow_long = htf_bull or not htf_bear
    htf_allow_short = htf_bear or not htf_bull

    # ── ICT Sweep + KillZone ──
    swept_low_reclaimed = swept_high_rejected = False
    for lb in data.get("labels", []):
        txt = str(lb.get("text", ""))
        lb_price = lb.get("price", 0)
        if "低" in txt and lb_price and price > lb_price:
            swept_low_reclaimed = True
        if "高" in txt and lb_price and price < lb_price:
            swept_high_rejected = True

    vah_rejected = vah > 0 and price < vah
    val_reclaimed = val > 0 and price > val

    # ── Key level proximity ──
    near_key_level = any(f_near_level(price, l, atr, 0.45)
                         for l in [vah, val, poc, vwap, b1h, b1l] if l)
    near_a_key = any(f_near_level(price, l, atr, 0.60)
                     for l in [vah, val, poc, vwap, b1h, b1l] if l)
    allow_a_by_location = near_a_key

    # ═══ TREND SCORE ═══
    trend_long = trend_short = 0
    trend_long += 2 if price_above_s else 0
    trend_long += 2 if price_above_vah else (1 if price_in_va else 0)
    trend_long += 2 if ema_bull else 0
    trend_long += 2 if dmi["bull_confirm"] else 0
    trend_long += 1 if (vol_high and close_near_high) else 0
    trend_long += 1 if (price_above_w and price_above_m) else 0  # MTF VWAP bonus
    trend_long += 1 if killzone_active else 0  # KillZone bonus
    trend_long += triple_confirm_bonus  # 三层确认
    trend_long += int(cvd_bull_confirm)
    trend_long -= int(cvd_bear_div)

    trend_short += 2 if price_below_s else 0
    trend_short += 2 if price_below_val else (1 if price_in_va else 0)
    trend_short += 2 if ema_bear else 0
    trend_short += 2 if dmi["bear_confirm"] else 0
    trend_short += 1 if (vol_high and close_near_low) else 0
    trend_short += 1 if (not price_above_w and price_below_m) else 0  # MTF
    trend_short += 1 if killzone_active else 0
    trend_short += triple_confirm_bonus
    trend_short += int(cvd_bear_confirm)
    trend_short -= int(cvd_bull_div)

    trend_long = max(0, min(trend_long, 10))
    trend_short = max(0, min(trend_short, 10))

    # ═══ REVERSAL SCORE ═══
    reversal_long = reversal_short = 0
    reversal_long += 3 if swept_low_reclaimed else 0
    reversal_long += 2 if val_reclaimed else 0
    reversal_long += 2 if vwap_extended_dn else 0
    reversal_long += 1 if dmi["hot"] else 0
    reversal_long += 1 if (vol_high and not close_near_low) else 0
    reversal_long += int(cvd_bull_div)
    reversal_long += int(cvd_absorb_buy)

    reversal_short += 3 if swept_high_rejected else 0
    reversal_short += 2 if vah_rejected else 0
    reversal_short += 2 if vwap_extended_up else 0
    reversal_short += 1 if dmi["hot"] else 0
    reversal_short += 1 if (vol_high and not close_near_high) else 0
    reversal_short += int(cvd_bear_div)
    reversal_short += int(cvd_distribute_sell)

    reversal_long = max(0, min(reversal_long, 10))
    reversal_short = max(0, min(reversal_short, 10))

    # ═══ GRADE ═══
    acceptance_bull_ok = price_above_s and (price_above_vah or price_in_va)
    acceptance_bear_ok = price_below_s and (price_below_val or price_in_va)

    x_hot = dmi["hot"]
    x_extended = vwap_extended_up or vwap_extended_dn
    x_conflict = (price_above_s and ema_bear) or (price_below_s and ema_bull)
    x_htf_conflict = htf_bear and trend_long >= 7
    setup_x = x_hot or x_extended or x_conflict or x_htf_conflict

    setup_long_a = (trend_long >= 8 and trend_long >= trend_short + 2 and
                    cvd_bull_confirm and price_above_s and acceptance_bull_ok and
                    htf_allow_long and allow_a_by_location and not dmi["hot"])
    setup_short_a = (trend_short >= 8 and trend_short >= trend_long + 2 and
                     cvd_bear_confirm and price_below_s and acceptance_bear_ok and
                     htf_allow_short and allow_a_by_location and not dmi["hot"])
    setup_long_b = (trend_long >= 6 and trend_long >= trend_short + 2 and
                    cvd_long_ok and htf_allow_long and not setup_long_a)
    setup_short_b = (trend_short >= 6 and trend_short >= trend_long + 2 and
                     cvd_short_ok and htf_allow_short and not setup_short_a)
    setup_long_c = reversal_long >= 6 and reversal_long >= reversal_short + 2 and htf_allow_long
    setup_short_c = reversal_short >= 6 and reversal_short >= reversal_long + 2 and htf_allow_short

    # ── TV grade override ──
    if tv_grade in ("A", "B", "C", "X"):
        grade_raw = tv_grade
    elif setup_x:
        grade_raw = "X"
    elif setup_long_a or setup_short_a:
        grade_raw = "A"
    elif setup_long_b or setup_short_b:
        grade_raw = "B"
    elif setup_long_c or setup_short_c:
        grade_raw = "C"
    else:
        grade_raw = "C"

    # Bias
    if (grade_raw == "A" or grade_raw == "B"):
        bias = "偏多" if (setup_long_a or setup_long_b) else "偏空" if (setup_short_a or setup_short_b) else "中性"
    elif setup_long_c: bias = "反多"
    elif setup_short_c: bias = "反空"
    elif tv_grade == "X": bias = "禁做"
    else: bias = "中性"

    # Treatment
    if tv_grade:
        treatment = f"TV决策: {tv_grade}"
    elif setup_x:
        treatment = "过热禁追" if x_hot else "延展禁追" if x_extended else "冲突观望"
    elif setup_long_a: treatment = "回踩做多"
    elif setup_short_a: treatment = "反抽做空"
    elif setup_long_b: treatment = "轻仓等多"
    elif setup_short_b: treatment = "轻仓等空"
    elif setup_long_c: treatment = "站回再多"
    elif setup_short_c: treatment = "跌回再空"
    else: treatment = "观望"

    return {
        "grade": grade_raw, "bias": bias, "treatment": treatment,
        "trend_long": trend_long, "trend_short": trend_short,
        "reversal_long": reversal_long, "reversal_short": reversal_short,
        "dmi": dmi, "atr": round(atr, 1),
        "ema_bull": ema_bull, "ema_bear": ema_bear,
        "cvd_state": cvd_state, "cvd_bull_confirm": cvd_bull_confirm,
        "cvd_bear_confirm": cvd_bear_confirm, "cvd_bull_div": cvd_bull_div,
        "cvd_bear_div": cvd_bear_div,
        "cvd_absorb_buy": cvd_absorb_buy, "cvd_distribute_sell": cvd_distribute_sell,
        "price_above_s": price_above_s, "price_above_vah": price_above_vah,
        "price_below_val": price_below_val, "price_in_va": price_in_va,
        "near_key_level": near_key_level, "near_a_key": near_a_key,
        "allow_a_by_location": allow_a_by_location,
        "swept_low_reclaimed": swept_low_reclaimed,
        "swept_high_rejected": swept_high_rejected,
        "htf_bull": htf_bull, "htf_bear": htf_bear,
        "vol_high": vol_high, "vol_low": vol_low, "rel_vol": round(rel_vol, 2),
        "x_hot": x_hot, "x_extended": x_extended,
        "x_conflict": x_conflict, "x_htf_conflict": x_htf_conflict,
        "setup_x": setup_x, "setup_long_a": setup_long_a,
        "setup_short_a": setup_short_a,
        "price_above_w": price_above_w, "price_above_m": price_above_m,
        "killzone_active": killzone_active,
        "triple_confirm_bonus": triple_confirm_bonus,
    }
