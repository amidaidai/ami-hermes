# 用户报告交叉验证方法（防错信/防误命中）

> 2026-08-31 审计时用户提交的报告含 2 类错信（auto_card.py:4806 行号巧合 + text_push_status 编造字段），写下此文件作为下次审计的硬性流程。

## 为什么需要这一步

用户偏好："想当然"表述会引发反感（记忆）。审计报告里掺错信比不写更危险——修复方案会走错方向、消耗 token、污染 last_error 历史。

**典型错信源**：
1. 用户 LLM 推理时把"应该引用"当成"实际引用"（行号巧合）
2. 用户从二手转述/老记忆里粘贴字段（编造/过时）
3. 用户把"设计性退役"误报成"故障"
4. 用户把"自动兜底 try/except 吞掉"误报成"链路通"

## 3 类典型错信 + 验证命令

### 类型 A：行号巧合

**案例**：用户报"auto_card.py:4806 引用 cvd_analyzer" → 实际该行是 `_mode = "quick"` 路由逻辑。

```bash
# 验证：grep + sed 看真实上下文
grep -n "cvd_analyzer" scripts/auto_card.py
# 输出: 4806:scripts/auto_card.py  ← 只有一个匹配点
sed -n '4800,4815p' scripts/auto_card.py
# 看：是不是真 import？还是巧合匹配（注释/字符串）？
```

**判定规则**：
- 匹配行是 `from X import Y` / `import X` → 确认
- 匹配行是字符串/注释/其他逻辑 → 巧合，**报告里写错**

### 类型 B：编造/过时字段

**案例**：用户报"`text_push_status: failed_or_missing`" → 三个日志位置全空。

```bash
# 验证：找用户报的字段在哪里
grep -rn "text_push_status" data/ cron/ scripts/ 2>/dev/null | head -5
# 输出空 → 字段不存在

# 进一步：用户报的"失败原因"是否真实日志？
ls -lt data/keylevel_triggers/ data/keylevel_analysis/ 2>/dev/null
cat "C:/Users/Administrator/AppData/Local/hermes/cron/output/keylevel_read_trigger.md" 2>/dev/null | tail -10
```

**判定规则**：
- grep 有匹配 + 真实日志佐证 → 确认
- grep 无匹配 / 日志全空 → 编造，**反问用户出处**

### 类型 C：自动兜底被误报

**案例**：用户报"auto_card 链路断" → 实际 auto_card 用 try/except 兜底，主流程仍出卡。

```bash
# 验证：跑一次看真实行为
timeout 60 python scripts/auto_card.py BTCUSDT --quick
echo "exit=$?"
ls -la data/source_snapshot_BTCUSDT.json  # 看快照是否刷新
```

**判定规则**：
- exit=0 + 快照刷新 → 实际链路通
- exit≠0 + 快照无更新 → 确认断

## 3 步验证流程（强制）

```bash
# 1. 找原文位置
grep -n "<claim-string>" scripts/<file> data/<file> cron/jobs.json

# 2. 看上下文（±5 行）
sed -n 'N-5,N+5p' <file>

# 3. 跑相关逻辑
python -c "<import 链>"
python scripts/<script>.py  # 跑一次看真实行为
```

## 验证失败时怎么反问用户

**不要直接归类"用户撒谎"**——可能用户记错/二手转述/口径过时。用证据反问出处：

> "你报 `text_push_status: failed_or_missing` 的具体文件路径+行号？我 grep 了 `data/keylevel_triggers/ data/keylevel_analysis/ cron/output/keylevel_read_trigger.md` 三个位置都空。"

> "你报 `auto_card.py:4806` 引用 cvd_analyzer，我 sed 出 4800-4815 行实际是 `_mode` 路由逻辑。请确认行号？"

如果用户给不出出处 → **错信处理**（按系统铁律：报告无据 = 不写进审计卡也不发 TG）。

如果用户给得出新出处 → 重新验证，纳入审计卡。

## 防错信清单（审计前自检）

写审计卡前自问：
- [ ] 每条"X 文件 Y 行"断言都有 grep/sed 验证截图
- [ ] 每条"字段 Z=值"都有源文件读出
- [ ] 每条"链路断"都有实际跑过的 exit code
- [ ] 每条"过期"都有 stat mtime + 阈值对比
- [ ] 每条"被引用"都有 `grep -rln` 双向往返

漏一项 = 错信风险。

## 已知易错点（用户偏好相关）

| 易错点 | 真实情况 |
|--------|---------|
| "行情守望心跳停 49 天" | 实际是迁移性退役，**不是故障**——新架构用 keylevel_guard 替代 |
| "btc_daemon 守护死" | 同上 |
| "21 个 cron paused 是 P0" | 实际是 8/29 binance-only 设计，**不是故障**——除非白名单里的关键 cron 缺 |
| "monitor_levels.json 过期" | 已被 keylevels_config.json 替代，**是设计性退役** |
| "protections_state.json 过期" | 用户偏好"手动控制"+ trade_events 不再写 → 失活是合理状态 |
