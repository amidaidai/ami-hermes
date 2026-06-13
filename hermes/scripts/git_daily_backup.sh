#!/bin/bash
REPO="/d/Hermes agent"
HERMES_HOME="$HOME/AppData/Roaming/cn.org.hermesagent.desktop/runtime/hermes-home"

# 同步 Hermes 个性化配置
cp "$HERMES_HOME/SOUL.md" "$REPO/hermes/" 2>/dev/null
cp -r "$HERMES_HOME/memories/"* "$REPO/hermes/memories/" 2>/dev/null
cp "$HERMES_HOME/scripts/"*.sh "$REPO/hermes/scripts/" 2>/dev/null

if [ -f "$HERMES_HOME/cron/jobs.json" ]; then
  cp "$HERMES_HOME/cron/jobs.json" "$REPO/hermes/cron/"
fi

# 提交推送
cd "$REPO"
git add -A
DATE=$(date +%Y-%m-%d)
git commit -m "📦 每日备份 ${DATE}" --quiet 2>/dev/null
git push --quiet 2>&1
echo "✅ Hermes 配置备份完成 ${DATE}"
