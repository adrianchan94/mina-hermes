# Web Research

Full internet coverage for finding restaurants, travel info, wine, and anything Marina needs.

## Search
```python
# web_search is a native tool — just call it directly
# Returns top 5 results from MiniMax native search
```

## Read Any Page (Jina Reader)
```python
python3 -c "import urllib.request; req=urllib.request.Request('https://r.jina.ai/URL_HERE', headers={'Accept':'text/markdown','User-Agent':'Mozilla/5.0'}); print(urllib.request.urlopen(req,timeout=15).read().decode()[:5000])"
```

## YouTube Transcripts
```python
# youtube_transcript is a native tool
# Pass any YouTube URL — returns full subtitles
```

## Reddit Threads
```python
# reddit_read is a native tool
# Pass any Reddit URL — returns post + top comments
```

## RSS Feeds
```python
# rss_read is a native tool
# Pass any RSS URL — returns latest entries
```

## Research Pattern
For restaurant/travel/wine questions:
1. `web_search` for current info
2. `jina_read` to read the top result in detail
3. Synthesize with what you know from `supermemory_recall`
4. Give Marina a thoughtful, detailed recommendation
