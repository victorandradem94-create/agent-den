"""`agentden` command line: validate/generate systemd units, run the Guardian."""
import argparse
import json
import sys
from pathlib import Path

from . import __version__, systemd
from .guardian import supervisor as sv


def _guardian(args):
    try:
        cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))["guardian_runtime"]
        base = cfg["state_dir"]
        services = {a: f"{systemd.PREFIX}-{a}.service" for a in cfg["agents"]}
        if cfg.get("rotator") != "slack":
            raise ValueError("only rotator 'slack' is bundled")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: bad guardian config: {exc}", file=sys.stderr)
        return sv.EXIT_USAGE
    from .guardian.systemd_control import SystemdUser
    from .slack_oauth import SlackRotator

    guardian = sv.Guardian(base, services, SlackRotator(cfg["env_file"]), SystemdUser())
    print("GUARDIAN", "REAL OPERATIONS" if args.run else "DRY RUN")
    results = guardian.run_once(run=args.run)
    for agent, res in results.items():
        print(f"  {agent}: [{res.code}] {res.message}")
    code = sv.worst(r.code for r in results.values())
    print(f"exit={code}")
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agentden", description="Run a few Python agents on one VM, carefully.")
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command", required=True)
    v = subs.add_parser("validate", help="validate a config without writing anything")
    v.add_argument("config")
    g = subs.add_parser("generate", help="write systemd user units to a local folder")
    g.add_argument("config")
    g.add_argument("--output", required=True)
    gd = subs.add_parser("guardian", help="one Guardian pass (dry run unless --run)")
    gd.add_argument("config")
    gd.add_argument("--run", action="store_true", help="allow REAL refresh and restart")
    args = parser.parse_args(argv)

    if args.command == "guardian":
        return _guardian(args)
    try:
        config = systemd.load_config(args.config)
        if args.command == "validate":
            print("OK: config is valid")
        else:
            for path in systemd.generate(config, args.output):
                print(f"WROTE {path}")
            print("Review the files before installing. Nothing was deployed.")
        return 0
    except (OSError, ValueError) as exc:  # JSONDecodeError is a ValueError
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
