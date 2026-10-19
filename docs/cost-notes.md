# Cost notes

What this setup costs **today**, for this case: $0/month in cloud fees.

- Oracle Cloud Always Free Ampere A1 capacity (we use 2 OCPU / 12 GB).
  Terms, limits and idle-reclaim policies are Oracle's to change; check the
  current docs. Free capacity can be hard to obtain in some regions.
- Slack: a free workspace was enough for four bots in this case.
- xAI/Grok API usage is **not** free; it is billed per token by xAI and is the
  real variable cost. Set limits in the provider console.
- No Docker, no managed DB, no load balancer, no paid monitoring.

What you do *not* get for free: high availability, backups, alerting, support.
One VM is a single point of failure. If the bots matter, budget for a cheap
paid VM and a second region before anything else.
