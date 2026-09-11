# 20260814 增强最终版验证 + 评分基线更新（覆盖 upload-version-full-audit 的 95/94）

场景：用户上传「SVP主指标_增强最终版_20260814.txt」（3484 行 / 242,240 B）+「AggVol副指标_增强最终版_20260814.txt」（797 行 / 72,302 B），问评分、加密/贵金属/股票/外汇适配、能否辅助决策、表格是否优化。

## 一、快速识别已交付版（审计前先做）

- 上传文件与 `hermes/sandboxes/pine_audit_20260814/` 的 svp.txt/aggvol.txt **字节完全一致**（72,302 / 242,240）→ 就是当天交付版，不是新版本。
- `grep -c $'\r'` = 0 → LF 干净，无 CRLF 坑（Web UI 上传转 CRLF 的 CE10156 本轮未触发）。
- 判定为已交付版后：只做编译实测 + 配额扫描 + 按上一轮审计结论 grep 修复签名，**不复审全文**（与 upload-version-full-audit 的高效路径一致，但先加字节比对一步）。

## 二、编译实测（无需 TV 桌面/CDP）

execute_code 内 Python urllib 直调 translate_light 全量编译：

- 主指标 221,544 字符 → 0 错 0 警，1.2s；副指标 59,474 字符 → 0 错 0 警，1.5s。
- 端点、headers 与 cross-anchor-and-compile-endpoint.md 相同；**本轮 urllib TLS 直通无问题**，失败再回退 curl / CDP fetch。
- 配额（pine_static_scan.py）：主 8 个 request 调用点/40（ADR / HTF FVG / HTF OB 三处函数化短路均生效）、43 plot + 2 fill + 1 bgcolor = 46/64；副展开 30/40（较上轮 29 多出的 1 = CVD 1m 低周期升档 f_cvd_ltf_pack）、41/64 plot。
- 静态扫描误报照旧：hour/minute "未定义"=Pine 内建；def-before-use 违例(kzShort/sweepCntText)=函数内局部；编译 0 错为最终裁判。

## 三、评分基线更新（20260814 最终版，沿用 20260810 口径）

| 分 | 主 SVP | 副 AggVol | 上轮 |
|---|---|---|---|
| 综合 | **97** | **96** | 95 / 94 |
| 市场适配 | **94** | **91** | 93 / 90 |
| 辅助决策 | **96** | **86** | 84 / 78 |

主综合五维：编译 100 / 配额 100（遗留5 修复后无扣分项）/ 逻辑 96 / 诚实 96 / 决策辅助 95（R2.1 格式修复 +3；无隐背离、无薄量区标注两项仍存）。
副综合五维：编译 100 / 配额 95（calctype 死参、RUB 复合 ticker 死路径）/ 逻辑 95 / 诚实 96 / 决策辅助 94（CVD 升档 + 信号新鲜度 + 缺票维度 + OI 加速度 + 爆仓强度）。

**副指标辅助决策 86 偏低 = 分工设计不是缺陷**：主指标唯一授权 Entry/Stop/Target，副=确认器不重复距离原语。给用户解释评分时必说这句，防止误读为"副指标差"。市场适配扣分项：主=股票 SVP 行数无专门分支、个股无 SMT 配对；副=calctype/RUB 遗留。

## 四、本轮确认落地（上一轮 ✗ → 本轮 ✓ 的关键翻转）

- **遗留5（上一轮唯一 ✗）已修**：HTF FVG/OB 双 request 函数化短路（主 L2157-2176 f_htf_fvg_pack / f_htf_ob_pack，fvgHtfValid=false 走 else 空元组）——request 语义：函数未调用/分支未进入才真正省请求。
- 副指标 CVD 估算升档落地：body+wick → 1m security_lower_tf 聚合（f_cvd_ltf_pack，与主指标同口径），元组三坑规避=request 放 pack 函数 if/else 内、空数组分支=自动回退 wick 版。
- 风控行 "标·2.1R" → "R2.1"（L3324）；确认行 HTF 双显示去重（ckHtf 删除，guideHtfText 承担）；失效文本"空失效"删除（失效价=止损价，风控行"止"已显示）。
- 副指标 7 行紧凑=20260814 拍板终稿，5 行精简**明确不落地**——审计时不要再提"5 行定稿未落地"。

## 五、仍开放项（功能冻结：只登记不主动动，改前先问用户）

1. 主指标股票 SVP 行数无专门分支（FINAL_ROWS 仅 crypto/forex 有 max 分支，股票走默认 50）。
2. 副指标 calctype 仅 SUM 一个选项的死参数（转 const 有功能损失，可不动）。
3. f_is_metal_ticker 主（L269）/副（L37）各一份实现——改一处必须同步另一处。

## 六、坑：MSYS /c/ 路径传参给 Windows 原生 python 被改写

`python "/c/Users/.../pine_static_scan.py" <file>` → python.exe 报找不到 `C:\c\Users\...`（MSYS 把 /c/ 前缀原样传给原生 exe）。修法：`cd "C:/Users/.../scripts"`（Windows 全路径进目录）后以相对名调用 `python pine_static_scan.py <Windows全路径文件>`；所有参数一律 Windows 全路径，不用 /c/ 形式。与既有坑"MSYS /tmp 与 Windows 原生 Python 不互通"同源。
