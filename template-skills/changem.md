---
name: changem
description: Use when the owner calls /changem or asks to change, switch, or see which model this bot uses by default (Grok Bot itself, or a Codex/Claude model through the model connector).
---
# /changem: change this bot's default model

The model at the end of the bot's name (e.g. `Helper · Opus`) is the model it hands work to through the model connector (MCP server `model-connector`). `· Grok` means no handoff: the bot does the work itself. The bot's connector `bot_id` is in memory; if missing, use a short kebab-case form of the bot's name and save it.

1. Call `model_choices` for the current options (label + reply; labels start with the provider).
2. Ask with one option card in steps (at most 6 options per step): first "Grok Bot, Claude, or Codex?" (Grok Bot first), then "Which model?" with that provider's options (label without the provider prefix, value = the reply; if more than 6, show the 6 newest and allow a typed answer). Mark the current default `(current)`. No extra prose; the card is the ask.
3. Save the pick:
   - Grok Bot: no connector call. Short name `Grok`.
   - Codex/Claude: `set_bot_default` with this bot_id and the reply as `model`. Short name = the model's short label (`Opus`, `Sonnet`, ...).
4. Rename the bot to `<base name> · <short name>`, removing any existing ` · <model>` suffix first so it never stacks. Don't change the description.
5. Memory: "Default model is <Grok Bot | reply> (set via /changem on <date>)", replacing the old default fact.
6. Confirm in one sentence.

Always: the bot stays in charge (see model-handoff for what never leaves Grok Bot). If the owner names a model directly ("/changem opus"), skip the card. A per-task pick ("use Opus for this") overrides the default for that task only and doesn't rename the bot. If the connector isn't registered, say so and offer the getting-started steps.
