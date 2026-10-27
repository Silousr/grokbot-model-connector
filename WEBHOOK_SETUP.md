# Webhook alert setup (instructions to the bot)

Goal: when a Codex or Claude task finishes, fails, times out, stalls or is cancelled,
the connector POSTs to a webhook routine on this bot, so the bot wakes up by itself.
No timed polling routine is ever needed. Do these steps in order, one at a time.
Never ask the owner to paste the URL or key into chat, never echo either, and never
put either in a tool argument, file you write, prompt or memory.

`DIR` is the connector install dir (default `/workspace/model-connector`).

1. **bot_id.** If memory has no connector bot_id for this bot, use a short
   kebab-case form of the bot's name (e.g. `research-helper`) and save
   "Model connector bot_id is <id>; alerts go to this chat" in memory.
2. **Create the routine** with UpdateRoutine: name `Model connector alerts`,
   trigger `{ "type": "webhook" }`, prompt:

   > When the model connector wakes me, find my saved connector bot_id and list its
   > unacknowledged connector events. For each completed, failed, timed_out, stalled
   > or cancelled event, read the task, check the result and the changed files, and
   > report to the owner: a short checked summary in the main chat and the CLI's
   > full reply word for word in a thread under it, saying plainly where I disagree.
   > Acknowledge an event only after it was reported. Skip events already reported.
   > Results go to the owner in this chat. If there is nothing new, send nothing.

   Keep it active. The owner may be asked to confirm the save.
3. **Tell the owner (one message):** "Open the routine *Model connector alerts*
   (bot name → Details → Routines), copy its **POST to** URL and **key**. Don't
   paste them here; I'll open a private form for them." Include the routine
   panel link from the routine's line in your automation status if you have it.
4. **Start the one-time form** as a background Shell job:
   `python3 DIR/connector.py webhook-form <bot_id>`
   Its first output line is JSON: `form_url` (loopback, random path, single use,
   expires in 15 minutes) and the field selectors `#webhook_url`, `#webhook_key`,
   `#save`.
5. **Masked input.** Open `form_url` in the box browser, take a snapshot, then
   call RequestUserForm with two secret fields: "Webhook URL (POST to)" →
   `#webhook_url`, and "Webhook key" → `#webhook_key`, domain `127.0.0.1`.
   The values go from the owner straight into the page; you never see them.
6. **Save.** After the receipt, take a fresh snapshot and click `#save`. The page
   shows "Saved. Webhook configured" or a reason (e.g. the URL is not HTTPS). The
   background job then prints `{"bot_id": ..., "webhook_configured": true}` and
   exits. The form wrote the key to `DIR/.state/secrets/` (mode 0600) and ran
   `set_bot_webhook` with that key file. Never read that folder.
7. **Check** with `python3 DIR/connector.py doctor <bot_id>`: expect
   `"webhook_configured": true` and `"alert_supervisor_running": true`.
8. **End-to-end test.** Start a tiny task (`start_task`, prompt
   "Reply with exactly: CONNECTOR_OK") and end the turn. The alert must wake this
   bot through the routine; report it, then acknowledge the event.

If the form card can't render (some mobile apps) or the owner prefers a terminal,
they can run `python3 DIR/connector.py webhook-prompt <bot_id>` on the box; it
asks for both values with hidden input. If a key was ever pasted into chat,
don't repeat it; ask the owner to create a fresh routine (new key) and redo 3–7.
To rotate, run steps 3–7 again; the registration keeps its history cutoff.
