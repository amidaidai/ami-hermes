# 20260814 双指标修复：跨锚背离 + 爆仓代理 + 全量编译端点

## 一、全量编译直调端点（替代内联 pine_check，省 token）

完整源码不必塞进 MCP 参数（内联会消耗数万 token 且易引入字符误差）。
POST `https://pine-facade.tradingview.com/pine-facade/translate_light?user_name=Guest&pine_id=00000000-0000-0000-0000-000000000000`：

- body: urlencoded `source=<完整源码>`（Content-Type: application/x-www-form-urlencoded）
- headers: `Accept: application/json` + `Referer: https://www.tradingview.com/` + 浏览器 UA
- 响应: `result.errors2[]` / `result.warnings2[]`（每项 start.line/column/message），两者皆空仅表示 translate_light 轻量转换未报错，不等于客户端完整编译/IL限额验收。20260907 实例：主指标轻量端点成功，客户端仍报 CE10117 100488 > 100256。
- CE10117 官方专项：https://www.tradingview.com/pine-script-docs/errors/CE10117/ 。有效技术包括缩短嵌入常量字符串（如tooltip，保留语义）及将非完全相同的重复结构封装为UDF；空白/注释/变量短名和编译器自动合并的相同表达式不能作为IL节省证据。成功响应不返回IL大小，不报推算余量。
- 条件调用构造器UDF时，将 chart-series 历史表达式先在全局逐K求值再供函数读取，避免新引入 CW10003；对每一方向把函数参数代回原分支进行规范化源码比较，同时检查门控、对象插入顺序、EMA相等边界（>=与<=分别保留）。
- Python urllib 即可，单文件 ~5 秒；Windows TLS 不通时改 curl 或 CDP 浏览器上下文 fetch
- 端点源自 `D:/Hermes agent/tools/tradingview-mcp/src/core/pine.js` 的 check()；pine_check MCP 工具是它的薄封装
- 经验：副指标 69KB / 主指标 241KB 修改后全文直传均 0 错 0 警（20260814 实测）

## 二、P0：主指标 CVD 背离补锚定一致性检查

**问题**：主指标 cvdBearDiv 用 `ta.valuewhen(_phPair, ...)` 取上一对 pivot 直接比较 CVD，
但没有检查两 pivot 是否在同一锚定周期。跨锚时 CVD 已在 `cvdReset` 处归零，值域不可比 → 假背离
污染 C 级反转信号。副指标早有 `cvdSameAnchorHighA`（L416-428），主副口径分叉。

**修法（与副指标同口径）**：
```
int cvdAnchorId = int(time(cvdAnchorTf))
int cvdPivotAnchorHigh = _phPair ? cvdAnchorId[_pl] : na
int _pah = ta.valuewhen(_phPair, cvdPivotAnchorHigh, 1)
bool cvdSameAnchorHigh = not na(cvdPivotAnchorHigh) and cvdPivotAnchorHigh == _pah
```
- pivot 确认 K 上取 `cvdAnchorId[_pl]`（事件发生 K 的锚 ID，_pl=5 是 pivot 回看）
- cvdBearDiv/cvdBullDiv 各加 `and cvdSameAnchor*` 条件
- `ta.valuewhen` 的 source 可以是 int series，返回 int，赋 int 变量合法（已编译验证）
- 跨锚形态：`cvdCrossAnchor* = 背离条件成立 and not cvdSameAnchor*` → cvdRefTag 显示"·跨锚"
- **cvdRefTag 定义必须移到背离检测之后**（依赖 cvdCrossAnchor*，Pine 自上而下编译，
  原 L767 位置前向引用会报 Undeclared）。grep 确认消费点唯一再移动。

**审计复用**：双指标审计时逐行核对主副 CVD 背离检测是否同口径（锚定一致性/摆动过滤/关键位过滤三项）。

## 三、P1：爆仓代理前置 PERP>SPOT 恒真

`liqA = perpSpotImbalance > 0` 在加密永续恒真（PERP 量常态 SPOT 5-10 倍）→ 无过滤力。
改：`liqA = not na(perpShareBaseA) and perc_perp >= perpShareBaseA`（永续占比不低于自身 50 周期 SMA 基线）。
语义：现货主导行情时排除爆仓代理（衍生品叙事弱）。核心过滤仍由 OI 一致收缩+放量+CVD 同向承担。
注意 perpShareBaseA（ta.sma(perc_perp,50)）定义在 liqA 之前才可用，且 perc_perp 与 datatype 无关（跨所聚合量），无死路径。

## 四、P2：MFI 口径标注（只注释不改代码）

ta.mfi(hlc3) 内建图表成交量，无法注入 5 所聚合量；与 OBV（聚合口径）不同。
2026-08 曾因社区 plyst 版指出自定义公式偏离标准而改回官方 ta.mfi()——不要再改回自定义。
正确动作：代码注释 + TTmode tooltip 标注"MFI=当前图表口径，非5所聚合，勿与OBV混用"。

## 五、P3：request 三元注释修正

"USD 短路跳过请求"不实——TV request.* 计算独立于条件块/三元，条件只控结果消费。
注释改中性："USD 默认路径结果恒为1.0；三元条件只控制结果消费，底层请求仍会执行；仅非USD路径实际使用汇率值"。

## 六、表格增强（零配额，移动优先）

1. 副指标信号行共振补缺票：`' 缺' + 缺失维度名`（CVD/OI/量/HTF），str.trim 去尾空格；
   仅 dirUpA/dirDnA 存在且 resoCountA<4 时拼接；4/4 不加字保持宽度。
2. 主指标结论行信号新鲜度：`setupX ? "" : lastSignalBars == 0 ? "·新" : "·信号N根前"`，
   math.min(lastSignalBars, 99) 封顶。lastSignalBars 既有逻辑（信号边沿归零/无信号递增）直接复用。
   注意 lastSignalBars==0 ⟺ 信号存续（signalNowLong/Short 为真），无需再判 planSide。

## 七、配额不变性核对

本轮修改 0 新增 input/plot/request/alert（全部普通变量），六项和不变：主 250/254、副 121/254。
修改后每次审计都应核对"新增变量是否触碰六项"。

## 八、20260814 第二批：单边适配 + 副指标增强 + 设置项（编译0错0警）

**主指标 8 处**（详见 pine-20260812 参考"已落地"节）：f_sup_res 次级位 swept 门控（注意 UDF 引用全局 bool 计外部元素，+4 后仍过编译）、活N/M、obLife 删除、ADR 函数化、磁吸格式对齐定稿、finalInvalidSpecificText 删除（失效价=止损价重复，用户"空失效"反馈）、看位"等新位"文案。

**副指标增强 2 项（用户确认后落地）**：
1. OI 加速度：`oiAccelA = not na(oiPctChgA) ? oiPctChgA - nz(oiPctChgA[5]) : na`，持仓行尾部 ±2pct 阈值显示"·加速/·减速"。**陷阱**：oiAccelA 定义在 oiOkA 之前（L385 vs L387），用 oiOkA 守卫会前向引用报错——改用 `not na(oiPctChgA)`。
2. 爆仓强度：var liqStreakA/liqOIDropA，信号期累加 streak + math.min 追踪 OI 最低变化率，断信号清零；量能行 `liqStreakA>=2` 才追加"·3根·OI-2.5%"。信号期 oiPctChgA 恒负（shortLiqA 要求 oiDnA），liqOIDropA 正确累积。

**设置项（用户偏好，默认值改动）**：主指标 ACTION_PANEL_SIZE 默认 size.tiny；副指标 forceovy 默认 false（不叠加主图）+ ACT_POS 默认'右中'。
