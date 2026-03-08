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
    if (text && !text.startsWith("/")) {
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
          const data = await res.json() as Record<string, unknown>;
          const reply = (data.response ?? data.message ?? "") as string;
          if (reply) {
            await ctx.reply(reply);
            return; // handled — skip OpenClaw's default path
          }
        }
      } catch (err) {
        console.error("[gato-brain] middleware error, falling through to OpenClaw:", err?.message ?? err);
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
