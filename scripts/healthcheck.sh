#!/usr/bin/env bash
# Read-only health check. Run on the VM as the user that owns the services.
# Exits non-zero if any agent service is not active.
set -uo pipefail
AGENTS=${AGENTS:-"dudu bubu kuro mimi"}
PREFIX=${PREFIX:-agentden}
status=0
for a in $AGENTS; do
  state=$(systemctl --user is-active "${PREFIX}-${a}.service" 2>/dev/null)
  printf '%-28s %s\n' "${PREFIX}-${a}.service" "${state:-unknown}"
  [ "$state" = "active" ] || status=1
done
echo "--- linger (needed so services survive logout/reboot)"
loginctl show-user "$USER" --property=Linger 2>/dev/null || echo "unknown"
echo "--- guardian timer"
systemctl --user list-timers --all --no-pager "${PREFIX}-guardian.timer" || true
echo "--- guardian last result (oneshot: inactive/dead + status=0 is normal)"
systemctl --user show "${PREFIX}-guardian.service" --property=Result,ExecMainStatus --no-pager || true
journalctl --user -u "${PREFIX}-guardian.service" -n 15 --no-pager || true
exit $status
