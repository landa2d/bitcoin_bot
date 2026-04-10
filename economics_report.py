#!/usr/bin/env python3
"""
Weekly economics report — queries proxy wallet/governance data and produces
a structured JSON report.  Optionally inserts into editorial_inputs.

Usage:
    python3 economics_report.py              # generate + insert
    python3 economics_report.py --dry-run    # generate + print only
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent / "config" / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

# Rough BTC-USD for sat→USD conversion (1 sat = 1e-8 BTC)
BTC_USD = 87_000
SAT_USD = BTC_USD / 1e8


def fetch_transactions(sb, since, until):
    """Fetch wallet_transactions in a date range."""
    rows = (
        sb.table("wallet_transactions")
        .select("agent_name, amount_sats, transaction_type, metadata, created_at")
        .gte("created_at", since.isoformat())
        .lt("created_at", until.isoformat())
        .order("created_at")
        .execute()
    )
    return rows.data or []


def fetch_governance_events(sb, since, until):
    rows = (
        sb.table("governance_events")
        .select("agent_name, event_type, details, created_at")
        .gte("created_at", since.isoformat())
        .lt("created_at", until.isoformat())
        .execute()
    )
    return rows.data or []


def fetch_wallets(sb):
    rows = (
        sb.table("agent_wallets_v2")
        .select("agent_name, balance_sats, total_spent_sats, total_deposited_sats, spending_cap_sats, spending_cap_window")
        .execute()
    )
    return rows.data or []


def analyse_transactions(current_txs, previous_txs):
    """Build per-agent breakdown, model usage, totals, and trend."""

    def _aggregate(txs):
        agent_spend = defaultdict(int)
        agent_calls = Counter()
        agent_models = defaultdict(Counter)
        model_usage = Counter()
        refund_count = 0

        for tx in txs:
            agent = tx["agent_name"]
            amt = abs(tx["amount_sats"] or 0)
            ttype = tx.get("transaction_type", "")
            meta = tx.get("metadata") or {}

            if ttype in ("refund", "settlement") and (tx.get("amount_sats") or 0) > 0:
                refund_count += 1
                continue

            agent_spend[agent] += amt
            agent_calls[agent] += 1
            model = meta.get("model", "unknown")
            agent_models[agent][model] += 1
            model_usage[model] += 1

        return agent_spend, agent_calls, agent_models, model_usage, refund_count

    cur_spend, cur_calls, cur_models, model_usage, refund_count = _aggregate(current_txs)
    prev_spend, prev_calls, _, _, _ = _aggregate(previous_txs)

    total_sats = sum(cur_spend.values())
    total_calls = sum(cur_calls.values())
    prev_total_sats = sum(prev_spend.values())

    if prev_total_sats > 0:
        trend_pct = ((total_sats - prev_total_sats) / prev_total_sats) * 100
    elif total_sats > 0:
        trend_pct = 100.0
    else:
        trend_pct = 0.0

    # Per-agent breakdown
    agents = sorted(set(cur_spend) | set(prev_spend))
    agent_breakdown = []
    for agent in agents:
        spent = cur_spend.get(agent, 0)
        calls = cur_calls.get(agent, 0)
        models = cur_models.get(agent, Counter())
        primary_model = models.most_common(1)[0][0] if models else "n/a"
        avg_cost = round(spent / calls) if calls else 0
        prev_agent_spent = prev_spend.get(agent, 0)
        if prev_agent_spent > 0:
            agent_trend = ((spent - prev_agent_spent) / prev_agent_spent) * 100
            trend_str = f"{agent_trend:+.1f}%"
        elif spent > 0:
            trend_str = "new"
        else:
            trend_str = "dormant"
        agent_breakdown.append({
            "agent": agent,
            "spent_sats": spent,
            "calls": calls,
            "primary_model": primary_model,
            "avg_cost": avg_cost,
            "trend": trend_str,
        })

    agent_breakdown.sort(key=lambda x: x["spent_sats"], reverse=True)

    summary = {
        "total_cost_sats": total_sats,
        "total_cost_usd": f"${total_sats * SAT_USD:.2f}",
        "total_calls": total_calls,
        "trend_vs_last_week": f"{trend_pct:+.1f}%",
        "refund_count": refund_count,
    }

    return summary, agent_breakdown, dict(model_usage.most_common()), cur_spend, prev_spend


def analyse_governance(events):
    """Summarise governance events by agent + type."""
    counts = Counter()
    for ev in events:
        counts[(ev["agent_name"], ev["event_type"])] += 1
    result = [
        {"agent": agent, "event_type": etype, "count": cnt}
        for (agent, etype), cnt in counts.most_common()
    ]
    return result


def detect_anomalies(cur_spend, prev_spend, gov_events):
    anomalies = []

    # Spend changed > 50%
    all_agents = set(cur_spend) | set(prev_spend)
    for agent in all_agents:
        cur = cur_spend.get(agent, 0)
        prev = prev_spend.get(agent, 0)
        if prev > 0 and cur > 0:
            change = abs(cur - prev) / prev
            if change > 0.5:
                direction = "increased" if cur > prev else "decreased"
                anomalies.append(
                    f"{agent}: spend {direction} {change*100:.0f}% vs previous week "
                    f"({prev} → {cur} sats)"
                )
        elif prev > 0 and cur == 0:
            anomalies.append(f"{agent}: went dormant (spent {prev} sats last week, 0 this week)")

    # >5 governance events
    agent_gov_count = Counter(ev["agent_name"] for ev in gov_events)
    for agent, cnt in agent_gov_count.items():
        if cnt > 5:
            anomalies.append(f"{agent}: {cnt} governance events this week (threshold: 5)")

    return anomalies


def build_wallet_balances(wallets):
    balances = []
    for w in wallets:
        cap = w.get("spending_cap_sats") or 0
        spent = w.get("total_spent_sats") or 0
        utilization = round((spent / cap) * 100, 1) if cap > 0 else 0.0
        balances.append({
            "agent": w["agent_name"],
            "balance": w["balance_sats"],
            "utilization_pct": utilization,
        })
    balances.sort(key=lambda x: x["balance"], reverse=True)
    return balances


def print_summary(report):
    s = report["summary"]
    print("=" * 60)
    print(f"  WEEKLY ECONOMICS REPORT — {report['period']}")
    print("=" * 60)
    print(f"\n  Total cost:  {s['total_cost_sats']:,} sats ({s['total_cost_usd']})")
    print(f"  Total calls: {s['total_calls']:,}")
    print(f"  Trend:       {s['trend_vs_last_week']} vs previous week")
    print(f"  Refunds:     {s.get('refund_count', 0)}")

    print("\n  --- Per-Agent Breakdown ---")
    for a in report["agent_breakdown"]:
        print(f"  {a['agent']:20s}  {a['spent_sats']:>8,} sats  {a['calls']:>4} calls  "
              f"model={a['primary_model']:20s}  avg={a['avg_cost']:>6}  trend={a['trend']}")

    print("\n  --- Model Usage ---")
    for model, count in report["model_usage"].items():
        print(f"  {model:30s}  {count:>6} calls")

    if report["governance_events"]:
        print("\n  --- Governance Events ---")
        for g in report["governance_events"]:
            print(f"  {g['agent']:20s}  {g['event_type']:20s}  x{g['count']}")

    if report["anomalies"]:
        print("\n  --- Anomalies ---")
        for a in report["anomalies"]:
            print(f"  ⚠ {a}")

    print("\n  --- Wallet Balances ---")
    for w in report["wallet_balances"]:
        print(f"  {w['agent']:20s}  balance={w['balance']:>10,} sats  utilization={w['utilization_pct']:.1f}%")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Generate weekly economics report")
    parser.add_argument("--dry-run", action="store_true", help="Print report without inserting into editorial_inputs")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY not set", file=sys.stderr)
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    now = datetime.now(timezone.utc)
    period_end = now
    period_start = now - timedelta(days=7)
    prev_start = period_start - timedelta(days=7)

    # Fetch data
    current_txs = fetch_transactions(sb, period_start, period_end)
    previous_txs = fetch_transactions(sb, prev_start, period_start)
    gov_events = fetch_governance_events(sb, period_start, period_end)
    wallets = fetch_wallets(sb)

    # Analyse
    summary, agent_breakdown, model_usage, cur_spend, prev_spend = analyse_transactions(current_txs, previous_txs)
    gov_summary = analyse_governance(gov_events)
    anomalies = detect_anomalies(cur_spend, prev_spend, gov_events)
    wallet_balances = build_wallet_balances(wallets)

    report = {
        "report_type": "weekly_economics",
        "period": f"{period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}",
        "generated_at": now.isoformat(),
        "summary": summary,
        "agent_breakdown": agent_breakdown,
        "model_usage": model_usage,
        "governance_events": gov_summary,
        "anomalies": anomalies,
        "wallet_balances": wallet_balances,
    }

    # Print human-readable summary
    print_summary(report)

    # Save to file
    reports_dir = Path(__file__).resolve().parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    filename = reports_dir / f"economics_{now.strftime('%Y-%m-%d')}.json"
    filename.write_text(json.dumps(report, indent=2))
    print(f"\n  Saved to {filename}")

    # Insert into editorial_inputs
    if not args.dry_run:
        sb.table("editorial_inputs").insert({
            "user_id": "system",
            "command": "queue",
            "priority": "medium",
            "content_type": "data",
            "body": json.dumps(report),
            "source_filename": f"economics_{now.strftime('%Y-%m-%d')}.json",
            "metadata": {
                "source": "proxy_economics",
                "input_type": "data",
                "period": report["period"],
            },
        }).execute()
        print("  Inserted into editorial_inputs ✓")
    else:
        print("  --dry-run: skipped editorial_inputs insert")


if __name__ == "__main__":
    main()
