# TradingView云端身份、可见Monaco与中文按钮闭环

## 适用场景

TradingView Desktop同时保留多个Pine编辑器模型，或用户重命名/重建云端主副指标后，需要安全验证、编译和更新图表实例。

## 已验证的安全选择器

禁止固定使用`monacoEnv.editor.getEditors()[0]`。TradingView可能保留叠加层、分割视图及隐藏旧脚本模型。应对所有editor评分：

1. `getDomNode()`存在且`isConnected`；
2. `getBoundingClientRect().width/height > 0`；
3. 包含`document.activeElement`者优先；
4. 多个可见editor时按可见面积降序；
5. 仅在所有DOM几何不可用时才回退第一个。

单元测试至少覆盖：隐藏主脚本、隐藏副脚本、当前可见脚本位于数组末尾；多个可见editor时焦点优先。

## 中文页面动作按钮

当前Pine Editor的“添加到图表”可能是无文本图标按钮，动作名只在`title`，而不是`textContent`。编译器必须按以下顺序取标签：

```text
textContent → title → aria-label
```

需要同时识别：

- `Save and add to chart` / `保存并添加到图表`
- `Add to chart` / `添加到图表`
- `Update on chart` / `图表更新` / `在图表上更新`

不得把普通`Save/保存`当成编译或图表更新。若只命中`Pine Save`，说明没有真正更新图表实例，应继续检查按钮标题、编辑器身份和保存弹窗。

## 云端身份三重验证

用户改名后，必须分别验证：

1. 云端脚本列表的`name`与`title`一致；
2. 打开目标脚本后，读取当前**可见**editor源码；
3. CRLF归一为LF后，云端源码SHA256与本地上传源码一致。

随后读取图表study的`pineId`，确认它等于当前云端脚本ID。仅凭图表显示名称相同不够，因为旧实例与新脚本可同名。

## 截图前UI清理

Pine Editor关闭命令可能只关闭底部面板，而叠加层仍可见。截图前检查可见Monaco矩形；若仍非零，点击编辑器自身`aria-label=关闭`。同时关闭“保存脚本”模态框（常见`data-name=close`）。以截图熵/文件大小异常偏低作为遮罩或空白页线索，但最终仍需图面核验。

## 验收证据

- 主副云端源码分别重开并SHA匹配；
- 编译错误数组为空；
- 图表仅各一个主/副实例，`pineId`匹配新云端ID；
- Data Window能读主副指标；
- BTC与XAU五周期全部读到两个study；
- 全屏截图含价格轴、行动格和CVD副窗。
