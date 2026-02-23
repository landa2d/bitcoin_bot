# AgentPulse Analyst — Direct OpenAI intelligence agent
# Python-only container, no OpenClaw dependency

FROM python:3.12-slim

# Install procps for healthcheck (pgrep)
RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash openclaw

# Set working directory
WORKDIR /home/openclaw

# Install Python dependencies
COPY --chown=openclaw:openclaw requirements.txt /home/openclaw/requirements.txt
RUN pip install --no-cache-dir -r /home/openclaw/requirements.txt

# Copy analyst poller and schemas
COPY --chown=openclaw:openclaw analyst_poller.py /home/openclaw/analyst_poller.py
COPY --chown=openclaw:openclaw schemas.py /home/openclaw/schemas.py

# Copy entrypoint
COPY --chown=openclaw:openclaw entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

# Create directories and ensure correct ownership
RUN mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/analysis \
             /home/openclaw/.openclaw/logs \
    && chown -R openclaw:openclaw /home/openclaw/.openclaw

USER openclaw

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f analyst_poller.py || exit 1

ENTRYPOINT ["/home/openclaw/entrypoint.sh"]
