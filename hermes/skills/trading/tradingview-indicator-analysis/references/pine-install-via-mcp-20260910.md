# 用 MCP 把 Pine 源码装进 TradingView（2026-09-10 实战）

## 触发

需要用脚本/自动化把改好的 Pine 源码装到 TV 账号并挂上图表（源码几十 KB，
无法作为工具参数贴进对话；手工粘贴易截断）。

## 三个必须知道的坑

### 坑 1：Ctrl+S 不覆盖原脚本，而是弹「新脚本名称」

通过内部 API 打开脚本后（`pine_open`），**UI 的「当前脚本」指针是空的**，
此时保存会弹出：

```
保存脚本
新脚本名称: <原名> 1        ← 预填
[保存] [取消]
```

直接 `pine_save` 只返回 `"Ctrl+S_dispatched"`（**不等于保存成功**）：
账号里 `modified` 不变、`pine_open` 仍读到旧行数、图表继续跑旧代码。

**正确做法**：给对话框 input 赋值（原生 setter + input/change 事件）再点「保存」：

```js
const inp = document.querySelector('[data-name="rename-dialog"] input');
Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set
  .call(inp, '新名字');
inp.dispatchEvent(new Event('input',{bubbles:true}));
inp.dispatchEvent(new Event('change',{bubbles:true}));
[...document.querySelectorAll('[data-name="rename-dialog"] button')]
  .find(b => b.textContent.trim()==='保存').click();
```

结果：**新建一个同源代码脚本**（不是覆盖）。
所以改名后要在交付说明里写清楚：旧脚本可以删，图表现在用的是新脚本。

### 坑 2：`pine_list_scripts` 有缓存

它走 `internal_api`，刚保存后立刻复读**可能看不到新脚本**（`modified` 也是旧的）。
**不要据此判定保存失败** —— 先等几秒再读，或用行为判据（DW 值）验证。
本人在此误判过一次，差点白折腾。

### 坑 3：「添加到图表」按钮的 JS `.click()` 不生效

必须用真实鼠标事件：先拿到按钮 rect 坐标，再 `ui_mouse_click(x, y)`。

```js
document.querySelectorAll('button,[role=button]')   // 找 textContent 含「添加到图表」
```

## 验证必须用「行为判据」，不能用「源码判据」

改完一定要读 **Data Window 值**验证行为变化，例如本次：

| 观测 | v13（旧） | v14（新） |
|---|---|---|
| `Coverage Feed Mode` | 4（异常） | **1（聚合可用）** |
| `HALDRO Valid Code` | 0 | **2** |
| `HALDRO State Pack` | 0（无效） | **4（S4降权，真值）** |
| `Exchange Dominance %` | 0 | **40** |

**排除法判据**（用于判断图表到底跑的是哪版）：找一个「旧版必然为 X、新版不可能为 X」的输出。
本次 `Feed Mode = 4` 只可能出现在 `AggregatedVolume` 为 na 时，而新版已把求和改成
na 安全 → 4 就等价于「装的还是旧版」。

## 图表 study 重建后必须重接主线（重要）

新增/替换脚本时，图表 study 会被重建 → **实体 id 变化** → 主指标里指向副指标
plot 的 `input.source` 会失效 → 主指标显示「副S0未接」。

补法：

```
indicator_set_inputs(entity_id=<主指标>, inputs='{"in_164": "Basic Packed Bus (唯一主副连接)"}')
```

（`in_164` 是主指标「免费版唯一总线」那个 input 的 id，换版本时需重新核对。）

**验收标准**：主指标「协同」行的 S-code 与副指标「信号」行的 S-code 必须一致。
不一致就是没接上或接错了。

## 环境事实

- MCP 服务器：`tools/tradingview-mcp/src/server.js`，用 `node` 起 stdio
- 调用模板见 `scripts/install_pine_source.py` / `install_pine_source_v2.py` /
  `attach_pine_v14b.py` / `tv_state_check.py`
- MCP 返回是**双层包装**：`{"success":true,"result":"<json 字符串>"}` —— 解析要拆两层
