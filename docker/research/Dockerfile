# AgentPulse Research Agent — Conviction-Driven Thesis Builder
# Python-only container using Anthropic Claude

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

# Copy research agent, schemas, and system prompt
COPY --chown=openclaw:openclaw research_agent.py /home/openclaw/research_agent.py
COPY --chown=openclaw:openclaw schemas.py /home/openclaw/schemas.py
COPY --chown=openclaw:openclaw IDENTITY.md /home/openclaw/IDENTITY.md

# Copy entrypoint
COPY --chown=openclaw:openclaw entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

# Create directories
RUN mkdir -p /home/openclaw/.openclaw/logs \
    && chown -R openclaw:openclaw /home/openclaw/.openclaw

USER openclaw

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f research_agent.py || exit 1

ENTRYPOINT ["/home/openclaw/entrypoint.sh"]
