"""Heartbeat helper for the agent side.

Call `write_heartbeat(base, "kuro", connected=...)` every ~10 s from the bot
process. The Guardian accepts it as restart proof only if the PID matches
systemd's MainPID, connected is true and it is fresh. That proves a live
connection, NOT that the agent can answer a real message.
"""
import json
import os
import time

from .store import Store, atomic_write


def write_heartbeat(base, agent, connected, clock=time.time):
    store = Store(base, agent)
    atomic_write(store.heartbeat_path, json.dumps({
        "agent": agent, "pid": os.getpid(), "connected": connected is True, "timestamp": clock(),
    }))
