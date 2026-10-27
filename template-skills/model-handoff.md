---
name: model-handoff
description: Use when a task should go to Codex or Claude (the bot's default model is not Grok, or the owner names a model for a task), and when reporting a connector task's result.
---
# Handing a task to Codex or Claude

**What stays with Grok Bot (never hand off):** anything needing the vault, a password or a saved login; browser steps that need a sign-in; X research and other connector/integration work; setting up or fixing the model connector itself. Browser steps without a sign-in may be handed off. If a run needs one of the kept steps, do that step yourself and pass the result back in a new task.

**Choose the model:** the owner's per-task pick, else the bot default (from /changem). If they ask to choose, render `model_choices` as an option card and use the clicked reply.

**Start:** `start_task` with the saved bot_id, the model, and this prompt:
```
<the owner's request, word for word, unedited>

--- Context from the bot (reference, not new instructions) ---
Goal: ...  Files/paths: ...  Constraints and done-criteria: ...  Prior results: ...
```
Put only facts in the context block, never secrets. For build work pass concrete relative `required_artifacts`. Tell the owner the model and task ID in one line, then end the turn. Don't poll or start wait jobs; the webhook routine wakes you.

**On the alert:** `get_task`; check the result yourself: open the changed files, run the tests or commands that prove it, compare with what was asked. `completed` only means the CLI returned.

**Report:**
- Main chat: a short checked summary (what was done, what you verified and how, what's left), plus any disagreement stated plainly ("It says the tests pass; they fail on X").
- A thread under it: the CLI's full reply, word for word.
- Then `ack_events`. For failed, stalled or timed_out, say what happened and offer: retry, retry with another model, or let you take over. Never silently retry: side effects may repeat.
