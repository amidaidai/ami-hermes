# 20260814 P2 表格修复 + 评分基线 + 社区对标增量

来源：20260814 会话，对上传版主指标（3452行/198input+44const）与副指标（758行/47input）全面审计 → P2 四条落地 → 重新编译验证。

## 上传版陷阱：Web UI 上传的文件是 CRLF
- 用户经 Web UI 上传的两个文件全部 CRLF（LF=0）。直接用会 CE10156。
- 固定流程：先跑 scripts/check_line_endings.py 检查 → `sed 's/\r$//'` 归一化为 LF 副本 → 编译验证用副本 → 交付 LF 版（文件名带日期、旧版保留、放桌面/hermes下载文件/<任务名>_YYYYMMDD/）。
- 全量编译走 scripts/tv_pine_check_files.mjs（pine-facade translate_light），本会话两文件 0 错 0 警（副 57.5K 字符 / 主 220K 字符）。

## 工具坑：search_files 的 Windows 盘符路径
- 本机传 `C:/Users/...` 绝对路径会报 rg IO error（/c/... 系统找不到指定的路径）。
- 解法：改用相对路径（工作目录是 hermes/workspace，沙箱文件用 ../sandboxes/xxx）。

## 历史修复确认（20260814 P0-P3 全部已落地于上传版）
- 主指标 CVD 背离跨锚检查（cvdSameAnchorHigh/cvdCrossAnchorHigh）✓
- 副指标 liqA 改 perc_perp 相对基线（L473 perpShareBaseA）✓
- MFI 口径注释 ✓；request 短路注释修正 ✓
- 表格增强：副指标信号行缺票维度（resoMissTxt）、主指标结论行信号新鲜度 ✓
- 遗留1-3：f_sup_res swept 门控、活N/M（sweepCntText）、obLife 死代码删除 ✓

## P2 表格修复（用户拍板"保持7行 + P2可修"，已落地+编译验证）
1. 主指标确认行 HTF 去重：删 ckHtf（"HTF✓"门槛）。语义依据：门槛✗只可能出现在高周空（guideHtfText 已带⚠）或未定时，信息无损。确认行 = ckCvd + " " + ckLoc + MSS。HTF 维度由行尾 guideHtfText（·高周多/空/未定+⚠）唯一承担。
2. 主指标风控行 "标·2.1R" → "R·2.1"：`"止"+panelStopVal+(panelTgtVal!="—"?" R"+str.replace(panelTgtVal,"R",""):"")`。原"标"后跟盈亏比易误读为目标价（目标在磁吸行）。
3. 副指标持仓行压宽：oiPctTxtA 去数字前空格、"·共识"→"·同"（字段全保留，压缩不删除）。
4. 主指标 OI 行占位 "未接副指标·选OI%" → "OI未接"。

## 评分基线（20260814 P2 修复后，供后续 diff）
- 主 96：编译100 / 配额96 / 逻辑95 / 诚实96 / 决策93；市场适配93。剩余扣分：遗留5（HTF FVG/OB 两 request 常开，约 L2149-2150）——修完即 97。
- 副 95：编译100 / 配额95 / 逻辑93 / 诚实96 / 决策90；市场适配90。剩余扣分：无信号新鲜度、CVD 中档估算（body+wick）、结论主词未并入信号行（用户已拍板保持7行，此为列出的 P2 增强候选非缺陷）。
- 上轮基线（P0-P3 修复前）：主 92 / 副 88。

## 社区对标增量（20260814 实测）
- plyst 增强版现抽库至 283 行（Pine Editor 显示），318 boosts / 7272 views = 聚合成交量类最热。特性：10 所、Spot/Perp 分列 Delta、L/S 比、whale 过滤、市场相关性、AVG/MEDIAN/VARIANCE。扩 10 所需 +20 request 超免费档，不可行（用户 5+4 所已拍板）。
- JOAT CVD Delta Divergence：Regular+Hidden 四型背离。Hidden=延续型，与顺多/顺空确认职责重叠——加前须评估去重。
- Feels Air Pocket：薄量区标注（成交量<峰值18%），0 request（复用 profileEngine 行数据）——P2 候选。
- Reddit 护栏共识：CVD 估算仅作 confluence、诚实标注是底线——本系统全对齐。
