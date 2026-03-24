"""Repo resolver — resolves a query string to a code_repos entry.

Resolution order:
1. Exact alias match
2. Exact match in other_aliases array
3. Fuzzy match (Levenshtein-like via SequenceMatcher)
4. GitHub URL detection (existing or new entry)
5. No match — return available repos
"""

import os
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ENV_PATH = os.getenv("CODE_ENV_PATH", "/home/openclaw/.openclaw/config/.env")
FUZZY_CONFIDENCE_THRESHOLD = 0.55
FUZZY_AMBIGUITY_GAP = 0.10  # if top two scores are within this gap, it's ambiguous

_env_cache = None


def _parse_env(path: str = ENV_PATH) -> dict:
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


def _supabase_headers() -> dict:
    env = _parse_env()
    key = env.get("SUPABASE_SERVICE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _supabase_url(table: str) -> str:
    env = _parse_env()
    base = env.get("SUPABASE_URL", "")
    return f"{base}/rest/v1/{table}"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
@dataclass
class ResolveResult:
    """Result of repo resolution."""
    repo: dict | None = None
    match_type: str = ""       # "exact_alias", "other_alias", "fuzzy", "github_url", "none"
    confidence: float = 0.0
    fuzzy_matches: list = field(default_factory=list)  # top candidates for ambiguous fuzzy
    available: list = field(default_factory=list)       # all repo aliases (for "none")
    message: str = ""

    @property
    def exact(self) -> bool:
        return self.match_type in ("exact_alias", "other_alias", "github_url")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def _fetch_active_repos() -> list[dict]:
    """Fetch all active repos from Supabase."""
    url = _supabase_url("code_repos") + "?is_active=eq.true&order=alias.asc"
    resp = requests.get(url, headers=_supabase_headers(), timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch repos ({resp.status_code}): {resp.text}")
    return resp.json()


def _update_last_used(repo_id: str):
    """Update last_used_at timestamp."""
    from datetime import datetime, timezone
    url = _supabase_url("code_repos") + f"?id=eq.{repo_id}"
    requests.patch(
        url,
        headers=_supabase_headers(),
        json={"last_used_at": datetime.now(timezone.utc).isoformat()},
        timeout=5,
    )


def _insert_repo(data: dict) -> dict:
    """Insert a new repo entry."""
    url = _supabase_url("code_repos")
    resp = requests.post(url, headers=_supabase_headers(), json=data, timeout=10)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to insert repo ({resp.status_code}): {resp.text}")
    rows = resp.json()
    return rows[0] if isinstance(rows, list) and rows else rows


def _update_repo(repo_id: str, data: dict) -> dict:
    """Update a repo entry."""
    url = _supabase_url("code_repos") + f"?id=eq.{repo_id}"
    resp = requests.patch(url, headers=_supabase_headers(), json=data, timeout=10)
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Failed to update repo ({resp.status_code}): {resp.text}")
    try:
        rows = resp.json()
        return rows[0] if isinstance(rows, list) and rows else rows
    except Exception:
        return {}


def _soft_delete_repo(repo_id: str):
    """Soft-delete a repo (set is_active = false)."""
    _update_repo(repo_id, {"is_active": False})


# ---------------------------------------------------------------------------
# GitHub URL parsing
# ---------------------------------------------------------------------------
_GITHUB_PATTERNS = [
    re.compile(r"^https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$"),
    re.compile(r"^github\.com/([^/]+/[^/]+?)(?:\.git)?/?$"),
    re.compile(r"^gh:([^/]+/[^/]+?)(?:\.git)?$"),
]


def _parse_github_ref(query: str) -> str | None:
    """Extract owner/repo from various GitHub URL formats. Returns None if not a GitHub ref."""
    for pattern in _GITHUB_PATTERNS:
        m = pattern.match(query)
        if m:
            return m.group(1)

    # owner/repo format: exactly one slash, no spaces, no dots before slash
    if "/" in query and query.count("/") == 1:
        parts = query.split("/")
        if all(p and not p.startswith(".") and " " not in p for p in parts):
            return query

    return None


def _detect_default_branch(remote: str) -> str:
    """Query GitHub API for the default branch of a repo."""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{remote}",
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("default_branch", "main")
    except Exception:
        pass
    return "main"


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------
def _tokenize(s: str) -> set[str]:
    """Split by common separators and return lowercase tokens."""
    return set(re.split(r"[-_/\s]+", s.lower())) - {""}


def _fuzzy_score(query: str, repo: dict) -> float:
    """Score a repo against a query. Higher is better (0.0 to 1.0)."""
    q = query.lower()
    scores = []

    # Alias similarity (high weight)
    alias = repo.get("alias", "").lower()
    scores.append(SequenceMatcher(None, q, alias).ratio() * 1.0)

    # Other aliases similarity (high weight)
    for a in (repo.get("other_aliases") or []):
        scores.append(SequenceMatcher(None, q, a.lower()).ratio() * 1.0)

    # Display name similarity (medium weight)
    dn = (repo.get("display_name") or "").lower()
    if dn:
        scores.append(SequenceMatcher(None, q, dn).ratio() * 0.7)

    # GitHub remote similarity (medium weight)
    gr = (repo.get("github_remote") or "").lower()
    if gr:
        # Compare against just the repo name part
        repo_name = gr.split("/")[-1] if "/" in gr else gr
        scores.append(SequenceMatcher(None, q, repo_name).ratio() * 0.8)

    # Substring bonus
    all_names = [alias] + [a.lower() for a in (repo.get("other_aliases") or [])] + [dn, gr]
    for name in all_names:
        if name and q in name:
            scores.append(0.7)
            break

    # Token overlap bonus
    q_tokens = _tokenize(query)
    repo_tokens = set()
    for name in all_names:
        if name:
            repo_tokens |= _tokenize(name)
    if q_tokens and repo_tokens:
        overlap = len(q_tokens & repo_tokens) / max(len(q_tokens), 1)
        if overlap > 0:
            scores.append(overlap * 0.6)

    return max(scores) if scores else 0.0


# ---------------------------------------------------------------------------
# Main resolution function
# ---------------------------------------------------------------------------
def resolve_repo(query: str, mark_used: bool = True) -> ResolveResult:
    """Resolve a query to a repo.

    Args:
        query: alias, name fragment, or GitHub URL
        mark_used: if True, update last_used_at on match

    Returns:
        ResolveResult with match details
    """
    query = query.strip()
    if not query:
        return ResolveResult(match_type="none", message="Empty query")

    repos = _fetch_active_repos()
    aliases = [r["alias"] for r in repos]

    # Step 1: Exact alias match
    for repo in repos:
        if repo["alias"] == query:
            if mark_used:
                _update_last_used(repo["id"])
            return ResolveResult(
                repo=repo, match_type="exact_alias", confidence=1.0,
                message=f'Exact alias match: "{query}"'
            )

    # Step 2: Match in other_aliases
    for repo in repos:
        other = repo.get("other_aliases") or []
        if query in other:
            if mark_used:
                _update_last_used(repo["id"])
            return ResolveResult(
                repo=repo, match_type="other_alias", confidence=1.0,
                message=f'Matched other_alias "{query}" → {repo["alias"]}'
            )

    # Step 3: Fuzzy match
    scored = [(repo, _fuzzy_score(query, repo)) for repo in repos]
    scored.sort(key=lambda x: x[1], reverse=True)

    if scored and scored[0][1] >= FUZZY_CONFIDENCE_THRESHOLD:
        best_repo, best_score = scored[0]

        # Check for ambiguity
        if len(scored) > 1 and (scored[0][1] - scored[1][1]) < FUZZY_AMBIGUITY_GAP:
            candidates = [
                {"alias": r["alias"], "score": round(s, 3), "description": r.get("description", "")}
                for r, s in scored[:3] if s >= FUZZY_CONFIDENCE_THRESHOLD
            ]
            return ResolveResult(
                match_type="fuzzy", confidence=best_score,
                fuzzy_matches=candidates, available=aliases,
                message=f'Ambiguous fuzzy match for "{query}" — top candidates listed'
            )

        if mark_used:
            _update_last_used(best_repo["id"])
        return ResolveResult(
            repo=best_repo, match_type="fuzzy", confidence=best_score,
            message=f'Fuzzy match: "{query}" → {best_repo["alias"]} (confidence: {best_score:.2f})'
        )

    # Step 4: GitHub URL detection
    github_remote = _parse_github_ref(query)
    if github_remote:
        # Check if this remote already exists
        for repo in repos:
            if repo.get("github_remote") and repo["github_remote"].lower() == github_remote.lower():
                if mark_used:
                    _update_last_used(repo["id"])
                return ResolveResult(
                    repo=repo, match_type="github_url", confidence=1.0,
                    message=f'GitHub remote match: {github_remote} → {repo["alias"]}'
                )

        # New repo — create entry
        repo_name = github_remote.split("/")[-1]
        default_branch = _detect_default_branch(github_remote)

        new_repo = _insert_repo({
            "alias": repo_name,
            "other_aliases": [],
            "display_name": repo_name,
            "local_path": None,
            "github_remote": github_remote,
            "default_branch": default_branch,
            "description": f"Auto-added from GitHub: {github_remote}",
            "is_active": True,
        })
        return ResolveResult(
            repo=new_repo, match_type="github_url", confidence=1.0,
            message=f'New repo created from GitHub URL: {github_remote} (branch: {default_branch})'
        )

    # Step 5: No match
    return ResolveResult(
        match_type="none", available=aliases,
        message=f'No match for "{query}". Available repos: {", ".join(aliases)}'
    )


# ---------------------------------------------------------------------------
# CLI helpers for repo management
# ---------------------------------------------------------------------------
def list_repos() -> list[dict]:
    """Return all active repos."""
    return _fetch_active_repos()


def add_repo(alias: str, github_remote: str = None, local_path: str = None,
             display_name: str = None, description: str = None,
             other_aliases: list = None, default_branch: str = "main") -> dict:
    """Add a new repo to the registry."""
    data = {
        "alias": alias,
        "other_aliases": other_aliases or [],
        "display_name": display_name or alias,
        "local_path": local_path,
        "github_remote": github_remote,
        "default_branch": default_branch,
        "description": description or "",
        "is_active": True,
    }
    return _insert_repo(data)


def remove_repo(alias: str) -> bool:
    """Soft-delete a repo by alias. Returns True if found and deleted."""
    repos = _fetch_active_repos()
    for repo in repos:
        if repo["alias"] == alias:
            _soft_delete_repo(repo["id"])
            return True
    return False
