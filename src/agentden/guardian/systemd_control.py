"""The two systemctl calls the Guardian needs. The runner is injectable for tests."""
import re
import subprocess

SERVICE = re.compile(r"^[A-Za-z0-9_.@-]+\.service$")


def _default_runner(argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=30, check=True).stdout


class SystemdUser:
    def __init__(self, runner=_default_runner):
        self.runner = runner

    @staticmethod
    def _check(service):
        if not isinstance(service, str) or not SERVICE.fullmatch(service):
            raise ValueError("invalid service name")
        return service

    def restart(self, service):
        self.runner(["systemctl", "--user", "restart", self._check(service)])

    def main_pid(self, service):
        out = self.runner(["systemctl", "--user", "show", self._check(service), "--property=MainPID", "--value"])
        value = (out or "").strip()
        return int(value) if value.isdigit() and int(value) > 0 else None
