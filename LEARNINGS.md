# AgentPulse — Project Learnings

Hard-won lessons from building and operating a multi-agent newsletter pipeline.

---

## 1. LLM prompt rules don't enforce system behavior

**Problem:** We added rules to the newsletter agent's system prompt telling it to resolve stale predictions (target_date in the past) and avoid repeating themes from recent editions. The LLM consistently ignored both rules — stale predictions kept appearing as "Active" and the same topic dominated consecutive newsletters.

**Root cause:** Prompt rules are suggestions, not guarantees. When the LLM receives input data containing stale predictions with `status: active`, it treats them as active regardless of what Rule 14 says. Similarly, telling the LLM to "avoid recent themes" doesn't work when every data signal (opportunities, analyst insights, spotlight, emerging signals) all point to the same topic.

**Fix:** Enforce constraints at the **data layer**, not the prompt layer:
- Auto-expire predictions with `target_date < today` in the database before the LLM ever sees them
- Filter opportunities, analyst theses, and spotlight topics by theme overlap before passing to the LLM
- The LLM should receive data that already reflects the constraints, not instructions to self-censor

**Rule of thumb:** If a behavior must always happen, enforce it in code. Use prompt rules only for editorial judgment calls (tone, framing, structure).

---

## 2. Docker Compose `environment:` overrides `env_file:`

**Problem:** DeepSeek API key was correctly set in `config/.env` but all three agents reported "DeepSeek client not available." The containers were falling back to OpenAI (or crashing with 404 errors when model was set to `deepseek-chat`).

**Root cause:** In `docker-compose.yml`, we had both:
```yaml
env_file:
  - ../config/.env          # Loads DEEPSEEK_API_KEY=sk-xxx into container
environment:
  DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}   # Resolves from HOST shell, not env_file
```
The `environment:` block takes precedence over `env_file:`. The `${DEEPSEEK_API_KEY:-}` syntax resolves from the **host machine's shell environment**, not from the env_file. Since the host didn't have it exported, it resolved to an empty string — overriding the valid key from `config/.env`.

**Fix:** Don't duplicate env vars in the `environment:` section if they're already provided by `env_file:`. Only put service-specific overrides (like `AGENT_NAME`, `MODEL`) in `environment:`.

**Rule of thumb:** Use `env_file:` for secrets and shared config. Use `environment:` only for values that differ per service or need hardcoded defaults.

---

## 3. Theme diversity requires closing ALL input vectors

**Problem:** After implementing spotlight cooldown (4-edition block) and theme penalty in spotlight selection, the newsletter still repeated the same "assumption gap" topic across consecutive editions.

**Root cause:** The newsletter receives data from 5+ independent sources — opportunities, emerging signals, trending topics, analyst insights, and spotlight. The cooldown only blocked the spotlight vector. The same theme leaked through via:
- **High-confidence opportunity** that survived staleness decay (0.85 * 0.7 = 0.595, still top-ranked)
- **Analyst insights** — the latest `analysis_runs` record directly fed the Big Insight with zero theme checks
- **Spotlight reuse** — `_fetch_latest_spotlight_for_newsletter()` returned the same spotlight for every edition until it was 7 days old (no "used" flag)

**Fix:** Apply theme diversity at every input vector:
- Opportunities: theme overlap penalty on `effective_score`
- Analyst insights: filter theses matching recent themes
- Spotlight: only fetch spotlights queued for the current edition number
- Bootstrap `primary_theme` from titles for existing newsletters so the system has history to compare against

**Rule of thumb:** In a multi-source pipeline, a filter on one source is not a filter on the output. Every input path that can carry a theme must be checked.

---

## 4. Agent boundaries create enforcement gaps

**Problem:** The processor prepares newsletter data and applies freshness rules (exclude IDs, staleness decay). The newsletter agent applies editorial rules (avoid recent themes, resolve stale predictions). But the processor doesn't know what the newsletter agent will write, and the newsletter agent can't change the data it receives.

**Root cause:** Each agent operates in isolation with its own context. Rules set "at the agent level" (in system prompts or SKILL.md) can only be enforced by that agent. If Agent A prepares data and Agent B writes content, Agent B cannot retroactively fix data quality issues — it can only work with what it receives.

**How to avoid:** Place enforcement at the **handoff point** — the function that prepares data for the next agent. `prepare_newsletter_data()` is the single chokepoint where all data flows to the newsletter agent. All diversity filtering, expiry, and deduplication should happen there, not in the newsletter agent's prompt.

**Rule of thumb:** The agent that controls the data has the real power. Prompt rules on a downstream agent are advisory at best. Always enforce constraints where data is assembled, not where it's consumed.

---

## 5. Cold-start problems in tracking systems

**Problem:** We added a `primary_theme` column to track newsletter themes for diversity enforcement. But all existing newsletters had `primary_theme = NULL`, so `get_recent_newsletter_themes()` returned an empty list and `avoided_themes` was `[]`. The diversity system was live but had nothing to avoid.

**Fix:** Added a bootstrap step in `prepare_newsletter_data()` that backfills `primary_theme` from newsletter titles for recent editions with NULL themes. This runs automatically on the first cycle and seeds the system.

**Rule of thumb:** When adding a new tracking column, always include a migration or bootstrap step that backfills from existing data. Don't assume the system will "catch up" — it may take weeks of natural operation to accumulate enough history.

---

## 6. Fallback models must be valid for the target API

**Problem:** When `deepseek_client` was `None` (API key missing), the analyst and newsletter `routed_llm_call()` fell through to sending `model="deepseek-chat"` to the OpenAI API, which returned a 404 error ("model does not exist").

**Root cause:** The fallback code path (`return client.chat.completions.create(model=model, ...)`) used the original model name without checking if it was valid for the fallback provider.

**Fix:** When the DeepSeek client isn't available, explicitly swap the model to `gpt-4o-mini` before calling the OpenAI client.

**Rule of thumb:** When routing LLM calls across providers, the fallback path must change both the client AND the model name. A model string valid for one provider is not valid for another.

---

## 7. Validators catch what prompt rules miss

**Problem:** Rule 15 in the newsletter system prompt says "NEVER use dates in the past" for predictions. The LLM still generated predictions like "By Q4 2025" and "By June 2025" when today is February 2026. Additionally, old predictions with `target_date = NULL` (created before the target_date column existed) were invisible to the auto-expiry query.

**Root cause:** Two gaps: (1) the LLM ignores prompt rules when its training data or pattern-matching favors a particular date format, and (2) the target-date-based expiry query uses `.not_.is_("target_date", "null")` which skips predictions with NULL dates — they never get expired.

**Fix:**
- Added `validate_prediction_dates()` as a post-generation validator. It parses every prediction date in the generated newsletter markdown. If any date is in the past, it flags it as severity=CRITICAL, which triggers a retry with specific feedback ("Prediction X has past date Y — resolve or replace").
- Added `backfill_null_target_dates()` that runs before expiry. It parses `target_date` from `prediction_text` for predictions with NULL dates, using the same regex patterns (Q-format, month-year, year-end). Once backfilled, the existing target-date expiry handles them.

**Rule of thumb:** When an LLM must never produce X, add a validator that detects X in the output and triggers a retry. Two lines of regex are more reliable than two paragraphs of prompt instructions. For tracking columns added after launch, always include a backfill step that parses existing data.

---

## 8. Agent self-awareness must be non-blocking and cached

**Problem:** We wanted each agent to include a spending summary in its system prompt so agents are aware of their own economics. The naive approach — call an HTTP endpoint before every LLM call — would add latency to every task and break agents if the proxy was down.

**Design decisions:**
1. **Non-blocking fetch with 5-second timeout.** All exceptions caught; returns empty string on failure. An agent should never fail because of missing economics data.
2. **5-minute TTL cache.** The economics block doesn't change meaningfully between consecutive LLM calls within a task. Caching avoids hammering the proxy.
3. **Gato Brain queries Supabase directly** instead of calling its own HTTP endpoint, avoiding a circular dependency at startup.
4. **Auto-key-lookup from Supabase.** Instead of requiring operators to configure `AGENT_API_KEY` in every service's environment, each agent resolves its key from the `agent_api_keys` table on first use. One less thing to forget during deployment.
5. **Processor uses log-only approach.** The processor has 10+ inline system prompts for different tasks (extraction, clustering, opportunity generation, etc.). Injecting economics into all of them would be invasive. Logging to stdout at startup and every 6 hours via the scheduler gives visibility without touching prompt construction.

**Rule of thumb:** Self-awareness features must be strictly additive — they should enhance behavior when available but have zero impact when unavailable. Cache aggressively, fail silently, and prefer log-only for agents with many prompt paths.

---

## 9. HTTP-to-self creates circular startup dependencies

**Problem:** Gato Brain hosts the `/v1/proxy/wallet/{agent_name}/summary` endpoint. If Gato Brain also calls that endpoint to get its own economics, it would need to HTTP-request itself — which fails during startup (server not yet listening) and adds unnecessary network hops.

**Fix:** Gato Brain's `fetch_economics_block()` queries Supabase directly for the same data the endpoint would return. The HTTP endpoint exists for other agents on the Docker network; the host agent bypasses it.

**Rule of thumb:** When a service needs data that it also serves, query the underlying data source directly rather than calling your own HTTP endpoint. This avoids startup ordering issues and eliminates a network round-trip.
