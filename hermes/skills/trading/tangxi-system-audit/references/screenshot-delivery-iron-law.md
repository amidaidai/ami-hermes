# 截图交付铁律

棠溪要求：BTC/XAU 分析必须附带 TV 截图（含价格轴+CVD）。

## ❌ 错误做法

```
# 在 Markdown 回复里写 MEDIA: 路径
MEDIA:D:\Hermes agent\tools\tradingview-mcp\screenshots\btc_analysis.png
```

→ 图片可能发到 Home 频道而非当前话题
→ 用户说"截图呢？"

## ✅ 正确做法

```python
# 必须用 send_message 精确投递到目标话题
send_message(
    target='telegram:阿弥黛黛 / topic 386',  # 精确话题
    message='BTC 15m 全图 · 含右侧价格轴 + 下方 CVD\n\nMEDIA:D:\\thumb.png'
)
```

## 步骤

1. `mcp_tradingview_capture_screenshot(region='full')` → 获取 file_path
2. `send_message(target='telegram:阿弥黛黛 / topic 386', message='描述\nMEDIA:<path>')`
3. 确认 `success: true`

## 截图规格要求

- `region='full'`（非 'chart'）— 含右侧价格轴 + 下方 CVD 子图
- BTC 15m · SVP+ICT+VWAP+EMA+CVD + Volume + CVD 子图
- 文件名带有日期标识（如 `btc_full_0622.png`）

## 实案（2026-06-22）

两次 MEDIA: 在回复里写路径 → 图片未出现在话题中。
第三次改用 `send_message` 精确指向 → 立即成功。
