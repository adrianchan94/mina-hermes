"""Supermemory MCP bridge — stdio MCP server that wraps the Supermemory v4 API.

Validated against official docs: https://supermemory.ai/docs/api-reference/

Endpoints used:
  POST /v4/memories          — Create memories (bypasses document ingestion)
  POST /v4/search            — Hybrid search across memories
  DELETE /v4/memories        — Soft-delete (forget) a memory
  POST /v4/memories/list     — List all memories in a container
"""

import os
import json
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

SUPERMEMORY_API_KEY = os.environ.get("SUPERMEMORY_API_KEY", "")
CONTAINER_TAG = "mina"

mcp = FastMCP("supermemory-bridge")


def _api(method: str, path: str, body: dict = None, timeout: int = 15) -> dict:
    if not SUPERMEMORY_API_KEY:
        return {"ok": False, "error": "SUPERMEMORY_API_KEY not set"}

    url = f"https://api.supermemory.ai{path}"
    headers = {
        "Authorization": f"Bearer {SUPERMEMORY_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "mina-supermemory-bridge/1.0",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return {"ok": True, "data": json.loads(raw)}
            except json.JSONDecodeError:
                return {"ok": True, "data": raw}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        return {"ok": False, "error": f"HTTP {e.code}: {error_body[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
def supermemory_remember(content: str, is_static: bool = False) -> str:
    """Save a memory to Supermemory. Use this to remember important things about
    the user — preferences, favorite places, travel plans, dietary needs, names,
    dates, anything worth remembering for future conversations.

    Args:
        content: The memory to save (be specific and detailed)
        is_static: True for permanent facts (name, birthday), False for changeable info
    """
    # Docs: POST /v4/memories
    # Body: { memories: [{content, isStatic?, metadata?, forgetAfter?}], containerTag }
    body = {
        "memories": [
            {
                "content": content,
                "isStatic": is_static,
            }
        ],
        "containerTag": CONTAINER_TAG,
    }

    result = _api("POST", "/v4/memories", body)
    if result.get("ok"):
        data = result.get("data", {})
        memories = data.get("memories", [])
        if memories:
            return f"Remembered: {memories[0].get('memory', content[:100])}"
        return f"Remembered: {content[:100]}"
    return f"Failed to save memory: {result.get('error', 'unknown error')}"


@mcp.tool()
def supermemory_recall(query: str, limit: int = 10) -> str:
    """Search Supermemory for relevant memories. Use this to recall what you know
    about the user, their preferences, past conversations, travel plans, etc.

    Args:
        query: What to search for (e.g. "favorite restaurants", "travel plans")
        limit: Max number of results (default 10)
    """
    # Docs: POST /v4/search
    # Body: { q, containerTag, searchMode: "hybrid", limit }
    result = _api("POST", "/v4/search", {
        "q": query,
        "containerTag": CONTAINER_TAG,
        "searchMode": "hybrid",
        "limit": limit,
    })

    if not result.get("ok"):
        # Fallback to listing all memories if search fails
        return _recall_via_list(query)

    data = result.get("data", {})
    results = data.get("results", [])

    if not results:
        # Search index may not be ready — fallback to list
        return _recall_via_list(query)

    parts = []
    for i, mem in enumerate(results[:limit], 1):
        text = mem.get("memory", mem.get("content", mem.get("text", "")))
        if text:
            parts.append(f"{i}. {text.strip()[:300]}")

    return f"Found {len(parts)} memories:\n" + "\n".join(parts)


def _recall_via_list(query: str = "") -> str:
    """Fallback: list all memories and filter client-side."""
    result = _api("POST", "/v4/memories/list", {
        "containerTags": [CONTAINER_TAG],
    })

    if not result.get("ok"):
        return f"Recall failed: {result.get('error', 'unknown error')}"

    entries = result.get("data", {}).get("memoryEntries", [])
    active = [e for e in entries if not e.get("isForgotten", False)]

    if query:
        query_lower = query.lower()
        active = [e for e in active if query_lower in e.get("memory", "").lower()]

    if not active:
        return f"No memories found{' for: ' + query if query else ''}."

    parts = []
    for i, mem in enumerate(active[:15], 1):
        text = mem.get("memory", "")
        if text:
            parts.append(f"{i}. {text.strip()[:300]}")

    return f"Found {len(parts)} memories:\n" + "\n".join(parts)


@mcp.tool()
def supermemory_forget(content: str, reason: str = "") -> str:
    """Forget/remove a memory from Supermemory. Use when the user asks you to
    forget something or when information is no longer relevant.

    Args:
        content: The memory content to forget (matched against stored memories)
        reason: Optional reason for forgetting
    """
    # Docs: DELETE /v4/memories
    # Body: { containerTag, content?, id?, reason? }
    body = {
        "containerTag": CONTAINER_TAG,
        "content": content,
    }
    if reason:
        body["reason"] = reason

    result = _api("DELETE", "/v4/memories", body)
    if result.get("ok"):
        data = result.get("data", {})
        if data.get("forgotten"):
            return f"Forgotten: {content[:100]}"
        return f"Processed forget request for: {content[:100]}"
    return f"Failed to forget: {result.get('error', 'unknown error')}"


@mcp.tool()
def supermemory_list_all() -> str:
    """List ALL stored memories. Use this to see everything you remember about
    the user. Good for checking what you know before a conversation."""
    return _recall_via_list()


if __name__ == "__main__":
    mcp.run(transport="stdio")
