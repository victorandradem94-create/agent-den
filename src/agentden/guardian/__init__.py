"""Guardian: a small, fail-closed supervisor for credential rotation.

Generic parts live here (state machine, receipts, scheduling, systemd restart,
heartbeat proof). Provider-specific refresh logic (e.g. Slack OAuth) is a
separate, optional plugin: see agentden.slack_oauth.
"""
