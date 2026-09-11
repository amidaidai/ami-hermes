# 20260810 定稿交付后复核教训（审计会话实发）

触发：用户上传 SVP_ICT_v2_20260810_fix.pine + AggVol_v2_20260810_fix.pine 要求审计 + 辅助决策推荐 + 全面联网推荐。上传版与桌面「指标审计修复_20260810」交付版逐字节一致 → 直接进入基线对照审计。

## 1. 基线记录可能错——交付文件行尾必须字节级实测

`20260810-audit-baselines.md` 记录主指标"LF（无CRLF）"，**实际交付文件是 CRLF**（3081 个 \r\n）：

- 08-09 交付版主指标：纯 LF（2989 行，CRLF=0）✓
- 08-10 交付版主指标：CRLF=LF=3081 → CRLF ✗（多轮 patch 被工具转成 CRLF，交付前没复检）
- 副指标两版都是 LF ✓

教训：**基线文件是助手自己写的记录，也会错**。审计任何版本先跑字节级行尾检测，并对比上一交付版 vs 本版（LF→CRLF 即 patch 工具回归铁证）：

```bash
python -c "d=open(f,'rb').read(); crlf=d.count(b'\r\n'); lf=d.count(b'\n'); print('CRLF' if crlf==lf else 'LF' if crlf==0 else 'MIXED')"
```

修复（只改行尾，零逻辑改动）：
```bash
sed 's/\r$//' 原文件 > 新文件
diff <(sed 's/\r$//' 原文件) 新文件   # 无输出 = 仅行尾差异
```

LF 修复版已交付：`桌面/hermes下载文件/指标审计定稿_20260810/SVP_ICT_v2_20260810_fix_LF.pine`（主指标；副指标原版即 LF 原样拷贝）。

## 2. 上传文件先与最新交付文件夹 diff 确认同版本再审计

`diff 桌面交付版 上传版` 无输出 = 同版本，直接引用基线数字进入对照审计；有差异才审增量（用户可能又改了）。避免审计错版本浪费整轮。

## 3. 扫描数 vs 基线数分桶裁决（三选一，别默认谁对）

本会话静态扫描 vs 08-10 基线差异逐项归因：

| 差异 | 归因 | 处置 |
|------|------|------|
| plot 43 vs 基线 39 | ①计数口径：`color.new(#hex, 常量透明度)` 按 TV 是编译期常量=1 槽，但扫描正则 `color\s*=\s*[^#,\)]` 见 `color.new` 首字符非 # 按 series 计 2 → 扫描偏保守（EMA 4 个 + S VWAP input.color） | 口径差，无需修文件 |
| alert() 2 vs 基线 1 | ②扫描器伪影：`\balert\(` 把注释"alert() 只在实时K评估"（主 L3057 / 副 L662 注释行）数进去 | static_scan.py 已修：剔除全行注释再数告警 |
| 行尾 CRLF vs 基线 LF | ③真实回归：基线错、扫描对 | 修文件转 LF（见上） |

## 4. 联网复核（2026-08 官方 + 社区，支撑"全面联网推荐"）

- Pine v6 仍当前版本（无 v7）；64 plots / 40 requests / 100K intrabar 限制未变（官方 Writing/Limitations 页）。
- `request.footprint()` 2026-01 发布，**仅 Premium/Ultimate**（官方 Other timeframes and data 页：footprints exclusive to Premium/Ultimate）；免费档脚本含此调用无法编译。社区已有 Footprint CVD 脚本（JJ CVD、Footprint CVD rv77777 等）可参考吸收/派发阈值，但免费档用不了。
- CVD 社区共识（Bookmap 官方博客：CVD 是 confluence 工具非独立信号；Reddit OrderFlow_Trading 2026：CVD divergence 是"retail TA concept forced onto orderflow, price is not accumulated"）→ 纯背离无 edge，指标现有「关键位 + 1.5ATR 摆动 + 吸收/派发」三层过滤即正确上限。
- 推荐方向结论：功能不再堆（行动格 12 行已是 SMC 面板化趋势的超集），攒配额等升档接 footprint；免费档真实边界 = CVD 估算不可替代，这是账号档位问题不是代码缺陷。
