## API 5 — Provision your code locally

### What it does
Prepares a local workspace for your repo. Clones or copies it. Writes a small info file.

### When to use it
After your lease is set up. Before you launch servers.

### Inputs
- reservation-id: Lease ID.
- repo: Local path or Git URL.
- branch: Branch name. Default: main.
- workdir: Target folder. Default: /tmp/envagent.
- timeout: Seconds for cloning. Default: 600.
- dry-run: Simulate without cloning.

### What you get back
A JSON object. It includes:
- ok: true or false.
- data.reservation_id, data.repo, data.branch, data.workdir.
- data.status and data.artifacts (provision.json path).
- error: Details when ok=false.
- metrics.elapsed_ms and version.

### Commands
Dry run:
```bash
python3 src/api-core/api-5.py \
  --reservation-id <Real-lease-id> \
  --repo https://github.com/EaminC/ENVBoot.git \
  --workdir /tmp/envagent \
  --dry-run
```
Real run:
```bash
python3 src/api-core/api-5.py \
  --reservation-id <Real-lease-id> \
  --repo https://github.com/EaminC/ENVBoot.git \
  --branch callable-api \
  --workdir /tmp/envagent
```

### Example result
{
  "ok": true,
  "data": {
    "reservation_id": "sim-lease-20251105120000",
    "repo": "https://example.com/repo.git",
    "branch": "main",
    "workdir": "/tmp/envagent",
    "status": "simulated",
    "artifacts": ["/tmp/envagent/provision.json"],
    "dry_run": true
  },
  "error": null,
  "metrics": {"elapsed_ms": 6},
  "version": "1.0.0"
}

Real run
- After provisioning, use API 6 to launch servers. For a complete real example, see docs/RealRun.md.
