# Lessons learned

1. **One instance per credential.** Socket Mode happily accepts two clients
   with the same token; events get split and it looks like flaky AI. Stop the
   old host first.
2. **Don't copy runtime state.** Old lock/heartbeat files from the laptop made
   the new host believe things that weren't true. Copy code and `.env` only.
3. **`OnCalendar` beats `OnBootSec` + `OnUnitActiveSec`** for a simple
   periodic oneshot: the latter showed no next run in our setup.
4. **`inactive (dead)` + `status=0/SUCCESS` is healthy** for a oneshot.
   Exit codes are how it talks; the v0.1 Guardian always exited 0 and printed
   errors as text, so systemd never saw a failure. Fixed in v0.2.
5. **Refresh tokens may be single-use.** If you can't tell whether a refresh
   reached the provider, stop. A blind retry can lock the bot out for good.
6. **A PID is not proof.** We require a heartbeat from the *new* MainPID that
   says it is connected. Even that isn't proof the agent can answer.
7. **Names are case-sensitive.** `Kuro` vs `kuro` broke a lookup; v0.2 uses
   lowercase identifiers everywhere.
8. **Leftover comments lie.** A "wait for launchd" comment survived the move
   to Linux. Port the comments too.
9. **Free tier is a constraint, not a feature.** Design so moving to a $5 VM
   is a config change.
