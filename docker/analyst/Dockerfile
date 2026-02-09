# OpenClaw Analyst — Headless analysis worker
# OpenClaw + Python for analysis tasks, no Telegram

FROM node:22-slim

# Install system dependencies including Python for analysis
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    gettext-base \
    jq \
    procps \
    python3 \
    python3-pip \
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

# Install Node.js dependencies
RUN pnpm install

# Build OpenClaw
RUN pnpm run build

# Create directories for persistent data and skills
RUN mkdir -p /home/openclaw/.openclaw /home/openclaw/skills

# Volume mount points for persistence
VOLUME ["/home/openclaw/.openclaw", "/home/openclaw/skills"]

# Environment variables (overridden by docker-compose)
ENV NODE_ENV=production
ENV OPENCLAW_DATA_DIR=/home/openclaw/.openclaw
ENV OPENCLAW_SKILLS_DIR=/home/openclaw/skills

# Install Python dependencies
COPY --chown=openclaw:openclaw requirements.txt /home/openclaw/requirements.txt
RUN pip3 install --break-system-packages -r /home/openclaw/requirements.txt

# Copy analyst poller
COPY --chown=openclaw:openclaw analyst_poller.py /home/openclaw/analyst_poller.py

# Copy entrypoint
COPY --chown=openclaw:openclaw entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD node -e "console.log('healthy')" || exit 1

ENTRYPOINT ["/home/openclaw/entrypoint.sh"]
