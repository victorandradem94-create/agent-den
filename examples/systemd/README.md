# systemd examples

Generated with `agentden generate sample-config.json --output examples/systemd`.
They point at private bot scripts that are **not** in this repo, so do not
enable them as-is. Copy, adapt paths, review, then install into
`~/.config/systemd/user/`.

The Guardian service runs in **dry run**. To allow real operations you must
append `--run` to its `ExecStart` yourself, after reading
[docs/security.md](../../docs/security.md).
