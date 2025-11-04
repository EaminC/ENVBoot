## API 4 — Delete a reservation

### What it does
Cancels a lease by ID. Can wait until it is gone.

### When to use it
After you are done. To free resources.

### Inputs
- reservation-id: Lease ID.
- zone: Optional label in output.
- dry-run: Simulate deletion.
- confirm: Required for real deletion.
- wait: Seconds to poll for deletion. Optional.
- interval: Polling step in seconds. Default: 5.
- treat-not-found-as-ok: If the lease is already gone, return ok.

### What you get back
A JSON object. It includes:
- ok: true or false.
- data.reservation_id, data.action, data.status.
- data.wait: Only when wait is used.
- error: Details when ok=false.
- metrics.elapsed_ms and version.

### Command
python3 src/api-core/api-4.py --reservation-id sim-lease-20251105120000 --dry-run

### Example result
{
  "ok": true,
  "data": {
    "reservation_id": "sim-lease-20251105120000",
    "action": "delete",
    "status": "simulated",
    "dry_run": true
  },
  "error": null,
  "metrics": {"elapsed_ms": 9},
  "version": "1.0.0"
}

Real run
- This is step 6 in the end-to-end flow. See docs/RealRun.md for when and how to clean up safely.
