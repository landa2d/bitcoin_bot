"""CTO Commands — Personal CTO interface via Telegram.

Routes /cto subcommands for real-time system awareness:
  /cto status  — Docker container status
  /cto db      — Database table counts
  /cto spend   — Agent wallet balances
  /cto logs    — Recent service logs
  /cto git     — Recent commits across repos
  /cto search  — Grep across all repos
  /cto arch    — AI architecture research (async, pushes result via Telegram)

All commands are admin-only (TELEGRAM_OWNER_ID).
"""

import logging
import os
import re
import subprocess
import threading

import docker
import requests
from supabase import create_client, Client

logger = logging.getLogger("cto-commands")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_OWNER_ID = os.getenv("TELEGRAM_OWNER_ID", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")

# Container shortname → docker container_name mapping
_CONTAINER_MAP = {
    "gato": "openclaw-gato",
    "gato_brain": "agentpulse-gato-brain",
    "brain": "agentpulse-gato-brain",
    "analyst": "agentpulse-analyst",
    "newsletter": "agentpulse-newsletter",
    "research": "agentpulse-research",
    "processor": "agentpulse-processor",
    "llm-proxy": "agentpulse-llm-proxy",
    "proxy": "agentpulse-llm-proxy",
    "lab": "agentpulse-lab-data-provider",
    "web": "agentpulse-web",
}

# Repos available on disk
_REPOS = {
    "bitcoin_bot": "/root/bitcoin_bot",
    "lab": "/root/lab",
    "rivalscope": "/root/rivalscope",
}

# Key tables to count (public schema)
_KEY_TABLES = [
    "source_posts",
    "analysis_runs",
    "x_content_candidates",
    "agent_wallets",
    "agent_transactions",
    "conversation_sessions",
    "conversation_messages",
    "embeddings",
    "corpus_users",
    "query_log",
    "llm_call_log",
    "user_usage",
]

# Lazy-init Supabase client
_supabase: Client = None


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL/KEY not configured")
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_admin(user_id: str) -> bool:
    """Only the operator can use CTO commands."""
    return str(user_id) == str(TELEGRAM_OWNER_ID)


def _send_telegram(text: str, chat_id: str = None, parse_mode: str = "Markdown"):
    """Push a message to Telegram via Bot API (for async result delivery)."""
    chat_id = chat_id or TELEGRAM_OWNER_ID
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        logger.warning("Telegram credentials not configured for push notification")
        return
    try:
        if len(text) > 4000:
            text = text[:4000] + "\n\n... (truncated)"
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning(f"Telegram push returned {resp.status_code}: {resp.text[:200]}")
            # Retry without Markdown if parse fails
            if "parse" in resp.text.lower():
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": text},
                    timeout=10,
                )
    except Exception as e:
        logger.error(f"Telegram push failed: {e}")


def _run_cmd(cmd: list, timeout: int = 15, cwd: str = None) -> tuple:
    """Run a subprocess command. Returns (exit_code, stdout, stderr)."""
    logger.info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def _truncate(text: str, limit: int = 3500) -> str:
    """Truncate text to fit Telegram message limits."""
    if len(text) > limit:
        return text[:limit] + "\n\n... (truncated)"
    return text


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

_HELP = """*Personal CTO Commands*

/cto status — Docker containers status
/cto db — Database table counts
/cto spend — Agent wallet balances
/cto logs <service> — Last 20 lines of service logs
/cto git — Recent commits across repos
/cto search <query> — Grep across all repos
/cto arch <question> — AI architecture research"""


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def handle_cto_command(message: str, user_id: str) -> str:
    """Dispatch a /cto command. Returns response string for /chat."""
    if not _is_admin(user_id):
        return "CTO commands are restricted to the operator."

    msg = message.strip()
    parts = msg.split(None, 2)  # ["/cto", "subcommand", "args..."]
    subcmd = parts[1].lower() if len(parts) > 1 else ""
    args_str = parts[2] if len(parts) > 2 else ""

    try:
        if subcmd == "status":
            return _handle_status()
        elif subcmd == "db":
            return _handle_db()
        elif subcmd == "spend":
            return _handle_spend()
        elif subcmd == "logs":
            return _handle_logs(args_str)
        elif subcmd == "git":
            return _handle_git()
        elif subcmd == "search":
            return _handle_search(args_str)
        elif subcmd == "arch":
            return _handle_arch(args_str)
        else:
            return _HELP
    except Exception as e:
        logger.error(f"CTO command failed: {subcmd} - {e}", exc_info=True)
        return f"Command failed: {e}"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _handle_status() -> str:
    """/cto status — Show all Docker containers with status and uptime."""
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
    except Exception as e:
        return f"Docker error: {e}"

    if not containers:
        return "No containers found."

    lines = ["*Docker Containers*\n"]
    for c in sorted(containers, key=lambda x: x.name):
        status = c.status  # running, exited, etc.
        name = c.name
        # Get uptime from attrs
        started = c.attrs.get("State", {}).get("StartedAt", "")[:19] if c.status == "running" else ""
        emoji = "+" if status == "running" else "-"
        line = f"  {emoji} {name}: {status}"
        if started:
            line += f" (since {started})"
        lines.append(line)

    return _truncate("\n".join(lines))


def _handle_db() -> str:
    """/cto db — Query table row counts."""
    sb = _get_supabase()
    lines = ["*Database Table Counts*\n"]

    for table in _KEY_TABLES:
        try:
            res = sb.table(table).select("*", count="exact", head=True).execute()
            count = res.count if res.count is not None else "?"
            lines.append(f"  {table}: {count:,}" if isinstance(count, int) else f"  {table}: {count}")
        except Exception as e:
            lines.append(f"  {table}: error ({e})")

    return "\n".join(lines)


def _handle_spend() -> str:
    """/cto spend — Show wallet balances for all agents."""
    sb = _get_supabase()

    try:
        wallets = sb.table("agent_wallets").select("agent_name, balance_sats").order("agent_name").execute()
    except Exception as e:
        return f"Wallet query failed: {e}"

    if not wallets.data:
        return "No agent wallets found."

    lines = ["*Agent Wallet Balances*\n"]
    total = 0
    for w in wallets.data:
        name = w["agent_name"]
        bal = w.get("balance_sats", 0) or 0
        total += bal
        lines.append(f"  {name}: {bal:,} sats")

    lines.append(f"\n  *Total: {total:,} sats*")
    return "\n".join(lines)


def _handle_logs(args_str: str) -> str:
    """/cto logs <service> — Show last 20 lines of docker logs."""
    service = args_str.strip()
    if not service:
        services = ", ".join(sorted(_CONTAINER_MAP.keys()))
        return f"Usage: /cto logs <service>\nAvailable: {services}"

    # Sanitize input
    if not re.match(r'^[a-zA-Z0-9_-]+$', service):
        return "Invalid service name."

    # Resolve shortname to container name
    container_name = _CONTAINER_MAP.get(service.lower(), service)

    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        logs = container.logs(tail=20, timestamps=False).decode("utf-8", errors="replace")
    except docker.errors.NotFound:
        return f"Container '{container_name}' not found. Try: {', '.join(sorted(_CONTAINER_MAP.keys()))}"
    except Exception as e:
        return f"Docker error: {e}"

    if not logs.strip():
        return f"No recent logs for {service}."

    return _truncate(f"*Last 20 lines: {service}*\n```\n{logs.strip()}\n```")


def _handle_git() -> str:
    """/cto git — Show last 5 commits across repos."""
    lines = ["*Recent Commits*\n"]

    for name, path in _REPOS.items():
        rc, stdout, stderr = _run_cmd(
            ["git", "log", "--oneline", "--no-decorate", "-5"],
            timeout=10,
            cwd=path,
        )
        lines.append(f"*{name}*")
        if rc == 0 and stdout.strip():
            lines.append(f"```\n{stdout.strip()}\n```")
        else:
            lines.append(f"  (error: {stderr.strip()[:100]})")
        lines.append("")

    return _truncate("\n".join(lines))


def _handle_search(args_str: str) -> str:
    """/cto search <query> — Grep across all repos."""
    query = args_str.strip()
    if not query:
        return "Usage: /cto search <query>"

    lines = ["*Search Results*\n"]

    for name, path in _REPOS.items():
        rc, stdout, stderr = _run_cmd(
            ["grep", "-rnl",
             "--include=*.py", "--include=*.js", "--include=*.ts",
             "--include=*.mjs", "--include=*.json", "--include=*.yml",
             "--include=*.md", "--include=*.sh",
             query, path],
            timeout=15,
        )
        if rc == 0 and stdout.strip():
            files = stdout.strip().split("\n")
            lines.append(f"*{name}* ({len(files)} files)")
            for f in files[:10]:
                short = f.replace(path, "")
                lines.append(f"  {short}")
            if len(files) > 10:
                lines.append(f"  ... +{len(files) - 10} more")
        else:
            lines.append(f"*{name}*: no matches")
        lines.append("")

    return _truncate("\n".join(lines))


def _handle_arch(args_str: str) -> str:
    """/cto arch <question> — AI architecture research (async)."""
    question = args_str.strip()
    if not question:
        return "Usage: /cto arch <question>\nExample: /cto arch How does the intent router work?"

    def run():
        try:
            rc, stdout, stderr = _run_cmd(
                ["claude", "--print", "-p", question],
                timeout=300,  # 5 minutes
                cwd="/root/bitcoin_bot",
            )
            if rc == 0 and stdout.strip():
                _send_telegram(f"*CTO Arch*\n\n{_truncate(stdout.strip())}")
            else:
                error = stderr.strip()[:500] if stderr else "No output"
                _send_telegram(f"*CTO Arch failed*\n\n{error}")
        except Exception as e:
            logger.error(f"CTO arch error: {e}", exc_info=True)
            _send_telegram(f"CTO arch error: {e}")

    threading.Thread(target=run, daemon=True).start()
    return f"Researching: _{question}_\n\nI'll push the answer when done."
