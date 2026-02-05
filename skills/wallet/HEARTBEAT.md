# Wallet Heartbeat

Periodic wallet maintenance tasks.

## Schedule

Run wallet checks at each heartbeat interval (every 60 minutes).

## Heartbeat Tasks

### Task 1: Balance Check

Monitor wallet balance and alert on significant changes.

```
1. GET wallet balance from LNbits
2. Compare to last recorded balance
3. If changed significantly (>10%), log and possibly notify owner
4. Record current balance
```

### Task 2: Reset Daily Spending Counter

At midnight (agent timezone), reset the daily spending counter.

```
1. Check current time
2. If new day:
   - Log yesterday's total spending
   - Reset daily_spending_sats to 0
   - Reset approval count
```

### Task 3: Check Pending Invoices

Check if any invoices you generated have been paid.

```
1. GET /api/v1/payments?pending=true
2. For each pending invoice:
   - Check if now paid
   - If paid, log the receipt
   - Thank the payer if identifiable
```

### Task 4: Low Balance Alert

Warn if balance is getting low.

```
1. If balance < 1000 sats:
   - Send alert to human owner via Telegram
   - "⚠️ Wallet balance low: {balance} sats remaining"
2. If balance < 100 sats:
   - "🚨 Wallet nearly empty: {balance} sats. Payments disabled."
```

## Daily Summary (Optional)

If enabled, send a daily summary to human owner:

```
📊 Daily Wallet Summary
━━━━━━━━━━━━━━━━━━━━
Balance: 8,500 sats
Spent today: 1,500 sats
Received today: 0 sats
Transactions: 3
━━━━━━━━━━━━━━━━━━━━
```

## Logging

Record all wallet activity:
```
[WALLET] Balance check: 8500 sats (no change)
[WALLET] Daily spending reset: 1500 -> 0
[WALLET] Invoice lnbc... paid: +500 sats
```

## Error Recovery

If LNbits is unreachable:
1. Log the error
2. Disable payment functionality temporarily
3. Retry next heartbeat
4. Alert human owner if persistent (>3 failures)
