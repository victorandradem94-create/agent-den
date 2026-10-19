# Architecture

One small ARM64 VM, four long-running Python processes, one timer. No Docker,
no orchestrator, no database.

```mermaid
flowchart LR
  subgraph Slack
    WS[Socket Mode WebSocket]
    OAUTH[oauth.v2.access]
  end
  subgraph VM["Oracle Cloud Always Free VM (Ubuntu 24.04 ARM64)"]
    direction TB
    SD["systemd --user (linger on)"]
    SD --> A1[agentden-dudu]
    SD --> A2[agentden-bubu]
    SD --> A3[agentden-kuro]
    SD --> A4[agentden-mimi]
    T[agentden-guardian.timer\nOnCalendar=*:0/5] --> G[agentden-guardian.service\nType=oneshot]
    G -- "state / receipts / markers\n(.guardian_*)" --> FS[(project dir, 0600)]
    A3 -- heartbeat --> FS
    A4 -- heartbeat --> FS
    G -- "systemctl --user restart\n(once per rotation)" --> SD
  end
  A1 & A2 & A3 & A4 <--> WS
  A1 & A2 & A3 & A4 --> XAI[xAI / Grok API]
  G -. "slack_oauth plugin\n(only with --run)" .-> OAUTH
```

## Pieces

| Piece | Where | Notes |
| --- | --- | --- |
| Agents | `*_bot.py` (private) | Slack Bolt + Socket Mode, so no public HTTP endpoint is needed. |
| Units | `agentden generate` | `Restart=on-failure`, `RestartSec=10`, `UMask=0077`. |
| Persistence | `loginctl enable-linger` | User services run without an SSH session. |
| Guardian | `agentden.guardian` | Generic state machine; no provider code. |
| Slack plugin | `agentden.slack_oauth` | Only module that talks to an OAuth endpoint. |

## Guardian state machine

```mermaid
stateDiagram-v2
  [*] --> ok
  ok --> ok: not due (WAIT, exit 0)
  ok --> uncertain: due + --run (persisted BEFORE request)
  uncertain --> restart_pending: valid new receipt
  uncertain --> uncertain: any doubt — never auto-retried (exit 4)
  restart_pending --> restart_pending: restart requested / no proof yet (exit 5)
  restart_pending --> ok: fresh heartbeat, PID == MainPID, connected
```

Any inconsistency (incident marker, receipt/state mismatch, bad dates,
restart failure) returns **BLOCKED (exit 3)** without changing state.

## Exit codes

| Code | Meaning | Unit result |
| --- | --- | --- |
| 0 | OK / WAIT / step completed | success |
| 1 | unexpected error | failed |
| 2 | bad config / usage | failed |
| 3 | BLOCKED, human needed | failed |
| 4 | UNCERTAIN, do not retry | failed |
| 5 | PENDING restart/proof | success (`SuccessExitStatus=5 6`) |
| 6 | DUE, dry run | success |

With several agents, the worst code wins.
