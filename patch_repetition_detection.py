#!/usr/bin/env python3
"""Patch repetition detection into the agent loop.

MiniMax research: 3000+ consecutive high-probability tokens can lead to
degenerate looping output. This patch detects when the agent calls the
same tool with identical args 3+ times in a row.
"""

RUN_AGENT = "/opt/hermes/run_agent.py"

with open(RUN_AGENT) as f:
    src = f.read()

changes = 0

# 1. Add repetition tracking state after other init vars
old_init = '''        api_call_count = 0
        final_response = None
        interrupted = False
        codex_ack_continuations = 0
        length_continue_retries = 0
        truncated_response_prefix = ""
        compression_attempts = 0'''

new_init = '''        api_call_count = 0
        final_response = None
        interrupted = False
        codex_ack_continuations = 0
        length_continue_retries = 0
        truncated_response_prefix = ""
        compression_attempts = 0

        # ── Repetition detection ──────────────────────────────────
        _recent_tool_calls = []   # list of (name, args_hash) tuples
        _repetition_warnings = 0  # how many times we've warned'''

if old_init in src:
    src = src.replace(old_init, new_init)
    changes += 1
    print("[repetition] Added tracking state variables")

# 2. Add repetition check after api_call_count increment (match upstream exactly)
old_budget = '''            api_call_count += 1
            self._api_call_count = api_call_count
            self._touch_activity(f"starting API call #{api_call_count}")
            if not self.iteration_budget.consume():'''

new_budget = '''            api_call_count += 1
            self._api_call_count = api_call_count
            self._touch_activity(f"starting API call #{api_call_count}")

            # ── Repetition detection ──────────────────────────────
            if len(_recent_tool_calls) >= 3:
                _last3 = _recent_tool_calls[-3:]
                if _last3[0] == _last3[1] == _last3[2]:
                    _repetition_warnings += 1
                    _rep_tool = _last3[0][0]
                    if _repetition_warnings >= 2:
                        if not self.quiet_mode:
                            self._safe_print(f"\\n🔄 LOOP DETECTED: {_rep_tool} called identically 3+ times. Forcing stop.")
                        break
                    else:
                        if not self.quiet_mode:
                            self._safe_print(f"\\n🔄 REPETITION WARNING: {_rep_tool} called with identical args 3 times.")
                        messages.append({
                            "role": "user",
                            "content": (
                                f"[SYSTEM WARNING] You called {_rep_tool} with identical arguments 3 times in a row. "
                                "You are in a loop. STOP. Try a different approach, use a different tool, "
                                "or respond explaining what went wrong. Do NOT repeat the same call."
                            ),
                        })

            if not self.iteration_budget.consume():'''

if old_budget in src:
    src = src.replace(old_budget, new_budget)
    changes += 1
    print("[repetition] Added repetition check in main loop")

# 3. Track tool calls — inject after the first tool_msg append (sequential path)
old_track = '''            tool_msg = {
                "role": "tool",
                "content": function_result,
                "tool_call_id": tc.id,
            }
            messages.append(tool_msg)

        # ── Budget pressure injection'''

new_track = '''            tool_msg = {
                "role": "tool",
                "content": function_result,
                "tool_call_id": tc.id,
            }
            messages.append(tool_msg)

            # Track for repetition detection
            import hashlib as _hl
            _ah = _hl.md5(tc.function.arguments.encode()).hexdigest()[:8]
            _recent_tool_calls.append((tc.function.name, _ah))
            if len(_recent_tool_calls) > 10:
                _recent_tool_calls = _recent_tool_calls[-10:]

        # ── Budget pressure injection'''

if old_track in src:
    src = src.replace(old_track, new_track)
    changes += 1
    print("[repetition] Added tool call tracking after execution")

with open(RUN_AGENT, "w") as f:
    f.write(src)

print(f"\n[repetition] Done — {changes}/3 patches applied to run_agent.py")
if changes < 3:
    print("[repetition] WARNING: Some anchors not found. Check upstream changes.")
