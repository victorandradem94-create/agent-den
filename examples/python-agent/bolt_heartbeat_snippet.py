"""Sketch: heartbeat from a Slack Bolt Socket Mode app (not runnable alone).

Socket Mode client internals differ between slack_sdk versions, so treat
`is_connected()` as something to verify against YOUR installed version.
Unknown connection state must report connected=False (fail closed).
"""
import threading

from agentden.guardian.heartbeat import write_heartbeat


def start_heartbeat(handler, state_dir, agent, every=10):
    def loop():
        while True:
            try:
                connected = bool(handler.client.is_connected())
            except Exception:
                connected = False
            write_heartbeat(state_dir, agent, connected=connected)
            threading.Event().wait(every)

    threading.Thread(target=loop, daemon=True, name="agentden-heartbeat").start()

# app = App(token=...)                      # slack_bolt
# handler = SocketModeHandler(app, app_token)
# start_heartbeat(handler, "/home/ubuntu/agent-team", "kuro")
# handler.start()
