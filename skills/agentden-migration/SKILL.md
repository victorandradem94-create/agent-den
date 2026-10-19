---
name: agentden-migration
description: Guide a supervised move of long-running Python agents from a laptop to an Ubuntu VM with systemd user services. Never changes anything without explicit approval.
---

# agentden migration skill

## When to use
Someone wants to move a Python agent (e.g. a Slack Bolt bot) from macOS/Linux
to an Ubuntu server with persistent processes and logs.

## Hard rules
1. Inspect structure, dependencies, permissions and target first. Never ask
   the user to paste secrets.
2. Separate "documented in the case study" from "tested in this environment".
3. Present a plan with risks, backup, test and rollback before acting.
4. Ask for approval before SSH, file copies, stopping services or token rotation.
5. Never run the old and new host at the same time with the same tokens.
6. Never copy private keys or old lock/heartbeat/state files.
7. Verify with systemd **and** a real reply from the agent; a PID is not success.
8. If a token refresh outcome is uncertain, block retries and escalate.
9. One command per step if the user prefers.

## Flow
1. **Diagnose:** OS, Python, framework, deps, auth type, target, budget.
2. **Prepare:** inventory, backup, private secrets, change window.
3. **Generate:** `agentden validate` / `agentden generate` with an adapted config.
4. **Review:** paths, names, `ExecStart`, permissions.
5. **Deploy (supervised):** install deps, stop the source, enable target services.
6. **Validate:** logs, real reply, timers, linger, `scripts/healthcheck.sh`.
7. **Hand over:** maintenance checklist, rollback (`docs/rollback.md`), what is still unverified.

## Tools available
```bash
agentden validate sample-config.json
agentden generate sample-config.json --output ./generated
agentden guardian agentden.json          # dry run; --run only with explicit approval
```
There is no automated SSH deploy. Do not invent commands or results.
