# 静默降级与路由完备性（2026-09-11 实案）

来源：用户要求「全面更新优化系统」后，对定版双指标做全系统对齐时暴露的一类缺陷。
共同特征：**不报错、日志干净、卡面看着正常，但实际少干活或什么都不干**。

---

## 1. 实案一：路由对未识别资产类别返回空列表

```python
# 修前
ordered = ["tv", "binance", "cg_pro", "macro", ... , "card"]
return [s for s in ordered if s in STEPS and ac in STEPS[s]["assets"]]
# → SPX500 / FOOBAR / AAPL240119C150 的 asset_class 是 "other"，
#   而**没有任何步骤声明支持 "other"** → 返回 []
```

调用方拿到 `[]` 后既不报错也不分析。实测矩阵（修前）：

| 品种 | 识别 | full 步数 |
|---|---|---|
| `SPX500` | other | **0** |
| `AAPL240119C150`（OSI 标准期权码） | other（识别不了） | **0** |
| `AAPL 240119C150` / `OPRA:AAPL240119C150` | other | **0** |
| `FOOBAR` | other | **0** |

修法三层：

1. 新增缺失的资产类别（`index`：SPX500/NAS100/US30/DAX/VIX/DXY…），
   并把 `index`/`other` 登记进 tv/macro/x_sent/cron_read/corr/card 的 `assets`；
2. 期权识别支持三种写法（OSI 无空格 / OCC 空格补齐 / Deribit 破折号），
   抽出 `underlying` 与 `underlying_class`；
3. 路由尾部加断言，把「空管线」从「可能发生」变成「结构上不可能」：

```python
steps = [s for s in ordered if s in STEPS and ac in STEPS[s]["assets"]]
assert steps, f"路由为空：asset_class={ac!r} symbol={symbol!r} 未命中任何步骤"
return _add_option_chain(steps, identity)
```

---

## 2. 实案二：未知分析档位静默降档

```python
# 修前
return dict(MODE_SPECS.get(mode, MODE_SPECS["quick"]))   # ← 未知 mode 静静变 quick
```

两个问题叠在一起：

- **大小写敏感**：对话层写「Quick / Full」，代码只认小写 → 全部回落 quick。
- **未知档位无提示**：Fall 少跑十一步，卡面与正常 quick 一样。

修法：

```python
key = str(mode or "").strip().lower()
spec = MODE_SPECS.get(key)
if spec is None:
    spec = dict(MODE_SPECS["quick"])
    spec["mode_error"] = f"未知分析档位 {mode!r}；已按 quick 执行，请核对档位名"
    spec["requested_mode"] = str(mode)
spec["mode"] = key if key in MODE_SPECS else "quick"
return dict(spec)
```

并且 `route_pipeline` 遇未知 mode **按 full 处理**（不是 quick）：
**少跑步骤比多跑危险**。

配套测试：断言四档 spec 互不相同（防绕后被改成同一个）+ 断言未知档位带 `mode_error`。

---

## 3. 实案三：契约兑底 stub 静默降级



```python
# auto_card.py
try:
    import tv_indicator_contract as TVC
except Exception:
    class _TVCStub:  # ← 字段/行名全空
        MAIN_ROW_LABELS: list = []
        ...
    TVC = _TVCStub()
```

「不阻断出卡」的初衷是对的，但结果是：契约缺失 → 所有 DW 字段与行动格行读不到 →
出一张**看起来正常、实际全空**的卡。

修法：stub 置 `DEGRADED = True`、补齐 stub 缺失的属性（否则消费方报 AttributeError
又是另一种崩），让卡面的数据状态行把「契约缺失」写出来。
**降级可以，静默不行。**

---

## 4. 实案四：用户口述的市场规则没落到代码

用户规则早已明确：「主周期 crypto 15m / gold 5m / forex 15m / stock 1h / futures 15m；
**option 跟随底层**。」但代码里只有一条通用的 `option` TF 规则，没有「跟随底层」的解析。

后果：Deribit 期权 `BTC-29MAR24-60000-C` 的 full 只跑 3 步
（`tv / options_chain / card`），**拿不到驱动它价格的 Binance OI/费率/CVD**。

修后矩阵：

| 品种 | class | base | 主周期 | quick | full | monitor |
|---|---|---|---|---|---|---|
| `BTCUSDT.P` | crypto | — | 15m | 3 | 15 | 1 |
| `OANDA:XAUUSD` | gold | — | 5m | 2 | 8 | 0 |
| `EURUSD` | forex | — | 15m | 2 | 7 | 0 |
| `AAPL` | stock | — | 1h | 2 | 8 | 0 |
| `ES1!` | futures | — | 15m | 2 | 6 | 0 |
| `SPX500` | index | — | 15m | 2 | 6 | 0 |
| `AAPL240119C150` | option | stock | **1h** | 3 | 8 | 0 |
| `SPX 240119C5000` | option | index | **15m** | 3 | 7 | 0 |
| `BTC-29MAR24-60000-C` | option | crypto | **15m** | 4 | **16** | 2 |
| `FOOBAR` | other | — | 15m | 2 | 6 | 0 |

**教训：用户口述的多市场规则就是契约。** 落地后要跑一张矩阵表逐类验证，
不能只测当下手头那个品种（本轮只测 BTC/XAU 就会全部通过）。

---

## 5. 期权链注入的两个边界

```python
def _add_option_chain(steps: list[str], identity: dict) -> list[str]:
    if not steps:
        return steps          # ← monitor 档位本来就无步骤：补期权链会把它变成一次分析
    if identity.get("asset_class") != "option":
        return steps
    if "options_chain" in steps:
        return steps
    out = list(steps)
    out.insert(-1 if out and out[-1] == "card" else len(out), "options_chain")
    return out
```

- 空步骤集**不补**（否则 `monitor` 的 `[]` 变成 `['options_chain']`，语义被偷改）。
- 期权链放在 `card` 之前（它是证据，要在出卡前拿到）。
初始没加 `if not steps` 时就是这个 bug：crypto 期权的 monitor 档返回了 `['binance','options_chain']`。

---

## 6. 自测清单（新增/重构路由或档位时跑）

1. 「资产 × 档位」矩阵：每格非空，主周期一起打出来对账；
2. 未知资产类别（乱写一个 ticker）不得返回 `[]`；
3. 未知档位名必须带 `mode_error`，且按 `full` 而非 `quick` 处理；
4. 四档 spec 互不相同（防绕后被拍平）；
5. 期权：三种代码写法都能解析出 `underlying` + `underlying_class`，
   主周期跟随底层，`options_chain` 出现在 full/quick 但**不在** monitor。
