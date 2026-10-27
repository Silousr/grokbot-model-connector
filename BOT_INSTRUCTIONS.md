# Bot-side procedure

Register the connector (MCP_REGISTRATION.md), install the skills in
`template-skills/`, and set up alerts (WEBHOOK_SETUP.md). Keep one stable bot_id
per bot and chat, saved in the bot's memory with its destination chat.

On every webhook wakeup, reconnect or user turn:
1. `list_events` for the saved bot_id; deduplicate by (bot_id, event.id).
2. For terminal events, `get_task`; inspect result, error and changed/deleted
   files and run relevant checks. `completed` means the runner returned, not that
   the work is right. If only a plan came back for requested code, continue.
3. Deliver to the chat, then `ack_events`. Leave failed deliveries pending.
   HTTP 200 means the routine accepted the wakeup, not that chat delivery happened.
4. `list_tasks` to reconcile active work. Never create timed polling routines or
   background wait jobs: the worker detects stalls and timeouts itself.

New tasks: honor an explicit model, else the bot default. When a choice is needed,
render `model_choices` as native option buttons and pass the clicked reply as
`start_task.model`. Change `set_bot_default` only for a lasting preference. Save
durable preferences with `set_bot_memory` (it replaces memory; merge first). For
build work pass concrete relative `required_artifacts`. Report task ID and model.

Only completed, failed, timed_out, stalled and cancelled wake the routine.
Retries carry a stable Idempotency-Key; a lost response can still cause a repeat
wakeup, so deduplicate. Never silently retry provider tasks with side effects.
