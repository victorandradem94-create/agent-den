# agent-den 🐻

**How I run a team of 4 AI agents in production on a zero budget — and what I learned.**

[Español](README.es.md) · [![CI](https://github.com/Victorandrade94/agent-den/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)

Four Slack agents (Python, Slack Bolt, Socket Mode, Grok via the xAI API) run
24/7 on an Oracle Cloud Always Free ARM64 VM, as plain `systemd --user`
services. No Docker, no Kubernetes, no paid monitoring.

This is not a tool everyone needs. It is a write-up of a real setup plus the
two small pieces of code I wish I'd had: a **safe systemd unit generator**
and a **fail-closed token-rotation Guardian**. It started life as
*Osito Cloud Migrator*; `agentden` is the generic name.

## The journey

Terminal on macOS → **launchd** LaunchAgents (`KeepAlive`) plus a token
supervisor, *Slack Token Guardian* (`StartInterval`) → Ubuntu in the cloud
with **systemd user services**, `loginctl enable-linger` and an `OnCalendar`
timer. Details in the [case study](docs/case-study.md).

| macOS (launchd) | Ubuntu (systemd) |
| --- | --- |
| `KeepAlive` in a LaunchAgent plist | `Restart=on-failure` |
| `StartInterval` (Guardian) | `.timer` with `OnCalendar=*:0/5` |
| `~/Library/LaunchAgents/` | `~/.config/systemd/user/` |
| `launchctl` | `systemctl --user` |
| runs while the user is logged in | `loginctl enable-linger` |

A leftover "wait for launchd" comment/loop survived the port; v0.2 removes it.

## Status / what is verified

| Claim | Status |
| --- | --- |
| 4 agents answer in Slack from the VM | ✅ observed 2026-10-19 |
| Services survive SSH logout (linger) | ✅ observed |
| Guardian timer fires every 5 min (`OnCalendar`) | ✅ observed |
| Guardian with real ops returns `WAIT` when nothing is due | ✅ observed (original Guardian) |
| First **real** OAuth rotation in production | ⏳ **not yet observed** |
| Full recovery after a **VM reboot** | ⏳ **not yet tested** |
| v0.2 Guardian (this repo) running in production | ⏳ not deployed yet; unit-tested with fakes |
| Slack plugin against the real Slack API | ⏳ unit-tested with fakes only |

## What's inside

```text
src/agentden/systemd.py         validate config, generate systemd user units (local only)
src/agentden/guardian/          generic state machine: ok → uncertain → restart_pending → ok
src/agentden/slack_oauth.py     optional Slack refresh plugin (stdlib, injectable)
examples/                       generated units, demo agent, Bolt heartbeat sketch
scripts/healthcheck.sh          read-only checks on the VM
skills/agentden-migration/      procedure for AI assistants helping with a migration
docs/                           architecture, case study, lessons, security, guides
```

## Quick start (no network, no servers)

```bash
python3 -m unittest discover -s tests -t . -v      # or: pip install -e . && agentden ...
PYTHONPATH=src python3 -m agentden validate sample-config.json
PYTHONPATH=src python3 -m agentden generate sample-config.json --output ./generated
```

The generator only writes files to `--output`. It never runs SSH or
`systemctl`, and it refuses to generate a Guardian with real operations.

## The Guardian in one paragraph

Some Slack tokens rotate; the refresh token may be single-use. So the Guardian
persists `uncertain` **before** asking for a new token, and if anything is
unclear afterwards it stays `uncertain` and exits 4 — it never retries on its
own. After a valid receipt it restarts the agent **once** and only returns to
`ok` when the *new* process writes a connected heartbeat. Dry run is the
default. See [architecture](docs/architecture.md) and
[what changed from the original](docs/guardian-review.md).

## Docs

- [Architecture (mermaid)](docs/architecture.md) · [Case study](docs/case-study.md) · [Lessons learned](docs/lessons-learned.md)
- [Security model](docs/security.md) · [Migration guide](docs/migration-guide.md) · [Rollback](docs/rollback.md) · [Cost notes](docs/cost-notes.md)

## Honest limits

One VM is a single point of failure. "Always Free" is Oracle's offer, not a
promise from me. xAI usage costs money. A heartbeat proves a live connection,
not a correct answer.

## Author

Víctor Andrade ([@Victorandrade94](https://github.com/Victorandrade94)), Mexico —
learning ML and agent engineering by running real things. MIT licensed.
