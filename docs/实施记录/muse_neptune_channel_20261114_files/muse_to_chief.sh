#!/bin/bash
# muse_to_chief.sh — Muse -> Neptune (chief agent) via the file inbox.
# Appends ONE JSON line to ~/sys2/inbox/muse_to_chief.jsonl (Python json.dumps + "\n",
# so lines never stick together). The inbox_watcher (60s poll) delivers it to the
# chief agent via `openclaw agent --session-key agent:main:muse-inbox`.
# Usage: muse_to_chief.sh <kind> "<body>" [need_reply:true|false]
#   kind: 指令 | 复核 | 转群 | 请示 | 报警  (see inbox_watcher.py for handling rules)
#   body: message text (may contain newlines/Chinese; JSON-escaped by Python)
#   need_reply: true (default) or false
# Replies arrive in ~/sys2/inbox/chief_to_muse.jsonl — poll that file to read them.
# This is the CANONICAL Muse->Neptune channel. Do NOT use Feishu for Muse->Neptune:
# Feishu does not deliver bot-sent messages to another bot (verified 2026-11-14).
set -e
KIND="$1"
BODY="$2"
NEED_REPLY="${3:-true}"
python3 -c "
import json, sys, datetime
line = {
  'time': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%dT%H:%M:%S+08:00'),
  'from': 'Muse',
  'to': 'chief',
  'kind': sys.argv[1],
  'body': sys.argv[2],
  'need_reply': sys.argv[3].lower() == 'true',
}
with open('/home/madaha/sys2/inbox/muse_to_chief.jsonl', 'a', encoding='utf-8') as f:
    f.write(json.dumps(line, ensure_ascii=False) + '\n')
print('APPENDED kind=' + sys.argv[1])
" "$KIND" "$BODY" "$NEED_REPLY"
