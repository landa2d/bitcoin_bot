# Agent Spend Analysis: Pre-Proxy vs Post-Proxy

**Date:** 2026-03-18
**Source:** Supabase tables `wallet_transactions`, `agent_wallets_v2`, `agent_daily_usage`, `agent_spending_windows`, `governance_events`

---

## Timeline

- **Proxy went live:** March 15, 2026 ~20:00 UTC (first `wallet_transactions` entry)
- **Data available from:** February 17, 2026 (via `agent_daily_usage`)

---

## The Analyst Problem (biggest spender by far)

The analyst is essentially the only agent with meaningful LLM volume. Three distinct phases:

### Phase 1 — Pre-proxy, low volume (Feb 17-22): ~10-76 calls/day

Normal task-driven usage. The analyst was responding to actual tasks.

### Phase 2 — Pre-proxy, runaway (Feb 23 - Mar 15): ~17,000-42,000 calls/day

Something changed on Feb 23 that caused the analyst to start polling/calling DeepSeek at an extreme rate. Peak was **41,136 calls on Feb 26**. These calls went directly to DeepSeek with **zero cost tracking**.

| Period | Daily Avg Calls | Est. Daily Cost (DeepSeek) |
|--------|----------------|---------------------------|
| Feb 23 - Mar 1 | ~26,000 | ~$0.70-$1.00/day |
| Mar 2 - Mar 14 | ~22,000 | ~$0.60-$0.85/day |

### Phase 3 — Post-proxy (Mar 15 onward): Dramatic drop

| Date | Calls (daily_usage) | Calls (proxy logged) | Notes |
|------|--------------------|--------------------|-------|
| Mar 15 | 18,390 | 1,724 | Proxy caught partial day |
| Mar 16 | 190 | 3,742 | Proxy enforcing budgets |
| Mar 17 | 219 | 0 | Calls not going through proxy |
| Mar 18 | 219 | 0 | Calls not going through proxy |

The proxy **crushed** the runaway spend — daily calls dropped from ~22,000 to ~219. That's a **99% reduction**.

---

## Current Wallet Balances

| Agent | Deposited | Spent (wallet) | Balance | Status |
|-------|-----------|---------------|---------|--------|
| **Analyst** | 50,000 sats | 179,511 sats | **-129,511 sats** | Overdrawn |
| Processor | 100,000 sats | 152 sats | 99,848 sats | Healthy |
| Gato | 100,000 sats | 40 sats | 99,960 sats | Healthy |
| Newsletter | 50,000 sats | 16 sats | 49,984 sats | Healthy |
| Research | 50,000 sats | 0 sats | 50,000 sats | Unused |

---

## Proxy-Tracked Spend by Model (since Mar 15)

| Agent | Model | Calls | Input Tokens | Output Tokens | Sats | Est. USD |
|-------|-------|-------|-------------|--------------|------|----------|
| Analyst | deepseek-chat | 5,466 | 4,736,483 | 458,460 | 5,466 | ~$0.79 |
| Processor | deepseek-chat | 15 | 165,968 | 7,977 | 30 | ~$0.03 |
| Gato | claude-sonnet-4 | 3 | 5,649 | 662 | 26 | ~$0.03 |
| Gato | text-embedding-3-large | 7 | 29,037 | 0 | 10 | ~$0.004 |
| Gato | deepseek-chat | 4 | 3,480 | 722 | 4 | ~$0.001 |
| Newsletter | gpt-4o-mini | 1 | 33,558 | 875 | 6 | ~$0.006 |

**Total proxy-tracked spend: 5,542 sats (~$5.54 USD)**

---

## Estimated Total Spend (All Time, Including Pre-Proxy)

Using the analyst's avg token profile (~869 input, ~84 output per call on DeepSeek):

| Period | Total Analyst Calls | Est. Cost |
|--------|-------------------|-----------|
| Feb 17-22 (pre-runaway) | ~141 | ~$0.02 |
| Feb 23 - Mar 14 (runaway, no tracking) | ~461,403 | ~$65-70 |
| Mar 15-18 (proxy era) | ~5,466 tracked | ~$0.79 |
| **Total estimated** | **~467,000** | **~$66-71** |

---

## Analyst Hourly Breakdown (Mar 15-16, proxy-tracked)

| Hour (UTC) | Calls | Sats | Avg Input Tokens | Avg Output Tokens |
|------------|-------|------|-----------------|------------------|
| Mar 15 20:00 | 307 | 307 | 869 | 86 |
| Mar 15 21:00 | 456 | 456 | 869 | 86 |
| Mar 15 22:00 | 485 | 485 | 870 | 86 |
| Mar 15 23:00 | 476 | 476 | 870 | 86 |
| Mar 16 00:00 | 447 | 447 | 868 | 87 |
| Mar 16 01:00 | 392 | 392 | 864 | 87 |
| Mar 16 02:00 | 365 | 365 | 864 | 87 |
| Mar 16 03:00 | 354 | 354 | 863 | 84 |
| Mar 16 04:00 | 381 | 381 | 863 | 85 |
| Mar 16 05:00 | 374 | 374 | 863 | 84 |
| Mar 16 06:00 | 365 | 365 | 865 | 82 |
| Mar 16 07:00 | 375 | 375 | 867 | 77 |
| Mar 16 08:00 | 371 | 371 | 867 | 76 |
| Mar 16 09:00 | 318 | 318 | 868 | 77 |

---

## Key Issues Flagged

1. **Analyst wallet is -129,511 sats** — deeply overdrawn. The `allow_negative` flag or the reserve RPC let it keep spending past zero. The wallet `total_spent_sats` (179,511) doesn't match the transaction log sum (5,466) — meaning **174,045 sats of spend was recorded by the reserve/settle RPCs but the async transaction logging dropped those records** (likely the log queue was overwhelmed during the Mar 15-16 burst).

2. **Analyst is bypassing the proxy on Mar 17-18** — `agent_daily_usage` shows 219 calls/day but zero proxy transactions on those dates. The analyst is still calling DeepSeek directly for some operations, outside the proxy's cost tracking.

3. **Research agent has never been used** — 50,000 sats sitting idle.

4. **No governance events recorded** — the `governance_events` table is empty, meaning cap_hit/balance_exhausted events were never triggered despite the analyst going -129K sats negative.

---

## Recommendations

- **Investigate the analyst bypass** — it's still making ~219 calls/day outside the proxy on Mar 17-18
- **Top up or reset the analyst wallet** and enforce `allow_negative = false`
- **Fix the async transaction logger** — it dropped 97% of the analyst's transactions during the burst
- **Wire up governance events** — the cap/exhaustion triggers aren't firing
- **Consider reallocating** research's unused 50K sats
