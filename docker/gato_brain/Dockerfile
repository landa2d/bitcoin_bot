# Gato Brain — Conversational intelligence middleware (FastAPI)

FROM python:3.12-slim

# Install system deps: procps (healthcheck), git (code engine), Node.js (Claude CLI)
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps git curl ca-certificates gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (kept for path compat — container runs as root for code ops)
RUN useradd -m -s /bin/bash openclaw

WORKDIR /home/openclaw

# Install Python dependencies
COPY requirements.txt /home/openclaw/requirements.txt
RUN pip install --no-cache-dir -r /home/openclaw/requirements.txt

# Copy application
COPY gato_brain.py /home/openclaw/gato_brain.py
COPY corpus_probe.py /home/openclaw/corpus_probe.py
COPY intent_router.py /home/openclaw/intent_router.py
COPY query_templates.py /home/openclaw/query_templates.py
COPY web_search.py /home/openclaw/web_search.py
COPY embed_pipeline.py /home/openclaw/embed_pipeline.py

# Copy code engine
COPY code_commands.py /home/openclaw/code_commands.py
COPY code_session.py /home/openclaw/code_session.py
COPY repo_resolver.py /home/openclaw/repo_resolver.py

# Copy CTO commands
COPY cto_commands.py /home/openclaw/cto_commands.py

# Copy entrypoint
COPY entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

# Create directories
RUN mkdir -p /home/openclaw/.openclaw/logs \
    && mkdir -p /root/code-workspaces/.sessions

EXPOSE 8100

# Health check — hit the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')" || exit 1

ENTRYPOINT ["/home/openclaw/entrypoint.sh"]
