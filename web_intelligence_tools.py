#!/usr/bin/env python3
"""
Web Intelligence Tools — Fill the gaps in Jonah's web coverage.

Tools:
- jina_read: Extract clean markdown from any URL (Jina Reader, free)
- youtube_transcript: Get transcript from any YouTube video
- reddit_read: Read any Reddit post/thread as JSON
- rss_read: Parse any RSS feed

All zero-config, zero API keys, zero cost.
"""

import json
import logging
import os
import re
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)


def jina_read(url: str) -> str:
    """Read any webpage and return clean markdown via Jina Reader."""
    try:
        jina_url = f"https://r.jina.ai/{url}"
        req = urllib.request.Request(jina_url, headers={
            "Accept": "text/markdown",
            "User-Agent": "Mozilla/5.0",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        # Cap at 8000 chars to avoid flooding context
        if len(content) > 8000:
            content = content[:8000] + "\n\n... [truncated]"
        return json.dumps({"success": True, "content": content, "url": url})
    except Exception as e:
        logger.error("Jina read failed for %s: %s", url, e)
        return json.dumps({"error": str(e), "url": url})


def youtube_transcript(video_url: str, language: str = "en") -> str:
    """Get transcript/subtitles from a YouTube video."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        # Extract video ID from URL
        match = re.search(r'(?:v=|youtu\.be/|/v/|/embed/)([a-zA-Z0-9_-]{11})', video_url)
        if not match:
            return json.dumps({"error": f"Could not extract video ID from: {video_url}"})
        video_id = match.group(1)
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language, "en"])
        text = " ".join(entry["text"] for entry in transcript)
        if len(text) > 8000:
            text = text[:8000] + " ... [truncated]"
        return json.dumps({"success": True, "video_id": video_id, "transcript": text})
    except Exception as e:
        logger.error("YouTube transcript failed for %s: %s", video_url, e)
        return json.dumps({"error": str(e), "video_url": video_url})


def reddit_read(url: str) -> str:
    """Read Reddit content. Tries .json endpoint first, falls back to web search for Reddit content."""
    try:
        # Try .json endpoint first
        clean_url = url.replace("www.reddit.com", "old.reddit.com")
        if not clean_url.startswith("http"):
            clean_url = "https://old.reddit.com" + clean_url
        if not clean_url.endswith(".json"):
            clean_url = clean_url.rstrip("/") + ".json"
        req = urllib.request.Request(clean_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, list) and len(data) >= 2:
            post = data[0]["data"]["children"][0]["data"]
            comments = data[1]["data"]["children"][:10]
            return json.dumps({"success": True, "data": {
                "title": post.get("title", ""),
                "selftext": post.get("selftext", "")[:2000],
                "score": post.get("score", 0),
                "author": post.get("author", ""),
                "top_comments": [
                    {"author": c["data"].get("author", ""), "body": c["data"].get("body", "")[:500]}
                    for c in comments if c.get("kind") == "t1"
                ][:5],
            }})
        elif isinstance(data, dict) and "data" in data:
            posts = data["data"].get("children", [])[:10]
            return json.dumps({"success": True, "posts": [
                {"title": p["data"].get("title", ""), "score": p["data"].get("score", 0), "url": "https://reddit.com" + p["data"].get("permalink", "")}
                for p in posts
            ]})
    except Exception:
        pass
    # Fallback: use Jina Reader
    try:
        return jina_read(url)
    except Exception as e:
        return json.dumps({"error": f"Reddit blocked direct access and Jina fallback failed: {e}. Try using web_search with 'site:reddit.com' + your query instead.", "url": url})


def rss_read(feed_url: str, limit: int = 10) -> str:
    """Parse any RSS/Atom feed and return entries."""
    try:
        import feedparser
        feed = feedparser.parse(feed_url)
        entries = []
        for entry in feed.entries[:limit]:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", "")[:500],
            })
        return json.dumps({
            "success": True,
            "feed_title": feed.feed.get("title", ""),
            "entries": entries,
        })
    except Exception as e:
        logger.error("RSS read failed for %s: %s", feed_url, e)
        return json.dumps({"error": str(e), "feed_url": feed_url})


# ─── Registry ────────────────────────────────────────────────────────────────
from tools.registry import registry

JINA_SCHEMA = {
    "name": "jina_read",
    "description": "Read any webpage and return clean markdown. Works on articles, docs, blogs, news — anything with a URL. Free, no API key. Use this to extract content from web pages after finding them with web_search.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The full URL to read"}
        },
        "required": ["url"]
    }
}

YOUTUBE_SCHEMA = {
    "name": "youtube_transcript",
    "description": "Get the full transcript/subtitles from any YouTube video. Extracts the spoken text. Use this when you need to know what was said in a video.",
    "parameters": {
        "type": "object",
        "properties": {
            "video_url": {"type": "string", "description": "YouTube video URL (any format: youtube.com/watch?v=, youtu.be/, etc.)"},
            "language": {"type": "string", "description": "Preferred language code (default: en)", "default": "en"}
        },
        "required": ["video_url"]
    }
}

REDDIT_SCHEMA = {
    "name": "reddit_read",
    "description": "Read any Reddit post, thread, or subreddit. Returns post content, score, and top comments. Use any Reddit URL.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Reddit URL (post, thread, or subreddit like /r/programming)"}
        },
        "required": ["url"]
    }
}

RSS_SCHEMA = {
    "name": "rss_read",
    "description": "Parse any RSS or Atom feed. Returns latest entries with titles, links, and summaries. Use for news feeds, blogs, podcasts.",
    "parameters": {
        "type": "object",
        "properties": {
            "feed_url": {"type": "string", "description": "RSS/Atom feed URL"},
            "limit": {"type": "integer", "description": "Max entries to return (default: 10)", "default": 10}
        },
        "required": ["feed_url"]
    }
}

registry.register(name="jina_read", toolset="web_intelligence", schema=JINA_SCHEMA,
    handler=lambda args, **kw: jina_read(args.get("url", "")),
    check_fn=lambda: True, emoji="📄")

registry.register(name="youtube_transcript", toolset="web_intelligence", schema=YOUTUBE_SCHEMA,
    handler=lambda args, **kw: youtube_transcript(args.get("video_url", ""), args.get("language", "en")),
    check_fn=lambda: True, emoji="🎬")

registry.register(name="reddit_read", toolset="web_intelligence", schema=REDDIT_SCHEMA,
    handler=lambda args, **kw: reddit_read(args.get("url", "")),
    check_fn=lambda: True, emoji="🔶")

registry.register(name="rss_read", toolset="web_intelligence", schema=RSS_SCHEMA,
    handler=lambda args, **kw: rss_read(args.get("feed_url", ""), args.get("limit", 10)),
    check_fn=lambda: True, emoji="📡")
