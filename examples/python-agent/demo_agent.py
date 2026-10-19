"""Minimal long-running agent: no Slack, no credentials, no network.

Shows the two things a systemd-managed agent should do: exit cleanly on
SIGTERM and (optionally) write a heartbeat the Guardian can verify.
"""
import os
import signal
import time

running = True


def stop(_signum, _frame):
    global running
    running = False


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
state_dir = os.environ.get("AGENTDEN_STATE_DIR")  # e.g. the project dir
print("demo agent started", flush=True)
while running:
    if state_dir:
        from agentden.guardian.heartbeat import write_heartbeat
        write_heartbeat(state_dir, "demo", connected=True)
    time.sleep(2)
print("demo agent stopped", flush=True)
