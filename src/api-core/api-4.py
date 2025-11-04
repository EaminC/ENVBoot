#!/usr/bin/env python3
"""
api-4.py: Cancel/Delete a lease by ID using Blazar.

Callable CLI tool for EnvAgent-plus framework.
Returns structured JSON to stdout with schema: {ok, data, error, metrics, version}
Exit codes:
  0 = ok true
  1 = invalid args or missing --confirm
  2 = backend errors (HTTP 4xx/5xx or SDK exceptions) or timeout
"""

import argparse
import json
import sys
import time
from typing import Optional, Tuple

VERSION = "1.0.0"


def _extract_http_status(err: Exception) -> Optional[int]:
    """Best-effort extraction of HTTP status code from exception message/attrs."""
    # blazarclient/keystone exceptions often carry code/status in str(err)
    msg = str(err) or ""
    for code in (400, 401, 403, 404, 409, 500):
        if f" {code} " in f" {msg} ":
            return code
        if f"{code}:" in msg or f"({code})" in msg:
            return code
    # Some SDK errors have .http_status or .status_code
    for attr in ("http_status", "status_code", "code"):
        val = getattr(err, attr, None)
        if isinstance(val, int):
            return val
    return None


def _is_not_found(err: Exception) -> bool:
    code = _extract_http_status(err)
    if code == 404:
        return True
    msg = (str(err) or "").lower()
    return "notfound" in msg or "not found" in msg


def _delete_lease_real(reservation_id: str) -> Tuple[bool, Optional[str]]:
    """Attempt to delete lease. Returns (deleted_requested, error_message)."""
    try:
        from envboot.osutil import blz
        client = blz()
        # blazarclient returns None on success (HTTP 204)
        client.lease.delete(reservation_id)
        return True, None
    except Exception as e:
        return False, str(e)


def _lease_exists_real(reservation_id: str) -> Tuple[Optional[bool], Optional[str]]:
    """Check if a lease still exists via GET. Returns (exists, error_message)."""
    try:
        from envboot.osutil import blz
        client = blz()
        _ = client.lease.get(reservation_id)
        return True, None
    except Exception as e:
        if _is_not_found(e):
            return False, None
        return None, str(e)


def delete_reservation(
    reservation_id: str,
    zone: Optional[str],
    dry_run: bool,
    confirm: bool,
    wait: Optional[int],
    interval: int,
    treat_not_found_as_ok: bool,
) -> Tuple[dict, int]:
    """
    Perform deletion and return (result_json, exit_code).
    Exit codes per spec.
    """
    t0 = time.time()

    try:
        if not reservation_id:
            raise ValueError("reservation_id is required")

        # Dry-run simulation
        if dry_run:
            elapsed_ms = int((time.time() - t0) * 1000)
            data = {
                "reservation_id": reservation_id,
                "action": "delete",
                "status": "simulated",
                "dry_run": True,
            }
            if zone:
                data["zone"] = zone
            return {
                "ok": True,
                "data": data,
                "error": None,
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION,
            }, 0

        # Real mode requires explicit confirmation
        if not confirm:
            elapsed_ms = int((time.time() - t0) * 1000)
            return {
                "ok": False,
                "data": {
                    "reservation_id": reservation_id,
                    "action": "delete",
                    "status": "rejected_missing_confirm",
                    "dry_run": False,
                    **({"zone": zone} if zone else {}),
                },
                "error": {"type": "InvalidArgs", "message": "--confirm is required in real mode"},
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION,
            }, 1

        # Issue DELETE
        ok_delete, err = _delete_lease_real(reservation_id)
        if not ok_delete:
            # Handle 404 specially if requested
            fake_exc = Exception(err)
            if treat_not_found_as_ok and _is_not_found(fake_exc):
                elapsed_ms = int((time.time() - t0) * 1000)
                data = {
                    "reservation_id": reservation_id,
                    "action": "delete",
                    "status": "already_deleted",
                    "dry_run": False,
                }
                if zone:
                    data["zone"] = zone
                return {
                    "ok": True,
                    "data": data,
                    "error": None,
                    "metrics": {"elapsed_ms": elapsed_ms},
                    "version": VERSION,
                }, 0

            # Map backend error
            status = _extract_http_status(fake_exc)
            etype = {
                400: "BadRequest",
                401: "Unauthorized",
                403: "Forbidden",
                404: "NotFound",
                409: "Conflict",
                500: "ServerError",
            }.get(status, "BackendError")
            elapsed_ms = int((time.time() - t0) * 1000)
            return {
                "ok": False,
                "data": {
                    "reservation_id": reservation_id,
                    "action": "delete",
                    "status": "error",
                    "dry_run": False,
                    **({"zone": zone} if zone else {}),
                },
                "error": {"type": etype, "message": err},
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION,
            }, 2

        # If no wait, report requested
        if not wait or wait <= 0:
            elapsed_ms = int((time.time() - t0) * 1000)
            data = {
                "reservation_id": reservation_id,
                "action": "delete",
                "status": "requested",
                "dry_run": False,
            }
            if zone:
                data["zone"] = zone
            return {
                "ok": True,
                "data": data,
                "error": None,
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION,
            }, 0

        # Poll for deletion
        poll_count = 0
        timeout = max(0, int(wait))
        step = max(1, int(interval))
        deadline = time.time() + timeout
        last_exists = None
        last_err = None
        while time.time() < deadline:
            exists, perr = _lease_exists_real(reservation_id)
            poll_count += 1
            last_exists, last_err = exists, perr
            if exists is False:  # Not found => deleted
                elapsed_ms = int((time.time() - t0) * 1000)
                data = {
                    "reservation_id": reservation_id,
                    "action": "delete",
                    "status": "deleted",
                    "dry_run": False,
                    "wait": {
                        "timeout_seconds": timeout,
                        "interval_seconds": step,
                        "poll_count": poll_count,
                    },
                }
                if zone:
                    data["zone"] = zone
                return {
                    "ok": True,
                    "data": data,
                    "error": None,
                    "metrics": {"elapsed_ms": elapsed_ms},
                    "version": VERSION,
                }, 0
            # If error and not NotFound, treat as backend transient; continue until timeout
            time.sleep(step)

        # Timeout
        elapsed_ms = int((time.time() - t0) * 1000)
        data = {
            "reservation_id": reservation_id,
            "action": "delete",
            "status": "timeout",
            "dry_run": False,
            "wait": {
                "timeout_seconds": timeout,
                "interval_seconds": step,
                "poll_count": poll_count,
            },
        }
        if zone:
            data["zone"] = zone
        err_obj = None
        if last_err:
            # Surface last backend error if present
            err_obj = {"type": "BackendError", "message": last_err}
        return {
            "ok": False,
            "data": data,
            "error": err_obj,
            "metrics": {"elapsed_ms": elapsed_ms},
            "version": VERSION,
        }, 2

    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "ok": False,
            "data": None,
            "error": {"type": type(e).__name__, "message": str(e)},
            "metrics": {"elapsed_ms": elapsed_ms},
            "version": VERSION,
        }, 1


def main():
    parser = argparse.ArgumentParser(
        description="API-4: Cancel/Delete a lease by ID",
        add_help=False  # avoid default help output
    )
    parser.add_argument("--reservation-id", required=True, help="Reservation/lease ID")
    parser.add_argument("--zone", help="Zone/site (optional, for context)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate deletion")
    parser.add_argument("--confirm", action="store_true", help="Required in real mode")
    parser.add_argument("--wait", type=int, help="After DELETE, poll GET until 404 or timeout (seconds)")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval seconds (default: 5)")
    parser.add_argument("--treat-not-found-as-ok", action="store_true",
                        help="If initial DELETE is 404, return ok with status=already_deleted")

    args = parser.parse_args()

    result, exit_code = delete_reservation(
        reservation_id=args.reservation_id,
        zone=args.zone,
        dry_run=args.dry_run,
        confirm=args.confirm,
        wait=args.wait,
        interval=args.interval,
        treat_not_found_as_ok=args.treat_not_found_as_ok,
    )

    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
