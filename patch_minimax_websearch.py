#!/usr/bin/env python3
"""Patch web_tools.py to add MiniMax as a native web search backend.

MiniMax Token Plan includes a web search API at POST /v1/coding_plan/search.
Uses the existing MINIMAX_API_KEY — no extra keys needed, no anti-bot issues.
"""

import re

WEB_TOOLS = "/opt/hermes/tools/web_tools.py"

with open(WEB_TOOLS) as f:
    src = f.read()

changes = 0

# 1. Add minimax to _get_backend() configured check
old = '''if configured in ("parallel", "firecrawl", "tavily", "exa"):'''
new = '''if configured in ("parallel", "firecrawl", "tavily", "exa", "minimax"):'''
if old in src:
    src = src.replace(old, new)
    changes += 1
    print("[minimax-websearch] Added minimax to _get_backend() configured list")

# 2. Add minimax to backend_candidates (highest priority)
old_candidates = '''    backend_candidates = (
        ("firecrawl", _has_env("FIRECRAWL_API_KEY") or _has_env("FIRECRAWL_API_URL") or _is_tool_gateway_ready()),
        ("parallel", _has_env("PARALLEL_API_KEY")),
        ("tavily", _has_env("TAVILY_API_KEY")),
        ("exa", _has_env("EXA_API_KEY")),
    )'''
new_candidates = '''    backend_candidates = (
        ("minimax", _has_env("MINIMAX_API_KEY")),
        ("firecrawl", _has_env("FIRECRAWL_API_KEY") or _has_env("FIRECRAWL_API_URL") or _is_tool_gateway_ready()),
        ("parallel", _has_env("PARALLEL_API_KEY")),
        ("tavily", _has_env("TAVILY_API_KEY")),
        ("exa", _has_env("EXA_API_KEY")),
    )'''
if old_candidates in src:
    src = src.replace(old_candidates, new_candidates)
    changes += 1
    print("[minimax-websearch] Added minimax to backend_candidates")

# 3. Add minimax to _is_backend_available()
old_avail = '''def _is_backend_available(backend: str) -> bool:
    """Return True when the selected backend is currently usable."""
    if backend == "exa":'''
new_avail = '''def _is_backend_available(backend: str) -> bool:
    """Return True when the selected backend is currently usable."""
    if backend == "minimax":
        return _has_env("MINIMAX_API_KEY")
    if backend == "exa":'''
if old_avail in src:
    src = src.replace(old_avail, new_avail)
    changes += 1
    print("[minimax-websearch] Added minimax to _is_backend_available()")

# 4. Add minimax to check_web_api_key()
old_check = '''    if configured in ("exa", "parallel", "firecrawl", "tavily"):
        return _is_backend_available(configured)
    return any(_is_backend_available(backend) for backend in ("exa", "parallel", "firecrawl", "tavily"))'''
new_check = '''    if configured in ("exa", "parallel", "firecrawl", "tavily", "minimax"):
        return _is_backend_available(configured)
    return any(_is_backend_available(backend) for backend in ("minimax", "exa", "parallel", "firecrawl", "tavily"))'''
if old_check in src:
    src = src.replace(old_check, new_check)
    changes += 1
    print("[minimax-websearch] Added minimax to check_web_api_key()")

# 5. Add _minimax_search() function — insert before _get_firecrawl_client
minimax_fn = '''
def _minimax_search(query: str, limit: int = 5) -> dict:
    """Search the web using MiniMax's built-in search API (included in Token Plan).

    Endpoint: POST /v1/coding_plan/search
    No extra API keys needed — uses MINIMAX_API_KEY.
    """
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    api_host = os.getenv("MINIMAX_API_HOST", "https://api.minimax.io").strip().rstrip("/")
    if not api_key:
        return {"success": False, "error": "MINIMAX_API_KEY not set"}

    url = f"{api_host}/v1/coding_plan/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "MM-API-Source": "Minimax-MCP",
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json={"q": query}, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        organic = data.get("organic", [])[:limit]
        web_results = []
        for i, item in enumerate(organic):
            web_results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "description": item.get("snippet", ""),
                "position": i + 1,
            })

        return {"success": True, "data": {"web": web_results}}

    except Exception as e:
        logger.error("MiniMax search failed: %s", e)
        return {"success": False, "error": str(e)}


'''

anchor = "def _get_firecrawl_client():"
if "_minimax_search" not in src and anchor in src:
    src = src.replace(anchor, minimax_fn + anchor)
    changes += 1
    print("[minimax-websearch] Added _minimax_search() function")

# 6. Add minimax dispatch in web_search_tool()
old_dispatch = '''        # Dispatch to the configured backend
        backend = _get_backend()
        if backend == "parallel":'''
new_dispatch = '''        # Dispatch to the configured backend
        backend = _get_backend()
        if backend == "minimax":
            logger.info("MiniMax search: '%s' (limit: %d)", query, limit)
            response_data = _minimax_search(query, limit)
            debug_call_data["results_count"] = len(response_data.get("data", {}).get("web", []))
            result_json = json.dumps(response_data, indent=2, ensure_ascii=False)
            debug_call_data["final_response_size"] = len(result_json)
            _debug.log_call("web_search_tool", debug_call_data)
            _debug.save()
            return result_json

        if backend == "parallel":'''
if old_dispatch in src:
    src = src.replace(old_dispatch, new_dispatch)
    changes += 1
    print("[minimax-websearch] Added minimax dispatch to web_search_tool()")

# 7. Add MINIMAX_API_KEY to _web_requires_env
old_env = '''    requires = [
        "EXA_API_KEY",'''
new_env = '''    requires = [
        "MINIMAX_API_KEY",
        "EXA_API_KEY",'''
if "MINIMAX_API_KEY" not in src and old_env in src:
    src = src.replace(old_env, new_env)
    changes += 1
    print("[minimax-websearch] Added MINIMAX_API_KEY to _web_requires_env()")

with open(WEB_TOOLS, "w") as f:
    f.write(src)

print(f"\n[minimax-websearch] Done — {changes} patches applied to web_tools.py")
