#!/usr/bin/env python3
"""Apply PR #4558 fix: strip thinking blocks from streamed output.

Run inside the Docker container after Hermes is cloned and installed.
Uses double-quoted heredoc so \\n becomes actual newlines (not literal backslash-n).
"""
import re

BASE = "/opt/hermes"

def _read(path):
    with open(path) as f:
        return f.read()

def _write(path, content):
    with open(path, "w") as f:
        f.write(content)

# ═══════════════════════════════════════════════════════════════
# 1. stream_consumer.py — add _strip_think_blocks + offset tracking
# ═══════════════════════════════════════════════════════════════
sc = _read(f"{BASE}/gateway/stream_consumer.py")
changed = False

# 1a. Add regex patterns and _strip_think_blocks function after _DONE = object()
if "_COMPLETE_THINK_RE" not in sc:
    think_block = """
# Patterns for stripping thinking/reasoning blocks from streamed content.
# Matches complete blocks and also unclosed trailing blocks (still being generated).
_THINK_TAGS = ("think", "thinking", "reasoning", "REASONING_SCRATCHPAD", "thin", "result")
_COMPLETE_THINK_RE = re.compile(
    r"<(?:think|thinking|reasoning|REASONING_SCRATCHPAD|thin|result)>.*?</(?:think|thinking|reasoning|REASONING_SCRATCHPAD|thin|result)>",
    re.DOTALL | re.IGNORECASE,
)
_UNCLOSED_THINK_RE = re.compile(
    r"<(?:think|thinking|reasoning|REASONING_SCRATCHPAD|thin|result)>(?:(?!</(?:think|thinking|reasoning|REASONING_SCRATCHPAD|thin|result)>).)*$",
    re.DOTALL | re.IGNORECASE,
)
# Separate patterns for MiniMax-specific XML-ish tags: <think> and </thin>
_MINIMAX_THIN_RE = re.compile(r" <think>[^<]*?</think>", re.DOTALL | re.IGNORECASE)
_MINIMAX_THIN_OPEN_RE = re.compile(r" <think>(?!.*</think>)", re.DOTALL | re.IGNORECASE)
_MINIMAX_THIN_CLOSE_RE = re.compile(r"^</thin>", re.DOTALL | re.IGNORECASE | re.MULTILINE)


def _strip_think_blocks(text: str, as_spoiler: bool = False) -> str:
    \"\"\"Remove or convert thinking/reasoning blocks from streamed text.

    When as_spoiler=False (default): strips blocks entirely (used during streaming).
    When as_spoiler=True: converts complete blocks to Telegram spoiler format
    (used for the final message only).
    \"\"\"
    if not text or "<" not in text:
        return text
    if as_spoiler:
        def _to_spoiler(m):
            inner = re.sub(r'</?(?:think|thinking|reasoning|REASONING_SCRATCHPAD|thin|result)>', '', m.group(0), flags=re.IGNORECASE).strip()
            if inner and len(inner) > 5:
                # Truncate long thinking and wrap in spoiler
                excerpt = inner[:600].strip()
                if len(inner) > 600:
                    excerpt += "..."
                return "||" + chr(128173) + " " + excerpt + "||\\n\\n"
            return ""
        text = _COMPLETE_THINK_RE.sub(_to_spoiler, text)
    else:
        # Convert complete thinking blocks to blockquote with 💭 prefix
        def _to_thinking_display(m):
            inner = re.sub(r'</?(?:think|thinking|reasoning|REASONING_SCRATCHPAD|thin|result)>', '', m.group(0), flags=re.IGNORECASE).strip()
            if inner and len(inner) > 3:
                # Prefix each line with > for MarkdownV2 blockquote
                lines = inner.split("\\n")
                quoted = "\\n".join("> " + line for line in lines if line.strip())
                return "> " + chr(128173) + " " + quoted.lstrip("> ") + "\\n\\n"
            return ""
        text = _COMPLETE_THINK_RE.sub(_to_thinking_display, text)
    # Convert SOUL.md-style 💭 prefix to blockquote too
    # (Model writes 💭 directly when not using <think> tags)
    if text.startswith(chr(128173)):
        # Find end of thinking line(s) — separated from response by blank line
        _split = text.find("\\n\\n")
        if _split > 0:
            _thinking = text[:_split]
            _rest = text[_split:]
            _tlines = _thinking.split("\\n")
            _thinking = "\\n".join("> " + line for line in _tlines)
            text = _thinking + _rest

    # Hide unclosed (still generating) thinking blocks
    text = _UNCLOSED_THINK_RE.sub("", text)
    # MiniMax-specific partial tags
    text = _MINIMAX_THIN_RE.sub("", text)
    text = _MINIMAX_THIN_OPEN_RE.sub("", text)
    text = _MINIMAX_THIN_CLOSE_RE.sub("", text)
    # Strip orphaned closing tags
    text = re.sub(r'</?(?:think|thinking|reasoning|REASONING_SCRATCHPAD)>\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r"\\n{3,}", "\\n\\n", text)
    return text.strip()

"""
    # Ensure os is imported (needed for THINKING_DISPLAY env var check)
    if "import os" not in sc.split("\n")[0:30]:
        sc = sc.replace("import re\n", "import os\nimport re\n", 1)
    marker = "# Sentinel to signal the stream is complete\n_DONE = object()"
    sc = sc.replace(marker, marker + think_block)
    changed = True
    print("[patch] stream_consumer.py — added _strip_think_blocks + regex patterns")
else:
    print("[patch] stream_consumer.py — _strip_think_blocks already present")

# 1b. Add _finalized_offset = 0 in __init__
if "self._finalized_offset = 0" not in sc:
    old_init = '        self._last_sent_text = ""   # Track last-sent text to skip redundant edits'
    new_init = old_init + """
        self._finalized_offset = 0  # Characters of clean text finalized in previous messages"""
    sc = sc.replace(old_init, new_init)
    changed = True
    print("[patch] stream_consumer.py — added _finalized_offset init")
else:
    print("[patch] stream_consumer.py — _finalized_offset already present")

# 1c. Patch the run() method — replace the should_edit block
old_run_edit = """                if should_edit and self._accumulated:
                    # Split overflow: if accumulated text exceeds the platform
                    # limit, finalize the current message and start a new one.
                    while (
                        len(self._accumulated) > _safe_limit
                        and self._message_id is not None
                    ):
                        split_at = self._accumulated.rfind("\\n", 0, _safe_limit)
                        if split_at < _safe_limit // 2:
                            split_at = _safe_limit
                        chunk = self._accumulated[:split_at]
                        await self._send_or_edit(chunk)
                        self._accumulated = self._accumulated[split_at:].lstrip("\\n")
                        self._message_id = None
                        self._last_sent_text = ""

                    display_text = self._accumulated
                    if not got_done:
                        display_text += self.cfg.cursor

                    await self._send_or_edit(display_text)
                    self._last_edit_time = time.monotonic()"""

new_run_edit = """                if should_edit and self._accumulated:
                    # Strip thinking/reasoning blocks before display
                    full_clean = _strip_think_blocks(self._accumulated)
                    if not full_clean:
                        # All content so far is inside a thinking block —
                        # skip this edit cycle and wait for real content.
                        if got_done:
                            return
                        await asyncio.sleep(0.05)
                        continue

                    # Only show text belonging to the current message
                    # (prior messages were finalized during earlier splits).
                    current_text = full_clean[self._finalized_offset:]

                    # Split overflow: if current-message text exceeds the
                    # platform limit, finalize this message and start a new one.
                    while (
                        len(current_text) > _safe_limit
                        and self._message_id is not None
                    ):
                        split_at = current_text.rfind("\\n", 0, _safe_limit)
                        if split_at < _safe_limit // 2:
                            split_at = _safe_limit
                        chunk = current_text[:split_at]
                        await self._send_or_edit(chunk)
                        remaining = current_text[split_at:].lstrip("\\n")
                        self._finalized_offset += len(current_text) - len(remaining)
                        current_text = remaining
                        self._message_id = None
                        self._last_sent_text = ""

                    if not got_done:
                        current_text += self.cfg.cursor

                    await self._send_or_edit(current_text)
                    self._last_edit_time = time.monotonic()"""

if old_run_edit in sc:
    sc = sc.replace(old_run_edit, new_run_edit)
    changed = True
    print("[patch] stream_consumer.py — patched run() should_edit block")
else:
    print("[patch] stream_consumer.py — run() should_edit pattern not found (may already be patched)")

# 1d. Patch the got_done block
old_got_done = """                if got_done:
                    # Final edit without cursor
                    if self._accumulated and self._message_id:
                        await self._send_or_edit(self._accumulated)
                    return"""

new_got_done = """                if got_done:
                    # Final edit — show thinking as spoiler if enabled, else strip
                    _show_spoiler = os.environ.get("THINKING_DISPLAY") == "spoiler"
                    final_text = _strip_think_blocks(self._accumulated, as_spoiler=_show_spoiler)
                    final_current = final_text[self._finalized_offset:] if final_text else ""
                    if final_current and self._message_id:
                        await self._send_or_edit(final_current)
                    return"""

if old_got_done in sc:
    sc = sc.replace(old_got_done, new_got_done)
    changed = True
    print("[patch] stream_consumer.py — patched run() got_done block")
else:
    print("[patch] stream_consumer.py — run() got_done pattern not found")

# 1e. Patch the cancellation handler
old_cancel = """        except asyncio.CancelledError:
            # Best-effort final edit on cancellation
            if self._accumulated and self._message_id:
                try:
                    await self._send_or_edit(self._accumulated)
                except Exception:
                    pass"""

new_cancel = """        except asyncio.CancelledError:
            # Best-effort final edit on cancellation
            if self._accumulated and self._message_id:
                try:
                    final = _strip_think_blocks(self._accumulated)
                    final_current = final[self._finalized_offset:] if final else ""
                    await self._send_or_edit(final_current or self._last_sent_text)
                except Exception:
                    pass"""

if old_cancel in sc:
    sc = sc.replace(old_cancel, new_cancel)
    changed = True
    print("[patch] stream_consumer.py — patched run() cancellation handler")
else:
    print("[patch] stream_consumer.py — run() cancellation pattern not found")


# 1f. Patch _clean_for_display to convert 💭 prefix to > 💭 blockquote
old_clean = '''        if "MEDIA:" not in text and "[[audio_as_voice]]" not in text:
            return text'''
new_clean = '''        # Convert 💭 reasoning prefix to > blockquote
        _thinking_emoji = chr(128173)
        if text.startswith(_thinking_emoji):
            _bq_split = text.find(chr(10) + chr(10))
            if _bq_split > 0:
                _bq_think = text[:_bq_split]
                _bq_rest = text[_bq_split:]
                _bq_lines = _bq_think.split(chr(10))
                text = chr(10).join("> " + _l for _l in _bq_lines) + _bq_rest
        # Strip leaked XML tool calls (M2.7 sometimes outputs these as text)
        import re as _re
        text = _re.sub(r"<minimax:tool_call>.*?</minimax:tool_call>", "", text, flags=_re.DOTALL)
        text = _re.sub(r"<invoke\\s+name=.*?</invoke>", "", text, flags=_re.DOTALL)
        text = _re.sub(r"</?minimax:tool_call>", "", text)
        if "MEDIA:" not in text and "[[audio_as_voice]]" not in text:
            return text'''
if old_clean in sc:
    sc = sc.replace(old_clean, new_clean)
    changed = True
    print("[patch] stream_consumer.py — patched _clean_for_display with 💭→blockquote")
else:
    print("[patch] stream_consumer.py — _clean_for_display pattern not found")

if changed:
    _write(f"{BASE}/gateway/stream_consumer.py", sc)

# ═══════════════════════════════════════════════════════════════
# 2. base.py — add RESPONSE_ALREADY_STREAMED sentinel
# ═══════════════════════════════════════════════════════════════
base = _read(f"{BASE}/gateway/platforms/base.py")
base_changed = False

if "RESPONSE_ALREADY_STREAMED = object()" not in base:
    sentinel = """


# Sentinel returned by the message handler when streaming already delivered the
# response.  Lets _process_message_background distinguish "nothing to send"
# (legitimate) from "handler failed" so it can log at the appropriate level.
RESPONSE_ALREADY_STREAMED = object()
"""
    base = base.replace(
        "from hermes_constants import get_hermes_dir",
        "from hermes_constants import get_hermes_dir" + sentinel
    )
    base_changed = True
    print("[patch] base.py — added RESPONSE_ALREADY_STREAMED sentinel")
else:
    print("[patch] base.py — RESPONSE_ALREADY_STREAMED already present")

# Patch the handler response check
old_handler_check = """            # Send response if any.  A None/empty response is normal when
            # streaming already delivered the text (already_sent=True) or
            # when the message was queued behind an active agent.  Log at
            # DEBUG to avoid noisy warnings for expected behavior.
            if not response:
                logger.debug("[%s] Handler returned empty/None response for %s", self.name, event.source.chat_id)"""

new_handler_check = """            # Send response if any.  A None/empty response is normal when
            # streaming already delivered the text (already_sent=True) or
            # when the message was queued behind an active agent.  Log at
            # DEBUG to avoid noisy warnings for expected behavior.
            if response is RESPONSE_ALREADY_STREAMED:
                # Streaming consumer already delivered the response — nothing to send.
                response = None
            elif not response:
                logger.debug("[%s] Handler returned empty/None response for %s", self.name, event.source.chat_id)"""

if old_handler_check in base:
    base = base.replace(old_handler_check, new_handler_check)
    base_changed = True
    print("[patch] base.py — patched handler response check")
else:
    print("[patch] base.py — handler response check pattern not found")

if base_changed:
    _write(f"{BASE}/gateway/platforms/base.py", base)

# ═══════════════════════════════════════════════════════════════
# 3. run.py — return RESPONSE_ALREADY_STREAMED instead of None
# ═══════════════════════════════════════════════════════════════
run = _read(f"{BASE}/gateway/run.py")
run_changed = False

# 3a. Import RESPONSE_ALREADY_STREAMED
if "from gateway.platforms.base import" in run and "RESPONSE_ALREADY_STREAMED" not in run:
    run = run.replace(
        "from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType",
        "from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, RESPONSE_ALREADY_STREAMED"
    )
    run_changed = True
    print("[patch] run.py — imported RESPONSE_ALREADY_STREAMED")
elif "RESPONSE_ALREADY_STREAMED" in run:
    print("[patch] run.py — RESPONSE_ALREADY_STREAMED already imported")
else:
    print("[patch] run.py — base import line not found, skipping import patch")

# 3b. Change "return None" to "return RESPONSE_ALREADY_STREAMED" in the already_sent block
old_return = """            if agent_result.get("already_sent"):
                if response:
                    _media_adapter = self.adapters.get(source.platform)
                    if _media_adapter:
                        await self._deliver_media_from_response(
                            response, event, _media_adapter,
                        )
                return None"""

new_return = """            if agent_result.get("already_sent"):
                if response:
                    _media_adapter = self.adapters.get(source.platform)
                    if _media_adapter:
                        await self._deliver_media_from_response(
                            response, event, _media_adapter,
                        )
                return RESPONSE_ALREADY_STREAMED"""

if old_return in run:
    run = run.replace(old_return, new_return)
    run_changed = True
    print("[patch] run.py — changed return None → return RESPONSE_ALREADY_STREAMED")
else:
    print("[patch] run.py — already_sent return pattern not found (may already be patched)")

if run_changed:
    _write(f"{BASE}/gateway/run.py", run)

print("\n[pull] PR #4558 patch complete.")
