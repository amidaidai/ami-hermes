# TradingView 多 Monaco 编辑器与云端保存安全协议

## 适用场景
Pine Editor 同时存在叠加层、分割视图、隐藏旧模型时，`pine get/set/save/open` 可能读写错误脚本。常见表现：脚本列表名称是主指标，但源码标题/行数却是副指标；当前图表仍能运行，云端源却已错配。

## 根因
部分 TV MCP 实现从 React `monacoEnv.editor.getEditors()` 固定取 `editors[0]`。TradingView Desktop 可同时保留多个 Monaco editor：

- 当前可见编辑器：非零 `getDomNode().getBoundingClientRect()`；
- 隐藏旧编辑器：宽高为0，仍留在 `getEditors()`；
- 叠加层和分割视图各自可能产生独立 model URI。

固定取 `[0]` 不等于当前可见脚本。`setValue()` 还可能不触发 TradingView 的 dirty 状态，导致 `Ctrl+S` 看似成功但云端版本未保存。

## 正确选择器
在 `getEditors()` 中选择：

1. DOM node 存在；
2. `rect.width > 0 && rect.height > 0`；
3. 若多个可见，优先 URI/标题与当前脚本匹配；
4. 只有无可见编辑器时才回退最近激活模型，禁止默认 `[0]`。

伪代码：

```js
const editors = env.editor.getEditors();
const visible = editors.filter(ed => {
  const r = ed.getDomNode()?.getBoundingClientRect();
  return r && r.width > 0 && r.height > 0;
});
const editor = visible[0] ?? null;
```

## 保存闭环

1. `pine list`：记录脚本 `name/title/version/id`。
2. 打开目标脚本后，检查可见 editor 的 model URI、行数和源码头。
3. 写入源码后确认保存按钮进入 `unsaved`，而不是只相信 `lines_set`。
4. 若 `setValue()` 后保存按钮仍 disabled，说明应用未收到 dirty 事件；不得宣称已保存。
5. 保存后必须切到另一脚本，再重新打开目标，重新读取源码。
6. CRLF→LF归一化后比较完整 SHA256；行数、标题或 SHA 任一不符即失败。
7. 再执行图表更新/编译，并检查 `has_errors=false`。
8. 最后检查 `pine list` 的主副脚本 identity 和图表 Data Window。

## Unicode 交付陷阱

Windows `clip.exe < UTF-8文件` 可能让中文在 Pine 中变成乱码。即使剪贴板探针看似正常，也必须在编辑器中肉眼/DOM检查中文源码片段，并以云端重开后的SHA为最终证据。不要用“粘贴成功”代替字节验证。

## 禁止的完成声明

以下都不足以证明云端部署完成：

- `pine set` 返回 success；
- 编辑器当前缓冲区行数正确；
- `Ctrl+S_dispatched`；
- 图表旧实例仍输出正确 Data Window；
- 编译按钮返回无错误，但没有重开云端脚本比对SHA。

必须同时满足：目标脚本身份正确、重开后源码SHA一致、真实编译无错、图表实例Data Window正确。
