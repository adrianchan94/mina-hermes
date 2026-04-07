#!/usr/bin/env python3
"""Register web intelligence tools in Hermes tool discovery."""

import shutil
import os

SRC = "/opt/hermes/web_intelligence_tools.py"
DST = "/opt/hermes/tools/web_intelligence_tools.py"
MODEL_TOOLS = "/opt/hermes/model_tools.py"

# 1. Copy to tools/
shutil.copy2(SRC, DST)
print(f"[web-intel] Copied {SRC} -> {DST}")

# 2. Add to _discover_tools()
with open(MODEL_TOOLS) as f:
    src = f.read()

MODULE = '"tools.web_intelligence_tools"'
if MODULE not in src:
    ANCHOR = '"tools.homeassistant_tool",'
    if ANCHOR in src:
        src = src.replace(ANCHOR, f'{ANCHOR}\n        {MODULE},')
        print("[web-intel] Added via primary anchor")
    else:
        if '_discover_tools()' in src:
            src = src.replace(
                '_discover_tools()\n',
                f'_discover_tools()\ntry:\n    import importlib\n    importlib.import_module("tools.web_intelligence_tools")\nexcept Exception: pass\n',
                1
            )
            print("[web-intel] Added via fallback")
    with open(MODEL_TOOLS, "w") as f:
        f.write(src)
else:
    print("[web-intel] Already registered")

# 3. Test import
try:
    import sys
    sys.path.insert(0, "/opt/hermes")
    from tools.web_intelligence_tools import jina_read
    print("[web-intel] Import test: OK")
except Exception as e:
    print(f"[web-intel] Import test: FAILED - {e}")

print("[web-intel] Done — 4 tools: jina_read, youtube_transcript, reddit_read, rss_read")
