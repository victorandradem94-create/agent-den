# Changelog

## 0.2.0 — 2026-10-19
- Renamed from *Osito Cloud Migrator* (`osito_cloud`) to `agentden`; units are now `agentden-*.service`.
- English docs with Spanish README; docs restructured (architecture, lessons, rollback, cost notes).
- New: sanitized, generalized Guardian (`agentden.guardian`) with explicit exit codes and unit tests.
- New: optional Slack OAuth plugin (`agentden.slack_oauth`), separated from the generic flow.
- Guardian unit sets `SuccessExitStatus=5 6` so transient states don't fail the unit, real problems do.
- Timer interval configurable (divisors of 60) while keeping `OnCalendar`.
- Generator rejects reserved name `guardian`; CLI returns exit codes instead of always 0.
- `pyproject.toml`, `agentden` console script, GitHub Actions CI.

## 0.1.0
- Case study, safe systemd generator (injection checks, no `--run`), tests, skill (Spanish).
