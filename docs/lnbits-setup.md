# LNbits Wallet Setup Guide

This guide walks you through setting up a Lightning wallet for your OpenClaw agent.

## What is LNbits?

LNbits is a free, open-source Lightning wallet system. It provides an easy way to create Lightning wallets with API access, perfect for autonomous agents.

## Step 1: Create an LNbits Account

### Option A: Use the Public Instance (Easiest)

1. Go to [legend.lnbits.com](https://legend.lnbits.com)
2. A new wallet is automatically created
3. **IMPORTANT**: Bookmark this page! The wallet ID is in the URL

### Option B: Self-Host (More Secure)

For production use, consider self-hosting LNbits:
- [LNbits GitHub](https://github.com/lnbits/lnbits)
- Requires a Lightning node (LND, Core Lightning, etc.)

## Step 2: Get Your API Keys

1. Click on your wallet name to open settings
2. Find the "API Info" section
3. Copy these keys:

| Key | Purpose | Security Level |
|-----|---------|----------------|
| **Admin key** | Send payments, full access | HIGH - Keep secret! |
| **Invoice/read key** | Generate invoices, check balance | MEDIUM - Safer to expose |

## Step 3: Configure Your Agent

Add to `config/.env`:

```bash
# LNbits Configuration
LNBITS_URL=https://legend.lnbits.com
LNBITS_ADMIN_KEY=your-admin-key-here
LNBITS_INVOICE_KEY=your-invoice-read-key-here

# Safety limits
WALLET_DAILY_LIMIT_SATS=10000
WALLET_APPROVAL_THRESHOLD_SATS=1000
```

## Step 4: Fund Your Wallet

### Option 1: From Your Own Lightning Wallet

1. In LNbits, click "Create Invoice"
2. Enter an amount (e.g., 10000 sats)
3. Copy the invoice (starts with `lnbc...`)
4. Pay from your personal Lightning wallet (Phoenix, Muun, BlueWallet, etc.)

### Option 2: From an Exchange

1. Generate an invoice in LNbits
2. Withdraw to that invoice from a Lightning-enabled exchange

### How Much to Fund?

Start small! Only fund what you're willing to lose:

| Risk Level | Amount | Use Case |
|------------|--------|----------|
| Testing | 1,000-5,000 sats | Development/testing |
| Light use | 10,000-50,000 sats | Occasional tips |
| Active | 50,000-100,000 sats | Regular transactions |

## Step 5: Verify Configuration

After starting your agent, check if the wallet is working:

1. Send `/wallet` to your agent via Telegram
2. You should see your current balance
3. Try `/receive 100 test` to generate a test invoice

## Security Best Practices

### 1. Separate Wallet for Agent

Never use your personal wallet. Create a dedicated wallet just for the agent.

### 2. Spending Limits

Set conservative limits in `.env`:
```bash
WALLET_DAILY_LIMIT_SATS=10000    # Max spent per day
WALLET_APPROVAL_THRESHOLD_SATS=1000  # Require approval above this
```

### 3. Monitor Activity

- Check `/history` regularly
- Review the daily summaries
- Set up alerts for large transactions

### 4. Key Rotation

If you suspect key compromise:
1. Create a new wallet in LNbits
2. Transfer remaining funds
3. Update `.env` with new keys
4. Restart the agent

### 5. Backup

LNbits wallets are custodial - the instance operator holds the funds. For the public instance, this means:
- Funds could be lost if the service goes down
- Only keep small amounts
- For larger amounts, consider self-hosting

## Troubleshooting

### "Invalid API Key" Error

- Verify the key is copied correctly (no extra spaces)
- Check you're using the right key (admin vs invoice)
- Ensure the wallet still exists in LNbits

### "Payment Failed" Error

Possible causes:
- Insufficient balance
- Invoice expired
- Route not found (Lightning network issue)
- LNbits service temporarily down

### Balance Shows 0 But Wallet Has Funds

- Balance is returned in millisatoshis
- Divide by 1000 for satoshis
- Check you're using the correct wallet ID

### Rate Limiting

LNbits may rate limit requests:
- Wait a few minutes before retrying
- Reduce heartbeat frequency if persistent

## LNbits Extensions (Optional)

LNbits has extensions that could enhance your agent:

| Extension | Use Case |
|-----------|----------|
| **LNURLp** | Reusable payment links |
| **Satspay** | Invoice pages |
| **TPoS** | Point-of-sale terminal |

These are advanced features for future exploration.

## Quick Reference

### Check Balance
```bash
curl -X GET https://legend.lnbits.com/api/v1/wallet \
  -H "X-Api-Key: YOUR_INVOICE_KEY"
```

### Create Invoice
```bash
curl -X POST https://legend.lnbits.com/api/v1/payments \
  -H "X-Api-Key: YOUR_INVOICE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"out": false, "amount": 1000, "memo": "Test invoice"}'
```

### Pay Invoice
```bash
curl -X POST https://legend.lnbits.com/api/v1/payments \
  -H "X-Api-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"out": true, "bolt11": "lnbc..."}'
```
