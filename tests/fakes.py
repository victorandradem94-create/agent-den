"""Test doubles. Nothing here touches the network or systemd."""
from datetime import datetime, timedelta, timezone


class FakeClock:
    def __init__(self, start=None):
        self.now = start or datetime.now(timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


class FakeRotator:
    def __init__(self, expires_in=43200, error=None):
        self.expires_in, self.error, self.calls = expires_in, error, []

    def rotate(self, agent):
        self.calls.append(agent)
        if self.error:
            raise self.error
        return self.expires_in


class FakeSystemd:
    def __init__(self, pid=4242, fail=False):
        self.pid, self.fail, self.restarts = pid, fail, []

    def restart(self, service):
        self.restarts.append(service)
        if self.fail:
            raise RuntimeError("boom")

    def main_pid(self, service):
        return self.pid
