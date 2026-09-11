# TV 决策表直读（tv_grade / tv_treatment）

当 TV MCP 可用时，优先通过 MCP `data_get_pine_tables` 读决策表。若 MCP 不可用（no-agent cron 场景），通过 TV CLI 直读：

## TV CLI 命令

```bash
# 读 SVP 指标决策表（等级/处理/背景/位置/量能/CVD/执行/风控）
node tools/tradingview-mcp/src/cli/index.js data tables --study "SVP" --symbol "BINANCE:BTCUSDT.P"
```

输出示例：
```json
{
  "success": true,
  "studies": [{
    "name": "SVP+ICT+VWAP+EMA+CVD",
    "tables": [{
      "rows": [
        "等级 | X",
        "处理 | 远离VWAP",
        "背景 | 震荡 4h",
        "CVD | 顺空确认",
        "执行 | 等:看VAH",
        "风控 | 不进场"
      ]
    }]
  }]
}
```

## Python wrapper 合并模式

在 `tv_bridge_wrapper.py` 中使用两阶段采集：
1. 调用 `fetch_tv_data.cjs` 采集 VWAP/EMA/CVD/VAH/VAL/POC 等数值数据
2. 调用 TV CLI `data tables` 采集决策表等级
3. 将 `tv_grade` / `tv_treatment` 合并到同一 JSON 输出文件

关键代码：
```python
result2 = subprocess.run(
    ["node", str(TV_CLI), "data", "tables", "--study", "SVP"],
    capture_output=True, text=True, timeout=15
)
table_data = json.loads(result2.stdout)
for row in table_data["studies"][0]["tables"][0]["rows"]:
    parts = row.split("|")
    if parts[0].strip() == "等级":
        existing["tv_grade"] = parts[1].strip()
    if parts[0].strip() == "处理":
        existing["tv_treatment"] = parts[1].strip()
```

## 验证

```bash
python -c "import json; d=json.load(open('data/BTCUSDT.P_tv_data.json')); print('tv_grade:', d.get('tv_grade'), 'tv_treatment:', d.get('tv_treatment'))"
# 预期输出: tv_grade: X tv_treatment: 远离VWAP
```
