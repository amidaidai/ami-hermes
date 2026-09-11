# MCP 静默空转 + 主→副总线接线（2026-09-11 实测）

两个都属于「图表状态」但常被漏掉的部分：**工具返回成功 ≠ 操作生效**，以及
**指标之间的接线也是状态**。

## 一、静默空转：返回 `success: true` 但什么都没做

| 工具 | 返回值 | 真实行为 | 证据 |
|---|---|---|---|
| `indicator_set_inputs`（MCP） | `updated_inputs: {"in_164": "sQC3ma$49"}` | **生效** ✓ | 面板 S-code 恢复一致 |
| `tv indicator set <id> -i '{...}'`（CLI） | `success: true`、`updated_inputs: {}` | **空转** ✗ | 故意设成 `close` 后面板毫无变化 |
| `tv indicator get <id>`（CLI） | `success: true`、`inputs: []` | **读不到** ✗ | MCP 同一 study 能读出全部输入 |
| `tab_new`（MCP） | `action: "new_tab_opened"` | **没开** ✗ | CDP `/json/list` 仍只有 1 个 chart page |

`tab_new` 的实现（`src/core/tab.js`）就发一个 Ctrl+T 然后**无条件**返回成功：

```js
export async function newTab() {
  await c.Input.dispatchKeyEvent({ type: 'keyDown', modifiers: 2, key: 't', code: 'KeyT' });
  await new Promise(r => setTimeout(r, 2000));
  const state = await list();
  return { success: true, action: 'new_tab_opened', ...state };   // ← 从不校验
}
```

**结论性判据**：写操作必须**行为验收**。三条可用的验收通道，按可靠性排序：

1. **面板/Data Window 文案** —— 最强。设完总线等 35 秒，读主副面板比 S-code。
2. **CDP 直查** —— `curl -s http://127.0.0.1:9222/json/list | python -c "import json,sys;print(len([t for t in json.load(sys.stdin) if t['type']=='page']))"`。
   用来戳破「开了新页签」这类假成功。
3. **工具自身的回读** —— 最弱，`indicator get` 本身就可能是 `inputs: []`。

## 二、主→副总线会在切品种时断掉

现象：主指标显示「副S0未接·A禁」、主 OI 行「OI未接」，而副指标照常有值 →
**S-code 不一致**。这不是用户的设置问题。

机理（用 entity id 变化证实）：

| 时刻 | 主指标 id | 副指标 id | `in_164` |
|---|---|---|---|
| 切品种前 | `ZI6AGV` | `sQC3ma` | `sQC3ma$49` ✓ |
| 切走再切回后 | **`Rp0kZZ`**（换代了） | `sQC3ma` | **`close`** ✗ |

主指标被**重新实例化**（拿到新 entity id），它 `input.source` 里那条指向副指标的
引用（形如 `sQC3ma$49`）随旧实例一起消失 → 回退成 `close`。
副指标 id 不变，所以只有主这一侧坏掉。
**任何会切品种的后台任务都会打断它**（XAU 同步每 15 分钟一次）。

### 修复 recipe（只有 MCP 这条路管用）

```python
# 1) 取当前 id（id 会变，不要缓存）
state = json.loads(<chart_get_state>)
by_name = {s["name"]: s["id"] for s in state["studies"]}
main_id = by_name["SVP+ICT+VWAP+CVD"]
sub_id  = by_name["Volume Aggregated Spot & Futures"]

# 2) 用 MCP（不是 CLI）写入 study-id 引用
indicator_set_inputs(entity_id=main_id, inputs='{"in_164": "%s$49"}' % sub_id)

# 3) 等 15–30s 指标重算，再读面板验收：主「协同」S-code == 副「信号」S-code
```

字段名 `in_164` = 主指标的「Basic Packed Bus（唯一主副连接）」输入；`$49` 是 TV 的
study-id 引用后缀。**主指标 fail-closed 显示「副S0未接·A禁」本身是对的**
（宁可禁 A 也不能用错数据）—— 要修的是让它自愈，不是让它放行。

### 曾写过的错误修法（已撤销，勿重复）

在同步脚本里加「归还图表后自动重接总线」：因为脚本只能走 CLI，而 CLI 的
`indicator set` 静默空转 + 读回校验必然失败 → 每 15 分钟刷一条假告警。
**一个「看着成功其实没做」的修复比不修更糟。** 正确做法是把这条检查放进
**分析前置流程**，由 Agent 用 MCP 每次分析前执行。

## 三、共享图表切换的普查与实测（2026-09-11）

用户报「图表总自己切品种和周期」时，先做**切换源普查**再动手：

```bash
# 找出所有会切品种/周期的脚本
grep -rn 'set_symbol\|set_timeframe\|"symbol"\|"timeframe"' scripts/*.py \
  | grep -v tests | grep -v '^scripts/tv_data_bridge.py'
# 注意：[字符串 "symbol"] 可能是字典键、不是图表命令 —— 必须回看上下文，
#       本次就误把 keylevel_read_trigger（不切图）列为嫌疑。
```

普查结果与真实频率：

| 任务 | 频率 | 实际切图 |
|---|---|---|
| XAU TV现场同步 | 每 15 分 | 品种 + 5 周期 + 归还 = **7 次/轮 → 28 次/小时** |
| BTC TV五周期续航 | 每 20 分 | **条件触发**：快照 <22 分即整个跳过 → 实际约 40 分一次 |
| tv_screenshot | 按需 | `reuse_verified=True` 默认，图已就位就不切 |

**先把「谁在切、切几次」量出来**，再谈修。本次加了 `switch_stats_line()` 打印
「图表切换 品种(实切N/跳过N) 周期(实切N/跳过N)」，一眼能看出是频繁切还是还原坏了。

### 关键发现：5/7 次切换是可以省的

XAU 那 5 个周期的循环**只读 OHLCV**（`get_chart_state` + `get_ohlcv`），
**完全不读指标**（无 `get_study_values` / `get_pine_lines` / `get_pine_labels`），
报告 `_build_xau_report` 也只用 high/low/close。
→ 只有 **2 次是必需的**（读 5m 的 SVP 行动格 + 归还），其余 5 次纯粹为了取 K 线。
→ K 线可改走 API（脚本可像 `fetch_tv_mcp` 一样直连别的 MCP/HTTP）。

**代价是数值源改变**（卡片高/低值从用户图上的 TV 数据换成第三方），
会与用户对图核对的习惯冲突 —— 属于产品取舍，需用户拍板，不要自行替换。

### `data_get_ohlcv` 没有周期参数

只能读**当前图**的周期（只有 `count` / `summary`），所以走 MCP 取多周期 K 线
绕不开切周期。想不切图就只能换数据源。

## 四、不可行的方案（实测过，别再试）

**专用标签页隔离** —— TV Desktop 这个配置下没有图表页签条（DOM 全扫只有日期范围
页签与侧栏页签），且 `tab_new` 静默空转（见上）。所以「让采集跑在第二个图表页」
在当前工具下做不到。**不要把它写成推荐方案。**

同理，减少切换频率是**新鲜度取舍**而非纯优化：XAU 快照契约是 ≤30 分钟，
15 分钟排程已经是 2× 冗余；但改排程会让一次失败的恢复窗口从 15 分拉长到
40 分而破坏契约 —— 所以 15 分钟排程本身承担了重试余地，不要随手改。
