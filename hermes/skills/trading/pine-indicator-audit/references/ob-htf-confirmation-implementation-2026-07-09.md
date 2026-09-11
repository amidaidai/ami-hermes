# OB HTF 确认实现 — 2026-07-09 实装记录

## 背景

用户上传 `SVP_v6_ready.pine`，审计发现 OB 缺少 HTF 确认逻辑（FVG 有完整 HTF 确认链，OB 没有）。用户明确要求「ob的设置和fvg差不多，高周期可以确认低周期」。

## FVG HTF 确认链（参考实现）

```
f_htf_fvg() → request.security(htf, f_htf_fvg) → htfFvgList → 本级FVG维护时遍历检查重叠 → f.htfConf=true → 标签"HTF"后缀 + MCP质量码升级
```

## OB HTF 确认链（本轮新增）

### 1. f_htf_ob() 函数

```pine
f_htf_ob() =>
    float sh = ta.pivothigh(high, OB_LOOKBACK, OB_LOOKBACK)
    float sl = ta.pivotlow(low, OB_LOOKBACK, OB_LOOKBACK)
    var float lsh = na
    var float lsl = na
    if not na(sh)
        lsh := sh
    if not na(sl)
        lsl := sl
    bool hBosBull = not na(lsh) and close > lsh and close[1] <= lsh
    bool hBosBear = not na(lsl) and close < lsl and close[1] >= lsl
    float obTop = na
    float obBot = na
    bool obBull = false
    bool obBear = false
    if hBosBull or hBosBear
        // 合并 bull/bear 的 OB 查找逻辑省 token
        int off = na
        for k = 1 to 10
            if hBosBull and close[k] < open[k]
                off := k
                break
            if hBosBear and close[k] > open[k]
                off := k
                break
        if not na(off) and off + 1 <= 10
            bool prevBull = close[off + 1] > open[off + 1]
            bool prevBear = close[off + 1] < open[off + 1]
            if (hBosBull and prevBull) or (hBosBear and prevBear)
                obTop := high[off + 1]
                obBot := low[off + 1]
                obBull := hBosBull
                obBear := hBosBear
    [obBull, obBear, obTop, obBot]
```

### 2. request.security 调用

```pine
[obHBull, obHBear, obHTop, obHBot] = request.security(syminfo.tickerid, fvgHtfRes, f_htf_ob(), lookahead=barmerge.lookahead_on, ignore_invalid_symbol=true)
```

复用 FVG 的 `fvgHtfRes`（同一 HTF 周期），+1 配额。总 request.security 从 9 → 10。

### 3. htfObList 维护

```pine
var array<OBZone> htfObList = array.new<OBZone>()
bool newHtfOb = fvgHtfValid and SHOW_HTF_OB and barstate.isconfirmed and (obHBull or obHBear) and not na(obHTop) and not na(obHBot)
if newHtfOb and obHBull and (not obHBull[1] or obHTop != obHTop[1])
    array.push(htfObList, OBZone.new(na, na, obHTop, obHBot, true, false, false, true, bar_index))
if newHtfOb and obHBear and (not obHBear[1] or obHBot != obHBot[1])
    array.push(htfObList, OBZone.new(na, na, obHTop, obHBot, false, false, false, true, bar_index))
// 清理填充/过期
if array.size(htfObList) > 0
    int hoi = array.size(htfObList) - 1
    while hoi >= 0
        OBZone hz = array.get(htfObList, hoi)
        if (hz.isBull ? close < hz.bot : close > hz.top) or not fvgHtfValid
            array.remove(htfObList, hoi)
        hoi -= 1
    while array.size(htfObList) > 4
        array.shift(htfObList)
```

### 4. OBZone UDT 变更

```pine
type OBZone
    box   bx
    label lb
    float top
    float bot
    bool  isBull
    bool  isBreaker
    bool  mitigated
    bool  htfConf    // 新增字段
    int   bornBar
```

OBZone.new 从 8 参变 9 参：`OBZone.new(nb, olb, obTop, obBot, true, false, false, false, bar_index)`。

### 5. 本级 OB 维护中检查重叠

```pine
// 在 else 分支内, box.set_right 之前
ob.htfConf := false
if fvgHtfValid and array.size(htfObList) > 0
    for ogj = 0 to array.size(htfObList) - 1
        OBZone ohz = array.get(htfObList, ogj)
        if ohz.isBull == ob.isBull and ob.top >= ohz.bot and ob.bot <= ohz.top
            ob.htfConf := true
```

### 6. 标签加 HTF 后缀

```pine
string obTag = showBrkTxt ? (ob.isBull ? "BRK↑" : "BRK↓") : (ob.isBull ? "OB↑" : "OB↓") + (ob.htfConf ? " HTF" : "")
```

### 7. inBullObHtf / inBearObHtf

```pine
bool inBullObHtf = false
bool inBearObHtf = false
// 在 OB 维护循环中
inBullObHtf := inBullObHtf or ob.htfConf
inBearObHtf := inBearObHtf or ob.htfConf
```

### 8. confirmScore 额外加分

```pine
// 原: ((inBullOB and activeLongPlan) or (inBearOB and activeShortPlan) ? 1 : 0)
// 新: 同上 + ((inBullObHtf and activeLongPlan) or (inBearObHtf and activeShortPlan) ? 1 : 0)
```

### 9. bcDirectRaw 补 OB HTF

```pine
// 多: ...or inBullOB or inBullBreaker or inBullObHtf) and not adrLowRoomLong...
// 空: ...or inBearOB or inBearBreaker or inBearObHtf) and not adrLowRoomShort...
```

### 10. SHOW_HTF_OB 输入

```pine
bool SHOW_HTF_OB = input.bool(true, "高周期OB确认本级", group=OB_GROUP, tooltip="...")
```

`fvgHtfValid` 改为：
```pine
bool fvgHtfValid = (SHOW_HTF_FVG and SHOW_FVG) or (SHOW_HTF_OB and SHOW_OB) and timeframe.in_seconds(fvgHtfRaw) > curTfSec
```

## Token 预算管理

新增 OB HTF 约 1,400 tokens（函数+request.security+htfObList+维护+确认+标签+变量+score+bcDirect+输入）。

本轮从 79,380 → 80,731 超限，削减措施：
1. tooltip 截到 25 字符 → 省 ~217 tokens
2. 精简 f_htf_ob（合并 bull/bear 分支）→ 省 ~38 tokens
3. 内联 OB HTF 确认循环（for 替代 while）→ 省 ~38 tokens
4. 删行内注释 → 省 ~158 tokens

最终：79,951 / 80,000 ✅ 余量 49。

## 交付状态

- SHA: `ed514e23625db498`
- 三路径同步: upload/default + Desktop/SVP_v6.pine + Desktop/SVP_v6_ready.pine
- request.security: 10/40 ✅
- Data Window: 12 plots ✅
- Token: 79,951/80,000 ✅ 余量49（极薄，后续加功能必须先削）