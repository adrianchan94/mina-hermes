#!/usr/bin/env python3
"""Patch to register MiniMax media tools in the Hermes tool discovery system.

Copies minimax_media_tools.py into /opt/hermes/tools/ and adds it to
model_tools._discover_tools() so it gets auto-loaded at startup.
"""

import shutil
import os

TOOLS_DIR = "/opt/hermes/tools"
MODEL_TOOLS = "/opt/hermes/model_tools.py"
SRC = "/opt/hermes/minimax_media_tools.py"
DST = os.path.join(TOOLS_DIR, "minimax_media_tools.py")

# 1. Copy the tool file into tools/
if os.path.isfile(SRC):
    shutil.copy2(SRC, DST)
    print(f"[minimax-media] Copied {SRC} -> {DST}")
else:
    print(f"[minimax-media] ERROR: {SRC} not found")
    exit(1)

# 2. Add to _discover_tools() in model_tools.py
with open(MODEL_TOOLS) as f:
    src = f.read()

MODULE = '"tools.minimax_media_tools"'

if MODULE not in src:
    # Try primary anchor
    ANCHOR = '"tools.homeassistant_tool",'
    if ANCHOR in src:
        src = src.replace(ANCHOR, f'{ANCHOR}\n        {MODULE},')
        print(f"[minimax-media] Added via primary anchor (homeassistant_tool)")
    else:
        # Fallback: find the _modules list closing bracket and insert before it
        import re
        # Match the end of the _modules list
        pattern = r'(\s+\])\s*\n(\s+import importlib)'
        match = re.search(pattern, src)
        if match:
            src = src.replace(
                match.group(0),
                f'        {MODULE},\n{match.group(0)}'
            )
            print(f"[minimax-media] Added via fallback anchor (list end)")
        else:
            # Last resort: append import at the end of _discover_tools
            pattern2 = r'(def _discover_tools\(\):.*?)(^\w|\Z)'
            # Just force it by appending after _discover_tools() call
            if '_discover_tools()' in src:
                src = src.replace(
                    '_discover_tools()\n',
                    '_discover_tools()\n\n# Force-load MiniMax media tools\ntry:\n    import importlib\n    importlib.import_module("tools.minimax_media_tools")\nexcept Exception as _e:\n    import logging\n    logging.getLogger(__name__).warning("Could not import minimax_media_tools: %s", _e)\n\n',
                    1  # only first occurrence
                )
                print(f"[minimax-media] Added via last-resort (after _discover_tools call)")
            else:
                print(f"[minimax-media] WARNING: Could not find any anchor — manual wiring needed")
else:
    print("[minimax-media] tools.minimax_media_tools already in _discover_tools()")

with open(MODEL_TOOLS, "w") as f:
    f.write(src)

# 3. Verify
with open(MODEL_TOOLS) as f:
    verify = f.read()
if MODULE in verify or 'minimax_media_tools' in verify:
    print("[minimax-media] VERIFIED: minimax_media_tools is in model_tools.py")
else:
    print("[minimax-media] FAILED: minimax_media_tools NOT in model_tools.py")
    exit(1)

# 4. Create output directory
os.makedirs("/opt/data/media", exist_ok=True)
print("[minimax-media] Created /opt/data/media output directory")

# 5. Test import
try:
    import sys
    sys.path.insert(0, "/opt/hermes")
    from tools.minimax_media_tools import _check_minimax_key
    print(f"[minimax-media] Import test: SUCCESS")
except Exception as e:
    print(f"[minimax-media] Import test: FAILED - {e}")

print("\n[minimax-media] Done — 5 tools: minimax_image_understand, minimax_image_generate, minimax_speech, minimax_music, minimax_video")
