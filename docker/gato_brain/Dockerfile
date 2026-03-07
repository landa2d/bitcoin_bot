# Gato Brain — Conversational intelligence middleware (FastAPI)

FROM python:3.12-slim

# Install procps for healthcheck (pgrep)
RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash openclaw

WORKDIR /home/openclaw

# Install Python dependencies
COPY --chown=openclaw:openclaw requirements.txt /home/openclaw/requirements.txt
RUN pip install --no-cache-dir -r /home/openclaw/requirements.txt

# Copy application
COPY --chown=openclaw:openclaw gato_brain.py /home/openclaw/gato_brain.py
COPY --chown=openclaw:openclaw corpus_probe.py /home/openclaw/corpus_probe.py
COPY --chown=openclaw:openclaw intent_router.py /home/openclaw/intent_router.py

# Copy entrypoint
COPY --chown=openclaw:openclaw entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

# Create directories
RUN mkdir -p /home/openclaw/.openclaw/logs \
    && chown -R openclaw:openclaw /home/openclaw/.openclaw

USER openclaw

EXPOSE 8100

# Health check — hit the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')" || exit 1

ENTRYPOINT ["/home/openclaw/entrypoint.sh"]
