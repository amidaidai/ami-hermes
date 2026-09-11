# 双指标 LSR + GO/NO-GO 修复记录（2026-07-06）

适用：SVP v10 主指标 + HALDRO Volume Aggregated 副指标 + auto_card/go_nogo_gate 双指标驾驶舱。

## 发现的问题

1. **SVP 扫线视觉与评分不一致**
   - 评分链路已经识别 `sameBarTouch or gapThrough`。
   - 但线条变虚逻辑只看 `wickPierce`，跳空穿线时系统判已扫、图上线仍为实线。
   - 修法：线条维护处增加 `gapThroughLine`，合并为 `touchOrGap = wickPierce or gapThroughLine`，所有 `SWEEP_MARK_MODE` 分支改用 `touchOrGap`。

2. **HALDRO 需要 LSR 多空拥挤验证**
   - 新增 `BINANCE:{base}USDT_LSR`，增加 1 个 `request.security` 静态配额。
   - 在 5所聚合 + OI聚合架构下，静态点从 5 到 6，实际展开约 28/40，仍安全。
   - LSR > 1.3：多头拥挤；LSR < 0.8：空头拥挤。
   - 若当前方向与拥挤同侧，`Confirm Score` 扣 1，`riskWarnA` 增加 `⚠LSR拥挤`，新增 `alertcondition(alertOkA and lsrCrowdRiskA, 'LSR拥挤降权', ...)`。
   - Data Window 输出 `plot(lsrOkA ? lsrA : na, "LSR", display=display.data_window)`，便于 auto_card 读取。

3. **HALDRO shorttitle 警告**
   - TradingView 短标题需 ≤10 字符。
   - `shorttitle='Aggregated Volume'` 改为 `shorttitle='AggVol'`，仅改显示元数据，不改交易逻辑。

4. **auto_card 字段桥接**
   - `_tv_cache_indicators_to_studies()` 的 `sub_map` 增加 `lsr`/`long_short_ratio -> LSR`。
   - `_build_tv_main_data()` 增加 `("LSR", "sub_lsr")`。
   - `_dual_indicator_verdict()` 将 `sub_lsr` 渲染进 `haldro_position`：`OI ... · LSR 1.42·多头拥挤`。

5. **GO/NO-GO 8闸门一致性**
   - 加入 `dual_indicator` 后，`max_score` 必须是 8，而不是历史 7。
   - 修正 docstring、返回值和报告口径，新增回归断言。

## 必跑验证

```bash
python scripts/pine_static_scan.py svp_indicator.txt haldro_indicator.txt
python -m py_compile scripts/auto_card.py scripts/go_nogo_gate.py scripts/render_v8.py
pytest -q tests/test_dual_indicator_gate.py tests/test_card_render_locked.py
pytest -q
```

期望：
- SVP `request.security=11`、plot 约 23。
- HALDRO 新增 LSR 后静态 `request.security=6`、plot 约 30，仍低于限制。
- 全量 pytest 通过。

## 注意

- 不要把用户上传的旧 HALDRO 覆盖掉生产增强版；先 diff。若生产版已有 `Estimated CVD Value`、`CVD Quality Code`、三重过滤 CVD 背离，应保留生产增强版继续迭代。
- 本地无法替代 TradingView Pine Editor 最终编译；只能声明已完成静态扫描和系统回归，不要声称 TV 云端编译成功。