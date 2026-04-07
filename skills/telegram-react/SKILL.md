# Telegram Reactions

React to messages with emojis via the Bot API.

## Quick Command (terminal)
```python
import urllib.request, json, os

token = open('/opt/data/.env').read().split('TELEGRAM_BOT_TOKEN=')[1].split('\n')[0]
url = f'https://api.telegram.org/bot{token}/setMessageReaction'

data = json.dumps({
    'chat_id': CHAT_ID,        # Replace with actual chat_id (int)
    'message_id': MSG_ID,      # Replace with actual message_id (int)
    'reaction': [{'type': 'emoji', 'emoji': '🔥'}]  # Change emoji
}).encode()

req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req, timeout=10)
print(json.loads(resp.read()))
```

## Available Emojis
👍 👎 ❤️ 🔥 🥰 👏 😁 🤔 🤯 😱 🤬 😢 🎉 🤩 🤮 💩 🙏 👌 🕊 🤡 🥱 🥴 😍 🐳 ❤️‍🔥 🌚 🌭 💯 🤣 ⚡ 🍌 🏆 💔 🤨 😐 🍓 🍾 💋 🖕 😈 😴 😭 🤓 👻 👨‍💻 👀 🎃 🙈 😇 😨 🤝 ✍ 🤗 🫡 🎅 🎄 ☃ 💅 🤪 🗿 🆒 💘 🙉 🦄 😘 💊 🙊 😎 👾 🤷‍♂ 🤷 🤷‍♀ 😡

## When to React
- Someone sends a funny message → 😂 or 🔥
- Acknowledgment without needing a full response → 👍
- Something impressive → 🔥 or 💯
- Agreement → 👍 or 🤝
- Appreciation → ❤️ or 🙏
