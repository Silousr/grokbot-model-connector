# Grok Bot Model Connector

Let a Grok Bot hand work to **Codex CLI** or **Claude Code** on your own
subscriptions, pick the model with clickable buttons, keep each bot's memory and
recent context across models, and wake the bot by itself when a task finishes,
fails, stalls, times out or is cancelled.

- Python 3.9+, standard library only. Linux or macOS.
- Local, single user: it runs on your bot's box with **your** signed-in CLIs. It is
  not a hosted service and never exposes a network port (except a one-time,
  loopback-only form for webhook setup).
- Ships with skills for a Grok Bot template (`template-skills/`).

## Install

On the machine where your bot runs (normally its box):

```sh
curl -fsSL https://raw.githubusercontent.com/Silousr/grokbot-model-connector/main/install.sh | bash
# or
git clone https://github.com/Silousr/grokbot-model-connector.git /workspace/model-connector
/workspace/model-connector/install.sh
```

The installer is safe to rerun. It checks Python, clones or updates the code
(`MODEL_CONNECTOR_DIR` picks the dir; default `/workspace/model-connector`, or
`~/model-connector` when `/workspace` isn't writable), creates `models.json` from
`models.example.json`, reports whether `codex` / `claude` are installed and signed
in (it never signs in for you), starts the alert supervisor and sets up a boot-time
start when it can (systemd user service, cron `@reboot`, or the Grok Bot box boot
hook with passwordless sudo). Then it prints the next steps.

Sign in to each CLI yourself: `codex login`, `claude auth login`.

## Connect it to your bot

1. Register the MCP server: see [MCP_REGISTRATION.md](MCP_REGISTRATION.md)
   (command `python3 <DIR>/connector.py mcp`, name `model-connector`).
2. Set up wakeup alerts: see [WEBHOOK_SETUP.md](WEBHOOK_SETUP.md). The bot creates a
   webhook routine, you paste its URL and key into a masked form, and the connector
   stores the key in its private store (`.state/secrets/`, mode 0600).
3. Check health: `python3 <DIR>/connector.py doctor <bot_id>`.

With the template skills, a new bot walks its owner through all of this in the
first conversation (`template-skills/getting-started.md`).

## Commands

```sh
python3 connector.py mcp                       # MCP stdio server (what Grok Bot runs)
python3 connector.py doctor [BOT_ID]           # CLIs, sign-in, supervisor, webhook (no secrets)
python3 connector.py webhook-form BOT_ID       # one-time masked form for webhook URL + key
python3 connector.py webhook-prompt BOT_ID     # same, hidden terminal prompt
python3 connector.py call list_models
python3 connector.py call model_choices
python3 connector.py call set_bot_default '{"bot_id":"my-bot","model":"claude-opus"}'
python3 connector.py call start_task '{"bot_id":"my-bot","prompt":"Create hello.py","required_artifacts":["hello.py"]}'
python3 connector.py call get_task '{"task_id":"TASK_ID"}'
python3 connector.py call list_events '{"bot_id":"my-bot"}'
python3 connector.py call ack_events '{"bot_id":"my-bot","event_ids":[1]}'
python3 connector.py deliver-alerts            # alert sender loop (run by the supervisor)
python3 service.py start | status | run        # supervisor
```

`watch TASK_ID` and `wait-event TASK_ID` are manual inspection aids only; shell job
completion does not wake a Grok Bot.

## Models

Default order: per-task pick, then the bot's default (`set_bot_default`), then
`MODEL_CONNECTOR_DEFAULT` (else `codex`). `codex` and `claude` always exist and use
each CLI's default model. Add models your account can use in `models.json`:

```json
{"my-codex-model": {"provider": "codex", "model": "EXACT_MODEL_ID", "label": "Codex · My model"}}
```

Labels start with the provider so option buttons can group them. Installed does
not mean signed in or entitled to a model; your plan's rules apply.

## How alerts work

Workers watch each task for silence (`idle_seconds`, default 180) and overall time
(`timeout_seconds`, default 1800). On completed, failed, timed_out, stalled or
cancelled, the connector POSTs `{event_id, task_id, bot_id, kind, message}` with
`Authorization: Bearer <key>` to the bot's webhook routine. The body never contains
prompts or model output. HTTPS only (HTTP for loopback tests), redirects refused,
5 s timeout, exponential retries up to 5 min, durable receipts, stable
`Idempotency-Key`. Events older than the webhook registration and acknowledged
events are never sent. A supervisor (`service.py`) keeps `deliver-alerts` running
and restarts it 2 s after a crash; the MCP server also starts the supervisor each
time the host launches it. Task workers are never restarted automatically, to avoid
repeating side effects.

`completed` means the CLI exited with an answer, not that the goal was met
(`completion_verified` is always false). Pass `required_artifacts` for build work:
an answer without those files changed becomes `failed`.

Codex runs with `--sandbox workspace-write`; Claude with `--permission-mode
dontAsk`. Each bot gets its own workspace under `workspaces/`. This is trusted
single-user software, not a tenant boundary.

## Data and privacy

`.state/` holds the SQLite database (tasks, bot memory, events), run logs and the
secret store. It is created with owner-only permissions and git-ignored. Relocate
with `MODEL_CONNECTOR_STATE` / `MODEL_CONNECTOR_WORKSPACE`. Never share `.state/`,
`workspaces/` or CLI credentials.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Fake CLIs cover provider switching, context isolation, defaults, artifact gates,
failures, stalls, timeouts, cancellation, webhook delivery and retries, the secret
store and masked form, supervisor restart and singleton, and the MCP wire format.

## License

MIT. See `LICENSE`.
Codex and Claude Code are separate products under their own terms; this project
only calls the CLIs you install and sign in to.
