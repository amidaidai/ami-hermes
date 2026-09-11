#!/usr/bin/env bash
# 同题横评批量跑：对同一份 fixture 提示词依次跑多个 provider/model，结果落盘。
#
# 用法:
#   bash head2head_probe.sh <fixture_prompt.txt> "deepseek:deepseek-flash" "openai-codex:gpt-5.6-luna" ...
#   输出追加到 $LOCALAPPDATA/Temp/head2head.txt （Linux/macOS 用 /tmp/head2head.txt）
#
# 要点:
#   --ignore-rules 让所有模型看到完全相同的上下文（横评模型，不横评技能加载）
#   -t file 限制工具集，避免模型在横评里自己去拉数据
#   每个模型给 240s 上限；失败的先重跑一次再记为失败
set -u
PROMPT="${1:?usage: head2head_probe.sh <fixture.txt> provider:model [provider:model ...]}"
shift
OUTDIR="${LOCALAPPDATA:-/tmp}/Temp"; mkdir -p "$OUTDIR"
OUT="$OUTDIR/head2head.txt"
: > "$OUT"
for pair in "$@"; do
  p="${pair%%:*}"; m="${pair#*:}"
  s=$(date +%s)
  echo "===== $p / $m =====" >> "$OUT"
  timeout 240 hermes chat --query-file "$PROMPT" --provider "$p" --model "$m" \
      -t file --ignore-rules -Q --yolo 2>&1 | tr -d '\r' | grep -v '^session_id' >> "$OUT"
  echo "[elapsed $(( $(date +%s) - s ))s]" >> "$OUT"; echo "" >> "$OUT"
done
echo "ALLDONE -> $OUT"
