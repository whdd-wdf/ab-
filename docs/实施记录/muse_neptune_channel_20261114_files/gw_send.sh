#!/bin/bash
# gw_send.sh — send a message to Neptune (OpenClaw main agent) via gateway chat.send.
# Token is sourced from ~/sys2/config/openclaw.env at runtime (never printed).
# Usage: gw_send.sh <sessionKey> "<message>" [timeout-ms]
set -e
# shellcheck disable=SC1091
source /home/madaha/sys2/config/openclaw.env
export PATH=/home/madaha/node-v24/bin:$PATH
SESSION_KEY="$1"
MSG="$2"
TIMEOUT="${3:-120000}"
PARAMS=$(python3 -c "import json,sys,uuid; print(json.dumps({'sessionKey': sys.argv[1], 'message': sys.argv[2], 'idempotencyKey': str(uuid.uuid4())}, ensure_ascii=False))" "$SESSION_KEY" "$MSG")
openclaw gateway call chat.send --token "$OPENCLAW_GATEWAY_TOKEN" --port 18789 --json --params "$PARAMS" --timeout "$TIMEOUT"
