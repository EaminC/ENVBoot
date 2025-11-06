## API 2 — Create a reservation

### What it does
Creates a lease for a zone and time window.

### When to use it
After checking capacity. You want to hold nodes for later use.

### Inputs
- zone: Site code (example: uc).
- start: Start time in UTC. Format: YYYY-MM-DD HH:MM.
- duration: Minutes to reserve.
- nodes: Number of nodes.
- name: Optional label.
- resource-type: virtual:instance or physical:host. Default: physical:host.
- dry-run: Simulate without creating.

### What you get back
A JSON object. It includes:
- ok: true or false.
- data.reservation_id, data.name, data.zone.
- data.start, data.end, data.duration_minutes, data.nodes_requested.
- data.resource_type and status.
- error: Details when ok=false.
- metrics.elapsed_ms and version.

### Commands
Dry run:
```bash
python3 src/api-core/api-2.py --zone uc --start "2025-11-05 12:00" --duration 120 --nodes 1 --resource-type physical:host --dry-run
```
Real run:
```bash
python src/api-core/api-2.py --zone uc --start "$(date -u -d '+3 minutes' '+%Y-%m-%d %H:%M')" --duration 45 --nodes 1
```

### Example result
{
  "ok": true,
  "data": {
    "reservation_id": "sim-lease-20251105120000",
    "name": "envboot-api2-20251105-120000",
    "zone": "uc",
    "start": "2025-11-05T12:00:00Z",
    "end": "2025-11-05T14:00:00Z",
    "duration_minutes": 120,
    "nodes_requested": 1,
    "resource_type": "physical:host",
    "status": "simulated",
    "dry_run": true
  },
  "error": null,
  "metrics": {"elapsed_ms": 25},
  "version": "1.0.0"
}

Real run
- Next steps: check status (API 3), then launch servers (API 6). For an end-to-end walkthrough, see docs/RealRun.md.
