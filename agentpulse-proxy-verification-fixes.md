# Proxy Fixes — Three Issues Found in Verification

Run these in order. All three need to be resolved before any new experiments.

---

## Fix 1: Find and close the analyst's proxy bypass (CRITICAL)

```
The analyst agent is still making ~219 LLM calls per day that bypass the proxy entirely. On March 17-18, agent_daily_usage shows 219 calls/day but wallet_transactions has zero entries from the proxy for those dates.

This means the analyst has a code path that still calls DeepSeek directly instead of through the proxy.

1. Read docker/analyst/analyst_poller.py completely
2. Find EVERY place where an LLM client is created or an API call is made
3. Check each one: does it use the proxy URL (http://llm-proxy:8200/v1) or a direct provider URL (api.deepseek.com)?
4. The prediction monitoring loop (monitor_predictions / assess_and_flag) is the most likely culprit — it was the source of 13,000 calls/day before. Check if it creates its own client separately from the task processing client.
5. Also check: is there a fallback mechanism that reverted to direct calls? Maybe the proxy was briefly unreachable and the fallback stuck.
6. Also check the Docker environment variables for the analyst container — run: docker exec <analyst_container> env | grep -i url to see what URLs it's actually using at runtime.

Fix every direct provider URL to route through the proxy. There should be ZERO direct calls to api.deepseek.com, api.openai.com, or api.anthropic.com from any agent.

After fixing, monitor for 1 hour and verify: every analyst call appears in wallet_transactions.
```

---

## Fix 2: Fix the async transaction logger (HIGH)

```
The async transaction logger dropped 97% of records during the March 15-16 analyst burst. The wallet balance (via synchronous reserve-settle RPCs) shows 179,511 sats spent, but wallet_transactions only has 5,466 entries. That's a 174,045 sat gap in the ledger.

The wallet BALANCES are correct (reserve-settle is atomic and synchronous). But the TRANSACTION HISTORY is incomplete, which breaks the economics reporting, audit trail, and any analytics built on wallet_transactions.

Investigate and fix:

1. Read the async logging code in the proxy. Find where transactions are queued and written.

2. Diagnose: what happened during the burst?
   - Was the in-memory queue capped at 1000 entries and overflow was lost?
   - Did Supabase insert rate limiting kick in?
   - Did the async tasks get cancelled when the proxy restarted?
   - Check proxy logs from March 15-16 for any error messages about failed writes or queue overflow.

3. Fix the logger to handle burst volume:
   - If the queue has a cap, write overflow to a local JSON lines file (append-only) as a fallback
   - Add a reconciliation mechanism: a script that compares wallet balances (from reserve-settle) against wallet_transactions sum, and flags discrepancies
   - Consider batching: instead of one Supabase insert per transaction, batch them (e.g., flush every 5 seconds or every 50 records, whichever comes first)

4. Create a reconciliation script reconcile_transactions.py that:
   - Compares agent_wallets_v2.total_spent_sats against SUM(ABS(amount_sats)) from wallet_transactions per agent
   - Reports the gap per agent
   - Optionally generates synthetic "reconciliation" entries to close the gap (so the ledger balances)

5. Run the reconciliation for the current gap. The analyst has 174,045 sats of unlogged transactions. Insert a single reconciliation entry:
   - transaction_type: 'reconciliation' (add this to the CHECK constraint if needed)
   - amount_sats: -174045
   - metadata: {"reason": "async_logger_overflow_mar15_16", "estimated_calls": 174045}

After fixing, stress-test: simulate 500 rapid calls and verify all 500 appear in wallet_transactions with zero drops.
```

---

## Fix 3: Wire up governance events (MEDIUM)

```
The governance_events table is empty despite the analyst being at -129,511 sats negative. Either the governance checks aren't in the request flow, or allow_negative=true is bypassing them entirely.

1. Read the proxy's request flow and find where governance checks happen (spending cap, balance checks, model access).

2. Verify: when the analyst makes a call, does the proxy:
   a. Look up governance rules for the analyst?
   b. Check the spending window against the cap?
   c. Log a governance_event when a cap is hit?
   d. Log a governance_event when balance goes below zero?

3. The issue might be that allow_negative=true skips ALL governance checks, not just the balance floor. Fix this: allow_negative should only skip the balance-must-be-positive check. Spending caps and governance event logging should STILL fire for internal agents. You want to see "analyst hit daily cap" events even if the agent is allowed to keep spending.

4. Add these governance event triggers if they're missing:
   - 'cap_hit': when spending window total exceeds spending_cap_sats
   - 'balance_low': when balance drops below 20% of original deposit
   - 'balance_exhausted': when balance hits zero (even if allow_negative lets it continue)
   - 'model_downgrade': when a downgrade action fires

5. Reset the analyst's wallet for a clean experiment:
   UPDATE agent_wallets_v2 
   SET balance_sats = 50000, 
       total_spent_sats = 0, 
       total_deposited_sats = 50000 
   WHERE agent_name = 'analyst';

6. Set the analyst's spending cap:
   UPDATE agent_wallets_v2 
   SET spending_cap_sats = 1000, 
       spending_cap_window = 'daily' 
   WHERE agent_name = 'analyst';

7. Monitor for 24 hours. Verify:
   - Analyst calls appear in wallet_transactions (Fix 1 resolved the bypass)
   - Governance events fire when the analyst approaches and hits the 1000 sat daily cap
   - The analyst's behavior when the cap is hit matches the configured action (reject/alert)
```
