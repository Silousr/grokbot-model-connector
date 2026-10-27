#!/usr/bin/env bash
# Idempotent installer for the Grok Bot model connector.
# Usage (from a clone):    ./install.sh
# Usage (fresh box):       curl -fsSL https://raw.githubusercontent.com/Silousr/grokbot-model-connector/main/install.sh | bash
# Options (env vars):
#   MODEL_CONNECTOR_DIR   install dir (default /workspace/model-connector if /workspace is writable, else ~/model-connector)
#   MODEL_CONNECTOR_REPO  git URL (default https://github.com/Silousr/grokbot-model-connector.git)
#   MODEL_CONNECTOR_BOOT  auto | systemd | cron | boot-hook | none   (default auto)
# Never signs in to anything, never asks for or prints secrets.
set -euo pipefail

REPO="${MODEL_CONNECTOR_REPO:-https://github.com/Silousr/grokbot-model-connector.git}"
BOOT_MODE="${MODEL_CONNECTOR_BOOT:-auto}"
say() { printf '%s\n' "$*"; }
ok() { printf '  [ok] %s\n' "$*"; }
warn() { printf '  [!!] %s\n' "$*"; }

# Running from inside a clone installs in place.
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -z "${MODEL_CONNECTOR_DIR:-}" ] && [ -f "$SELF_DIR/connector.py" ] && [ -f "$SELF_DIR/service.py" ]; then
  DIR="$SELF_DIR"
elif [ -n "${MODEL_CONNECTOR_DIR:-}" ]; then
  DIR="$MODEL_CONNECTOR_DIR"
elif [ -d /workspace ] && [ -w /workspace ]; then
  DIR=/workspace/model-connector
else
  DIR="$HOME/model-connector"
fi

say "Model connector installer"
say "1) Requirements"
command -v python3 >/dev/null || { warn "python3 not found. Install Python 3.9+ and rerun."; exit 1; }
python3 - <<'PY' || { warn "Python 3.9+ with sqlite3 is required."; exit 1; }
import sys, sqlite3
sys.exit(0 if sys.version_info >= (3, 9) else 1)
PY
ok "python3 $(python3 -c 'import sys;print(sys.version.split()[0])') with sqlite3 (no pip packages needed)"
case "$(uname -s)" in Linux|Darwin) ok "OS $(uname -s)";; *) warn "Untested OS $(uname -s); Linux or macOS expected";; esac

say "2) Code in $DIR"
if [ -f "$DIR/connector.py" ] && [ -d "$DIR/.git" ]; then
  if git -C "$DIR" remote get-url origin >/dev/null 2>&1; then
    git -C "$DIR" pull --ff-only --quiet && ok "updated (git pull)" || warn "could not fast-forward; left as is"
  else
    ok "local checkout (no remote); left as is"
  fi
elif [ -f "$DIR/connector.py" ]; then
  ok "existing install found (not a git clone); left as is"
elif [ -e "$DIR" ] && [ -n "$(ls -A "$DIR" 2>/dev/null)" ]; then
  warn "$DIR exists and is not a connector install. Set MODEL_CONNECTOR_DIR to another path."; exit 1
else
  command -v git >/dev/null || { warn "git not found; install git or download the repo manually."; exit 1; }
  git clone --quiet "$REPO" "$DIR" && ok "cloned $REPO"
fi
cd "$DIR"
umask 077
mkdir -p .state && chmod 700 .state
[ -f models.json ] || { cp models.example.json models.json; ok "created models.json from models.example.json"; }
python3 connector.py version >/dev/null && ok "connector runs (v$(python3 connector.py version))"

say "3) Model CLIs (report only; this script never signs in)"
for cli in codex claude; do
  if command -v "$cli" >/dev/null; then
    if [ "$cli" = codex ]; then st=(codex login status); else st=(claude auth status); fi
    if "${st[@]}" </dev/null >/dev/null 2>&1; then ok "$cli installed and signed in"
    else warn "$cli installed but NOT signed in. Run: $([ "$cli" = codex ] && echo 'codex login' || echo 'claude auth login')"; fi
  else
    warn "$cli not installed. $([ "$cli" = codex ] && echo 'npm i -g @openai/codex' || echo 'npm i -g @anthropic-ai/claude-code') then sign in"
  fi
done

say "4) Alert supervisor (keeps webhook alerts sending)"
SUP="$(command -v python3) $DIR/service.py start"
boot_done=""
want() { [ "$BOOT_MODE" = auto ] || [ "$BOOT_MODE" = "$1" ]; }
if [ -z "$boot_done" ] && want systemd && command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
  unit="$HOME/.config/systemd/user/model-connector-alerts.service"
  mkdir -p "$(dirname "$unit")"
  cat > "$unit" <<UNIT
[Unit]
Description=Model connector alert supervisor
[Service]
Type=simple
ExecStart=$(command -v python3) $DIR/service.py run
Restart=always
[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload && systemctl --user enable --now model-connector-alerts.service >/dev/null 2>&1 \
    && { ok "systemd user service enabled"; boot_done=1; } || warn "systemd user service could not be enabled"
fi
if [ -z "$boot_done" ] && want cron && command -v crontab >/dev/null && pgrep -x cron >/dev/null 2>&1; then
  line="@reboot $SUP # model-connector"
  ( crontab -l 2>/dev/null | grep -v '# model-connector$'; echo "$line" ) | crontab - && { ok "cron @reboot entry set"; boot_done=1; }
fi
if [ -z "$boot_done" ] && want boot-hook && [ -f /usr/local/bin/start-sand-box ]; then
  if sudo -n true 2>/dev/null; then
    sudo -n "$(command -v python3)" "$DIR/service.py" install-hook && boot_done=1 || warn "boot hook not installed"
  else
    warn "Grok Bot box boot script found but no passwordless sudo; skipping boot hook"
  fi
fi
python3 service.py start
sleep 2
if python3 service.py status >/dev/null; then ok "supervisor running now"; else warn "supervisor not running; check .state/supervisor.log"; fi
[ -n "$boot_done" ] || warn "No boot-time start available. That's OK: the connector restarts the supervisor every time the bot launches its MCP server."

say ""
say "Done. Next steps:"
say "  a) In Grok Bot, add a custom MCP connector named model-connector:"
say "       command: python3"
say "       args:    $DIR/connector.py mcp"
say "     (JSON: {\"mcpServers\":{\"model-connector\":{\"command\":\"python3\",\"args\":[\"$DIR/connector.py\",\"mcp\"]}}})"
say "  b) Sign in to any CLI marked [!!] above, in its own terminal."
say "  c) Ask your bot to set up webhook alerts (see WEBHOOK_SETUP.md). The key goes in a masked form, never chat."
say "  d) Health check any time: python3 $DIR/connector.py doctor YOUR_BOT_ID"
