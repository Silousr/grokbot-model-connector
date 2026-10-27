---
name: getting-started
description: Use in the first conversation with a new owner, or when they say "set me up" / "getting started", to install and verify the model connector, alerts, default model and decision desk.
---
# Getting started

Open with one line: "I hand work to Codex or Claude on your own subscriptions, wake myself when it's done, and keep your decisions in one queue." Then do the steps **one at a time**, skipping any already done (`doctor` tells you). DIR = `/workspace/model-connector` unless memory says otherwise.

1. **Install.** On the box: `curl -fsSL https://raw.githubusercontent.com/Silousr/grokbot-model-connector/main/install.sh | bash`. If `DIR` already holds something else, set `MODEL_CONNECTOR_DIR`. Save DIR in memory. Summarize its [ok]/[!!] lines plainly.
2. **Sign-ins.** Run `python3 DIR/connector.py doctor`. For each provider the owner wants that isn't signed in, tell them the exact command (`codex login` or `claude auth login`) to run in the box terminal themselves. Never sign in for them. One provider is enough.
3. **Register the connector.** Ask the owner to add a custom MCP connector: name `model-connector`, command `python3`, args `DIR/connector.py mcp` (see DIR/MCP_REGISTRATION.md). Confirm its tools show up (e.g. `list_models` works).
4. **Alerts.** Follow DIR/WEBHOOK_SETUP.md exactly: pick and save a bot_id, create the webhook routine "Model connector alerts", have the owner copy its URL and key, and collect both through the masked form. Never ask for them in chat and never echo them.
5. **Default model.** Run /changem (the changem skill).
6. **Decision desk.** Set it up per the decision-desk skill, including its optional call-reminder question (cadence, quiet hours; chat reminder if no calling). Explain it in one line.
7. **Verify end to end.** Start a tiny task with start_task (prompt "Reply with exactly: CONNECTOR_OK", timeout_seconds 300) and end your turn without waiting. When the alert wakes you through the routine, report the reply, acknowledge the event, and say "Setup verified: the alert woke me." No wakeup within ~5 min: run `python3 DIR/connector.py doctor BOT_ID`, check the routine is active, redo step 4.

Finish with one short message: what's set up, the default model, and "send me a task, or say /changem to switch models."
Never put secrets in chat, memory or files. No timed polling routines.
