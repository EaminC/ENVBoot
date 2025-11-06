## API 3 — Check reservation status

### What it does
Gets the status of a lease by ID. Can wait for a while.

### When to use it
After you create a lease. To see when it becomes active.

### Inputs
- reservation-id: Lease ID.
- zone: Optional label in output.
- wait: Seconds to poll before returning. Optional.
- dry-run: Simulate status.

### What you get back
A JSON object. It includes:
- ok: true or false.
- data.reservation_id, data.status (PENDING, ACTIVE, COMPLETE, etc.).
- data.start_date, data.end_date, data.created_at, data.updated_at (UTC).
- data.allocated: true when resources are ready.
- data.polling: Only when wait is used.
- error: Details when ok=false.
- metrics.elapsed_ms and version.

### Commands
Dry run:
```bash
python3 src/api-core/api-3.py --reservation-id sim-lease-20251105120000 --wait 15 --dry-run
```
Real run:
```bash
python3 src/api-core/api-3.py --reservation-id <REAL_LEASE_ID> --wait 15
```

### Example result
{
  "ok": true,
  "data": {
    "reservation_id": "sim-lease-20251105120000",
    "status": "ACTIVE",
    "name": "simulated-sim-lease-20251105120000",
    "start_date": "2025-11-05T12:00:10Z",
    "end_date": "2025-11-05T13:00:00Z",
    "created_at": "2025-11-05T12:00:00Z",
    "updated_at": "2025-11-05T12:00:15Z",
    "allocated": true,
    "dry_run": true,
    "polling": {
      "timeout_seconds": 15,
      "poll_count": 3,
      "elapsed_seconds": 15.0
    }
  },
  "error": null,
  "metrics": {"elapsed_ms": 15005},
  "version": "1.0.0"
}

Real run
- When the lease is ACTIVE, proceed to API 6 to launch servers. See docs/RealRun.md for a full sequence.
