---
name: decision-desk
description: Use whenever something needs the owner's decision or action, when the owner asks "what's waiting on me" / "next", or when another bot reports an item for them. Keeps one queue and walks it one item at a time.
---
# Decision desk

One queue for everything that needs the owner: approvals, choices, sign-ups, purchases, logins only they can do. Queue file: `/workspace/decision-desk/QUEUE.md` (create it if missing; save its path in memory with the rule "anything needing the owner goes to the decision desk").

**File layout:** `## Open (walk order)` numbered items; `## Closed` one line each with the reason; `## Done log` dated entries with the owner's exact words. Each open item: date added, source (which bot or task), the actual thing (full text, link, cost, file path), the options with one marked (rec), and a last-checked time.

**Adding:** append to Open; merge duplicates; put urgent or deadline items first. Don't interrupt for each item unless urgent; mention the count at a natural moment.

**Walking the queue** (owner says "next" / "what's waiting", or accepts your offer):
1. Before showing an item, re-check it with its source (the bot, the page, the task). If it's gone or handled, close it silently.
2. Close items older than 3 days that nobody has rechecked.
3. Show **one** item: a short line of context, the actual thing, and an option card (2–5 options, the recommended one first and marked "(recommended)", plus "Skip for now").
4. On the answer: log it in Done log with the date and their words, carry it out or pass it to the source, close the item, then offer the next one ("3 more. Next?").
5. "Skip" keeps it open with a note; "drop" closes it.

**Call reminders (optional, offered once at setup):** ask if they want a call every few hours while items wait. If yes, ask how often (2/3/4 h) and their quiet hours and time zone. Look for a calling capability: a built-in call tool, else a phone-call connector or plugin (SearchPlugins, e.g. Bland). Create a schedule routine at that cadence whose prompt says: if Open is empty or it's quiet hours in the owner's zone, do nothing; else call and briefly read the top 1–3 items, then say "answer in chat." No calling capability: say so and use a push/chat reminder on the same schedule and quiet hours. Save the choice in memory.

**Rules:** never decide for the owner, never act on an item before their answer, never put secrets in the queue file. Pass answers meant for another bot on, and log that.
