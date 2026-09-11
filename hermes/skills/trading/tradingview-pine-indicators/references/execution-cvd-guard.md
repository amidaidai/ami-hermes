# Execution Row + CVD Guard Pattern

Use this pattern when upgrading a TradingView Pine dashboard whose live table already has setup grades and plan/risk rows.

## Goal

Make the table directly executable without adding chart clutter:

- The `执行` row should include the price action plan and the confirmation condition.
- `X` / no-chase states should say what to wait for, not just why trading is forbidden.
- CVD should act as a guardrail that can downgrade setups when order flow stops confirming.

## Implementation Pattern

1. Add a CVD guard toggle in the CVD input group:

```pine
bool CVD_GUARD_DOWNGRADE = input.bool(true, "CVD失效时降级", tooltip="多单需要CVD维持抬高，空单需要CVD维持走低；不满足时A级降B，B级转等待。", group=CVD_GROUP)
```

2. Build readable CVD wait text before constructing plan strings:

```pine
string cvdLongWaitText = not SHOW_CVD_CONFIRM ? "CVD关闭" : cvdBullConfirm ? "CVD维持抬高" : cvdRising ? "CVD不转弱" : cvdBullDivQualified or cvdAbsorbBuy ? "CVD吸收不失守" : "等CVD转强"
string cvdShortWaitText = not SHOW_CVD_CONFIRM ? "CVD关闭" : cvdBearConfirm ? "CVD维持走低" : cvdFalling ? "CVD不转强" : cvdBearDivQualified or cvdDistributeSell ? "CVD派发不失守" : "等CVD转弱"
```

3. Use the previous CVD window as the guard level, not a window that includes the current bar. Including the current bar makes the guard trivially pass.

```pine
float cvdLongGuardLevel = ta.lowest(cvdValue[1], CVD_SLOPE_LEN)
float cvdShortGuardLevel = ta.highest(cvdValue[1], CVD_SLOPE_LEN)
bool cvdLongGuardOk = not SHOW_CVD_CONFIRM or na(cvdLongGuardLevel) or cvdValue >= cvdLongGuardLevel or cvdBullDivQualified or cvdAbsorbBuy
bool cvdShortGuardOk = not SHOW_CVD_CONFIRM or na(cvdShortGuardLevel) or cvdValue <= cvdShortGuardLevel or cvdBearDivQualified or cvdDistributeSell
```

4. Append wait conditions to execution plans:

```pine
string longPlanText = "多:" + longPlanAction + " " + f_fmt_price(longPlanPrice) + " + " + cvdLongWaitText
string shortPlanText = "空:" + shortPlanAction + " " + f_fmt_price(shortPlanPrice) + " + " + cvdShortWaitText
```

5. Make no-chase states operational:

```pine
string xWaitText = xHot ? "不追，等ADX降温+回VWAP" : xHtfConflict ? "不追，等高周同向或回POC" : xConflict ? "不追，等VWAP/VA边确认" : vwapExtendedUp ? "不追，等回踩VWAP/POC" : vwapExtendedDn ? "不追，等反抽VWAP/POC" : "不追，等关键位确认"
```

6. Apply the CVD guard to grades and downgrade text:

```pine
bool setupLongA = ... and cvdLongGuardOk
bool setupShortA = ... and cvdShortGuardOk
bool setupLongBRaw = ...
bool setupShortBRaw = ...
bool setupLongB = setupLongBRaw and (not CVD_GUARD_DOWNGRADE or cvdLongGuardOk)
bool setupShortB = setupShortBRaw and (not CVD_GUARD_DOWNGRADE or cvdShortGuardOk)
bool cvdLongDowngraded = CVD_GUARD_DOWNGRADE and setupLongBRaw and not cvdLongGuardOk
bool cvdShortDowngraded = CVD_GUARD_DOWNGRADE and setupShortBRaw and not cvdShortGuardOk
```

7. Risk row should include both price invalidation and CVD invalidation when a plan is active:

```pine
string longInvalidText = "多失效:" + invalidBaseText + " " + f_fmt_price(longInvalidPrice) + "｜" + cvdLongGuardText
string shortInvalidText = "空失效:" + invalidBaseText + " " + f_fmt_price(shortInvalidPrice) + "｜" + cvdShortGuardText
string invalidSpecificText = setupX ? "禁追，不谈失效" : activeLongPlan ? longInvalidText : activeShortPlan ? shortInvalidText : cvdDowngradeText
string focusedPlanText = setupX ? xWaitText : activeLongPlan ? longPlanText : activeShortPlan ? shortPlanText : cvdLongDowngraded ? "多等:" + cvdLongWaitText : cvdShortDowngraded ? "空等:" + cvdShortWaitText : planShortText
```

## Pitfalls

- Do not show fake risk for `X`; use `禁追，不谈失效` and put the actual waiting condition in `执行`.
- CVD values are not prices; label them as CVD guard levels (`破近低`, `回近高`) rather than mixing them with price invalidation.
- Keep wording readable for live use. Prefer `CVD维持抬高` / `CVD不转强` over terse abbreviations.
- This is a confirmation/downgrade layer, not a standalone trade signal. Price level, high timeframe filter, and structure still gate the setup.
