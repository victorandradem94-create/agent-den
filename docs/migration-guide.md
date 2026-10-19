# Migration guide (supervised)

A procedure, not a deploy script. Review every step.

## 1. Prepare
- Inventory scripts, dependencies, token types (rotating or not).
- Back up the project and keep a private copy of `.env`.
- Plan a window: the old and new hosts must never run at the same time.
- Read the current Oracle Always Free terms; they can change.

## 2. Server
```bash
python3 --version
mkdir -p ~/agent-team && python3 -m venv ~/agent-team/.venv
~/agent-team/.venv/bin/pip install -r requirements.txt   # pinned, trusted
~/agent-team/.venv/bin/pip install /path/to/agent-den      # this package
```
Copy only what you need (exclude `.git`, caches, keys, `.token_*`, `.guardian_*`).
Put `.env` in place with `chmod 600`.

## 3. Generate units locally
```bash
agentden validate sample-config.json
agentden generate sample-config.json --output ./generated
```

## 4. Install
```bash
mkdir -p ~/.config/systemd/user
cp generated/*.service generated/*.timer ~/.config/systemd/user/
systemctl --user daemon-reload
sudo loginctl enable-linger "$USER"
systemctl --user enable --now agentden-dudu.service   # after stopping the old host's copy
```
Repeat per agent. Confirm each one actually answers in Slack.

## 5. Guardian
Copy `examples/guardian_entry.py` and your config (as `agentden.json`) to the
project dir. Bootstrap a first receipt/state per rotating agent (see
`agentden.guardian.supervisor.initial_state`). Then:
```bash
systemctl --user enable --now agentden-guardian.timer
systemctl --user list-timers --all agentden-guardian.timer
journalctl --user -u agentden-guardian.service -n 30 --no-pager
```
Only after several clean dry runs, add `--run` to `ExecStart` by hand.

## 6. Verify
`scripts/healthcheck.sh`. Keep the old host's copy intact (but stopped) until
a real rotation and a VM reboot have both been observed. See [rollback](rollback.md).
