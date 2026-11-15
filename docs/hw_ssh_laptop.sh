#!/bin/bash
# Huawei VPS SSH wrapper for the laptop (Hailongxia maintenance use).
# Channel 1: Tailscale direct (native Tailscale on the laptop, hw-vps 100.74.158.35).
# Channel 2: direct to public IP 123.60.222.204:22.
# Usage: hw_ssh.sh root@100.74.158.35 '<command>'
# Huawei-only: refuses any other host (no misrouting).
# Fallback ONLY on ssh exit 255 (connection/setup failure); a remote
# command's own non-zero exit is returned immediately without retry.
set -u
KEY="$HOME/.ssh/homeline_agent_ed25519"
KNOWN="$HOME/.ssh/known_hosts"
PUB_IP="123.60.222.204"
TS_IP="100.74.158.35"

args=("$@")
user="root"
host=""
cmd=()
if [ "${#args[@]}" -ge 3 ] && [ "${args[0]}" = "-l" ]; then
  user="${args[1]}"; host="${args[2]}"; cmd=("${args[@]:3}")
elif [ "${#args[@]}" -ge 1 ] && [[ "${args[0]}" == *@* ]]; then
  user="${args[0]%%@*}"; host="${args[0]##*@}"; cmd=("${args[@]:1}")
elif [ "${#args[@]}" -ge 1 ] && [[ "${args[0]}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ || "${args[0]}" = "hw-vps" ]]; then
  host="${args[0]}"; cmd=("${args[@]:1}")
else
  echo "[hw_ssh] cannot parse host from args: $*" >&2
  exit 2
fi
case "$host" in
  "$TS_IP"|"$PUB_IP"|"hw-vps") ;;
  *) echo "[hw_ssh] refusing non-Huawei host: $host" >&2; exit 2 ;;
esac

common=(-o "UserKnownHostsFile=$KNOWN" -i "$KEY")

# Attempt 1: Tailscale.
ssh -o ConnectTimeout=15 "${common[@]}" "$user@$TS_IP" "${cmd[@]}"
rc=$?
[ "$rc" -eq 0 ] && exit 0
[ "$rc" -ne 255 ] && exit "$rc"
echo "[hw_ssh] tailscale failed (rc=$rc), trying direct $PUB_IP" >&2

# Attempt 2: direct to public IP.
ssh -o ConnectTimeout=15 "${common[@]}" "$user@$PUB_IP" "${cmd[@]}"
rc=$?
[ "$rc" -eq 0 ] && exit 0
[ "$rc" -ne 255 ] && exit "$rc"
echo "[hw_ssh] all channels failed (last rc=$rc)" >&2
exit "$rc"
