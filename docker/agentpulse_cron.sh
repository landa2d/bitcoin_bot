#!/bin/bash
# AgentPulse Cron Wrapper
# This script is called by cron to run AgentPulse tasks

set -e

# Load environment variables
source /home/openclaw/.env

# Log file
LOG_FILE="/home/openclaw/.openclaw/logs/agentpulse_cron.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Get task from argument
TASK="${1:-scrape}"

log "Starting AgentPulse task: $TASK"

# Run the processor
cd /home/openclaw
python3 /home/openclaw/agentpulse_processor.py --task "$TASK" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "Task $TASK completed successfully"
else
    log "Task $TASK failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
