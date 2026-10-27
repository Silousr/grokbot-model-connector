# Registering the connector in Grok Bot

The connector is a local **stdio MCP server**: Grok Bot starts it on the same
machine (normally the bot's box) and talks newline-delimited JSON-RPC
(protocol 2024-11-05). There is no network listener.

Add it as a **custom MCP connector** (Grok Bot settings → Connectors → add custom
/ local MCP server):

| Field   | Value                                   |
|---------|-----------------------------------------|
| Name    | `model-connector`                       |
| Command | `python3`                               |
| Args    | `<DIR>/connector.py` `mcp`              |

`<DIR>` is the install dir (default `/workspace/model-connector`). JSON form, as in
`bot/mcp-config.json`:

```json
{"mcpServers":{"model-connector":{"command":"python3","args":["/workspace/model-connector/connector.py","mcp"]}}}
```

Use the name `model-connector` exactly: the skills expect its tools under that
server (they appear to the bot as the `user-model-connector` namespace). Tools:
`list_models`, `model_choices`, `set_bot_default`, `set_bot_memory`, `start_task`,
`get_task`, `list_tasks`, `cancel_task`, `list_events`, `ack_events`,
`set_bot_webhook`. `set_bot_webhook` only accepts a key *file path* or *env var
name*, never the key. For new users, `connector.py webhook-form` (see
WEBHOOK_SETUP.md) writes the key file and calls it, so no secret passes through
chat or a tool call.

Each time the host launches the server, it also starts the alert supervisor if it
isn't running (set `MODEL_CONNECTOR_AUTOSTART=0` to turn that off).

If the host can't run local MCP servers, the bot can use the same tools through
its shell: `python3 <DIR>/connector.py call TOOL 'JSON'`.
