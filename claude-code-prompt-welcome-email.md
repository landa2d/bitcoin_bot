# Claude Code Prompt: Implement AgentPulse Welcome Email

## Context

AgentPulse is a multi-agent newsletter platform. We need to add a welcome email that gets sent to new subscribers when they sign up. The email explains what the newsletter is, where the intelligence comes from, the newsletter structure, the dual reading modes (Builder Mode / Impact Mode), and why it's valuable.

## What to implement

### 1. Welcome email HTML template

Create a file at `templates/welcome-email.html` (or wherever the existing email templates live — check the codebase first).

The email should be a self-contained HTML file with all CSS inlined/embedded (no external stylesheets — email clients don't support them). Here's the full template to use:

```
[PASTE THE CONTENTS OF agentpulse-welcome-email.html HERE]
```

**Important email compatibility notes before saving the template:**
- Convert any `display: flex` to `<table>` layouts for email client compatibility (Gmail, Outlook, Apple Mail). The template as-provided uses flexbox which won't render in most email clients. Convert the section map, sources grid, and dual-view box to table-based layouts.
- Inline all critical CSS into `style=""` attributes on each element (keep the `<style>` block too as a progressive enhancement, but don't rely on it).
- Replace `@media` queries with a fallback that works without them — many email clients strip `<style>` blocks entirely.
- Wrap everything in a `<table>` with `role="presentation"` as the outermost container (standard email template pattern).
- Test that the dark background (`#0a0a0f`) renders correctly — some email clients need it set on both `<body>` and the wrapper `<table>`.

### 2. Email sending function

Create a utility function (or add to existing email utils if they exist) that:
- Takes a subscriber email address as input
- Renders the welcome email HTML template
- Sends it via whatever email sending method is already configured in the project (check for existing SMTP config, SendGrid, Resend, Postmark, or similar)
- If no email sending is configured yet, set up a basic integration. Resend is the simplest option — just needs an API key in `.env` and a `POST` to their API. Create the `.env` variable `RESEND_API_KEY` (or equivalent for whatever service is used) with a placeholder value.
- The `From` address should be something like `brief@agentpulse.ai` or match whatever domain/sender is already configured
- Subject line: `You're in. Here's what this actually is.`

### 3. Trigger on new subscriber

Find where new subscribers are added to the system (likely a Supabase insert into a subscribers/contacts table) and hook the welcome email send into that flow:
- If there's a subscription endpoint or function, add the welcome email call after successful subscription
- If subscribers are added via Supabase directly, consider a Supabase database webhook or trigger, or add it to whichever agent/process handles new signups
- Make sure the welcome email only fires once per subscriber (idempotency) — add a `welcome_email_sent` boolean column or timestamp to the subscribers table if it doesn't exist, and check it before sending

### 4. Supabase migration (if needed)

If you need to modify the subscribers table (e.g., adding `welcome_email_sent`), create a proper migration file. Check `list_migrations` or the migrations directory for the existing naming convention.

## What NOT to do

- Don't modify any existing newsletter generation or sending logic
- Don't touch the Newsletter agent, Analyst agent, or any agent identity files
- Don't change the newsletter HTML template — this is a separate, one-time welcome email
- Don't set up a full email queue system — a simple direct send on subscription is fine for now

## Verification

After implementation:
1. Show me the final file structure of what was created/modified
2. Show the email sending function signature and the trigger point
3. If a migration was created, show the SQL
4. Confirm the template was converted to email-client-safe HTML (tables, inline styles)
