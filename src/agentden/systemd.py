"""Safe generator of systemd *user* units for Python agents.

Writes files to a local output directory only. Never runs SSH, systemctl or
anything remote. Config values are validated with strict allowlist regexes so
nothing can be injected into an ExecStart line.
"""
import json
import re
from pathlib import Path

NAME = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
ENTRY = re.compile(r"^[A-Za-z0-9_-]+\.py$")
ABS = re.compile(r"^/[A-Za-z0-9_./-]+$")
PREFIX = "agentden"
# Minute steps that divide an hour evenly, so OnCalendar=*:0/N is regular.
ALLOWED_INTERVALS = (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30)
# Guardian exit codes that are expected transient states, not failures.
# See agentden.guardian.supervisor for the full table.
GUARDIAN_SUCCESS_EXIT = "5 6"


def _safe_path(value, key):
    if not isinstance(value, str) or not ABS.fullmatch(value) or ".." in value.split("/"):
        raise ValueError(f"unsafe path: {key}")


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    for key in ("project_name", "remote_user", "remote_directory", "python_path", "agents"):
        if key not in data:
            raise ValueError(f"missing key: {key}")
    for key in ("project_name", "remote_user"):
        if not isinstance(data[key], str) or not NAME.fullmatch(data[key]):
            raise ValueError(f"invalid {key}")
    _safe_path(data["remote_directory"], "remote_directory")
    _safe_path(data["python_path"], "python_path")
    agents = data["agents"]
    if not isinstance(agents, list) or not agents:
        raise ValueError("at least one agent is required")
    names = set()
    for agent in agents:
        if (not isinstance(agent, dict)
                or not isinstance(agent.get("name"), str) or not NAME.fullmatch(agent["name"])
                or not isinstance(agent.get("entrypoint"), str) or not ENTRY.fullmatch(agent["entrypoint"])):
            raise ValueError("invalid agent: needs a lowercase name and a plain file.py entrypoint")
        if agent["name"] in names or agent["name"] == "guardian":
            raise ValueError(f"duplicate or reserved agent name: {agent['name']}")
        names.add(agent["name"])
    guardian = data.get("guardian", {"enabled": False})
    if not isinstance(guardian, dict):
        raise ValueError("invalid guardian section")
    if guardian.get("enabled", False):
        if not isinstance(guardian.get("entrypoint"), str) or not ENTRY.fullmatch(guardian["entrypoint"]):
            raise ValueError("guardian needs a plain file.py entrypoint")
        interval = guardian.get("interval_minutes", 5)
        if isinstance(interval, bool) or interval not in ALLOWED_INTERVALS:
            raise ValueError(f"interval_minutes must be one of {ALLOWED_INTERVALS}")
        if guardian.get("real_operations", False) is not False:
            raise ValueError("the generator only emits a dry-run Guardian; add --run by hand after review")
    return data


def load_config(path):
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))


def agent_unit(config, agent):
    return f"""[Unit]
Description={PREFIX} agent - {agent['name']}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={config['remote_directory']}
ExecStart={config['python_path']} {config['remote_directory']}/{agent['entrypoint']}
Restart=on-failure
RestartSec=10
UMask=0077

[Install]
WantedBy=default.target
"""


def guardian_units(config):
    g = config["guardian"]
    interval = g.get("interval_minutes", 5)
    service = f"""[Unit]
Description={PREFIX} Guardian (dry run unless enabled by hand)
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory={config['remote_directory']}
ExecStart={config['python_path']} {config['remote_directory']}/{g['entrypoint']}
# 0 = ok/wait. 5 = restart pending, 6 = due (dry run): expected, not failures.
# 1 error, 3 blocked, 4 uncertain -> unit fails so OnFailure=/journal shows it.
SuccessExitStatus={GUARDIAN_SUCCESS_EXIT}
TimeoutStartSec=120
UMask=0077
"""
    timer = f"""[Unit]
Description={PREFIX} Guardian timer - every {interval} minutes

[Timer]
# OnCalendar, not OnBootSec+OnUnitActiveSec: the latter never re-armed for us.
OnCalendar=*:0/{interval}
AccuracySec=30s
Persistent=true
Unit={PREFIX}-guardian.service

[Install]
WantedBy=timers.target
"""
    return service, timer


def generate(config, output):
    dest = Path(output)
    dest.mkdir(parents=True, exist_ok=True)
    files = [(f"{PREFIX}-{a['name']}.service", agent_unit(config, a)) for a in config["agents"]]
    if config.get("guardian", {}).get("enabled", False):
        service, timer = guardian_units(config)
        files += [(f"{PREFIX}-guardian.service", service), (f"{PREFIX}-guardian.timer", timer)]
    paths = []
    for name, text in files:
        path = dest / name
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return paths
