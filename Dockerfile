FROM debian:bookworm-slim

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential nodejs npm python3 python3-pip python3-venv \
        ripgrep ffmpeg gcc python3-dev libffi-dev git curl jq && \
    rm -rf /var/lib/apt/lists/*

# Clone Hermes Agent
RUN git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /opt/hermes
WORKDIR /opt/hermes

# Install Hermes + deps
RUN pip install --no-cache-dir -e ".[all]" --break-system-packages && \
    pip install --no-cache-dir --break-system-packages "anthropic>=0.86.0" && \
    npm install --prefer-offline --no-audit && \
    npx playwright install --with-deps chromium --only-shell 2>/dev/null || true && \
    npm cache clean --force

# ── Think tag handling (convert <think> to blockquote) ────────────────
COPY patch_pr4558.py /opt/hermes/patch_pr4558.py
RUN python3 /opt/hermes/patch_pr4558.py

# ── Telegram markdown fallback ────────────────────────────────────────
COPY patch_telegram_fallback.py /opt/hermes/patch_telegram_fallback.py
RUN python3 /opt/hermes/patch_telegram_fallback.py

# ── STT language ──────────────────────────────────────────────────────
COPY patch_stt_language.py /opt/hermes/patch_stt_language.py
RUN python3 /opt/hermes/patch_stt_language.py

# ── MiniMax optimization (temperature 1.0/0.95, compression strip) ───
COPY patch_minimax_optimize.py /opt/hermes/patch_minimax_optimize.py
RUN python3 /opt/hermes/patch_minimax_optimize.py

# ── Jina Reader fallback for web_extract ──────────────────────────────
COPY patch_jina_web_extract.py /opt/hermes/patch_jina_web_extract.py
RUN python3 /opt/hermes/patch_jina_web_extract.py

# ── MiniMax native web search ─────────────────────────────────────────
COPY patch_minimax_websearch.py /opt/hermes/patch_minimax_websearch.py
RUN python3 /opt/hermes/patch_minimax_websearch.py

# ── Tool ordering (high-frequency first) ──────────────────────────────
COPY patch_tool_ordering.py /opt/hermes/patch_tool_ordering.py
RUN python3 /opt/hermes/patch_tool_ordering.py

# ── Repetition detection ──────────────────────────────────────────────
COPY patch_repetition_detection.py /opt/hermes/patch_repetition_detection.py
RUN python3 /opt/hermes/patch_repetition_detection.py

# ── MiniMax native media tools (image/speech/video/VLM) ───────────────
COPY minimax_media_tools.py /opt/hermes/minimax_media_tools.py
COPY patch_minimax_media.py /opt/hermes/patch_minimax_media.py
RUN python3 /opt/hermes/patch_minimax_media.py

# ── Web intelligence tools (jina, youtube, reddit, rss) ───────────────
COPY web_intelligence_tools.py /opt/hermes/web_intelligence_tools.py
COPY patch_web_intelligence.py /opt/hermes/patch_web_intelligence.py
RUN python3 /opt/hermes/patch_web_intelligence.py

# ── Dependencies ──────────────────────────────────────────────────────
RUN pip install --no-cache-dir --break-system-packages \
    "mcp[cli]" \
    "youtube-transcript-api" \
    "feedparser"

# Pre-download faster-whisper model
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')" \
    && echo "[whisper] Pre-downloaded 'base' model"

# ── Baked skills ──────────────────────────────────────────────────────
COPY skills/ /opt/hermes/baked-skills/

# ── Customizations ────────────────────────────────────────────────────
COPY supermemory_mcp.py /opt/hermes/supermemory_mcp.py
COPY prefill.json /opt/hermes/prefill.json
COPY mina-config.yaml /opt/hermes/mina-config.yaml
COPY start.sh /opt/hermes/start.sh
RUN chmod +x /opt/hermes/start.sh

ENV HERMES_HOME=/opt/data
VOLUME ["/opt/data"]

ENTRYPOINT ["/opt/hermes/start.sh"]
