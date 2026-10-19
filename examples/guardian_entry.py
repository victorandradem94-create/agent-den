#!/usr/bin/env python3
"""Entry point referenced by agentden-guardian.service.

Dry run by default. Real refresh/restart happens only when systemd passes
--run, which you add to ExecStart by hand after review.
"""
import sys
from pathlib import Path

from agentden.cli import main

CONFIG = Path(__file__).resolve().parent / "agentden.json"
raise SystemExit(main(["guardian", str(CONFIG), *sys.argv[1:]]))
