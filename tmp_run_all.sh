#!/usr/bin/env bash
cd "D:/Hermes agent" || exit 1
OUT_BASE="$LOCALAPPDATA/hermes/cron/output"

jobs=(
"ada5d94913fd|BTC关键位同步"
"ef4cf5f7cd24|Orion全市场雷达"
"3a8bee120dd4|Dune链上刷新"
"b664f56f904c|COT报告刷新"
"0764c6922694|Deribit期权刷新"
"54661a43c839|BTC守护看门狗"
"f71dcf102007|每日复盘提醒"
"d6247e06ac30|X情绪数据刷新"
"5db6dd683b1d|清算压力监控"
"5f7192fd9029|稳定币供应监控"
"155082fc5e34|数据新鲜度看门狗"
"fd78e36de132|QLib因子信号"
"2bcc03c1f524|交易执行桥接"
"c6ad11110a80|X情绪LLM分析"
"eccf404b6c0a|宏观Poly刷新"
"020e260f5ac0|行情守望看门狗"
"cb8a96b39fed|每日运维聚合"
"113655ad34b5|XAU TV现场同步"
)

echo "===== 顺序实跑18个cron $(date '+%H:%M:%S') ====="
n=0
for entry in "${jobs[@]}"; do
  n=$((n+1))
  id="${entry%%|*}"
  name="${entry##*|}"
  echo ""
  echo "--- [$n/18] $name ($id) ---"
  before=$(ls -t "$OUT_BASE/$id/" 2>/dev/null | head -1)
  hermes cron run "$id" >/dev/null 2>&1
  # 轮询直到出现比 before 更新的输出文件
  waited=0
  st=""
  while [ $waited -lt 100 ]; do
    f=$(ls -t "$OUT_BASE/$id/" 2>/dev/null | head -1)
    if [ -n "$f" ] && [ "$f" != "$before" ]; then
      st=$(grep -m1 -E "Status:|script failed|succeeded|silent|error" "$OUT_BASE/$id/$f" 2>/dev/null | head -1)
      if [ -n "$st" ]; then break; fi
    fi
    sleep 5; waited=$((waited+5))
  done
  if [ -n "$st" ]; then echo "状态: $st"; else echo "状态: 超时未出"; fi
done
echo ""
echo "===== 全部跑完 $(date '+%H:%M:%S') ====="
