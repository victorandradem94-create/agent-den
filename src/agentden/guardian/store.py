"""State files, receipts, markers and a per-agent lock, all under one directory.

File layout (all private, mode 0600, all matched by .gitignore):
  .guardian_state_<agent>.json      {"status", "rotation_id", "next_rotation_at", ...}
  .guardian_receipt_<agent>.json    last completed rotation (no secrets)
  .guardian_incident_<agent>        presence = stop, a human must look
  .guardian_restart_<agent>_<id>    written BEFORE the single restart attempt
  .guardian_heartbeat_<agent>.json  written by the agent itself
  .guardian_lock_<agent>            flock target
"""
import contextlib
import fcntl
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

AGENT = re.compile(r"^[a-z][a-z0-9-]{0,39}$")

# The only legal transitions. Anything else is a bug or tampering -> refuse.
TRANSITIONS = {
    "ok": {"uncertain"},
    "uncertain": {"restart_pending"},
    "restart_pending": {"ok"},
}


class TransitionError(RuntimeError):
    pass


def parse_utc(value):
    """Parse an ISO-8601 timestamp that MUST carry a timezone."""
    if not isinstance(value, str):
        raise ValueError("timestamp missing or not a string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp without timezone")
    return dt.astimezone(timezone.utc)


def atomic_write(path, text):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=".guardian_tmp_", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Store:
    def __init__(self, base, agent):
        if not isinstance(agent, str) or not AGENT.fullmatch(agent):
            raise ValueError("invalid agent name")
        self.base = Path(base)
        self.agent = agent

    def _p(self, kind, suffix=""):
        return self.base / f".guardian_{kind}_{self.agent}{suffix}"

    @property
    def state_path(self):
        return self._p("state", ".json")

    @property
    def receipt_path(self):
        return self._p("receipt", ".json")

    @property
    def incident_path(self):
        return self._p("incident")

    @property
    def heartbeat_path(self):
        return self._p("heartbeat", ".json")

    def restart_marker(self, rotation_id):
        if not re.fullmatch(r"[0-9a-f-]{36}", str(rotation_id)):
            raise ValueError("invalid rotation id")
        return self._p("restart", f"_{rotation_id}")

    @contextlib.contextmanager
    def lock(self):
        fd = os.open(self._p("lock"), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # never queue up behind a stuck run
            yield
        finally:
            os.close(fd)

    @staticmethod
    def _load(path):
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ValueError(f"{Path(path).name} is not a JSON object")
        return obj

    def load_state(self):
        return self._load(self.state_path)

    def load_receipt(self):
        return self._load(self.receipt_path)

    def save_state(self, state):
        atomic_write(self.state_path, json.dumps(state, indent=2, sort_keys=True))

    def save_receipt(self, receipt):
        atomic_write(self.receipt_path, json.dumps(receipt, indent=2, sort_keys=True))

    def mark_incident(self, reason):
        atomic_write(self.incident_path, f"REVIEW_REQUIRED\nreason={reason}\n")

    def transition(self, src, dst, now, **fields):
        state = self.load_state()
        if state.get("status") != src:
            raise TransitionError(f"expected status {src!r}, found {state.get('status')!r}")
        if dst not in TRANSITIONS.get(src, set()):
            raise TransitionError(f"transition {src} -> {dst} not allowed")
        state.update(fields)
        state["status"] = dst
        state["updated_at"] = now.isoformat()
        self.save_state(state)
        return state
