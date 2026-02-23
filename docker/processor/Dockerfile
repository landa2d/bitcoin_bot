# AgentPulse Processor — Background scraper & task orchestrator
# Lightweight Python-only container (no Node.js/OpenClaw needed)

FROM python:3.12-slim

# Create non-root user for security
RUN groupadd -r openclaw && useradd -r -g openclaw -m -d /home/openclaw openclaw

WORKDIR /home/openclaw

# Install procps for pgrep (used in health check)
RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY --chown=openclaw:openclaw requirements.txt /home/openclaw/requirements.txt
RUN pip install --no-cache-dir -r /home/openclaw/requirements.txt

# Copy processor script
COPY --chown=openclaw:openclaw agentpulse_processor.py /home/openclaw/agentpulse_processor.py
RUN chmod +x /home/openclaw/agentpulse_processor.py

# Pre-create directories that the processor needs to write to.
# Volume mounts may create parent dirs as root, so we ensure openclaw owns them.
RUN mkdir -p /home/openclaw/.openclaw/logs \
             /home/openclaw/.openclaw/workspace/agentpulse/queue/responses \
             /home/openclaw/.openclaw/workspace/agentpulse/opportunities \
             /home/openclaw/.openclaw/workspace/agentpulse/cache \
    && chown -R openclaw:openclaw /home/openclaw/.openclaw

# Switch to non-root user
USER openclaw
CMD ["python3", "/home/openclaw/agentpulse_processor.py", "--task", "watch"]
