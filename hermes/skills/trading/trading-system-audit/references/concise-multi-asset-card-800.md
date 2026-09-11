# 800字多资产执行卡模式

适用场景：用户认为 1500 字左右的分析卡仍偏长，要求“压到 800 字这样看看”。目标不是完整报告，而是移动端可快速执行的交易卡。

## 设计原则

- 保留头部 `①-⑩` 标记，但允许合并为少量行，满足回归测试与模板锚点。
- 保留正文五段标题：环境、结构、博弈、操作、风控。
- 非操作段每段 1-2 行，只写判断结果，不展开解释。
- 操作段保留 A/B 双预案，但每个预案只保留：入场、触发、确认、SL、TP、仓位、失效。
- 保持多资产字段隔离：
  - 加密：Funding/Taker/CVD/订单流
  - 黄金：DXY/US10Y/Kill Zone/美元与美债
  - 外汇：美元腿、利差、央行/通胀窗口
  - 股票：指数、板块、成交量、财报
  - 期权：Delta/Theta/IV/希腊值/权利金最大亏损
- 非加密卡严禁泄漏 `Funding`、`Taker`、`CVD`、`订单流`。
- 期权 TP/SL 必须按权利金正数价格处理，不能出现负权利金。

## 推荐结构

```text
◷ 时间
① 品种
② 周期：4h/1h/15m/5m 一行
③ 现价
④ 状态 + ⑤ 模型
⑥ 评分 + ⑦ 决策
⑧ 仓位 + ⑨ 失效 + ⑩ 数据

一、环境：数据 + 资产核心因子；催化一句
二、结构：背景分界；执行触发/禁追
三、博弈：结构/引擎/资产流向裁决；多空强弱
四、操作：A/B 预案，入场/触发/确认/SL/TP/仓位/失效
五、风控：杠杆/资产风险/R:R；数据/事件/执行闸门
```

## 验证 Bundle

修改 `hermes/scripts/auto_card.py::render_card_locked()` 后必须执行：

```bash
python -m py_compile hermes/scripts/auto_card.py
python sandbox/send_multi_asset_mock_cards.py
python - <<'PY'
from pathlib import Path
import re
bad=[]
for p in sorted(Path('outputs/mock_cards').glob('*.md')):
    s=p.read_text(encoding='utf-8')
    print(p.name, len(s))
    if len(s)>920: bad.append((p.name,'too long',len(s)))
    if re.search(r'setup_id|model_id|entry_tag|exit_tag|critical|warning|info|\|', s): bad.append((p.name,'machine leak'))
    if p.name.startswith(('stock','option','forex')) and re.search(r'Funding|Taker|CVD|订单流', s): bad.append((p.name,'crypto field leak'))
    if p.name.startswith('option') and re.search(r'TP.*`-', s): bad.append((p.name,'negative option target'))
    for m in ['① 品种','② 周期','③ 现价','④ 状态','⑤ 模型','⑥ 评分','⑦ 决策','⑧ 仓位','⑨ 失效','⑩ 数据']:
        if m not in s: bad.append((p.name,'missing '+m))
print('BAD', bad)
PY
python -m pytest -q
```

成功基线：五类样卡约 `800-900` 字；扫描 `BAD []`；全量测试通过。

## 实战结果

2026-06-20 将 1500 字版进一步压缩为 800 字执行版，五类样卡最终为：

- BTC：895 字
- XAU：865 字
- EURUSD：860 字
- AAPL：850 字
- 期权：875 字

全量测试 `98 passed`，提交 `6429f0f trim analysis cards to 800-char execution format`。