"""Optional Slack plugin: refresh a rotating Slack token via oauth.v2.access.

Kept apart from the generic Guardian on purpose. It is the part that touches
real credentials, so it is small, stdlib-only and fully injectable.

Status: the request/persist path is unit-tested with fakes. A first REAL
rotation in production has NOT been observed yet (see README status table).

Env layout (.env, chmod 600), per agent name upper-cased:
  SLACK_ACCESS_TOKEN_<AGENT>, SLACK_REFRESH_TOKEN_<AGENT>,
  SLACK_CLIENT_ID_<AGENT>,    SLACK_CLIENT_SECRET_<AGENT>
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

from .guardian.store import atomic_write

OAUTH_URL = "https://slack.com/api/oauth.v2.access"


def _urllib_post(url, form, timeout=20):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
        return json.loads(resp.read().decode("utf-8"))


def read_env(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def update_env(path, changes):
    """Rewrite only the given keys, keep every other line, write atomically 0600."""
    lines, seen = [], set()
    for line in Path(path).read_text(encoding="utf-8").splitlines(keepends=True):
        key = line.split("=", 1)[0].strip()
        if key in changes:
            if key not in seen:
                lines.append(f"{key}={changes[key]}\n")
                seen.add(key)
        else:
            lines.append(line)
    lines += [f"{k}={v}\n" for k, v in changes.items() if k not in seen]
    atomic_write(path, "".join(lines))


class SlackRotator:
    def __init__(self, env_path, post=_urllib_post):
        self.env_path = Path(env_path)
        self.post = post

    @staticmethod
    def keys(agent):
        a = agent.upper().replace("-", "_")
        return {k: f"SLACK_{k.upper()}_{a}" for k in ("access_token", "refresh_token", "client_id", "client_secret")}

    def rotate(self, agent):
        """Return expires_in. Raise on anything unexpected (Guardian -> UNCERTAIN)."""
        keys = self.keys(agent)
        env = read_env(self.env_path)
        missing = [k for k, name in keys.items() if not env.get(name)]
        if missing:
            raise RuntimeError("missing credentials: " + ", ".join(missing))  # names only, never values
        data = self.post(OAUTH_URL, {
            "grant_type": "refresh_token",
            "refresh_token": env[keys["refresh_token"]],
            "client_id": env[keys["client_id"]],
            "client_secret": env[keys["client_secret"]],
        })
        if not isinstance(data, dict) or data.get("ok") is not True:
            raise RuntimeError("provider rejected refresh")
        access, refresh = data.get("access_token"), data.get("refresh_token")
        expires_in = data.get("expires_in")
        changes = {keys["access_token"]: access, keys["refresh_token"]: refresh}
        if not all(isinstance(v, str) and v for v in changes.values()):
            raise RuntimeError("incomplete provider response")
        # Recovery copy first: if the .env write fails, the new tokens are not lost.
        recovery = self.env_path.parent / f".token_recovery_{agent}"
        atomic_write(recovery, "".join(f"{k}={v}\n" for k, v in changes.items()))
        update_env(self.env_path, changes)
        if any(read_env(self.env_path).get(k) != v for k, v in changes.items()):
            raise RuntimeError(".env verification failed; tokens kept in recovery file")
        if isinstance(expires_in, bool) or not isinstance(expires_in, int):
            raise RuntimeError("no valid expires_in; tokens saved, schedule unknown")
        return expires_in
