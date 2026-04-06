#!/bin/bash
# mina-cli.sh — Send a message to Mina that she processes AND replies on Telegram
#
# Usage:
#   ./mina-cli.sh "Remember Marina loves Pinot Noir from Burgundy"
#   ./mina-cli.sh "Tell Marina the weather in Bangkok is 35C today"

MINA_API="https://api--mina-bot--5lgxdjrp66j6.code.run/v1/chat/completions"
TELEGRAM_BOT_TOKEN="8602581127:AAHMPBc7gQkMtyGvKm7sRSWfKTPfPNhPHtM"
MARINA_CHAT_ID="8717436820"
SESSION_ID="agent:main:telegram:dm:${MARINA_CHAT_ID}"

MESSAGE="$*"

if [ -z "$MESSAGE" ]; then
  echo "Usage: ./mina-cli.sh your message to Mina"
  exit 1
fi

echo "→ Sending to Mina..."

# 1. Build JSON payload safely with Python
PAYLOAD=$(python3 -c "
import json, sys
msg = sys.argv[1]
print(json.dumps({'messages': [{'role': 'user', 'content': msg}]}))
" "$MESSAGE")

# 2. Send to Mina's API (injects into Marina's Telegram session context)
RESPONSE=$(curl -s -m 120 -X POST "$MINA_API" \
  -H "Content-Type: application/json" \
  -H "X-Hermes-Session-Id: $SESSION_ID" \
  -d "$PAYLOAD")

# 3. Extract Mina's reply
REPLY=$(python3 -c "
import json, sys
try:
    d = json.loads(sys.argv[1])
    print(d.get('choices', [{}])[0].get('message', {}).get('content', ''))
except:
    print('')
" "$RESPONSE")

if [ -z "$REPLY" ]; then
  echo "✗ No response from Mina"
  echo "Raw: $RESPONSE"
  exit 1
fi

echo "← Mina: $REPLY"

# 4. Forward Mina's reply to Marina on Telegram
TG_PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({'chat_id': sys.argv[1], 'text': sys.argv[2]}))
" "$MARINA_CHAT_ID" "$REPLY")

TG_RESULT=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "$TG_PAYLOAD")

if echo "$TG_RESULT" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('ok') else 1)" 2>/dev/null; then
  echo "✓ Sent to Marina on Telegram"
else
  echo "✗ Telegram send failed: $TG_RESULT"
fi
