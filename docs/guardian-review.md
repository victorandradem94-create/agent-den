# Guardian: what changed from the private original

The original Guardian (8 modules on the VM) worked for the cases observed,
but reviewing it before publishing found real issues. v0.2 is a rewrite of
the same design, not a copy.

| Original issue | v0.2 |
| --- | --- |
| Always exited 0; errors only as text | Explicit exit codes, worst wins |
| Token manager and receipts wrote to their own module dir, ignoring the `base` the supervisor passed | One `Store(base, agent)` for every file |
| Non-string `rotated_at` raised `AttributeError`, not in the caught list | Validation catches it → BLOCKED |
| Scheduler parsed dates without `Z` handling (Python < 3.11); others did | Single `parse_utc` |
| `Kuro` in state, `kuro` in heartbeat; mixed casing | Lowercase ids everywhere |
| "Wait for launchd" loop with `sleep` inside a 5-min oneshot | No sleeping; the next timer tick checks proof |
| Restart proof used marker mtime | Marker stores its own timestamp |
| Lock waited forever (`LOCK_EX`) | Non-blocking; overlapping run → PENDING |
| Agent names hard-coded in 5 files | Config-driven |
| Slack refresh, `.env` editing and generic flow mixed | `agentden.slack_oauth` is a separate plugin |
| Lock module (`guardian_lock.py`) not included in the review export | Re-implemented (`Store.lock`) |
| A failed restart left `restart_pending` with a marker, forever PENDING | Restart failure writes an incident → BLOCKED |
