#!/bin/bash
# This script reads GH_TOKEN from environment variable
# Usage: GH_TOKEN=ghp_xxx python reset_repo.py

set -e

TOKEN="$GH_TOKEN"
if [ -z "$TOKEN" ]; then
  echo "No GH_TOKEN set"
  exit 1
fi

OWNER="amidaidai"
REPO="ami-hermes"

echo "=== Step 1: Delete remote repo ==="
HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE \
  "https://api.github.com/repos/$OWNER/$REPO" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github.v3+json")

if [ "$HTTP_CODE" = "204" ]; then
  echo "✅ Repo deleted (204)"
elif [ "$HTTP_CODE" = "404" ]; then
  echo "⚠️ Repo not found, will create new"
elif [ "$HTTP_CODE" = "401" ]; then
  echo "❌ Bad token!"
  exit 1
else
  echo "⚠️ HTTP $HTTP_CODE - continuing"
fi

echo ""
echo "=== Step 2: Create repo ==="
CREATE_RESULT=$(curl -sS -X POST "https://api.github.com/user/repos" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$REPO\",\"description\":\"安禾 - Hermes AI 个性化配置\",\"private\":false,\"auto_init\":false}")

if echo "$CREATE_RESULT" | grep -q "\"name\""; then
  echo "✅ Repo created"
elif echo "$CREATE_RESULT" | grep -q "Bad credentials"; then
  echo "❌ Bad token!"
  exit 1
else
  echo "⚠️ Create result: ${CREATE_RESULT:0:200}"
fi

echo ""
echo "=== Step 3: Force push ==="
AUTH_URL="https://amidaidai:${TOKEN}@github.com/${OWNER}/${REPO}.git"
cd "D:/Hermes agent"
git remote set-url origin "$AUTH_URL"
git push --force origin main 2>&1

echo ""
echo "✅ 搞定！远端仓库已清空并重新推送备份！"
