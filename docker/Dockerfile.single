# OpenClaw Bitcoin Agent - Secure Dockerfile
# This container runs an autonomous AI agent in an isolated environment

FROM node:22-slim

# Install system dependencies including Python for AgentPulse
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    gettext-base \
    jq \
    python3 \
    python3-pip \
    python3-venv \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Install pnpm globally
RUN npm install -g pnpm

# Create non-root user for security
RUN groupadd -r openclaw && useradd -r -g openclaw -m -d /home/openclaw openclaw

# Set working directory
WORKDIR /app

# Clone OpenClaw repository
RUN git clone https://github.com/openclaw/openclaw.git . \
    && chown -R openclaw:openclaw /app

# Switch to non-root user
USER openclaw

# Install dependencies
RUN pnpm install

# Build the application
RUN pnpm run build

# Create directories for persistent data and skills
RUN mkdir -p /home/openclaw/.openclaw /home/openclaw/skills

# Volume mount points for persistence
VOLUME ["/home/openclaw/.openclaw", "/home/openclaw/skills"]

# Environment variables (to be overridden by docker-compose)
ENV NODE_ENV=production
ENV OPENCLAW_DATA_DIR=/home/openclaw/.openclaw
ENV OPENCLAW_SKILLS_DIR=/home/openclaw/skills

# Copy entrypoint script
COPY --chown=openclaw:openclaw entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

# Copy security supervisor preflight script
COPY --chown=openclaw:openclaw preflight.sh /home/openclaw/preflight.sh
RUN chmod +x /home/openclaw/preflight.sh

# Copy Moltbook post-by-write queue watcher
COPY --chown=openclaw:openclaw moltbook_post_watcher.sh /home/openclaw/moltbook_post_watcher.sh
RUN chmod +x /home/openclaw/moltbook_post_watcher.sh

# Install AgentPulse Python dependencies
COPY --chown=openclaw:openclaw requirements-agentpulse.txt /home/openclaw/requirements-agentpulse.txt
RUN pip3 install --break-system-packages -r /home/openclaw/requirements-agentpulse.txt

# Copy AgentPulse processor
COPY --chown=openclaw:openclaw agentpulse_processor.py /home/openclaw/agentpulse_processor.py
RUN chmod +x /home/openclaw/agentpulse_processor.py

# Copy AgentPulse cron scripts
COPY --chown=openclaw:openclaw agentpulse_cron.sh /home/openclaw/agentpulse_cron.sh
RUN chmod +x /home/openclaw/agentpulse_cron.sh
COPY agentpulse_crontab /home/openclaw/agentpulse_crontab

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD node -e "console.log('healthy')" || exit 1

# Set entrypoint
ENTRYPOINT ["/home/openclaw/entrypoint.sh"]
