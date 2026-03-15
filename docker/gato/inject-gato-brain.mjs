/**
 * inject-gato-brain.mjs — Build-time patch for OpenClaw's bot.ts
 *
 * Injects a grammY middleware between registerTelegramNativeCommands and
 * registerTelegramHandlers.  Non-command text messages are forwarded to
 * the gato-brain service (FastAPI on port 8100).  If gato-brain is
 * unreachable or times out (15 s), the middleware falls through so
 * OpenClaw handles the message via its normal GPT-4o path.
 */

import { readFileSync, writeFileSync } from "fs";

const file = "src/telegram/bot.ts";
let code = readFileSync(file, "utf8");

const middleware = `
  // ═══ Gato Brain routing middleware ═══
  // Free-form text → gato-brain; slash commands pass through to OpenClaw.
  bot.on("message:text", async (ctx, next) => {
    const text = ctx.message?.text;

    // Handle /commands directly — show full AgentPulse command list
    if (text && (text.trim() === "/commands" || text.trim() === "/commands@\${bot.botInfo?.username}")) {
      const help = \`📡 AgentPulse Commands

📊 INTEL
/toolradar — Trending tools with sentiment
/toolcheck [name] — Stats for a specific tool
/opps — Business opportunities
/analysis — Analyst findings & confidence
/signals — Market signals
/curious — Fun trending topics
/topics — Topic lifecycle & evolution
/thesis [topic] — Analyst thesis on a topic

📰 NEWSLETTER
/brief — Latest newsletter (Telegram)
/newsletter_full — Generate new edition
/newsletter_publish — Publish draft
/newsletter_revise [text] — Send revision notes
/freshness — Excluded from next edition
/subscribers — Subscriber count & modes

🔍 RESEARCH
/scan — Run full data pipeline
/invest_scan — Investment scanner (7d)
/deep_dive [topic] — Deep research
/review [opp] — Review an opportunity
/predictions — Prediction scorecard
/predict [text] — Add a prediction
/sources — Scraping status

🧠 INTELLIGENCE
/briefing — Personal intelligence briefing
/context — Operator context & watch topics
/watch [topic] — Add to watch list
/alerts — Recent proactive alerts
/budget — Agent usage vs limits

🐦 X DISTRIBUTION
/x-plan — Today's X candidates
/x-approve [nums] — Approve (e.g. 1,3)
/x-reject [nums] — Reject candidates
/x-edit [num] — View draft to edit
/x-draft [num] [text] — Replace draft
/x-posted — Posted today
/x-budget — X API spend
/x-watch [handle] [cat] — Add to watchlist
/x-unwatch [handle] — Remove from watchlist
/x-watchlist — Show watchlist

💰 AGENT ECONOMY
/wallet — Agent wallet balances
/ledger [agent] — Last 10 transactions
/topup [agent] [amt] — Top up wallet (sats)
/negotiations — Active negotiations

⚙️ CORE
/status — Agent status
/publish — Publish newsletter
/help — Basic help\`;
      await ctx.reply(help);
      return;
    }

    // Forward /x-* commands to gato-brain (they're handled there, not in OpenClaw)
    const isXCommand = text && /^\\/x-/i.test(text.trim());

    if (text && (!text.startsWith("/") || isXCommand)) {
      try {
        const res = await fetch("http://gato_brain:8100/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: String(ctx.from?.id),
            message: text,
            message_type: "text",
          }),
          signal: AbortSignal.timeout(30000),
        });
        if (res.ok) {
          const data = await res.json();
          const reply = String((data as any).response || "");
          if (reply) {
            await ctx.reply(reply);
            return; // handled — skip OpenClaw's default path
          }
        }
      } catch (err: any) {
        console.error("[gato-brain] middleware error, falling through to OpenClaw:", String(err));
      }
    }
    await next();
  });

`;

const marker = "  registerTelegramHandlers({";
const idx = code.indexOf(marker);

if (idx === -1) {
  console.error(
    "ERROR: could not find registerTelegramHandlers in bot.ts — " +
      "OpenClaw source may have changed. Skipping gato-brain injection.",
  );
  process.exit(1);
}

code = code.slice(0, idx) + middleware + code.slice(idx);
writeFileSync(file, code);
console.log("Injected gato-brain middleware into src/telegram/bot.ts");
