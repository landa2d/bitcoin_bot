# AgentPulse Newsletter Agent — Python-only (direct OpenAI API)
# No Node.js/OpenClaw needed — just polls Supabase and calls GPT-4o directly.

FROM python:3.12-slim

# Install procps for health check
RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r openclaw && useradd -r -g openclaw -m -d /home/openclaw openclaw

WORKDIR /home/openclaw

# Install Python dependencies
COPY --chown=openclaw:openclaw requirements.txt /home/openclaw/requirements.txt
RUN pip install --no-cache-dir -r /home/openclaw/requirements.txt

# Copy agent script, schemas, and entrypoint
COPY --chown=openclaw:openclaw newsletter_poller.py /home/openclaw/newsletter_poller.py
COPY --chown=openclaw:openclaw schemas.py /home/openclaw/schemas.py
COPY --chown=openclaw:openclaw entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

# Pre-create directories
RUN mkdir -p /home/openclaw/.openclaw/logs \
             /home/openclaw/.openclaw/workspace/agentpulse/newsletters \
    && chown -R openclaw:openclaw /home/openclaw/.openclaw

# Switch to non-root user
USER openclaw

# Health check — verify the Python process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f newsletter_poller.py || exit 1

ENTRYPOINT ["/home/openclaw/entrypoint.sh"]
