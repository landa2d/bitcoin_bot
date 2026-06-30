---
phase: 28-layer-1-deterministic-gate
reviewed: 2026-06-30T11:59:24Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - docker/newsletter/deterministic_gate.py
  - tests/test_28_deterministic_gate.py
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 28: Code Review Report

**Reviewed:** 2026-06-30T11:59:24Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

`deterministic_gate.py` implements the Layer-1 emit-only gate: it runs both body
versions through the reused `verify_draft` engine, layers two net-new fabrication
sub-checks (arXiv membership, entity-merge), adds a network-liveness layer (GitHub
API + URL HEAD) behind an SSRF guard, and emits a four-key flags object. The
emit-only contract holds (no `verdict`, no DB write, no LLM call), the three-outcome
network taxonomy is correctly structured (404 → fabricated, quota/5xx/timeout →
unverified, never collapsed), token hygiene is sound (token only to `api.github.com`,
only a bool in `meta`, never logged), the flags object is JSON-serializable, and the
56-test suite passes.

Two BLOCKERs were found, both on the security-critical network surface and both
**unexercised by the current test suite**:

1. The SSRF guard (`_is_safe_public_url`) validates the host *string* with
   `ipaddress.ip_address`, which only recognizes canonical dotted-quad / IPv6. The OS
   resolver used by `httpx` accepts non-canonical forms (`127.1`, `0x7f.0.0.1`,
   `0177.0.0.1`, `10.1`, `0xa9.0xfe.0xa9.0xfe`) that map to loopback / RFC-1918 /
   the cloud metadata IP. All of these return `True` from the guard — the URL HEAD
   layer will fetch them. Empirically confirmed below.
2. Only `httpx.TimeoutException` and `httpx.ConnectError` are caught in
   `_classify_github` / `_classify_url`. Common transport errors when probing dead
   URLs (`ReadError`, `RemoteProtocolError`, `TooManyRedirects` with
   `follow_redirects=True`, `ProxyError`, `DecodingError`) are siblings, escape the
   `except`, and abort the entire `run_deterministic_gate` — discarding all
   already-computed fabrication/mechanical flags.

In addition, the net-new `_check_entity_merge` produces false positives that land in
the `fabrication` hard-hold tier (including repos the network layer just confirmed
live), which conflicts with the module's claim of inheriting the Edition-34 ~0-FP
calibration.

## Critical Issues

### CR-01: SSRF guard bypassed by non-canonical IP encodings (loopback / RFC-1918 / metadata reachable)

**File:** `docker/newsletter/deterministic_gate.py:388-402`
**Issue:** `_is_safe_public_url` decides whether a host is a literal IP by calling
`ipaddress.ip_address(host)`. That function only parses *canonical* dotted-quad
(four octets) and IPv6 literals. Any other numeric host form raises `ValueError`,
so `ip` becomes `None`, and the function then falls through to the
`"." not in host` branch — which **passes** any string containing a dot. The OS
resolver that the real `httpx.Client` (Phase 30) uses (glibc `getaddrinfo`) happily
resolves these shorthand/octal/hex forms to internal addresses. Confirmed against the
live code:

```
'http://127.1/'                -> _is_safe_public_url = True   # -> 127.0.0.1 (loopback)
'http://0x7f.0.0.1/'           -> _is_safe_public_url = True   # -> 127.0.0.1
'http://0177.0.0.1/'           -> _is_safe_public_url = True   # -> 127.0.0.1 (octal)
'http://10.1/'                 -> _is_safe_public_url = True   # -> 10.0.0.1 (RFC-1918)
'http://0xa9.0xfe.0xa9.0xfe/'  -> _is_safe_public_url = True   # -> 169.254.169.254 (metadata)
'http://127.0.0.1/'            -> _is_safe_public_url = False  # canonical (correctly rejected)
'http://169.254.169.254/'      -> _is_safe_public_url = False  # canonical (correctly rejected)
```

Because the host text is taken verbatim from untrusted LLM draft prose and the URL
HEAD layer (`_classify_url` → `client.head(url, follow_redirects=True)`) fetches any
URL the guard accepts, this defeats the guard's one job: a crafted/prompt-injected
draft URL can reach the loopback interface, internal RFC-1918 hosts, or the cloud
metadata endpoint. `test_ssrf_guard_rejects_internal_and_private` only covers
canonical forms, so this gap is invisible to the suite.
**Fix:** Reject any host that is not a registrable DNS name *or* a canonical public
IP. Concretely, resolve-then-validate the destination instead of trusting the string,
or at minimum reject numeric-looking hosts that fail canonical parsing. For example:

```python
# after the *.internal and denylist checks, before "return True":
ip = None
try:
    ip = ipaddress.ip_address(host)
except ValueError:
    # Not a canonical IP literal. Resolve and validate EVERY answer so
    # shorthand/octal/hex numeric hosts (127.1, 0x7f.0.0.1, 10.1) and
    # hostnames that point at private space cannot slip through.
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        candidate = ipaddress.ip_address(info[4][0])
        if (candidate.is_loopback or candidate.is_private or candidate.is_link_local
                or candidate.is_reserved or candidate.is_unspecified
                or candidate.is_multicast):
            return False
    return True
if (ip.is_loopback or ip.is_private or ip.is_link_local
        or ip.is_reserved or ip.is_unspecified or ip.is_multicast):
    return False
return True
```

Add regression tests for `127.1`, `0x7f.0.0.1`, `0177.0.0.1`, `10.1`, and a hex
metadata form. (Resolve-then-validate still has a TOCTOU/DNS-rebinding window — see
WR-02 — but it closes the literal-encoding bypass that is exploitable today.)

### CR-02: Unhandled `httpx` transport errors crash the whole gate and discard all flags

**File:** `docker/newsletter/deterministic_gate.py:424-433` and `590-600`
**Issue:** Both network classifiers catch only `httpx.TimeoutException` and
`httpx.ConnectError`:

```python
try:
    resp = client.head(url, timeout=5, follow_redirects=True)
except httpx.TimeoutException:
    ...
except httpx.ConnectError:
    ...
```

Several transport errors that are *expected* when HEAD-probing dead / flaky /
untrusted URLs are NOT subclasses of those two and therefore propagate uncaught
(verified against the installed `httpx`):

```
ReadError            issubclass(TimeoutException)=False issubclass(ConnectError)=False
RemoteProtocolError  issubclass(TimeoutException)=False issubclass(ConnectError)=False
TooManyRedirects     issubclass(TimeoutException)=False issubclass(ConnectError)=False
ProxyError           issubclass(TimeoutException)=False issubclass(ConnectError)=False
DecodingError        issubclass(TimeoutException)=False issubclass(ConnectError)=False
```

`follow_redirects=True` makes `TooManyRedirects` a realistic outcome for parked/dead
domains, and `ReadError` (connection reset mid-read) is routine when probing dead
links — which is the exact population this layer targets. An uncaught exception
propagates out of `_classify_url`/`_classify_github` → `_run_url_layer`/
`_run_github_layer` → `run_deterministic_gate`, which raises **before building the
return dict**. Result: a single malformed draft URL aborts the gate and throws away
the fabrication and mechanical flags already computed for that edition. This breaks
the documented contract that network failures become a visible `unverified` state
("an error is not evidence") and is contrary to the emit-only design.
**Fix:** Catch the transient transport families and route them to `unverified`
(retry-once still applies to the genuinely transient ones), e.g.:

```python
except (httpx.TimeoutException, httpx.PoolTimeout):
    if attempt == 1:
        continue
    return ("unverified", "timeout")
except (httpx.ConnectError, httpx.ReadError, httpx.WriteError,
        httpx.RemoteProtocolError, httpx.ProxyError):
    if attempt == 1:
        continue
    return ("unverified", "network_error")
except httpx.TooManyRedirects:
    return ("unverified", "too_many_redirects")  # not transient — do not retry
```

A broad `except httpx.HTTPError` (or `httpx.RequestError`) catch-all that maps to
`("unverified", "network_error")` would also satisfy the "never crash, never a pass"
contract. Apply the same change to `_classify_github` (lines 426-433).

## Warnings

### WR-01: `_check_entity_merge` flags grounded composites as fabrications (false positives in the hard-hold tier)

**File:** `docker/newsletter/deterministic_gate.py:308-348`
**Issue:** The docstring states the check catches a composite "present only
split-across two sources" (a fabricated cross-source merge). The implementation
actually flags **any** multi-word entity (or `owner/repo` token) whose full string is
not a verbatim, contiguous substring of *at least one* source — regardless of whether
the words come from one source or two. Two confirmed false positives, both landing in
`fabrication` (the hard-hold tier):

```
Case A: source = "Acme's Widgets are popular."  draft = "Acme Widgets"
        -> entity_merge fabrication ['Acme Widgets']   # one source, non-contiguous (apostrophe-s)

Case B: draft = "github.com/torvalds/linux", repo returns HTTP 200 (verified live),
        text fact base does not contain the literal "torvalds/linux"
        -> entity_merge fabrication ['torvalds/linux']  # a repo the network layer just confirmed exists
```

Case B is especially perverse: GATE-02 verifies the repo is live (no `github_repo`
flag), yet GATE-05 simultaneously brands the same ref a fabrication. Any real,
grounded multi-word product name phrased differently from its source ("Acme's
Widgets", "Acme and Widgets", "the Widgets from Acme") trips this. This directly
undercuts the module's stated inheritance of the Edition-34 ~0-tier1-FP calibration,
because it introduces a new strict-verbatim path that the calibrated engine
deliberately softens with fuzzy matching.
**Fix:** Make the check match its docstring — only flag a *cross-source* merge:
confirm each token of the composite appears in some source but the full composite
appears in none, AND require ≥2 distinct sources to supply the parts; otherwise defer
to the reused `verify_draft` tier-1 path. Also exclude `owner/repo` tokens that the
GitHub layer has already classified `verified`, so a live repo is never double-flagged
as a fabricated merge.

### WR-02: SSRF guard performs no DNS resolution — public hostname pointing at internal IP bypasses it

**File:** `docker/newsletter/deterministic_gate.py:388-402`
**Issue:** Even after CR-01 is addressed by string normalization alone, the guard
only inspects the host *literal*. A draft URL such as `http://attacker-controlled.com/`
whose A record points at `127.0.0.1`, `10.x.x.x`, or `169.254.169.254` passes the
guard (`"." in host`, not in denylist, not a literal private IP) and is then fetched
by the URL HEAD layer. This is the classic SSRF-via-DNS gap; with untrusted
LLM-generated URLs the attacker (or a prompt-injected source) controls the hostname.
**Fix:** Resolve-then-validate every resolved address against the private/loopback/
link-local/metadata ranges before fetching (see CR-01 fix). For full robustness
against DNS-rebinding, resolve once, validate, then pin/connect to that validated IP
(e.g., a custom transport or `Host`-header + IP target) so the value cannot change
between the check and the request.

### WR-03: arXiv membership uses an unanchored substring test — masks fabricated IDs

**File:** `docker/newsletter/deterministic_gate.py:291-304`
**Issue:** `_check_arxiv_membership` decides an arXiv ID is grounded with
`if arxiv_id not in concatenated` — a bare substring test over the joined source
text. A fabricated 4-digit-fraction ID can be a substring of a longer real ID present
in a source (e.g., body `2605.9999` is a substring of source `2605.99999`), or of any
unrelated digit run, and is then silently treated as grounded — a missed fabrication.
The matching is also asymmetric with `_ARXIV_ID`'s `\b...\b` boundaries used to
*extract* the ID.
**Fix:** Test membership against the **set of arXiv IDs extracted from the sources**,
not a raw substring of concatenated text:

```python
source_ids = {m.group(0) for s in source_texts for m in _ARXIV_ID.finditer(s)}
...
if arxiv_id not in source_ids:
    flags.append({...})
```

### WR-04: `draft` argument is not validated while `fact_base` is — inconsistent fail-loud

**File:** `docker/newsletter/deterministic_gate.py:130-134` (and first use at `147-150`)
**Issue:** The function fails loud on a non-dict `fact_base` (good), but `draft` is
used immediately via `draft.get(...)` with no guard. A `None`/non-dict `draft` raises
a bare `AttributeError` deep in the body instead of the clear, contract-level
`ValueError` the module otherwise favors. For a gate whose whole purpose is "an error
must surface, never silently verify against the wrong input," the two required dict
inputs should be guarded symmetrically.
**Fix:** Add the same guard for `draft` next to the `fact_base` check:

```python
if not isinstance(draft, dict):
    raise ValueError(
        "run_deterministic_gate: draft must be a dict, got "
        f"{type(draft).__name__}"
    )
```

## Info

### IN-01: `meta.github_token_present` reflects env-token presence even when no network ran

**File:** `docker/newsletter/deterministic_gate.py:232`
**Issue:** `github_token_present` is computed as
`bool(github_token or os.getenv("GITHUB_TOKEN"))` unconditionally, so it reports
`True` even when `http_client is None` and no GitHub call was ever made. The field
name implies the token was relevant to this run.
**Fix:** Either rename to convey "configured" semantics, or gate it on
`http_client is not None` so it tracks whether the token was actually available to the
network layer.

### IN-02: reading-mode-label leak uses unanchored substring match — soft false positives

**File:** `docker/newsletter/deterministic_gate.py:676-681`
**Issue:** Members like `"READING MODE"`, `"IMPACT MODE"`, `"TECHNICAL MODE"` are
matched as case-insensitive substrings anywhere in the body, so legitimate prose
("a big impact mode of failure", "reading mode toggles") can trip them. These land in
`mechanical` (soft, operator-tunable per the design), so impact is low, but the
match could be tightened (line/word-anchored, or restrict to the uppercase
scaffolding forms only) to reduce Phase 30 calibration noise.
**Fix:** Match against the original-case body for the all-caps scaffolding tokens, or
anchor to start-of-line, rather than a lowercased substring scan.

### IN-03: `urls_checked` counts SSRF-rejected hosts that were never fetched

**File:** `docker/newsletter/deterministic_gate.py:629-631`
**Issue:** `_run_url_layer` adds every cache-miss URL to `checked` — including hosts
that `_classify_url` short-circuits to `unverified`/`unsafe_host` *without any
request*. `meta.urls_checked` therefore overcounts relative to actual egress (the
name implies "fetched"). Minor reporting inaccuracy.
**Fix:** Increment the fetched counter only when a request was actually issued (e.g.,
have `_classify_url` signal whether it fetched), or rename the counter to
`urls_classified`.

---

_Reviewed: 2026-06-30T11:59:24Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
