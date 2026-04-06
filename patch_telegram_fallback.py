#!/usr/bin/env python3
"""Patch Telegram adapter: strip markdown markers in the plaintext fallback path.

When MarkdownV2 formatting fails (tables, complex markdown, unescaped chars),
edit_message falls back to sending raw content without parse_mode. This causes
**bold**, ||spoiler||, and table syntax to show as literal text.

Fix: strip markdown markers before the fallback send so users see clean text.
"""

BASE = "/opt/hermes"

def _read(path):
    with open(path) as f:
        return f.read()

def _write(path, content):
    with open(path, "w") as f:
        f.write(content)


# ── 1. Add _strip_markdown helper to TelegramAdapter ─────────────────────

tp_path = f"{BASE}/gateway/platforms/telegram.py"
tp = _read(tp_path)
changed = False

# Add the helper method after MAX_MESSAGE_LENGTH class attribute
if "_strip_markdown_plain" not in tp:
    helper = '''
    @staticmethod
    def _strip_markdown_plain(text: str) -> str:
        """Strip markdown markers for clean plaintext fallback.

        Used when MarkdownV2 formatting fails and we fall back to sending
        without parse_mode. Removes bold, italic, strikethrough, spoiler,
        header, and table markers so users see clean text.
        """
        import re as _re
        # Headers: ## Title → Title
        t = _re.sub(r'^#{1,6}\\s+', '', text, flags=_re.MULTILINE)
        # Bold: **text** → text
        t = _re.sub(r'\\*\\*(.+?)\\*\\*', r'\\1', t)
        # Italic: *text* or _text_ → text
        t = _re.sub(r'(?<!\\w)\\*([^*\\n]+)\\*(?!\\w)', r'\\1', t)
        t = _re.sub(r'(?<!\\w)_([^_]+)_(?!\\w)', r'\\1', t)
        # Strikethrough: ~~text~~ → text
        t = _re.sub(r'~~(.+?)~~', r'\\1', t)
        # Spoiler: ||text|| → text
        t = _re.sub(r'\\|\\|(.+?)\\|\\|', r'\\1', t, flags=_re.DOTALL)
        # Inline code: `text` → text (keep content)
        t = _re.sub(r'`([^`]+)`', r'\\1', t)
        # Tables: | col | col | → col  col (strip pipes and dashes)
        t = _re.sub(r'^\\|[-:| ]+\\|$', '', t, flags=_re.MULTILINE)  # header separator
        t = _re.sub(r'^\\|\\s*', '', t, flags=_re.MULTILINE)  # leading pipe
        t = _re.sub(r'\\s*\\|\\s*$', '', t, flags=_re.MULTILINE)  # trailing pipe
        t = _re.sub(r'\\s*\\|\\s*', '  ', t)  # inner pipes → spaces
        # Blockquotes: > text → text
        t = _re.sub(r'^>+\\s?', '', t, flags=_re.MULTILINE)
        # Collapse excess blank lines
        t = _re.sub(r'\\n{3,}', '\\n\\n', t)
        return t.strip()

'''
    # Insert after MAX_MESSAGE_LENGTH line
    marker = "    MAX_MESSAGE_LENGTH = 4096"
    if marker in tp:
        tp = tp.replace(marker, marker + helper)
        changed = True
        print("[patch] telegram.py — added _strip_markdown_plain helper")
    else:
        print("[patch] telegram.py — MAX_MESSAGE_LENGTH marker not found")
else:
    print("[patch] telegram.py — _strip_markdown_plain already present")


# ── 2. Patch edit_message fallback to strip markdown ─────────────────────

old_fallback = '''                # Fallback: retry without markdown formatting
                await self._bot.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=int(message_id),
                    text=content,
                )'''

new_fallback = '''                # Fallback: strip markdown markers for clean plaintext
                _plain = self._strip_markdown_plain(content)
                await self._bot.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=int(message_id),
                    text=_plain,
                )'''

if old_fallback in tp:
    tp = tp.replace(old_fallback, new_fallback)
    changed = True
    print("[patch] telegram.py — patched edit_message fallback to strip markdown")
else:
    print("[patch] telegram.py — edit_message fallback pattern not found")


# ── 3. Patch send() fallback too ─────────────────────────────────────────

# The send() method has a similar fallback pattern
old_send_fallback = '''                    # Fallback: try without markdown
                    msg = await self._bot.send_message(
                        chat_id=int(chat_id),
                        text=content,'''

new_send_fallback = '''                    # Fallback: strip markdown for clean plaintext
                    _plain = self._strip_markdown_plain(content)
                    msg = await self._bot.send_message(
                        chat_id=int(chat_id),
                        text=_plain,'''

if old_send_fallback in tp:
    tp = tp.replace(old_send_fallback, new_send_fallback)
    changed = True
    print("[patch] telegram.py — patched send() fallback to strip markdown")
else:
    # Try alternate pattern
    print("[patch] telegram.py — send() fallback pattern not found (may differ)")


if changed:
    _write(tp_path, tp)

print("\n[patch] Telegram fallback patch complete.")
