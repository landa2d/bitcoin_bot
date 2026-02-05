# Telegram Bot Setup Guide

This guide walks you through creating a Telegram bot to control your OpenClaw agent.

## Step 1: Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Start a chat with BotFather
3. Send the command: `/newbot`
4. Follow the prompts:
   - Enter a **name** for your bot (e.g., "Gato Bitcoin Agent")
   - Enter a **username** for your bot (must end in `bot`, e.g., `lloyd_btc_agent_bot`)
5. BotFather will respond with your **Bot Token** - save this!

Example token format:
```
123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

## Step 2: Get Your Telegram User ID

To ensure only you can control the agent, you need your Telegram user ID:

1. Search for `@userinfobot` on Telegram
2. Start a chat and send any message
3. The bot will reply with your user information including your **ID**

Example:
```
Id: 123456789
First: John
Lang: en
```

## Step 3: Configure the Environment

Add the values to your `config/.env` file:

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_OWNER_ID=123456789
```

## Step 4: Start the Agent

```powershell
.\scripts\start.ps1
```

## Step 5: Pair with Your Bot

1. Open Telegram
2. Search for your bot by its username (e.g., `@lloyd_btc_agent_bot`)
3. Start a chat with `/start`
4. The agent should respond and be ready for commands

## Telegram Commands

Once connected, you can interact with your agent:

| Command | Description |
|---------|-------------|
| Any text | Chat with the agent naturally |
| `/status` | Check agent status |
| `/wallet` | Check wallet balance |
| `/stop` | Pause the agent |
| `/resume` | Resume the agent |
| `/help` | Show available commands |

## Troubleshooting

### Bot doesn't respond

1. Check that the container is running:
   ```powershell
   docker ps
   ```

2. Check the logs:
   ```powershell
   .\scripts\logs.ps1
   ```

3. Verify the bot token is correct in `.env`

### "Unauthorized" errors

- Make sure the bot token is copied correctly (no extra spaces)
- Verify the token hasn't been revoked (check with BotFather)

### Can't find the bot

- The bot username must end in `bot`
- Wait a few minutes after creation for Telegram to index it
- Try searching by the full username including `@`

## Security Notes

- **Never share your bot token** - anyone with it can control your agent
- **Set TELEGRAM_OWNER_ID** - this restricts commands to only you
- The bot token is stored in `.env` which should never be committed to git
- You can revoke and regenerate the token via BotFather if compromised

## Advanced: Multiple Admins

To allow multiple people to control the agent, you can set multiple owner IDs (comma-separated):

```bash
TELEGRAM_OWNER_ID=123456789,987654321
```

Only users with IDs in this list will be able to send commands to the agent.
