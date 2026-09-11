# 20260814 上传版双指标全量审计（评分 + 社区对标 + 表格审查 + 高效流程）

来源：20260814 会话第二轮全面审计（上传版副指标 758 行/47 input、主指标 3452 行/198 input+44 const）。
核心结论：上一轮（pine-20260814-community-audit-findings.md）的 P0-P3 与表格增强**全部已落地**，两文件全量编译 0 错 0 警，是发布以来最干净一版。本轮最大表格问题=副指标"5 行精简"定稿未落地。

## 一、历史修复落地验证（高效方法：按修复签名 grep，勿从头审计）

| 历史项 | 签名 | 状态 |
|---|---|---|
| P0 主指标 CVD 跨锚检查 | cvdSameAnchorHigh / cvdCrossAnchorHigh（主 L818-838） | ✓ |
| P1 副指标爆仓 liqA 基线化 | perc_perp >= perpShareBaseA（副 L473） | ✓ |
| P2 MFI 口径注释 | 副 L181-183 注释块 | ✓ |
| 表格增强1 缺票维度 | resoMissTxt（副 L577-582） | ✓ |
| 表格增强2 结论行信号新鲜度 | lastSignalBars（主 L3259-3260） | ✓ |
| 遗留1 f_sup_res swept 门控 | not prevDayHighSwept（主 L1716-1763） | ✓ |
| 遗留2 扫N/M→活N/M | sweepCntText（主 L3160-3162） | ✓ |
| 遗留3 obLife 死代码 | 已删（主 L2464-2466） | ✓ |
| 遗留4 ADR 无条件 request | f_adr_daily()（主 L301-307） | ✓ |
| 遗留5 HTF FVG/OB 两 request 常开 | 主 L2149-2150 无条件 request.security | ✗ **仍未修** |
| 遗留6 calctype SUM 死参数 | 副 L30 | ✗ 仍存（转 const 0 功能损失，可不动） |
| 遗留7 f_is_metal_ticker 双实现 | 主 L269 / 副 L37 各一份 | ✗ 仍存（改一处忘另一处会分叉） |

## 二、编译与配额实证（本轮数据，供后续 diff）

- 全量编译：pine-facade translate_light（scripts/tv_pine_check_files.mjs），副 57.5K 字符、主 220K 字符，均 0 错 0 警。
- 副指标：29/40 request（20聚合+4OI+1LSR+1现货+1单源+1汇率+1HTF）、41/64 plot、47 input、表格容量 10。
- 主指标：8/40 request、46/64 plot（43 plot+2 fill+1 bgcolor）、242/254 input+const、表格容量 18 用 13 行。
- 主指标行动格已 13 行=原 12 行把"看位"拆成前位+现位（20260813 定稿）；副指标紧凑模式 7 行（信号/结论/流向/持仓/量能/覆盖/[风险]/操作）。
- 静态扫描误报（勿当 P0）：def 顺序"违例"=函数返回元组解构跨函数；hour/minute"未定义"=Pine 内建。编译 0 错为最终裁判。

## 三、评分新基线（口径沿用 indicator-scoring-rubric-2026-08-10）

| 维度 | 主 SVP | 副 AggVol |
|---|---|---|
| 编译合规 | 100 | 100 |
| 配额健康 | 96（遗留5 常开 req -4） | 95（calctype 死参 -2、RUB 复合 ticker 死路径 -3） |
| 逻辑一致性 | 94（确认行 HTF 双显示、标·R 语义） | 92（5 行定稿未落地 -4、持仓行超宽 -2、MFI/OBV 口径分裂已标注仍易混 -2） |
| 诚实性 | 96 | 96 |
| 决策辅助 | 92（标·R 易误读 -3、无隐背离但顺确认替代 -2、薄量区无图标注 -3） | 90（无信号新鲜度 -4、结论主词未并入信号行 -3、CVD 中档估算 -3） |
| 综合 | **95**（上轮 92） | **94**（上轮 88） |
| 市场适配 | 93 | 90（上轮 85，非加密短路函数化已落地 +2） |

诚实性双 96 维持：CVD=估算、爆仓=proxy、现货无逐笔、跨锚标记、LSR缺——审计时不得建议削弱。

## 四、表格问题清单（本轮新发现）

P1（应改，待用户拍板）：
1. 副指标紧凑模式 7 行 ≠ 20260813 定稿 5 行（信号含结论主词/流向含量能/持仓/数据=覆盖+风险警告优先/操作）。代码未落地，须确认落地 or 维持（"信息完整甚于行数少"）。

P2（可选）：
2. 主指标确认行 HTF 双显示："HTF✓"（计划门槛）与行尾"·高周多"（实际方向）语义不同但视觉重复。
3. 主指标风控行"标·2.1R"——"标"后放的是盈亏比不是目标价（目标在磁吸行），改"R2.1"更准。
4. 副指标持仓行三拼（OI状态+LSR+基差）最长"▲新多 2.35%·共识85%·加速·均衡·基差-0.05%"，手机宽度风险。
5. 副指标 OI 行未接时"未接副指标·选OI%"占位正常态浪费宽度。

明确不动：主 13 行定稿、磁吸格式（分NN★HTF距离A）、KZ 倒计时、波%分位、前位/现位行——信息密度已到顶。

## 五、社区新对标（本轮联网）

- **plyst script/Mdwp2lQs**（317 boosts，同主题最热）：10 所 + Spot/Perp 分列 Delta + L/S Ratio + whale 过滤 + Market correlation；已抽库至 283 行。扩 10 所需 +20 request 直接超 40 上限——不扩是配额事实不是偏好。
- **JOAT CVD script/V5NHdMI3**：Regular + Hidden 背离四型 + 锚定模式（累计/日/周）。Hidden（延续型）与我们"顺多/顺空确认"职责重叠，加前需评估去重。
- **Feels（VolodymyrFilias/feels-indicators）**：Liquidity Magnet 命中追踪 → 磁吸 v3（30 窗口分方向）已对标 ✓；Air Pocket 薄量区标注（0 request，复用 profileEngine 行数据）→ 候选；Power of Three → 与 ICT 会话/扫线重叠，不加。
- Reddit r/Daytrading 护栏共识：CVD 估算只作 confluence、诚实标注是底线 → 全部对齐。

## 六、增强候选清单（功能冻结流程：只建议不落地）

副指标：P1 结论行补信号新鲜度"·信号N根前"（零配额，主指标 lastSignalBars 已有）；P2 CVD 估算升档 body+wick→security_lower_tf 低周期聚合（+1 req 30/40 + 一份免费档 intrabar 预算）；P2 隐背离；P3 request.footprint（Premium+）。
主指标：遗留5 HTF FVG/OB request 函数化短路省 2 req（零成本，最该先做）；Air Pocket 薄量区标注。

## 七、技术坑（本轮踩到，可复用）

1. **Web UI 上传把 Pine 文件转 CRLF** → CE10156。流程：check_line_endings.py 检出 → `sed 's/\r$//'` 归一化到 LF 副本 → 编译验证 → LF 版交付到 桌面/hermes下载文件/<任务名>_YYYYMMDD/（文件名带日期，原版保留）。
2. **MSYS /tmp 与 Windows 原生 Python 不互通**：sed（git-bash）写 /tmp 后 Python 找不到。临时工作文件放 `hermes/sandboxes/<name>/` 用 `C:/Users/...` 全路径。
3. **TV CDP 断线报 ClosedResourceError → tv_launch 重拉即可**（tv_pine_check_files.mjs 依赖 TV 桌面在跑；import 路径 D:/Hermes agent/tools/tradingview-mcp/src/connection.js）。
4. **web_extract 对 tradingview.com 返回 "Blocked: private or internal network"**（本机代理环境）→ 改 browser_navigate；TV 脚本页描述文本已含特性清单，Monaco 源码用 browser_console 抓 .view-lines 拿不到（空）——脚本源码走 TV 桌面 Pine 编辑器或官方 API。
5. **skill references 中文 md 编码探测顺序**：utf-8 → gbk → gb18030 → utf-16（本轮文件实为 utf-8 + \r\r\n 行尾，直接 utf-8 解码即可）。
6. **高效审计路径**：读两文件全文 → 读上一轮 audit findings 文件按修复签名 grep（勿从头审）→ 行尾检查+归一化 → tv_pine_check_files.mjs 全量编译 → pine_static_scan.py 配额 → 社区搜索对标 → 表格逐行对照用户定稿记忆审查 → rubric 口径评分 → LF 版交付桌面。
