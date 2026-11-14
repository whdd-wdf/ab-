#!/bin/bash
# gw_call.sh — call an OpenClaw gateway method.
# Token is sourced from ~/sys2/config/openclaw.env at runtime (never printed, never stored).
# Usage: gw_call.sh <method> [params-json] [timeout-ms]
set -e
# shellcheck disable=SC1091
source /home/madaha/sys2/config/openclaw.env
export PATH=/home/madaha/node-v24/bin:$PATH
METHOD="$1"
PARAMS="${2:-{}}"
TIMEOUT="${3:-30000}"
openclaw gateway call "$METHOD" --token "$OPENCLAW_GATEWAY_TOKEN" --port 18789 --json --params "$PARAMS" --timeout "$TIMEOUT"
