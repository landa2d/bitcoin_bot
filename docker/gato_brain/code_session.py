#!/usr/bin/env python3
"""Gato Code Engine — CLI for managing Claude Code sessions.

Manages coding sessions: receives a natural language instruction, runs Claude Code
headless against a target repo, captures the diff, and can commit/push/create a
GitHub PR on command.

Usage:
    python3 code_session.py start --repo <alias> --instruction "..." [--budget 3.00] [--timeout 15] [--max-turns 20]
    python3 code_session.py diff --session <id>
    python3 code_session.py approve --session <id>
    python3 code_session.py reject --session <id>
    python3 code_session.py followup --session <id> --instruction "..."
    python3 code_session.py status
    python3 code_session.py list
    python3 code_session.py repos list
    python3 code_session.py repos add --alias myproject --github owner/repo
    python3 code_session.py repos remove --alias myproject
    python3 code_session.py repos resolve "bitcoin"
"""

import argparse
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ENV_PATH = os.getenv("CODE_ENV_PATH", "/home/openclaw/.openclaw/config/.env")
# repo_registry.json no longer used — repos resolved via Supabase code_repos table
# REGISTRY_PATH kept for backward compat reference only
REGISTRY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "repo_registry.json")
SATS_PER_USD = 1000
WORKSPACES_DIR = "/root/code-workspaces"
SESSION_SUMMARY_FILE = ".code-session-summary.txt"

# ---------------------------------------------------------------------------
# Env parsing (same pattern as wallet.py / notify.py)
# ---------------------------------------------------------------------------
_env_cache = None


def parse_env(path: str = ENV_PATH) -> dict:
    global _env_cache
    if _env_cache is not None:
        return _env_cache
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            env[key] = value
    _env_cache = env
    return env


def get_env_var(name: str, default: str = "") -> str:
    env = parse_env()
    return env.get(name, default)


# ---------------------------------------------------------------------------
# Supabase helpers (PostgREST)
# ---------------------------------------------------------------------------
_supabase_available = None  # None = unknown, True/False = tested


def supabase_headers() -> dict:
    key = get_env_var("SUPABASE_SERVICE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def supabase_url(table: str) -> str:
    base = get_env_var("SUPABASE_URL")
    return f"{base}/rest/v1/{table}"


def check_supabase() -> bool:
    """Check if Supabase code_sessions table is available."""
    global _supabase_available
    if _supabase_available is not None:
        return _supabase_available
    try:
        resp = requests.get(
            supabase_url("code_sessions") + "?limit=1",
            headers=supabase_headers(),
            timeout=5,
        )
        _supabase_available = resp.status_code == 200
    except Exception:
        _supabase_available = False
    if not _supabase_available:
        print("Note: Supabase code_sessions table not found. Using local storage.", file=sys.stderr)
        print("Run setup.sql in Supabase SQL editor to enable remote persistence.", file=sys.stderr)
    return _supabase_available


# ---------------------------------------------------------------------------
# Local JSON storage (fallback when Supabase table doesn't exist)
# ---------------------------------------------------------------------------
LOCAL_SESSIONS_DIR = os.getenv("CODE_SESSIONS_DIR", "/root/code-workspaces/.sessions")


def _local_path(session_id: str) -> str:
    os.makedirs(LOCAL_SESSIONS_DIR, exist_ok=True)
    return os.path.join(LOCAL_SESSIONS_DIR, f"{session_id}.json")


def _local_save(data: dict):
    with open(_local_path(data["id"]), "w") as f:
        json.dump(data, f, indent=2, default=str)


def _local_load(session_id: str) -> dict | None:
    path = _local_path(session_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _local_list(limit: int = 10) -> list:
    os.makedirs(LOCAL_SESSIONS_DIR, exist_ok=True)
    sessions = []
    for fname in sorted(os.listdir(LOCAL_SESSIONS_DIR), reverse=True):
        if fname.endswith(".json"):
            with open(os.path.join(LOCAL_SESSIONS_DIR, fname)) as f:
                sessions.append(json.load(f))
    return sessions[:limit]


# ---------------------------------------------------------------------------
# Unified DB layer: Supabase when available, local JSON as fallback
# ---------------------------------------------------------------------------
def db_insert(table: str, data: dict) -> dict:
    if table == "code_sessions" and not check_supabase():
        # Generate UUID locally
        import uuid
        if "id" not in data:
            data["id"] = str(uuid.uuid4())
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        data["started_at"] = data.get("started_at", data["created_at"])
        _local_save(data)
        return data

    resp = requests.post(supabase_url(table), headers=supabase_headers(), json=data)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"DB insert failed ({resp.status_code}): {resp.text}")
    rows = resp.json()
    result = rows[0] if isinstance(rows, list) and rows else rows
    # Also save locally for consistency
    if table == "code_sessions":
        _local_save(result)
    return result


def db_update(table: str, filters: str, data: dict) -> dict:
    if table == "code_sessions" and not check_supabase():
        # Parse session ID from filters like "id=eq.xxx"
        for part in filters.split("&"):
            if part.startswith("id=eq."):
                sid = part.split("eq.", 1)[1]
                existing = _local_load(sid)
                if existing:
                    existing.update(data)
                    _local_save(existing)
                    return existing
        return {}

    resp = requests.patch(
        supabase_url(table) + f"?{filters}",
        headers=supabase_headers(),
        json=data,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"DB update failed ({resp.status_code}): {resp.text}")
    try:
        rows = resp.json()
        result = rows[0] if isinstance(rows, list) and rows else rows
        if table == "code_sessions" and result and "id" in result:
            _local_save(result)
        return result
    except Exception:
        return {}


def db_query(table: str, filters: str = "", order: str = "created_at.desc", limit: int = 10) -> list:
    if table == "code_sessions" and not check_supabase():
        sessions = _local_list(limit=100)
        # Apply filters
        if filters:
            for f in filters.split("&"):
                if "=eq." in f:
                    key, val = f.split("=eq.", 1)
                    sessions = [s for s in sessions if str(s.get(key)) == val]
                elif "=in." in f:
                    key, vals = f.split("=in.", 1)
                    vals = vals.strip("()").split(",")
                    sessions = [s for s in sessions if s.get(key) in vals]
        # Sort
        if "desc" in order:
            field = order.replace(".desc", "")
            sessions.sort(key=lambda s: s.get(field, ""), reverse=True)
        return sessions[:limit]

    url = supabase_url(table) + f"?order={order}&limit={limit}"
    if filters:
        url += f"&{filters}"
    resp = requests.get(url, headers=supabase_headers())
    if resp.status_code != 200:
        raise RuntimeError(f"DB query failed ({resp.status_code}): {resp.text}")
    return resp.json()


# ---------------------------------------------------------------------------
# Repo resolution (via Supabase code_repos table)
# ---------------------------------------------------------------------------
from repo_resolver import resolve_repo as _resolve_repo_db, list_repos, add_repo, remove_repo


def resolve_repo(repo_ref: str) -> dict:
    """Resolve a repo alias, fuzzy name, or GitHub URL to a repo config dict.

    Uses the Supabase code_repos table via repo_resolver module.
    """
    result = _resolve_repo_db(repo_ref)

    if result.repo:
        repo = result.repo
        return {
            "local_path": repo.get("local_path"),
            "github_remote": repo.get("github_remote"),
            "default_branch": repo.get("default_branch", "main"),
            "alias": repo.get("alias"),
            "is_adhoc": repo.get("local_path") is None,
            "_resolve_result": result,
        }

    if result.fuzzy_matches:
        print(f"Ambiguous match for '{repo_ref}'. Did you mean:", file=sys.stderr)
        for m in result.fuzzy_matches:
            print(f"  - {m['alias']} (score: {m['score']}) {m.get('description', '')}", file=sys.stderr)
        sys.exit(1)

    print(f"Error: Unknown repo '{repo_ref}'.", file=sys.stderr)
    if result.available:
        print(f"Available repos: {', '.join(result.available)}", file=sys.stderr)
    sys.exit(1)


def _run_claude_as_openclaw(cmd: str, timeout_seconds: int, output_log: str) -> subprocess.CompletedProcess:
    """Run a claude CLI command as the openclaw user (non-root).

    Claude CLI refuses --dangerously-skip-permissions when run as root.
    The container stays root for everything else; only this subprocess
    drops to openclaw.
    """
    result = subprocess.run(
        ["su", "-s", "/bin/bash", "openclaw", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env={**os.environ, "HOME": "/home/openclaw"},
    )
    with open(output_log, "w") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\n--- STDERR ---\n")
            f.write(result.stderr)
    return result


def _chown_to_openclaw(path: str):
    """Give openclaw ownership so Claude CLI can read/write."""
    subprocess.run(["chown", "-R", "openclaw:openclaw", path], check=False)


def ensure_repo_exists(repo: dict) -> str:
    """Ensure repo exists locally. Clone if needed. Return local path."""
    path = repo.get("local_path") or repo["local_path"]

    # If local_path is None, compute a default and clone
    if not path:
        if repo.get("github_remote"):
            repo_name = repo["github_remote"].split("/")[-1]
            path = os.path.join(WORKSPACES_DIR, repo_name)
            repo["local_path"] = path
        else:
            print(f"Error: Repo has no local_path and no github_remote", file=sys.stderr)
            sys.exit(1)

    if os.path.isdir(path):
        return path

    if repo.get("github_remote"):
        token = get_env_var("GITHUB_TOKEN")
        remote = repo["github_remote"]
        clone_url = f"https://{token}@github.com/{remote}.git" if token else f"https://github.com/{remote}.git"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print(f"Cloning {remote} to {path}...")
        subprocess.run(["git", "clone", clone_url, path], check=True)
        # Give openclaw ownership so Claude CLI can write
        _chown_to_openclaw(path)
        # Update code_repos table with the local_path
        try:
            from repo_resolver import _update_repo
            resolve_result = repo.get("_resolve_result")
            if resolve_result and resolve_result.repo and resolve_result.repo.get("id"):
                _update_repo(resolve_result.repo["id"], {"local_path": path})
        except Exception:
            pass
        return path

    print(f"Error: Repo path does not exist: {path}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def git(repo_path: str, *args, check: bool = True, capture: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path] + list(args),
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip() if capture else ""


def is_repo_clean(repo_path: str) -> bool:
    status = git(repo_path, "status", "--porcelain")
    return len(status) == 0


def current_branch(repo_path: str) -> str:
    return git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len]


def make_branch_name(instruction: str) -> str:
    ts = hex(int(time.time()) % 0xFFFF)[2:]
    return f"code/{slugify(instruction)}-{ts}"


# ---------------------------------------------------------------------------
# Wallet helpers (reuse proxy wallet pattern)
# ---------------------------------------------------------------------------
def create_wallet(session_short_id: str, budget_usd: float) -> tuple[str, str]:
    """Create a proxy wallet for cost tracking. Returns (agent_name, api_key)."""
    agent_name = f"code_{session_short_id}"
    budget_sats = int(budget_usd * SATS_PER_USD)
    api_key = f"ap_code_{session_short_id}_{secrets.token_hex(8)}"

    try:
        import bcrypt
        key_hash = bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        # Fallback: store plaintext hash marker (wallet still works for tracking)
        import hashlib
        key_hash = "sha256:" + hashlib.sha256(api_key.encode()).hexdigest()

    # Insert agent_registry
    try:
        db_insert("agent_registry", {
            "agent_name": agent_name,
            "agent_type": "internal",
            "api_key_hash": key_hash,
            "access_tier": "internal",
            "allowed_models": ["deepseek-chat", "gpt-4o-mini"],
            "rate_limit_rpm": 30,
            "is_active": True,
            "metadata": {"source": "gato-code", "session": session_short_id},
        })
    except Exception as e:
        print(f"Warning: Failed to create agent_registry entry: {e}", file=sys.stderr)

    # Insert wallet
    try:
        db_insert("agent_wallets_v2", {
            "agent_name": agent_name,
            "balance_sats": budget_sats,
            "balance_usd_cents": int(budget_usd * 100),
            "total_deposited_sats": budget_sats,
            "total_deposited_usd_cents": int(budget_usd * 100),
            "total_spent_sats": 0,
            "total_spent_usd_cents": 0,
            "allow_negative": False,
        })
    except Exception as e:
        print(f"Warning: Failed to create wallet: {e}", file=sys.stderr)

    return agent_name, api_key


def teardown_wallet(agent_name: str) -> int:
    """Deactivate wallet and return total spent sats."""
    cost_sats = 0
    try:
        rows = db_query("agent_wallets_v2", f"agent_name=eq.{agent_name}", limit=1)
        if rows:
            cost_sats = rows[0].get("total_spent_sats", 0)
    except Exception:
        pass

    try:
        db_update("agent_registry", f"agent_name=eq.{agent_name}", {"is_active": False})
    except Exception:
        pass

    return cost_sats


# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------
def notify_telegram(message: str):
    """Send a Telegram notification to the owner."""
    token = get_env_var("TELEGRAM_BOT_TOKEN")
    chat_id = get_env_var("TELEGRAM_OWNER_ID")
    if not token or not chat_id:
        print("Warning: Telegram credentials not configured", file=sys.stderr)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        print(f"Warning: Telegram notification failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# GitHub PR creation (REST API)
# ---------------------------------------------------------------------------
def create_github_pr(remote: str, branch: str, base: str, title: str, body: str) -> dict | None:
    """Create a GitHub PR via REST API. Returns {url, number} or None."""
    token = get_env_var("GITHUB_TOKEN")
    if not token:
        print("Warning: GITHUB_TOKEN not set, skipping PR creation", file=sys.stderr)
        return None

    resp = requests.post(
        f"https://api.github.com/repos/{remote}/pulls",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        json={
            "title": title,
            "head": branch,
            "base": base,
            "body": body,
        },
        timeout=30,
    )
    if resp.status_code in (200, 201):
        data = resp.json()
        return {"url": data["html_url"], "number": data["number"]}
    else:
        print(f"Warning: PR creation failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Auth placeholder
# ---------------------------------------------------------------------------
def verify_caller(shared_secret: str = None) -> bool:
    """Verify the caller by comparing the shared secret against CODE_SESSION_SECRET."""
    import hmac
    expected = os.environ.get("CODE_SESSION_SECRET") or get_env_var("CODE_SESSION_SECRET")
    if not expected:
        # No secret configured — fail closed
        return False
    if not shared_secret:
        return False
    return hmac.compare_digest(expected, shared_secret)


# ---------------------------------------------------------------------------
# Conventional commit prefix
# ---------------------------------------------------------------------------
def infer_commit_prefix(instruction: str) -> str:
    instruction_lower = instruction.lower()
    if any(w in instruction_lower for w in ["fix", "bug", "patch", "repair"]):
        return "fix"
    if any(w in instruction_lower for w in ["refactor", "clean", "reorganize"]):
        return "refactor"
    if any(w in instruction_lower for w in ["test", "spec"]):
        return "test"
    if any(w in instruction_lower for w in ["doc", "readme", "comment"]):
        return "docs"
    return "feat"


# ---------------------------------------------------------------------------
# Setup command
# ---------------------------------------------------------------------------
def cmd_setup(args):
    """Print setup instructions and verify connectivity."""
    setup_sql = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup.sql")
    print("=== Gato Code Engine Setup ===\n")

    if check_supabase():
        print("Supabase: connected (code_sessions table exists)")
    else:
        print("Supabase: code_sessions table NOT found")
        print(f"\nRun this SQL in your Supabase SQL Editor:")
        print(f"  File: {setup_sql}\n")
        if os.path.exists(setup_sql):
            with open(setup_sql) as f:
                print(f.read())

    print("\nLocal storage:", LOCAL_SESSIONS_DIR)
    print("Sessions will use local JSON files as fallback.")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_start(args):
    """Start a coding session."""
    if not verify_caller(shared_secret=getattr(args, 'secret', None)):
        print("Error: Unauthorized caller", file=sys.stderr)
        sys.exit(1)

    # Resolve repo
    repo = resolve_repo(args.repo)
    repo_path = ensure_repo_exists(repo)

    # Safety: dirty repo check
    if not is_repo_clean(repo_path):
        print(f"Error: Repo has uncommitted changes at {repo_path}", file=sys.stderr)
        print("Commit or stash changes before starting a session.", file=sys.stderr)
        sys.exit(1)

    # Safety: one active session per repo
    try:
        active = db_query(
            "code_sessions",
            f"repo_path=eq.{repo_path}&status=in.(running,review)",
            limit=1,
        )
        if active:
            sid = active[0]["id"]
            status = active[0]["status"]
            print(f"Error: Active session exists for this repo (id={sid[:8]}..., status={status})", file=sys.stderr)
            print("Approve, reject, or wait for the current session to finish.", file=sys.stderr)
            sys.exit(1)
    except Exception:
        pass  # Table may not exist yet, proceed

    # Safety: branch protection
    cur = current_branch(repo_path)
    default_br = repo["default_branch"]
    if cur != default_br:
        print(f"Warning: Repo not on {default_br} (currently on {cur}). Switching...", file=sys.stderr)
        git(repo_path, "checkout", default_br)

    # Create branch
    branch = make_branch_name(args.instruction)
    git(repo_path, "checkout", "-b", branch)
    print(f"Created branch: {branch}")

    # Create wallet
    short_id = secrets.token_hex(4)
    wallet_name, api_key = create_wallet(short_id, args.budget)

    # Insert session
    session = db_insert("code_sessions", {
        "status": "running",
        "repo_alias": repo["alias"],
        "repo_path": repo_path,
        "github_remote": repo.get("github_remote"),
        "branch_name": branch,
        "default_branch": default_br,
        "instruction": args.instruction,
        "wallet_agent_name": wallet_name,
        "max_turns": args.max_turns,
        "timeout_minutes": args.timeout,
        "budget_usd": args.budget,
    })
    session_id = session["id"]
    print(f"session_id: {session_id}")

    # Build Claude Code prompt
    prompt = f"""{args.instruction}

RULES:
- You are working in: {repo_path} on branch: {branch}
- Make the requested changes to the codebase.
- Run tests if a test suite exists.
- Do NOT commit. Do NOT push. Leave changes unstaged or staged.
- Write a brief summary (what you changed and why) to {SESSION_SUMMARY_FILE}
- If you cannot complete the task, explain what went wrong in {SESSION_SUMMARY_FILE}"""

    # Write prompt to temp file (avoids shell escaping issues with instruction text)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, dir='/tmp') as f:
        f.write(prompt)
        prompt_file = f.name
    os.chmod(prompt_file, 0o644)  # readable by openclaw

    # Ensure openclaw can write to the repo
    _chown_to_openclaw(repo_path)

    # Run Claude Code headless as openclaw (non-root)
    timeout_seconds = args.timeout * 60
    claude_cmd = (
        f"cd {shlex.quote(repo_path)} && "
        f"claude --dangerously-skip-permissions --print "
        f"--max-budget-usd {args.budget} "
        f"\"$(cat {shlex.quote(prompt_file)})\""
    )

    # Save output log
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    output_log = os.path.join(log_dir, f"{session_id}.log")

    print(f"Running Claude Code (timeout={args.timeout}m, budget=${args.budget})...")
    try:
        result = _run_claude_as_openclaw(claude_cmd, timeout_seconds, output_log)
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        print("Claude Code timed out")
        try:
            os.remove(prompt_file)
        except OSError:
            pass
        db_update("code_sessions", f"id=eq.{session_id}", {
            "status": "timeout",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "claude_output_path": output_log,
        })
        # Return to default branch
        git(repo_path, "checkout", default_br, check=False)
        git(repo_path, "branch", "-D", branch, check=False)
        teardown_wallet(wallet_name)
        notify_telegram(f"*Code Session Timeout*\n\nRepo: {repo['alias']}\nInstruction: {args.instruction}\nSession: `{session_id[:8]}...`")
        print(f"session_id: {session_id}")
        return

    # Clean up prompt file
    try:
        os.remove(prompt_file)
    except OSError:
        pass

    # Capture results
    try:
        diff_full = git(repo_path, "diff", "HEAD")
        diff_stats = git(repo_path, "diff", "--stat", "HEAD")
        files_changed_raw = git(repo_path, "diff", "--name-only", "HEAD")
        files_changed = [f for f in files_changed_raw.split("\n") if f]
    except Exception:
        diff_full = ""
        diff_stats = ""
        files_changed = []

    # Also check staged changes
    try:
        staged_diff = git(repo_path, "diff", "--cached")
        staged_stats = git(repo_path, "diff", "--cached", "--stat")
        staged_files = git(repo_path, "diff", "--cached", "--name-only")
        if staged_diff:
            diff_full = (diff_full + "\n" + staged_diff).strip()
            diff_stats = (diff_stats + "\n" + staged_stats).strip()
            files_changed = list(set(files_changed + [f for f in staged_files.split("\n") if f]))
    except Exception:
        pass

    # Also check untracked files
    try:
        untracked = git(repo_path, "ls-files", "--others", "--exclude-standard")
        if untracked:
            untracked_files = [f for f in untracked.split("\n") if f and f != SESSION_SUMMARY_FILE and not f.endswith(".tmp")]
            files_changed = list(set(files_changed + untracked_files))
            # Get content of untracked files for the diff
            for uf in untracked_files:
                try:
                    content = git(repo_path, "diff", "--no-index", "/dev/null", uf, check=False)
                    if content:
                        diff_full = (diff_full + "\n" + content).strip()
                except Exception:
                    pass
    except Exception:
        pass

    # Read Claude's summary
    claude_summary = ""
    summary_path = os.path.join(repo_path, SESSION_SUMMARY_FILE)
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            claude_summary = f.read().strip()

    # Truncate diff for display
    diff_summary = diff_full[:2000] + ("..." if len(diff_full) > 2000 else "")

    # Determine status
    if not diff_full and not files_changed:
        status = "error"
        claude_summary = claude_summary or "No changes were made"
    else:
        status = "review"

    # Update session
    db_update("code_sessions", f"id=eq.{session_id}", {
        "status": status,
        "diff_summary": diff_summary,
        "diff_stats": diff_stats,
        "files_changed": files_changed,
        "claude_summary": claude_summary,
        "claude_output_path": output_log,
        "completed_at": datetime.now(timezone.utc).isoformat() if status != "review" else None,
    })

    # Print summary
    print(f"\nStatus: {status}")
    print(f"Branch: {branch}")
    if diff_stats:
        print(f"Stats: {diff_stats}")
    if claude_summary:
        print(f"Summary: {claude_summary[:200]}")
    print(f"\nsession_id: {session_id}")


def cmd_diff(args):
    """Show diff for a session."""
    sessions = db_query("code_sessions", f"id=eq.{args.session}", limit=1)
    if not sessions:
        print(f"Error: Session not found: {args.session}", file=sys.stderr)
        sys.exit(1)

    session = sessions[0]
    repo_path = session["repo_path"]
    branch = session["branch_name"]

    # If we're on the right branch, show live diff
    try:
        cur = current_branch(repo_path)
        if cur == branch:
            diff = git(repo_path, "diff", "HEAD", check=False)
            staged = git(repo_path, "diff", "--cached", check=False)
            untracked = git(repo_path, "ls-files", "--others", "--exclude-standard", check=False)
            full_diff = diff
            if staged:
                full_diff += "\n" + staged
            if untracked:
                for uf in untracked.split("\n"):
                    if uf and uf != SESSION_SUMMARY_FILE:
                        content = git(repo_path, "diff", "--no-index", "/dev/null", uf, check=False)
                        if content:
                            full_diff += "\n" + content
            if full_diff.strip():
                print(full_diff)
                return
    except Exception:
        pass

    # Fall back to stored diff
    if session.get("diff_summary"):
        print(session["diff_summary"])
    else:
        print("No diff available")


def cmd_approve(args):
    """Approve session: commit, push, create PR."""
    sessions = db_query("code_sessions", f"id=eq.{args.session}", limit=1)
    if not sessions:
        print(f"Error: Session not found: {args.session}", file=sys.stderr)
        sys.exit(1)

    session = sessions[0]
    if session["status"] != "review":
        print(f"Error: Session status is '{session['status']}', expected 'review'", file=sys.stderr)
        sys.exit(1)

    repo_path = session["repo_path"]
    branch = session["branch_name"]
    default_br = session["default_branch"]
    instruction = session["instruction"]

    # Verify branch
    cur = current_branch(repo_path)
    if cur != branch:
        print(f"Switching to branch {branch}...")
        git(repo_path, "checkout", branch)

    # Commit
    prefix = infer_commit_prefix(instruction)
    commit_msg = f"{prefix}: {instruction}"
    git(repo_path, "add", "-A")
    try:
        git(repo_path, "commit", "-m", commit_msg)
        print(f"Committed: {commit_msg}")
    except RuntimeError as e:
        if "nothing to commit" in str(e):
            print("Nothing to commit (changes may already be committed)")
        else:
            raise

    # Push
    try:
        git(repo_path, "push", "origin", branch)
        print(f"Pushed branch: {branch}")
    except RuntimeError as e:
        print(f"Warning: Push failed: {e}", file=sys.stderr)

    # Create PR if GitHub remote configured
    pr_url = None
    pr_number = None
    remote = session.get("github_remote")
    if remote:
        claude_summary = session.get("claude_summary", "")
        diff_stats = session.get("diff_stats", "")
        pr_body = (
            f"## Changes\n\n{claude_summary}\n\n"
            f"## Diff Stats\n\n```\n{diff_stats}\n```\n\n"
            f"---\n*Created via Gato Code*"
        )
        pr = create_github_pr(remote, branch, default_br, instruction, pr_body)
        if pr:
            pr_url = pr["url"]
            pr_number = pr["number"]
            print(f"PR created: {pr_url}")

    # Return to default branch
    git(repo_path, "checkout", default_br)

    # Teardown wallet
    wallet_name = session.get("wallet_agent_name", "")
    cost_sats = teardown_wallet(wallet_name) if wallet_name else 0

    # Update session
    update_data = {
        "status": "approved",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "cost_sats": cost_sats,
    }
    if pr_url:
        update_data["pr_url"] = pr_url
        update_data["pr_number"] = pr_number
    db_update("code_sessions", f"id=eq.{args.session}", update_data)

    print(f"\nSession {args.session[:8]}... approved")
    if pr_url:
        print(f"PR: {pr_url}")


def cmd_reject(args):
    """Reject session: discard changes, delete branch."""
    sessions = db_query("code_sessions", f"id=eq.{args.session}", limit=1)
    if not sessions:
        print(f"Error: Session not found: {args.session}", file=sys.stderr)
        sys.exit(1)

    session = sessions[0]
    if session["status"] not in ("review", "error"):
        print(f"Error: Session status is '{session['status']}', expected 'review' or 'error'", file=sys.stderr)
        sys.exit(1)

    repo_path = session["repo_path"]
    branch = session["branch_name"]
    default_br = session["default_branch"]

    # Discard changes and switch to default branch
    cur = current_branch(repo_path)
    if cur == branch:
        git(repo_path, "checkout", "--", ".", check=False)
        git(repo_path, "clean", "-fd", check=False)
        git(repo_path, "checkout", default_br)
    elif cur != default_br:
        git(repo_path, "checkout", default_br)

    # Delete branch
    git(repo_path, "branch", "-D", branch, check=False)
    print(f"Deleted branch: {branch}")

    # Teardown wallet
    wallet_name = session.get("wallet_agent_name", "")
    cost_sats = teardown_wallet(wallet_name) if wallet_name else 0

    # Update session
    db_update("code_sessions", f"id=eq.{args.session}", {
        "status": "rejected",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "cost_sats": cost_sats,
    })

    print(f"Session {args.session[:8]}... rejected")


def cmd_followup(args):
    """Continue session with additional instruction."""
    if not verify_caller(shared_secret=getattr(args, 'secret', None)):
        print("Error: Unauthorized caller", file=sys.stderr)
        sys.exit(1)

    sessions = db_query("code_sessions", f"id=eq.{args.session}", limit=1)
    if not sessions:
        print(f"Error: Session not found: {args.session}", file=sys.stderr)
        sys.exit(1)

    session = sessions[0]
    if session["status"] != "review":
        print(f"Error: Session status is '{session['status']}', expected 'review'", file=sys.stderr)
        sys.exit(1)

    repo_path = session["repo_path"]
    branch = session["branch_name"]
    instruction = session["instruction"]
    claude_summary = session.get("claude_summary", "")
    diff_summary = session.get("diff_summary", "")

    # Ensure we're on the right branch
    cur = current_branch(repo_path)
    if cur != branch:
        git(repo_path, "checkout", branch)

    # Update session
    followups = session.get("followup_instructions", []) or []
    followups.append(args.instruction)
    db_update("code_sessions", f"id=eq.{args.session}", {
        "status": "running",
        "followup_instructions": followups,
    })

    # Build followup prompt
    prompt = f"""Previous instruction: {instruction}

Changes made so far:
{diff_summary[:1000]}

Claude's summary of previous work:
{claude_summary}

New instruction: {args.instruction}

Continue working on branch {branch}. Build on the existing changes.
Same rules apply: do NOT commit, do NOT push.
Update {SESSION_SUMMARY_FILE} with what you changed this round."""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, dir='/tmp') as f:
        f.write(prompt)
        prompt_file = f.name
    os.chmod(prompt_file, 0o644)

    # Ensure openclaw can write to the repo
    _chown_to_openclaw(repo_path)

    budget = float(session.get("budget_usd", 3.00))
    timeout_min = session.get("timeout_minutes", 15)

    claude_cmd = (
        f"cd {shlex.quote(repo_path)} && "
        f"claude --dangerously-skip-permissions --print "
        f"--max-budget-usd {budget} "
        f"\"$(cat {shlex.quote(prompt_file)})\""
    )

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    output_log = os.path.join(log_dir, f"{args.session}_followup_{len(followups)}.log")

    print(f"Running Claude Code followup (timeout={timeout_min}m)...")
    try:
        result = _run_claude_as_openclaw(claude_cmd, timeout_min * 60, output_log)
    except subprocess.TimeoutExpired:
        print("Claude Code timed out during followup")
        try:
            os.remove(prompt_file)
        except OSError:
            pass
        db_update("code_sessions", f"id=eq.{args.session}", {
            "status": "timeout",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        return

    # Clean up
    try:
        os.remove(prompt_file)
    except OSError:
        pass

    # Re-capture diff (includes all rounds)
    try:
        diff_full = git(repo_path, "diff", "HEAD")
        diff_stats = git(repo_path, "diff", "--stat", "HEAD")
        files_raw = git(repo_path, "diff", "--name-only", "HEAD")
        files_changed = [f for f in files_raw.split("\n") if f]
    except Exception:
        diff_full = ""
        diff_stats = ""
        files_changed = []

    # Check untracked
    try:
        untracked = git(repo_path, "ls-files", "--others", "--exclude-standard")
        if untracked:
            for uf in untracked.split("\n"):
                if uf and uf != SESSION_SUMMARY_FILE:
                    files_changed.append(uf)
                    content = git(repo_path, "diff", "--no-index", "/dev/null", uf, check=False)
                    if content:
                        diff_full += "\n" + content
    except Exception:
        pass

    claude_summary = ""
    summary_path = os.path.join(repo_path, SESSION_SUMMARY_FILE)
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            claude_summary = f.read().strip()

    diff_summary = diff_full[:2000] + ("..." if len(diff_full) > 2000 else "")

    db_update("code_sessions", f"id=eq.{args.session}", {
        "status": "review",
        "diff_summary": diff_summary,
        "diff_stats": diff_stats,
        "files_changed": list(set(files_changed)),
        "claude_summary": claude_summary,
        "claude_output_path": output_log,
    })

    notify_telegram(
        f"*Code Session Followup Complete*\n\n"
        f"Repo: {session['repo_alias']}\n"
        f"New instruction: {args.instruction}\n"
        f"Files: {len(files_changed)}\n"
        f"Session: `{args.session[:8]}...`"
    )

    print(f"\nFollowup complete. Status: review")
    if diff_stats:
        print(f"Stats: {diff_stats}")
    print(f"session_id: {args.session}")


def cmd_status(args):
    """Show current/most recent session status."""
    try:
        sessions = db_query("code_sessions", "", limit=1)
    except Exception as e:
        print(f"Error querying sessions: {e}", file=sys.stderr)
        sys.exit(1)

    if not sessions:
        print("No sessions found")
        return

    s = sessions[0]
    print(f"Session: {s['id'][:8]}...")
    print(f"Status:  {s['status']}")
    print(f"Repo:    {s['repo_alias']} ({s['repo_path']})")
    print(f"Branch:  {s['branch_name']}")
    print(f"Instruction: {s['instruction']}")
    if s.get("diff_stats"):
        print(f"Stats:   {s['diff_stats']}")
    if s.get("claude_summary"):
        print(f"Summary: {s['claude_summary'][:200]}")
    if s.get("pr_url"):
        print(f"PR:      {s['pr_url']}")
    print(f"Created: {s['created_at']}")


def cmd_list(args):
    """List recent sessions."""
    limit = getattr(args, "limit", 10)
    try:
        sessions = db_query("code_sessions", "", limit=limit)
    except Exception as e:
        print(f"Error querying sessions: {e}", file=sys.stderr)
        sys.exit(1)

    if not sessions:
        print("No sessions found")
        return

    fmt = "{:<38} {:<10} {:<12} {:<40} {}"
    print(fmt.format("ID", "STATUS", "REPO", "INSTRUCTION", "CREATED"))
    print("-" * 120)
    for s in sessions:
        print(fmt.format(
            s["id"],
            s["status"],
            s["repo_alias"][:12],
            s["instruction"][:40],
            s["created_at"][:19] if s.get("created_at") else "",
        ))


# ---------------------------------------------------------------------------
# Repos subcommands
# ---------------------------------------------------------------------------
def cmd_repos(args):
    """Handle repos subcommands."""
    sub = args.repos_command

    if sub == "list":
        repos = list_repos()
        if not repos:
            print("No repos found")
            return
        fmt = "{:<20} {:<25} {:<35} {}"
        print(fmt.format("ALIAS", "GITHUB", "LOCAL_PATH", "DESCRIPTION"))
        print("-" * 110)
        for r in repos:
            print(fmt.format(
                r["alias"],
                r.get("github_remote") or "-",
                (r.get("local_path") or "-")[:35],
                (r.get("description") or "")[:40],
            ))
        print(f"\n{len(repos)} repos total")

    elif sub == "add":
        try:
            repo = add_repo(
                alias=args.alias,
                github_remote=args.github,
                local_path=args.path,
                display_name=args.name,
                description=args.desc,
                default_branch=args.branch or "main",
            )
            print(f"Added repo: {repo['alias']} (id: {repo['id'][:8]}...)")
        except Exception as e:
            print(f"Error adding repo: {e}", file=sys.stderr)
            sys.exit(1)

    elif sub == "remove":
        if remove_repo(args.alias):
            print(f"Removed repo: {args.alias}")
        else:
            print(f"Repo not found: {args.alias}", file=sys.stderr)
            sys.exit(1)

    elif sub == "resolve":
        result = _resolve_repo_db(args.query, mark_used=False)
        print(f"Query: \"{args.query}\"")
        print(f"Match type: {result.match_type}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Message: {result.message}")
        if result.repo:
            r = result.repo
            print(f"\nResolved → {r['alias']} ({r.get('local_path') or 'not cloned'}) "
                  f"[{result.match_type}, confidence: {result.confidence:.2f}]")
            if r.get("github_remote"):
                print(f"GitHub: {r['github_remote']}")
            if r.get("description"):
                print(f"Description: {r['description']}")
        elif result.fuzzy_matches:
            print("\nAmbiguous — top candidates:")
            for m in result.fuzzy_matches:
                print(f"  - {m['alias']} (score: {m['score']}) {m.get('description', '')}")
        else:
            print(f"\nNo match found.")
            if result.available:
                print(f"Available repos: {', '.join(result.available)}")


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Gato Code Engine — manage Claude Code sessions"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # start
    p_start = sub.add_parser("start", help="Start a new coding session")
    p_start.add_argument("--repo", required=True, help="Repo alias or owner/repo")
    p_start.add_argument("--instruction", required=True, help="What to do")
    p_start.add_argument("--budget", type=float, default=3.00, help="Budget in USD (default 3.00)")
    p_start.add_argument("--max-turns", type=int, default=20, help="Max turns (stored, not enforced by CLI)")
    p_start.add_argument("--timeout", type=int, default=15, help="Timeout in minutes (default 15)")
    p_start.add_argument("--secret", help="Shared secret for caller verification")

    # diff
    p_diff = sub.add_parser("diff", help="Show diff for a session")
    p_diff.add_argument("--session", required=True, help="Session ID")

    # approve
    p_approve = sub.add_parser("approve", help="Approve session: commit, push, create PR")
    p_approve.add_argument("--session", required=True, help="Session ID")

    # reject
    p_reject = sub.add_parser("reject", help="Reject session: discard changes")
    p_reject.add_argument("--session", required=True, help="Session ID")

    # followup
    p_followup = sub.add_parser("followup", help="Continue session with new instruction")
    p_followup.add_argument("--session", required=True, help="Session ID")
    p_followup.add_argument("--instruction", required=True, help="Additional instruction")
    p_followup.add_argument("--secret", help="Shared secret for caller verification")

    # status
    sub.add_parser("status", help="Show current session status")

    # list
    p_list = sub.add_parser("list", help="List recent sessions")
    p_list.add_argument("--limit", type=int, default=10, help="Max results")

    # setup
    sub.add_parser("setup", help="Check setup and print migration SQL")

    # repos (with sub-subcommands)
    p_repos = sub.add_parser("repos", help="Manage repo registry")
    repos_sub = p_repos.add_subparsers(dest="repos_command", required=True)

    repos_sub.add_parser("list", help="List all registered repos")

    p_repos_add = repos_sub.add_parser("add", help="Add a repo")
    p_repos_add.add_argument("--alias", required=True, help="Short alias")
    p_repos_add.add_argument("--github", help="GitHub remote (owner/repo)")
    p_repos_add.add_argument("--path", help="Local path")
    p_repos_add.add_argument("--name", help="Display name")
    p_repos_add.add_argument("--desc", help="Description")
    p_repos_add.add_argument("--branch", help="Default branch (default: main)")

    p_repos_rm = repos_sub.add_parser("remove", help="Remove a repo (soft delete)")
    p_repos_rm.add_argument("--alias", required=True, help="Repo alias to remove")

    p_repos_resolve = repos_sub.add_parser("resolve", help="Test repo resolution")
    p_repos_resolve.add_argument("query", help="Query string to resolve")

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "diff":
        cmd_diff(args)
    elif args.command == "approve":
        cmd_approve(args)
    elif args.command == "reject":
        cmd_reject(args)
    elif args.command == "followup":
        cmd_followup(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "setup":
        cmd_setup(args)
    elif args.command == "repos":
        cmd_repos(args)


if __name__ == "__main__":
    main()
