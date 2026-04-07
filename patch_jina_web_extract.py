#!/usr/bin/env python3
"""Patch web_extract to use Jina Reader when Firecrawl is not available.

Jina Reader: prefix any URL with https://r.jina.ai/ — returns clean markdown.
Free, no API key, works on any page. Replaces broken Firecrawl backend.
"""

WEB_TOOLS = "/opt/hermes/tools/web_tools.py"

with open(WEB_TOOLS) as f:
    src = f.read()

# Find the web_extract_tool function and add Jina fallback
# When Firecrawl fails, fall back to Jina Reader

JINA_FALLBACK = '''

def _jina_extract(url: str, timeout: int = 15) -> str:
    """Extract page content using Jina Reader (free, no API key)."""
    import urllib.request
    jina_url = f"https://r.jina.ai/{url}"
    req = urllib.request.Request(jina_url, headers={
        "Accept": "text/markdown",
        "User-Agent": "Mozilla/5.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Jina Reader error: {e}"

'''

# Add Jina function after imports
ANCHOR = "logger = logging.getLogger(__name__)"
if "_jina_extract" not in src and ANCHOR in src:
    src = src.replace(ANCHOR, ANCHOR + JINA_FALLBACK)
    print("[jina] Added _jina_extract function")

# Patch the web_extract_tool error handler to fall back to Jina
OLD_ERROR = '''    except Exception as e:
        error_msg = f"Error extracting content: {str(e)}"
        logger.debug("%s", error_msg)'''

NEW_ERROR = '''    except Exception as e:
        error_msg = f"Error extracting content: {str(e)}"
        logger.debug("%s — falling back to Jina Reader", error_msg)
        # Fallback: use Jina Reader for each URL
        jina_results = []
        for _jurl in urls[:5]:
            _jcontent = _jina_extract(_jurl)
            if _jcontent and not _jcontent.startswith("Jina Reader error"):
                jina_results.append({"url": _jurl, "content": _jcontent[:5000], "source": "jina"})
        if jina_results:
            return json.dumps({"success": True, "data": jina_results, "backend": "jina_fallback"}, indent=2, ensure_ascii=False)'''

if OLD_ERROR in src and "jina_fallback" not in src:
    src = src.replace(OLD_ERROR, NEW_ERROR)
    print("[jina] Patched web_extract error handler with Jina fallback")
else:
    print("[jina] Error handler pattern not found or already patched")

with open(WEB_TOOLS, "w") as f:
    f.write(src)

print("[jina] Done — web_extract now falls back to Jina Reader when Firecrawl fails")
