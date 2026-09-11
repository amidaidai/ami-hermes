# PIL 分析卡 Bloomberg 终端风格参考（v6/v7）

## 设计目标
对标 Bloomberg Terminal / Fortress / Vault 风格：深色 + 等宽数字 + 高密度 + 高对比。`scripts/render_analysis_card.py` v7 落地。

## 字体选型（Windows）

| 角色 | 字体 | 路径 | 字号 |
|------|------|------|------|
| 数字/英文/标点 | Consolas 等宽 | `C:/Windows/Fonts/consola.ttf` | 26 / 60 |
| 数字粗体 | Consolas Bold | `C:/Windows/Fonts/consolab.ttf` | 26 / 60 |
| 数字斜体 | Consolas Italic | `C:/Windows/Fonts/consolai.ttf` | 26 |
| 中文正文 | 微软雅黑 | `C:/Windows/Fonts/msyh.ttc` | 22 / 26 / 28 |
| 中文粗体 | 黑体 | `C:/Windows/Fonts/simhei.ttf` | 26 / 30 / 32 / 34 / 38 |

**为什么 Consolas 而不是 Courier**：Consolas 是 Windows Vista+ 的屏幕优化等宽，1/0/8/I/l 区分清晰，比 Courier 紧凑。

## 字号体系

```
KPI 数字      60 粗体（consolab）
KPI 标签      22 微软雅黑
section 标题  30 黑体
表头          26 黑体
label        26 微软雅黑
数值          26 Consolas
裁决          34 黑体
风险行        28 微软雅黑
callout 标题  32 黑体
callout 行   28 微软雅黑
徽章          38 黑体
状态条        24 Consolas
脚注          22 微软雅黑
```

## 配色

```
背景         #0E0E12  深近黑
表头蓝       #2563EB  鲜蓝（不要 #1A2433，太暗）
分隔线       #1F1F26
section 绿   #4ADE80  （状态条/分隔条/正向）
section 橙   #F59E0B  （警告）
section 红   #EF4444  （风险）
label 灰     #C8CCD2  （次要文字）
value 白     #FFFFFF
accent 蓝    #60A5FA  （强调数字）

# 填充色（必须够暗才看得出）
RED_BG  = #3A0808  深红底（不是 #1F0707，在黑底上几乎看不出）
GRN_BG  = #062812  深绿底
BLU_BG  = #0B1A2E  深蓝底（状态条用）
HDR_BG  = #1A2433  表头深蓝（备选）
```

**踩坑记录**：v4 用 `#1F0707` 做红色填充 → 视觉模型识别为"只有黑底+红边"，看不出深红。v5 改 `#3A0808` → "深红底+红框"清晰。

## 布局规范

- 宽 1080px（手机宽）
- 高 ≤ 2200px（Telegram 预览框安全阈值，pitfall 38）
- 左右 padding 24px
- 段间距 22px（v4-v5 没用，呼吸感差）
- 行高 60px（v4-v5 46-56，挤）
- 表头高 50px（v4-v5 44）
- 表格行底线 `DIV_C` 1px

## 渲染器结构

```
render_card(
    out_path, title,
    badge_text, badge_level,         # "C 级 · 等待"
    status,                           # [(text, level), ...] 顶部状态条
    kpis,                             # [(label, value, level), ...] × 4
    multi_tf,                         # [(周期, 结论, 关键位, 评级), ...] × 4
    signal,                           # {headers, rows} 主指标行动格
    monitor,                          # [(价格, 含义, 动作, 评级), ...] × 5-7
    ab_plan,                          # {"a": {...}, "b": {...}} 左右对比
    binance,                          # [(指标, 数值, 状态), ...] × 4
    risk_text,                        # 单行风险提示
    callout,                          # (title, [(text, level), ...])
    footer,                           # 脚注
) -> (out_path, (W, H))
```

## TG 投递铁律（v7 升级）

**重要：分析卡和 TV 截图必须分两条消息发**——用户 2026-08-31 明确"这个截图好垃圾，要分开"。

```python
# 1. 先发 TV 全屏截图（主周期：BTC 15m / XAU 5m）
telegram_reliable.send_telegram_photo(target, tv_screenshot_path, caption="...")

# 2. 再发分析卡 PIL PNG
telegram_reliable.send_telegram_photo(target, analysis_card_png, caption="...")
```

**v5 嵌入版（已弃用）**：
- `_draw_tv_thumb()` 360×280 缩略图嵌入到信号矩阵左侧 → 已删
- v5 嵌入图被用户吐槽"好垃圾"（糊、信息不全），改单独推全屏图

## v4 → v5 → v6 → v7 演进

| 版本 | 主要变更 | 用户反馈 |
|------|---------|---------|
| v4 | sparkline + 价格标尺 + 评级●色块 | "这个照片好难看，信息不够" |
| v5 | + TV 嵌入 + 多周期 + 监控检查单 + A/B对比 | "继续优化" |
| v6 | + 状态条 + 字号放大 + 段间距 | "继续" |
| v7 | + Consolas 等宽 + 删除嵌入图 + 单独推图 | ✅ 通过 |

**根因分析**：v4→v5 是"结构性扩列"（pitfall 40），v5→v7 是"风格终端化"（本文件）。两步必须都做——只做风格不扩列 → 信息密度不够；只扩列不换风格 → 数字不对齐、看着业余。

## 参考
- Bloomberg Terminal 风格：https://adminlte.io/blog/dark-dashboard-templates/ （Fortress / Vault）
- WCAG 对比度：文字对比度 ≥ 4.5:1，大字 ≥ 3:1
- Consolas vs Courier：Consolas 屏幕优化，字距 1/0/8/I/l 区分更清
- pitfall 38（Telegram 图片预览框高度截切）：高 ≤ 2200px，宽 ≤ 1080px
- pitfall 40（"信息不够"=结构扩列）：v4→v5 教训
- pitfall 41（PIL 表格多元组契约）：`_draw_table` 接受 2/3/4 元组
