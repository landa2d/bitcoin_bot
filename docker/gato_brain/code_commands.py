"""Code Commands — Telegram interface for Gato Code Engine.

Routes /code, /code-diff, /code-approve, /code-reject, /code-merge, /followup, /repos commands.
Long-running commands (/code, /followup) return an acknowledgment immediately
and push results via Telegram Bot API when complete.
Short commands run synchronously and return output in the /chat response.

Note: /approve and /reject are aliased to /code-approve and /code-reject
because Telegram intercepts bare /approve and /reject in group chats.
/diff is aliased to /code-diff for consistency.

Architecture note: code_session.py runs Claude CLI inside this container.
Node.js + claude CLI are installed in the Dockerfile. Repos and credentials
are mounted as volumes from the host.
"""

import logging
import os
import subprocess
import threading

import requests

logger = logging.getLogger("code-commands")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_OWNER_ID = os.getenv("TELEGRAM_OWNER_ID", "")
CODE_SESSION_PATH = "/home/openclaw/code_session.py"
CODE_SESSION_SECRET = os.getenv("CODE_SESSION_SECRET", "")

# Lock prevents concurrent code sessions (Claude CLI is single-threaded per repo)
_code_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_admin(user_id: str) -> bool:
    """Only the operator can use code commands."""
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
    except Exception as e:
        logger.error(f"Telegram push failed: {e}")


def _run_code_session(*args, timeout: int = 900) -> tuple:
    """Run code_session.py with given args. Returns (exit_code, stdout, stderr)."""
    cmd = ["python3", CODE_SESSION_PATH] + list(args)
    logger.info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd="/home/openclaw",
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def _get_latest_session_id(status_filter: str = None) -> str:
    """Get the most recent session ID (full UUID), optionally filtered by status."""
    try:
        exit_code, stdout, stderr = _run_code_session("list", "--limit", "5", timeout=15)
        if exit_code != 0 or not stdout.strip():
            return ""
        # Parse the table output — lines after header, first column is full UUID
        lines = stdout.strip().split("\n")
        for line in lines[2:]:  # skip header + separator
            parts = line.split()
            if len(parts) >= 2:
                sid = parts[0]
                status = parts[1]
                if status_filter is None or status == status_filter:
                    return sid
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def handle_code_command(message: str, user_id: str) -> str:
    """Dispatch a code command. Returns response string for /chat."""
    if not _is_admin(user_id):
        return "Code commands are restricted to the operator."

    msg = message.strip()
    parts = msg.split(None, 1)
    cmd = parts[0].lower()
    args_str = parts[1] if len(parts) > 1 else ""

    try:
        # Order matters: longer prefixes before shorter to avoid collision
        # (e.g. /code-approve before /code)
        if cmd in ("/code-approve", "/approve"):
            return _handle_approve(args_str)
        elif cmd in ("/code-reject", "/reject"):
            return _handle_reject(args_str)
        elif cmd == "/code-merge":
            return _handle_merge(args_str)
        elif cmd in ("/code-status", "/codestatus"):
            return _handle_status()
        elif cmd in ("/code-list", "/codelist"):
            return _handle_list()
        elif cmd in ("/code-diff", "/diff"):
            return _handle_diff(args_str)
        elif cmd == "/code":
            return _handle_code_start(args_str)
        elif cmd == "/followup":
            return _handle_followup(args_str)
        elif cmd == "/repos":
            return _handle_repos(args_str)
        else:
            return (
                "Unknown code command. Available:\n"
                "/code <repo> <instruction>\n"
                "/code-diff (or /diff)\n"
                "/code-approve (or /approve)\n"
                "/code-reject (or /reject)\n"
                "/code-merge — Merge latest PR\n"
                "/followup <instruction>\n"
                "/repos\n"
                "/code-status"
            )
    except Exception as e:
        logger.error(f"Code command failed: {cmd} — {e}", exc_info=True)
        return f"Command failed: {e}"


# ---------------------------------------------------------------------------
# Long-running handlers (background thread + Telegram push)
# ---------------------------------------------------------------------------

def _handle_code_start(args_str: str) -> str:
    """/code <repo> <instruction> — start a coding session."""
    parts = args_str.split(None, 1)
    if len(parts) < 2:
        return (
            "Usage: /code <repo> <instruction>\n"
            "Example: /code bot Fix the health check timeout\n"
            "Example: /code lab Create a hello world script"
        )

    repo = parts[0]
    instruction = parts[1]

    if not _code_lock.acquire(blocking=False):
        return "A code session is already running. Wait for it to finish, or check /code-status."

    def run():
        try:
            exit_code, stdout, stderr = _run_code_session(
                "start",
                "--repo", repo,
                "--instruction", instruction,
                "--budget", "3.00",
                "--timeout", "15",
                "--secret", CODE_SESSION_SECRET,
            )
            if exit_code == 0:
                _send_telegram(
                    f"*Code session complete*\n\n```\n{stdout[-3000:]}\n```",
                )
            else:
                error_msg = stderr[-1000:] if stderr else stdout[-1000:]
                _send_telegram(f"*Code session failed* (exit {exit_code})\n\n{error_msg}")
        except Exception as e:
            logger.error(f"Code start background error: {e}", exc_info=True)
            _send_telegram(f"Code session error: {e}")
        finally:
            _code_lock.release()

    threading.Thread(target=run, daemon=True).start()
    return f"Starting code session on `{repo}`...\n\nInstruction: {instruction}\n\nI'll push the result when it's done."


def _handle_followup(args_str: str) -> str:
    """/followup <instruction> — continue the latest session."""
    if not args_str.strip():
        return "Usage: /followup <additional instruction>"

    # Check if first word looks like a session ID (UUID prefix)
    parts = args_str.split(None, 1)
    if len(parts) >= 2 and len(parts[0]) >= 8 and "-" in parts[0]:
        session_id = parts[0]
        instruction = parts[1]
    else:
        # Default to latest session in review
        session_id = _get_latest_session_id("review")
        instruction = args_str
        if not session_id:
            return "No active session in review. Start one with /code first."

    if not _code_lock.acquire(blocking=False):
        return "A code session is already running."

    def run():
        try:
            exit_code, stdout, stderr = _run_code_session(
                "followup",
                "--session", session_id,
                "--instruction", instruction,
                "--secret", CODE_SESSION_SECRET,
            )
            if exit_code == 0:
                _send_telegram(f"*Followup complete*\n\n```\n{stdout[-3000:]}\n```")
            else:
                error_msg = stderr[-1000:] if stderr else stdout[-1000:]
                _send_telegram(f"*Followup failed* (exit {exit_code})\n\n{error_msg}")
        except Exception as e:
            logger.error(f"Followup background error: {e}", exc_info=True)
            _send_telegram(f"Followup error: {e}")
        finally:
            _code_lock.release()

    threading.Thread(target=run, daemon=True).start()
    return f"Running followup on session `{session_id[:8]}...`\n\nInstruction: {instruction}"


# ---------------------------------------------------------------------------
# Synchronous handlers (return directly in /chat response)
# ---------------------------------------------------------------------------

def _handle_diff(args_str: str) -> str:
    """/diff [session_id] — show diff for a session (defaults to latest)."""
    session_id = args_str.strip()
    if not session_id:
        session_id = _get_latest_session_id("review")
        if not session_id:
            return "No active session. Start one with /code first."

    exit_code, stdout, stderr = _run_code_session("diff", "--session", session_id, timeout=30)
    if exit_code == 0:
        diff = stdout.strip()
        if not diff:
            return "No diff available for this session."
        if len(diff) > 3500:
            return f"```\n{diff[:3500]}\n```\n\n... (truncated — full diff in repo)"
        return f"```\n{diff}\n```"
    return f"Error: {stderr.strip() or stdout.strip()}"


def _handle_approve(args_str: str) -> str:
    """/approve [session_id] — commit, push, create PR."""
    session_id = args_str.strip()
    if not session_id:
        session_id = _get_latest_session_id("review")
        if not session_id:
            return "No session in review to approve."

    exit_code, stdout, stderr = _run_code_session("approve", "--session", session_id, timeout=60)
    if exit_code == 0:
        return f"Approved.\n\n{stdout.strip()}"
    return f"Approve failed: {stderr.strip() or stdout.strip()}"


def _handle_reject(args_str: str) -> str:
    """/reject [session_id] — discard changes, delete branch."""
    session_id = args_str.strip()
    if not session_id:
        session_id = _get_latest_session_id("review") or _get_latest_session_id("error")
        if not session_id:
            return "No session to reject."

    exit_code, stdout, stderr = _run_code_session("reject", "--session", session_id, timeout=30)
    if exit_code == 0:
        return f"Rejected.\n\n{stdout.strip()}"
    return f"Reject failed: {stderr.strip() or stdout.strip()}"


def _handle_merge(args_str: str) -> str:
    """/code-merge — merge the GitHub PR from the latest approved session."""
    from code_session import db_query, db_update, get_env_var

    # Find the latest session that has a PR
    try:
        sessions = db_query(
            "code_sessions",
            filters="pr_number=not.is.null",
            order="created_at.desc",
            limit=1,
        )
    except Exception as e:
        return f"Failed to query sessions: {e}"

    if not sessions:
        return "No session with a PR found."

    session = sessions[0]
    pr_number = session.get("pr_number")
    github_remote = session.get("github_remote")

    if not pr_number or not github_remote:
        return "Latest session has no GitHub PR to merge."

    github_token = os.environ.get("GITHUB_TOKEN") or get_env_var("GITHUB_TOKEN")
    if not github_token:
        return "GITHUB_TOKEN not configured. Cannot merge."

    # Merge via GitHub API
    try:
        resp = requests.put(
            f"https://api.github.com/repos/{github_remote}/pulls/{pr_number}/merge",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"merge_method": "merge"},
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            # Update session status to merged
            try:
                db_update("code_sessions", f"id=eq.{session['id']}", {"status": "merged"})
            except Exception as e:
                logger.warning(f"Failed to update session status to merged: {e}")

            # Delete the remote branch to keep repo clean
            branch_name = session.get("branch_name")
            if branch_name:
                try:
                    requests.delete(
                        f"https://api.github.com/repos/{github_remote}/git/refs/heads/{branch_name}",
                        headers={
                            "Authorization": f"Bearer {github_token}",
                            "Accept": "application/vnd.github.v3+json",
                        },
                        timeout=10,
                    )
                except Exception:
                    pass  # branch cleanup is best-effort

            return (
                f"PR #{pr_number} merged successfully\n\n"
                f"Repo: {github_remote}\n"
                f"SHA: {data.get('sha', 'unknown')[:8]}\n"
                f"Message: {data.get('message', 'Merged')}"
            )
        elif resp.status_code == 405:
            return f"PR #{pr_number} cannot be merged (merge conflict or branch protection rules)"
        elif resp.status_code == 404:
            return f"PR #{pr_number} not found. It may have been merged or closed already."
        elif resp.status_code == 422:
            error_msg = resp.json().get("message", "Unknown error")
            return f"PR #{pr_number} merge failed: {error_msg}"
        else:
            return f"Merge failed (HTTP {resp.status_code}): {resp.text[:200]}"

    except requests.Timeout:
        return "Merge request timed out. Try again or merge on GitHub."
    except Exception as e:
        return f"Merge error: {e}"


def _handle_repos(args_str: str) -> str:
    """/repos — list available repos."""
    subcmd = args_str.strip()
    if not subcmd or subcmd == "list":
        exit_code, stdout, stderr = _run_code_session("repos", "list", timeout=15)
    else:
        exit_code, stdout, stderr = _run_code_session("repos", *subcmd.split(), timeout=15)

    if exit_code == 0:
        return stdout.strip() or "No repos found."
    return f"Error: {stderr.strip() or stdout.strip()}"


def _handle_status() -> str:
    """/code-status — show current/recent session status."""
    exit_code, stdout, stderr = _run_code_session("status", timeout=15)
    if exit_code == 0:
        return stdout.strip() or "No sessions found."
    return f"Error: {stderr.strip() or stdout.strip()}"


def _handle_list() -> str:
    """/code-list — list recent sessions."""
    exit_code, stdout, stderr = _run_code_session("list", timeout=15)
    if exit_code == 0:
        return f"```\n{stdout.strip()}\n```" if stdout.strip() else "No sessions found."
    return f"Error: {stderr.strip() or stdout.strip()}"
