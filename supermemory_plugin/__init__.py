"""Supermemory auto-context plugin for Hermes Agent.

Hooks:
  pre_llm_call  — Recalls relevant memories and injects them as context.
  post_llm_call — Auto-retains significant exchanges (decisions, preferences, facts).
  on_session_start — Logs session start for continuity tracking.
"""

import json
import logging
import os
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

SUPERMEMORY_API_KEY = os.environ.get("SUPERMEMORY_API_KEY", "")
SUPERMEMORY_API_URL = "https://api.supermemory.ai/v3"
CONTAINER_TAG = "mina"  # Scope all memories to Mina's container


def _api_request(method: str, path: str, body: dict = None) -> dict:
    """Make a request to Supermemory API."""
    if not SUPERMEMORY_API_KEY:
        return {"error": "SUPERMEMORY_API_KEY not set"}

    url = f"{SUPERMEMORY_API_URL}{path}"
    headers = {
        "Authorization": f"Bearer {SUPERMEMORY_API_KEY}",
        "Content-Type": "application/json",
    }

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        logger.warning("Supermemory API error %d: %s", e.code, error_body[:200])
        return {"error": f"HTTP {e.code}: {error_body[:200]}"}
    except Exception as e:
        logger.warning("Supermemory API request failed: %s", e)
        return {"error": str(e)}


def _recall(query: str, limit: int = 10) -> str:
    """Search Supermemory for relevant memories."""
    result = _api_request("POST", "/search", {
        "q": query,
        "containerTags": [CONTAINER_TAG],
        "limit": limit,
    })

    if "error" in result:
        return ""

    memories = result.get("results", result.get("memories", []))
    if not memories:
        return ""

    parts = []
    for mem in memories[:limit]:
        content = mem.get("content", mem.get("text", ""))
        if content:
            parts.append(f"- {content.strip()}")

    return "\n".join(parts)


def _retain(content: str) -> bool:
    """Save a memory to Supermemory."""
    result = _api_request("POST", "/memories", {
        "content": content,
        "containerTags": [CONTAINER_TAG],
    })
    return "error" not in result


# ── Hooks ────────────────────────────────────────────────────────────


def pre_llm_call(messages: list, **kwargs) -> list:
    """Recall relevant memories before each LLM call and inject as context."""
    if not SUPERMEMORY_API_KEY or not messages:
        return messages

    # Extract the last user message as the recall query
    user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                # Multimodal content — extract text parts
                text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                user_msg = " ".join(text_parts)
            else:
                user_msg = str(content)
            break

    if not user_msg or len(user_msg) < 5:
        return messages

    try:
        recalled = _recall(user_msg, limit=8)
        if recalled:
            context_block = (
                "\n<supermemory_context>\n"
                "Relevant memories from past conversations:\n"
                f"{recalled}\n"
                "</supermemory_context>\n"
            )
            # Inject into the system message if it exists, otherwise prepend
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = messages[0]["content"] + context_block
            else:
                messages.insert(0, {"role": "system", "content": context_block})
    except Exception as e:
        logger.warning("Supermemory pre_llm_call recall failed: %s", e)

    return messages


def post_llm_call(messages: list, response: str = "", **kwargs) -> None:
    """Auto-retain significant exchanges after each LLM call."""
    if not SUPERMEMORY_API_KEY or not response:
        return

    # Only retain if the exchange seems significant (not trivial)
    if len(response) < 50:
        return

    # Extract the user's message
    user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                user_msg = " ".join(text_parts)
            else:
                user_msg = str(content)
            break

    if not user_msg:
        return

    # Check for significance markers
    significance_markers = [
        "prefer", "favorite", "love", "hate", "always", "never",
        "remember", "don't forget", "important", "allergic", "birthday",
        "restaurant", "hotel", "flight", "booking", "trip", "travel",
        "wine", "food", "recipe", "recommend", "suggest",
        "address", "phone", "email", "name", "friend", "family",
    ]

    msg_lower = user_msg.lower()
    is_significant = any(marker in msg_lower for marker in significance_markers)

    if not is_significant:
        return

    try:
        # Build a concise memory entry
        memory_content = f"User said: {user_msg[:500]}\nMina responded: {response[:500]}"
        _retain(memory_content)
        logger.debug("Supermemory auto-retained exchange")
    except Exception as e:
        logger.warning("Supermemory post_llm_call retain failed: %s", e)


def on_session_start(**kwargs) -> None:
    """Log session start."""
    logger.info("Supermemory plugin: session started (container: %s)", CONTAINER_TAG)
