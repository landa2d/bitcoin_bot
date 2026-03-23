#!/usr/bin/env python3
"""
Reconciliation script — compares agent_wallets_v2.total_spent_sats against
SUM(ABS(amount_sats)) from wallet_transactions per agent, reports gaps,
and optionally inserts reconciliation entries to close them.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv("config/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")


def get_gaps(sb):
    """Return per-agent gap between wallet balance and logged transactions."""
    wallets = sb.table("agent_wallets_v2").select("agent_name, total_spent_sats").execute()
    tx_result = sb.rpc("get_transaction_sums", {}).execute()

    # Build lookup from wallet_transactions
    logged = {}
    if tx_result.data:
        for row in tx_result.data:
            logged[row["agent_name"]] = int(row["total_logged"])

    gaps = []
    for w in wallets.data or []:
        agent = w["agent_name"]
        spent = w["total_spent_sats"]
        log_total = logged.get(agent, 0)
        gap = spent - log_total
        gaps.append({
            "agent_name": agent,
            "total_spent_sats": spent,
            "logged_sats": log_total,
            "gap_sats": gap,
        })
    return sorted(gaps, key=lambda g: g["gap_sats"], reverse=True)


def get_gaps_sql(sb):
    """Fallback: compute gaps using direct queries (no RPC needed)."""
    wallets = sb.table("agent_wallets_v2").select("agent_name, total_spent_sats").execute()

    # Get logged totals per agent for llm_call transactions
    tx_raw = (
        sb.table("wallet_transactions")
        .select("agent_name, amount_sats")
        .eq("transaction_type", "llm_call")
        .execute()
    )
    logged = {}
    for row in tx_raw.data or []:
        agent = row["agent_name"]
        logged[agent] = logged.get(agent, 0) + abs(row["amount_sats"])

    gaps = []
    for w in wallets.data or []:
        agent = w["agent_name"]
        spent = w["total_spent_sats"]
        log_total = logged.get(agent, 0)
        gap = spent - log_total
        gaps.append({
            "agent_name": agent,
            "total_spent_sats": spent,
            "logged_sats": log_total,
            "gap_sats": gap,
        })
    return sorted(gaps, key=lambda g: g["gap_sats"], reverse=True)


def insert_reconciliation(sb, agent_name: str, gap_sats: int, reason: str):
    """Insert a reconciliation entry to close the gap."""
    # Get current balance
    wallet = (
        sb.table("agent_wallets_v2")
        .select("balance_sats")
        .eq("agent_name", agent_name)
        .single()
        .execute()
    )
    balance = wallet.data["balance_sats"]

    record = {
        "agent_name": agent_name,
        "transaction_type": "reconciliation",
        "amount_sats": -gap_sats,
        "amount_usd_cents": 0,
        "balance_after_sats": balance,
        "metadata": {
            "reason": reason,
            "estimated_calls": gap_sats,
            "reconciled_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    sb.table("wallet_transactions").insert(record).execute()
    print(f"  Inserted reconciliation: {agent_name} -> {gap_sats} sats")


def main():
    parser = argparse.ArgumentParser(description="Reconcile wallet balances vs transaction log")
    parser.add_argument("--fix", action="store_true", help="Insert reconciliation entries to close gaps")
    parser.add_argument("--reason", default="async_logger_gap", help="Reason tag for reconciliation metadata")
    parser.add_argument("--min-gap", type=int, default=1, help="Only report/fix gaps >= this many sats")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set", file=sys.stderr)
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    try:
        gaps = get_gaps(sb)
    except Exception:
        gaps = get_gaps_sql(sb)

    print("\n=== Transaction Reconciliation Report ===\n")
    print(f"{'Agent':<20} {'Spent (sats)':>14} {'Logged (sats)':>14} {'Gap (sats)':>12}")
    print("-" * 64)

    total_gap = 0
    fixable = []
    for g in gaps:
        flag = " *** " if g["gap_sats"] >= args.min_gap else ""
        print(f"{g['agent_name']:<20} {g['total_spent_sats']:>14,} {g['logged_sats']:>14,} {g['gap_sats']:>12,}{flag}")
        total_gap += g["gap_sats"]
        if g["gap_sats"] >= args.min_gap:
            fixable.append(g)

    print("-" * 64)
    print(f"{'TOTAL':<20} {'':>14} {'':>14} {total_gap:>12,}")
    print()

    if not fixable:
        print("No gaps to fix.")
        return

    if args.fix:
        print(f"Inserting {len(fixable)} reconciliation entries...\n")
        for g in fixable:
            insert_reconciliation(sb, g["agent_name"], g["gap_sats"], args.reason)
        print("\nDone. Re-run without --fix to verify.")
    else:
        print(f"{len(fixable)} agent(s) have gaps >= {args.min_gap} sats. Run with --fix to insert reconciliation entries.")


if __name__ == "__main__":
    main()
