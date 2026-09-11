# 极简决策卡实现 v6.9.9

> 2026-06-21 · 与 `hermes/scripts/auto_card.py` 锁定

## 触发条件

`render_card_locked()` 末尾的双模式判断：

```python
anchored = _near_key_level(klines, price)
if (status == "B等待" or status == "X禁做") and anchored:
    compact = _compact_card(...)
    if compact:
        return compact  # 8行极简卡
return full  # 60行全量卡（未锚定时回退）
```

**核心思路：** B等待不是"什么都不做"——当价格实打实在关键位（VAL/VAH/POC/VWAP/高低点），卡面必须给出两种走法让棠溪选。

## `_compact_card()` 输出格式（8行）

```
◷ 06-21 16:02 · BTCUSDT.P · BINANCE · VAL回收 · 空头偏
③ 64,187 · 高 64,568 · 低 64,143
VAL 64,143 ← 价踩在这 · 0.1%
CVD 卖 · Taker buy 1.09 · Funding 0.0030%
→ 破64,143：空 止损64,464 止盈62,219
→ 守64,143：多 止损63,822 止盈66,067
风控：⚠周末 0.68U上限 · Binance 100x · 🛡
—— 决策：你来选方向——
```

**设计原则：**
- 第1行：时间+品种+模型+方向——一眼定位
- 第2行：现价+高低——当前价格环境
- 第3行：最近关键位+距离——聚焦核心博弈点
- 第4行：CVD+Taker+Funding——订单流三要素
- 第5-6行：两种走法——棠溪自己判断选哪边
- 第7行：风控底线——周末/风险/杠杆/Protections
- 第8行：决策标记——提醒这是人工决策，不是自动执行

## `_find_nearest_key_level()` 算法

```python
candidates = []
for tf in ("15m", "1h", "4h"):
    k = klines.get(tf, {})
    for key, name in [("vah","VAH"),("val","VAL"),("poc","POC"),
                      ("vwap","VWAP"),("high","高"),("low","低")]:
        v = k.get(key)
        if v:
            dist = abs(float(v) - price) / price * 100
            candidates.append((float(v), name, dist))
candidates.sort(key=lambda x: x[2])  # 按距离升序
return candidates[0]  # 最近的那个
```

遍历三周期×六种关键位，找到距离价格最接近的那个。

## 方案A/B方向判定

```python
bearish = (cvd_dir == "卖" or taker_dir == "sell")
if bearish:
    plan_a = "→ 破{key}：空 止损... 止盈..."  # 顺向=破位做空
    plan_b = "→ 守{key}：多 止损... 止盈..."  # 反向=守住做多
else:
    plan_a = "→ 守{key}：多 止损... 止盈..."  # 顺向=守住做多
    plan_b = "→ 破{key}：空 止损... 止盈..."  # 反向=破位做空
```

**注意：** 周末或方向不明时，CVD N/A 会导致 bullish 判定为 False（走偏多路径），这是有意为之——偏保守。

## Python 执行顺序陷阱

```python
# ❌ 错误：_compact_card 定义在 __main__ 之后
if __name__ == "__main__":
    auto_card()  # → render_card_locked() → _compact_card() → NameError!

# ✅ 正确：_compact_card 定义在 __main__ 之前
def _compact_card(...): ...
if __name__ == "__main__":
    auto_card()  # 此时 _compact_card 已注册
```

**Python 执行顺序：** 模块级 `def` 从上到下依次注册。`if __name__ == "__main__":` 是模块级代码，按位置执行。定义在 `__main__` **之后**的函数，在 `__main__` 执行时尚未注册。
