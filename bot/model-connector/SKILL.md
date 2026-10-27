---
name: model-connector
description: Run tasks through the local Codex or Claude connector, show model-choice buttons, and relay durable task alerts.
---

Use the `model-connector` MCP tools. Shell fallback (DIR = install dir, default
/workspace/model-connector): `python3 DIR/connector.py call TOOL 'JSON'`. Pass JSON
safely; never interpolate user text into shell syntax.

Keep one stable bot_id per bot and chat in memory with its destination chat. Save
durable instructions with set_bot_memory (it replaces memory; merge first).

Alerts: set up once with WEBHOOK_SETUP.md (routine "Model connector alerts",
masked form via `connector.py webhook-form BOT_ID`). Never handle the key in chat or
tool arguments. `python3 DIR/connector.py doctor BOT_ID` checks CLIs, sign-in,
supervisor and webhook.

On webhook wakeup, turn start or reconnect: list_events for the bot_id, get_task
for terminal events, review result/error/artifacts, deliver, then ack_events.
Deduplicate by event id. completed only means the runner returned an answer.
Never silently retry uncertain provider outcomes. Use list_tasks to reconcile.

New task: explicit model, else saved default. If a choice is needed, render
model_choices as a native option card (max six: five plus "More"; never start a
task for More). Per-task picks don't change defaults. For build work pass relative
required_artifacts. Report task ID and model. Don't create timed checks or
background wait-event jobs; shell job completion doesn't wake the bot.
