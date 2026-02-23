"""
Pytest configuration for AgentPulse test suite.

Problem: All three agent directories contain a file named 'schemas.py'.
Multiple test files add different agent directories to sys.path and import
'schemas'. Once Python caches 'schemas' from one directory in sys.modules,
all later imports get the wrong module.

Solution: At conftest startup, pre-import each poller with the correct schemas
pre-registered, so they're cached in sys.modules from the start.
Test files that do `import newsletter_poller as nl` will use the cached version.
Tests that use importlib directly (test_error_paths) bypass sys.modules and
are unaffected.
"""
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_DOCKER = _ROOT / "docker"


def _load_module(unique_name: str, filepath: Path):
    """Load a Python file as a module under a unique sys.modules name."""
    spec = importlib.util.spec_from_file_location(unique_name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _preload_poller(poller_filename: str, agent_dir: Path, schemas_mod):
    """
    Import a poller file with a specific schemas module pre-registered.
    The poller does `from schemas import ...` at module level, so we register
    the correct schemas module as 'schemas' before importing.
    After the poller is cached, we restore schemas to its previous state.
    """
    prev_schemas = sys.modules.get("schemas")
    prev_poller = sys.modules.get(poller_filename.replace(".py", ""))
    poller_name = poller_filename.replace(".py", "")

    # Clear stale poller if present
    sys.modules.pop(poller_name, None)

    # Register the correct schemas under the generic name
    sys.modules["schemas"] = schemas_mod

    # Ensure agent dir is on sys.path for the duration of the import
    agent_dir_str = str(agent_dir)
    inserted = agent_dir_str not in sys.path
    if inserted:
        sys.path.insert(0, agent_dir_str)

    try:
        spec = importlib.util.spec_from_file_location(
            poller_name, agent_dir / poller_filename
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[poller_name] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        sys.modules.pop(poller_name, None)
        raise
    finally:
        # Restore sys.modules["schemas"] to what it was before
        if prev_schemas is not None:
            sys.modules["schemas"] = prev_schemas
        else:
            sys.modules.pop("schemas", None)

        if inserted:
            try:
                sys.path.remove(agent_dir_str)
            except ValueError:
                pass


# ---------------------------------------------------------------------------
# Pre-load schemas under unique names (no sys.modules["schemas"] side effect)
# ---------------------------------------------------------------------------

_NL_SCHEMAS = _load_module("__nl_schemas", _DOCKER / "newsletter" / "schemas.py")
_ANALYST_SCHEMAS = _load_module("__analyst_schemas", _DOCKER / "analyst" / "schemas.py")
_RESEARCH_SCHEMAS = _load_module("__research_schemas", _DOCKER / "research" / "schemas.py")

# ---------------------------------------------------------------------------
# Pre-import pollers with the correct schemas so they're cached in sys.modules.
# Test files that do `import newsletter_poller as nl` will get these cached
# versions. This avoids the sys.modules["schemas"] naming conflict entirely.
# ---------------------------------------------------------------------------

try:
    _preload_poller("newsletter_poller.py", _DOCKER / "newsletter", _NL_SCHEMAS)
except Exception as e:
    print(f"[conftest] Warning: could not pre-import newsletter_poller: {e}")

try:
    _preload_poller("analyst_poller.py", _DOCKER / "analyst", _ANALYST_SCHEMAS)
except Exception as e:
    print(f"[conftest] Warning: could not pre-import analyst_poller: {e}")

try:
    _preload_poller("research_agent.py", _DOCKER / "research", _RESEARCH_SCHEMAS)
except Exception as e:
    print(f"[conftest] Warning: could not pre-import research_agent: {e}")
