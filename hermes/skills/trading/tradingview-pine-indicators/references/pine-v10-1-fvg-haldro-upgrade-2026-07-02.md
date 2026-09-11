# SVP v10.1 + HALDRO v2.1 小版本升级记录（2026-07-02）

用于未来修改棠溪双指标（主 `svp_indicator.txt` + 副 `haldro_indicator.txt`）时复用。目标是小修增强，不推倒重构。

## 本次落地内容

### HALDRO 副指标：估算CVD背离三重过滤

副指标 CVD 是影线/实体比例估算，不是真逐笔 Delta；显示与 Data Window 必须诚实标注为估算口径。

推荐实现要点：

```pine
int    cvdDivLenA = ACT_LB * 3
float  prevPriceHighA = ta.highest(high[1], cvdDivLenA)
float  prevPriceLowA = ta.lowest(low[1], cvdDivLenA)
float  prevCvdHighA = ta.highest(sessCvdA[1], cvdDivLenA)
float  prevCvdLowA = ta.lowest(sessCvdA[1], cvdDivLenA)
float  cvdSwingRangeA = ta.highest(high, cvdDivLenA) - ta.lowest(low, cvdDivLenA)
float  cvdAtrA = ta.atr(14)
bool   cvdSwingOkA = not na(cvdAtrA) and cvdSwingRangeA > cvdAtrA * 1.5
bool   cvdBearDivA = high > prevPriceHighA and sessCvdA < prevCvdHighA and cvdSwingOkA and cvdSlopeA <= 0
bool   cvdBullDivA = low < prevPriceLowA and sessCvdA > prevCvdLowA and cvdSwingOkA and cvdSlopeA >= 0
```

三重过滤：
1. 价格 HH/LL；
2. CVD LH/HL 不确认；
3. 摆动幅度 `> 1.5 * ATR(14)` 且 CVD slope 方向确认。

集成规则：
- `flowShortA` 优先显示 `卖背离` / `买背离`。
- `cvdTxtA` 显示 `估算CVD ⚠卖背离` / `估算CVD ⚠买背离`。
- `confirmScoreA` 对 `cvdDivAnyA` 扣 1。
- `riskWarnA` 加 `⚠CVD背离`。
- 新增提醒 `估算CVD背离`。

### HALDRO Data Window 口径

将旧 `CVD Value` 改成：
- `Estimated CVD Value`
- `CVD Method Code`：`1` = 影线/实体估算Delta
- `CVD Quality Code`：`0` = 非加密不可用；`1` = 弱/中性；`2` = 有方向；`3` = 背离警告

未来自动脚本读取副指标时，应优先读 `Estimated CVD Value`；如要兼容旧版，再 fallback 到 `CVD Value`。

### HALDRO 精简行动格

用户要求手机/盯盘可读，副指标精简模式不要只剩 3 行。推荐 5 行：

| 行 | 内容 |
|---|---|
| 信号 | 信号灯 + 方向 + 共振数 + flowShort + confirmScore |
| 结论 | actText |
| 流向 | `cvdTxtA` + 风险警告 |
| 持仓 | OI 状态 |
| 操作 | comboTxt |

### SVP 主指标：FVG MCP Data Window

为了 MCP/自动分析稳定读取 FVG，而不是只从图形框推断，新增：
- `MCP Bull FVG CE`
- `MCP Bear FVG CE`
- `MCP FVG Quality Code`

质量码约定：
- `0`：无有效FVG
- `1`：最近多FVG，本级确认
- `2`：最近多FVG，HTF确认
- `11`：价格当前在多FVG内
- `12`：价格当前在HTF确认多FVG内
- 负数同理为空FVG：`-1/-2/-11/-12`

实现位置：在 FVG 维护循环里记录最近未填补多/空 FVG 的 CE、距离与 HTF确认；在 MCP Data Window 区域输出三条 plot。

### 颜色碰撞修复

保留用户长期指定色：
- DO：`#673AB7`
- 周VWAP：`#FF00FF`
- 月VWAP：`#FF9800`
- EMA55：`#B71C1C`

避开碰撞：
- EMA21 从 `#FF00FF` 改 `#009688`，不再撞周VWAP。
- 亚洲盘从 `#FF9800` 改 `#FFC107`，不再撞月VWAP。
- 前日线从 `#0F0F0F` 改 `#455A64`，不再撞POC。

## 验证清单

交付前至少做文本级审计：

```bash
python - <<'PY'
from pathlib import Path
import re
for p in [Path('D:/Hermes agent/svp_indicator.txt'), Path('D:/Hermes agent/haldro_indicator.txt')]:
    s=p.read_text(encoding='utf-8')
    print(p.name, 'lines', s.count('\n')+1,
          'plot', len(re.findall(r'\bplot\s*\(', s)),
          'fill', len(re.findall(r'\bfill\s*\(', s)),
          'bgcolor', len(re.findall(r'\bbgcolor\s*\(', s)),
          'table.new', len(re.findall(r'\btable\.new\s*\(', s)),
          'request.security', len(re.findall(r'\brequest\.security\s*\(', s)))
PY
```

同时检查：
- `MCP Bull FVG CE` / `MCP Bear FVG CE` / `MCP FVG Quality Code` 存在；
- `Estimated CVD Value` / `CVD Method Code` / `CVD Quality Code` 存在；
- 没有旧 `"CVD Value"` 标题残留；
- EMA21、周VWAP、月VWAP、亚洲盘、POC、前日线颜色不再碰撞；
- 复制到桌面后用 `sha256sum` 对比生产文件与桌面文件一致。

## 交付路径约定

用户偏好桌面 `.txt` 文件。交付时复制到：
- `C:/Users/Administrator/Desktop/svp_indicator_v10_1_YYYYMMDD.txt`
- `C:/Users/Administrator/Desktop/haldro_indicator_v2_1_YYYYMMDD.txt`

最终仍需 TradingView Pine Editor 服务器编译确认；本地只能做文本/结构级验证。
