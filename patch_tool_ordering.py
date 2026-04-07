#!/usr/bin/env python3
"""Patch tool definition ordering to prioritize high-frequency tools.

MiniMax research shows tool ordering affects selection accuracy.
Most-used tools first = model picks the right tool more often.
Patches registry.get_definitions() to sort by priority instead of alphabetically.
"""

REGISTRY_PATH = "/opt/hermes/tools/registry.py"

with open(REGISTRY_PATH) as f:
    src = f.read()

# The current code sorts alphabetically: `for name in sorted(tool_names):`
# Replace with priority-based ordering that puts high-frequency tools first.

old = '''    def get_definitions(self, tool_names: Set[str], quiet: bool = False) -> List[dict]:
        """Return OpenAI-format tool schemas for the requested tool names.

        Only tools whose ``check_fn()`` returns True (or have no check_fn)
        are included.
        """
        result = []
        check_results: Dict[Callable, bool] = {}
        for name in sorted(tool_names):'''

new = '''    # High-frequency tools listed first improve model selection accuracy.
    # MiniMax research: tool position in the definition list affects which
    # tool the model picks. Most-used tools first = fewer misroutes.
    _TOOL_PRIORITY = [
        # Core tools the agent uses on almost every turn
        "run_command",
        "web_search",
        "web_extract",
        "read_file",
        "write_file",
        "search_files",
        # Memory & communication
        "memory",
        "hindsight_auto_context",
        "hindsight_retain",
        "hindsight_recall",
        "send_message",
        # Browser
        "browser_navigate",
        "browser_snapshot",
        "browser_click",
        "browser_type",
        # MiniMax media (new, should be discoverable)
        "minimax_image_generate",
        "minimax_speech",
        "minimax_image_understand",
        "minimax_music",
        "minimax_video",
        # Vision & code
        "vision_analyze",
        "execute_code",
    ]

    def get_definitions(self, tool_names: Set[str], quiet: bool = False) -> List[dict]:
        """Return OpenAI-format tool schemas for the requested tool names.

        Only tools whose ``check_fn()`` returns True (or have no check_fn)
        are included. Tools are ordered by priority (high-frequency first)
        then alphabetically for the rest.
        """
        result = []
        check_results: Dict[Callable, bool] = {}

        # Build priority-ordered name list
        priority_order = [n for n in self._TOOL_PRIORITY if n in tool_names]
        remaining = sorted(tool_names - set(priority_order))
        ordered_names = priority_order + remaining

        for name in ordered_names:'''

if old in src:
    src = src.replace(old, new)
    with open(REGISTRY_PATH, "w") as f:
        f.write(src)
    print("[tool-ordering] Patched get_definitions() with priority-based ordering")
else:
    print("[tool-ordering] WARNING: Could not find target in registry.py — may already be patched")
