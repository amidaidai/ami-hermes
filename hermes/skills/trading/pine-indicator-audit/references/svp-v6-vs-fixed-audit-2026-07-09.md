# SVP_fixed vs SVP_v6 审计对照（2026-07-09）

## 权威文件

| 文件 | 角色 | 版本 | 备注 |
|------|------|------|------|
| `Desktop/SVP_v6.pine` | **生产主指标权威** | Pine v6 | 与 `~/.hermes-web-ui/upload/default/SVP_v6.pine` **同字节**（实测 sha1 一致） |
| `Desktop/SVP_fixed.pine` | v5 修复基线 / 回退 | Pine v5 | 无 OB/BOS/CHoCH/LV；日常交易不要优先于 v6 |

审计桌面文件前必须：

```python
# desktop == upload?
Path(desktop).read_bytes() == Path(upload).read_bytes()
```

不要假设「桌面 = 生产」或「上次改过的 = 当前」；以用户点名的路径 + 上传目录字节比对为准。

## 体量快照（本次）

| | SVP_fixed | SVP_v6 |
|--|-----------|--------|
| lines | ~3075 | ~2805 |
| chars | ~180705 | ~182079 |
| est_tokens (÷2.33) | ~77556 | ~78145（余量 ~1855，再加功能先削） |
| request.security | ~13 | ~11 |
| lower_tf | 2 | 2 |
| plot | 28 | 31 |
| MCP DW plots | 11 | **14** |
| OB/BOS/CHoCH/LV | 无 | 有 |

## 两边都已修好（不要当新 bug 重报）

- `executablePlan = ((displayLongA or displayShortA) and rrHardOk) or bcDirectOk`
- `rrHardBlock` 门控 panelEntry/Stop/Tgt
- `touchOrGap = wickPierce or gapThroughLine`；评分侧 `sweptHighRejected/sweptLowReclaimed` 收盘回线内
- `minBuckets` 自适应 minStep（小币 SVP 行数）
- `cvdBearStars/cvdBullStars` **已声明**（但仍是 `= 0` 占位，星级未实现）
- 旧叙事卡 `stateText/cardLine*` 已清；`invalidText/watchText` 仍消费
- HTF 非重绘：`lookahead_on + [1]/[3]`；FVG 本级 `barstate.isconfirmed`
- v6：`dynamic_requests` 仅 1 处；无 `na(hBull[1])`；`fixnan` 仅 float

## v6 独有集成（审计清单勾选项）

- 输入组 `02 ICT - OrderBlock/结构`：SHOW_OB / BREAKER / BOS_CHOCH / LIQ_VOID
- A 级汇合：`setupLongA/ShortA` 含 `(inBullOB or inBullBreaker or nearAKeyLevel)`（空对称）
- `confirmScore` OB 同向 +1
- 核对行 `ckOb` + BOS/CHoCH 文案
- MCP：`MCP OB Signal` / `MCP BOS/CHoCH` / `MCP Liq Void`
- alertcondition：BOS↑↓、CHoCH↑↓ 等

## 两边仍在的 P1（审计时必 grep）

### 1) BOS/CHoCH 优先级写反（仅 v6，真逻辑 bug）

`chochBull` 是 `bosBull` 的**子集**（多了「前收在 lastSwingLow 下方」等条件）。  
若文案/MCP 先判 BOS，则 CHoCH 分支**几乎永不亮**：

```pine
// 错误（当前）
bosChochText = bosBull ? "BOS↑" : bosBear ? "BOS↓" : chochBull ? "CHoCH↑" : ...
plot(... bosBull ? 1 : bosBear ? -1 : chochBull ? 2 : ...)

// 正确：先 CHoCH 后 BOS
bosChochText = chochBull ? "CHoCH↑" : chochBear ? "CHoCH↓" : bosBull ? "BOS↑" : bosBear ? "BOS↓" : ""
plot(... chochBull ? 2 : chochBear ? -2 : bosBull ? 1 : bosBear ? -1 : 0)
```

检证：

```bash
grep -n "bosChochText\|MCP BOS" SVP_v6.pine
# bosChochText / MCP 必须 choch 分支在 bos 之前
```

### 2) DO 延展缩回当前 bar（fixed + v6）

创建用 `bar_index + 1`，但维护：

```pine
line.set_x2(doLine, bar_index)   // 应 bar_index + 1
```

### 3) nPOC 零长度 + 延展无 +1（fixed + v6）

```pine
line.new(endBar, price, endBar, price)   // 应 endBar + 1
line.set_x2(np.ln, bar_index)            // 应 bar_index + 1
```

### 4) CVD 星级空壳

```pine
int cvdBearStars = 0
int cvdBullStars = 0
// 仅拼进 cvdStateText，无计算
```

## P2 文案 / 死参

- 扫位：`扫2/5` → 用户偏好 `已扫2/剩5`
- `RISK_PER_TRADE_PCT` / `DAILY_MAX_LOSS_PCT` / `WEEKLY_MAX_LOSS_PCT` 仅 input、零消费（标注即可，勿谎称有仓位门控）

## 选用建议（给用户的标准口径）

- **日常交易主指标**：`SVP_v6.pine`
- **SVP_fixed**：v5 修复合集 / 对照 diff / v6 挂掉时回退
- 加密：主 SVP + 副 HALDRO；非加密不套 HALDRO
- token 紧：v6 再加模块前先削死代码/tooltip

## 审计输出口径

先结论（能不能当生产主驾驶）→ P0/P1/P2 → 与另一版对照表 → 直接推荐挂哪份。  
不要只列功能清单不给裁决。
