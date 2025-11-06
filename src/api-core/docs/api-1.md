## API 1 — Check capacity

### What it does
Checks how many nodes are free in a zone for a time window.

### When to use it
Before you make a reservation. Pick a zone and a time.

### Inputs
- zone: Site code (example: uc).
- start: Start time in UTC. Format: YYYY-MM-DD HH:MM.
- duration: Minutes to reserve.
- dry-run: Simulate instead of using real data.

### What you get back
A JSON object. It includes:
- ok: true or false.
- data.zone, data.start, data.end, data.duration_minutes.
- data.available_nodes.
- data.nodes: List of nodes (uuid, hostname).
- error: Details when ok=false.
- metrics.elapsed_ms and version.

### Commands
Dry run:
```bash
python3 src/api-core/api-1.py --zone uc --start "2025-11-05 12:00" --duration 60 --dry-run
```
Real run:
```bash
python3 src/api-core/api-1.py --zone uc --start "2025-11-05 12:00" --duration 60
```

### Example result
{
  "ok": true,
  "data": {
    "zone": "uc",
    "start": "2025-11-05T12:00:00Z",
    "end": "2025-11-05T13:00:00Z",
    "duration_minutes": 60,
    "available_nodes": 5,
    "nodes": [
      {"uuid": "sim-uuid-1", "hostname": "sim-node-1"},
      {"uuid": "sim-uuid-2", "hostname": "sim-node-2"}
    ],
    "dry_run": true
  },
  "error": null,
  "metrics": {"elapsed_ms": 12},
  "version": "1.0.0"
}

Real run
- For a full real example from lease to SSH, see docs/RealRun.md.
