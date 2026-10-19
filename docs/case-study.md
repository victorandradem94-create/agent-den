# Case study: four Slack agents from a laptop to a free VM

## The journey
1. **Terminal on macOS.** Four Python agents (Dudu, Bubu, Kuro, Mimi) started
   by hand from Terminal on a MacBook Air.
2. **launchd on macOS.** Each agent became a LaunchAgent (plist with
   `KeepAlive`), plus a token supervisor, *Slack Token Guardian*, run
   periodically via `StartInterval`.
3. **systemd on Ubuntu (cloud).** For the move to Oracle Cloud, launchd was
   replaced by `systemd --user` services, `loginctl enable-linger`, and a
   systemd timer (`OnCalendar`) instead of `StartInterval`.

| macOS (launchd) | Ubuntu (systemd) |
| --- | --- |
| `KeepAlive` in a LaunchAgent plist | `Restart=on-failure` |
| `StartInterval` (Guardian) | `.timer` with `OnCalendar=*:0/5` |
| `~/Library/LaunchAgents/` | `~/.config/systemd/user/` |
| `launchctl` | `systemctl --user` |
| runs while the user is logged in | `loginctl enable-linger` |

One leftover: a "wait for launchd" comment and sleep loop survived in the
Guardian after the move to Linux (fixed in v0.2, see [guardian-review](guardian-review.md)).

## After
- Oracle Cloud `VM.Standard.A1.Flex`, 2 OCPU / 12 GB, Ubuntu 24.04 LTS ARM64.
- User `ubuntu`, project in `~/<project>` with a `.venv` (Python 3.12):
  `slack-bolt`, `python-dotenv`, `xai-sdk`, `requests`.
- Four `systemd --user` services, `Restart=on-failure`, linger enabled.
- Guardian as a `oneshot` service on a 5-minute `OnCalendar` timer, handling
  token rotation for Kuro and Mimi only (Dudu and Bubu use non-rotating tokens).
- The Mac copy was stopped before the VM copy started: two Socket Mode
  clients with the same credentials split events between them.

## Evidence (2026-10-19)
- All four agents answered in Slack after the move.
- The timer ran the Guardian in dry run at 16:20:25 CST (22:20:25 UTC).
- A manual run with real operations enabled at 16:26:47 CST returned
  `WAIT: no OAuth request` for both agents — correct, nothing was due.

## Not yet verified
- The first **real** token rotation in production.
- Full recovery after a VM reboot (services + linger + timer).

`WAIT` with real operations enabled proves the guard rails don't fire
spuriously. It does **not** prove the refresh path works.

The VM IP, SSH key names and all credentials are deliberately omitted.
