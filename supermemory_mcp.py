"""Supermemory MCP bridge — stdio MCP server that wraps the Supermemory v4 API.
Hermes Agent spawns this as a subprocess and gets memory/recall tools."""

import os
import json
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

SUPERMEMORY_API_KEY = os.environ.get("SUPERMEMORY_API_KEY", "")
CONTAINER_TAG = "mina"

mcp = FastMCP("supermemory-bridge")


def _api(method: str, path: str, body: dict = None, timeout: int = 15) -> dict:
    """Make a request to Supermemory API."""
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
def supermemory_remember(content: str) -> str:
    """Save a memory to Supermemory. Use this to remember important things about
    the user — preferences, favorite places, travel plans, dietary needs, names,
    dates, anything worth remembering for future conversations.

    Args:
        content: The memory to save (be specific and detailed)
    """
    # v4 API: memories array of objects + containerTag
    body = {
        "memories": [{"content": content}],
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
def supermemory_recall(query: str = "") -> str:
    """Recall memories from Supermemory. Returns all stored memories about the user.
    Use this to recall what you know about the user — preferences, past conversations,
    travel plans, etc.

    Args:
        query: Optional search hint (currently lists all memories, filter by keyword)
    """
    # v4 memories/list returns all memories (search index unreliable)
    result = _api("POST", "/v4/memories/list", {
        "containerTags": [CONTAINER_TAG],
    })

    if not result.get("ok"):
        return f"Recall failed: {result.get('error', 'unknown error')}"

    data = result.get("data", {})
    entries = data.get("memoryEntries", [])

    if not entries:
        return "No memories stored yet."

    # Filter by query if provided
    if query:
        query_lower = query.lower()
        entries = [e for e in entries if query_lower in e.get("memory", "").lower()]

    if not entries:
        return f"No memories matching: {query}"

    # Filter out forgotten memories
    active = [e for e in entries if not e.get("isForgotten", False)]

    parts = []
    for i, mem in enumerate(active[:15], 1):
        memory_text = mem.get("memory", "")
        if memory_text:
            parts.append(f"{i}. {memory_text.strip()[:300]}")

    return f"Found {len(parts)} memories:\n" + "\n".join(parts)


@mcp.tool()
def supermemory_forget(memory_text: str) -> str:
    """Forget/remove a memory from Supermemory. Use when the user asks you to
    forget something or when information is no longer relevant.

    Args:
        memory_text: The memory text to forget (will match against stored memories)
    """
    # List all memories and find a match
    result = _api("POST", "/v4/memories/list", {
        "containerTags": [CONTAINER_TAG],
    })

    if not result.get("ok"):
        return f"Could not list memories: {result.get('error')}"

    entries = result.get("data", {}).get("memoryEntries", [])
    query_lower = memory_text.lower()

    # Find best match
    match = None
    for entry in entries:
        if query_lower in entry.get("memory", "").lower():
            match = entry
            break

    if not match:
        return f"No matching memory found for: {memory_text}"

    # Delete via v4 API
    mem_id = match.get("id", "")
    del_result = _api("DELETE", "/v4/memories", {"memoryIds": [mem_id]})
    if del_result.get("ok"):
        return f"Forgotten: {match.get('memory', memory_text)[:100]}"
    return f"Failed to forget: {del_result.get('error')}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
