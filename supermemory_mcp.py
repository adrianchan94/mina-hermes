"""Supermemory MCP bridge — stdio MCP server that wraps the Supermemory HTTP API.
Hermes Agent spawns this as a subprocess and gets memory/recall tools."""

import os
import json
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

SUPERMEMORY_API_KEY = os.environ.get("SUPERMEMORY_API_KEY", "")
SUPERMEMORY_API_URL = "https://api.supermemory.ai/v3"
CONTAINER_TAG = "mina"

mcp = FastMCP("supermemory-bridge")


def _api(method: str, path: str, body: dict = None, timeout: int = 15) -> dict:
    """Make a request to Supermemory API."""
    if not SUPERMEMORY_API_KEY:
        return {"ok": False, "error": "SUPERMEMORY_API_KEY not set"}

    url = f"{SUPERMEMORY_API_URL}{path}"
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
def supermemory_remember(content: str, tags: str = "") -> str:
    """Save a memory to Supermemory. Use this to remember important things about
    the user — preferences, favorite places, travel plans, dietary needs, names,
    dates, anything worth remembering for future conversations.

    Args:
        content: The memory to save (be specific and detailed)
        tags: Optional comma-separated tags for organization
    """
    body = {"content": content}
    if tags:
        body["containerTags"] = [t.strip() for t in tags.split(",")]
    else:
        body["containerTags"] = [CONTAINER_TAG]

    result = _api("POST", "/documents", body)
    if result.get("ok"):
        return f"Remembered: {content[:100]}..."
    return f"Failed to save memory: {result.get('error', 'unknown error')}"


@mcp.tool()
def supermemory_recall(query: str, limit: int = 8) -> str:
    """Search Supermemory for relevant memories. Use this to recall what you know
    about the user, their preferences, past conversations, travel plans, etc.

    Args:
        query: What to search for (e.g. "favorite restaurants", "travel plans")
        limit: Max number of memories to return (default 8)
    """
    body = {
        "q": query,
        "containerTags": [CONTAINER_TAG],
        "limit": limit,
    }

    result = _api("POST", "/search", body)
    if not result.get("ok"):
        return f"Recall failed: {result.get('error', 'unknown error')}"

    data = result.get("data", {})
    memories = data.get("results", data.get("memories", data.get("documents", [])))

    if not memories:
        return f"No memories found for: {query}"

    parts = []
    for i, mem in enumerate(memories[:limit], 1):
        content = mem.get("content", mem.get("text", mem.get("title", "")))
        if content:
            parts.append(f"{i}. {content.strip()[:300]}")

    return f"Found {len(parts)} memories:\n" + "\n".join(parts)


@mcp.tool()
def supermemory_forget(content: str) -> str:
    """Forget/remove a memory from Supermemory. Use when the user asks you to
    forget something or when information is no longer relevant.

    Args:
        content: Description of what to forget
    """
    # First search for the memory
    search_result = _api("POST", "/search", {
        "q": content,
        "containerTags": [CONTAINER_TAG],
        "limit": 3,
    })

    if not search_result.get("ok"):
        return f"Could not search for memory to forget: {search_result.get('error')}"

    data = search_result.get("data", {})
    memories = data.get("results", data.get("memories", data.get("documents", [])))

    if not memories:
        return f"No matching memory found for: {content}"

    # Delete the first match
    mem_id = memories[0].get("id", memories[0].get("_id", ""))
    if mem_id:
        del_result = _api("DELETE", f"/documents/{mem_id}")
        if del_result.get("ok"):
            return f"Forgotten: {content[:100]}"
        return f"Failed to forget: {del_result.get('error')}"

    return "Could not identify the memory to forget"


if __name__ == "__main__":
    mcp.run(transport="stdio")
