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
    npm install --prefer-offline --no-audit && \
    npx playwright install --with-deps chromium --only-shell 2>/dev/null || true && \
    npm cache clean --force

# Patch: strip <think> tags from streamed output (MiniMax M2.7 emits these)
COPY patch_pr4558.py /opt/hermes/patch_pr4558.py
RUN python3 /opt/hermes/patch_pr4558.py

# Patch: strip markdown on Telegram fallback
COPY patch_telegram_fallback.py /opt/hermes/patch_telegram_fallback.py
RUN python3 /opt/hermes/patch_telegram_fallback.py

# Patch: force STT language for faster-whisper (prevents misdetection)
COPY patch_stt_language.py /opt/hermes/patch_stt_language.py
RUN python3 /opt/hermes/patch_stt_language.py

# Our config + entrypoint
COPY mina-config.yaml /opt/hermes/mina-config.yaml
COPY start.sh /opt/hermes/start.sh
RUN chmod +x /opt/hermes/start.sh

ENV HERMES_HOME=/opt/data
VOLUME ["/opt/data"]

ENTRYPOINT ["/opt/hermes/start.sh"]
