# Rollback

Golden rule: **stop the VM agents before starting the old ones.** Never both.

```bash
# on the VM
systemctl --user disable --now agentden-guardian.timer
systemctl --user stop agentden-dudu agentden-bubu agentden-kuro agentden-mimi
systemctl --user is-active agentden-kuro   # expect: inactive
```
Then start the agents on the old host.

## Tokens after a rotation
If the Guardian rotated a token on the VM, the old host's `.env` holds a
**dead refresh token**. Copy the current values from the VM `.env` (or
`.token_recovery_<agent>`) over a private channel before starting there.

## Guardian stuck
- `UNCERTAIN` (exit 4): check the Slack app / provider dashboard, find which
  token is valid, fix `.env` by hand, write a fresh receipt + `ok` state.
- `BLOCKED` (exit 3): read the reason in the journal; an incident file is
  removed by a human only after the cause is understood.
- `PENDING` for a long time: the agent never reported a connected heartbeat
  from its new PID. Check `journalctl --user -u agentden-<agent>`.
