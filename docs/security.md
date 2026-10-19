# Security model

## What is protected
Slack tokens (access, refresh, client secret), the xAI API key, the SSH key and
the VM address. None of them are in this repo.

## Rules the code enforces
- Generator: allowlist regexes for names, entrypoints and absolute paths; `..`
  rejected; it refuses to emit a Guardian with real operations.
- Guardian: dry run unless `--run`; `uncertain` is persisted before any
  refresh; one restart per rotation (O_EXCL marker); everything else fails
  closed with a non-zero exit code.
- All state files are written atomically with mode `0600`; units use `UMask=0077`.
- Errors print exception *types* and env *key names*, never values.

## Rules you must follow
- `.env` is `chmod 600`, transferred over a private channel, never pasted in
  chats, issues or logs. Never pass tokens as command-line arguments.
- `.gitignore` does not un-track a secret already committed. Check
  `git status` and the diff before every push. Rotate anything that leaked.
- Never copy `.guardian_*` or `.token_*` files between machines.
- SSH: dedicated key per project, verify the host key, least privilege.
- Stopping services, overwriting `.env`, refreshing tokens or restarting
  agents needs a human decision.

## Threats not covered
A compromised VM user can read `.env`. There is no secret manager, no
alerting beyond systemd unit failure, no HA. That is the trade-off of a
zero-budget setup.
