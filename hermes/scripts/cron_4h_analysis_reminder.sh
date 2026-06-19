#!/bin/bash
# 棠溪 · 4h 分析提醒 cron 脚本
# 在 4h K 线收线后 2 分钟触发，推送分析提醒到 Telegram + Discord
# Cron 调用：bash hermes/scripts/cron_4h_analysis_reminder.sh

LOG_DIR="D:/Hermes agent/data"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
UTC_HOUR=$(date -u +"%H")
MINUTE=$(date -u +"%M")

# 只在 4h 收线后 2 分钟内触发（00:02, 04:02, 08:02, 12:02, 16:02, 20:02 UTC）
# 对应北京时间：08:02, 12:02, 16:02, 20:02, 00:02, 04:02
HOUR_MOD=$((10#$UTC_HOUR % 4))
if [ "$HOUR_MOD" != "0" ] || [ "$MINUTE" != "02" ]; then
    echo "[$TIMESTAMP] Not a 4h candle close window (UTC: ${UTC_HOUR}:${MINUTE}). Exiting."
    exit 0
fi

echo "[$TIMESTAMP] 4h candle closed! Triggering analysis reminder..."

# 调用 hermes agent 发送分析提醒
# 这里用 .env 的环境变量来发消息
MSG="⏰ 4h K线收线提醒 · $(date -u +'%H:%M UTC') — 请检查多周期结构变化"

echo "$MSG" >> "$LOG_DIR/4h_reminders.log"
echo "[$TIMESTAMP] Reminder logged. Use hermes send_message to deliver."

# Note: actual send_message call is handled by hermes cron job's deliver field
exit 0
