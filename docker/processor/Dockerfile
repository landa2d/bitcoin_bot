# AgentPulse Processor — Background scraper & task orchestrator
# Lightweight Python-only container (no Node.js/OpenClaw needed)

FROM python:3.12-slim

# Create non-root user for security
RUN groupadd -r openclaw && useradd -r -g openclaw -m -d /home/openclaw openclaw

WORKDIR /home/openclaw

# Install Python dependencies
COPY --chown=openclaw:openclaw requirements.txt /home/openclaw/requirements.txt
RUN pip install --no-cache-dir -r /home/openclaw/requirements.txt

# Copy processor script
COPY --chown=openclaw:openclaw agentpulse_processor.py /home/openclaw/agentpulse_processor.py
RUN chmod +x /home/openclaw/agentpulse_processor.py

# Switch to non-root user
USER openclaw

# Workspace dirs are created by the shared volume mount and/or the processor script itself
CMD ["python3", "/home/openclaw/agentpulse_processor.py", "--task", "watch"]
