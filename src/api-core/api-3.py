#!/usr/bin/env python3
"""
api-3.py: Get reservation (lease) status by ID.

Callable CLI tool for EnvAgent-plus framework.
Returns structured JSON to stdout with schema: {ok, data, error, metrics, version}
Exit code 0 if ok=true, nonzero otherwise.
"""

import argparse
import datetime
import json
import sys
import time
from typing import Optional

VERSION = "1.0.0"


def get_lease_status_real(reservation_id: str) -> tuple:
    """
    Query Blazar for lease status.
    Returns (status_dict, error_message). On success, error_message is None.
    """
    try:
        from envboot.osutil import blz
    except ImportError:
        return None, "envboot.osutil module not found (required for real lease status)"
    
    try:
        lease = blz().lease.get(reservation_id)
        
        # Extract relevant status information
        status_info = {
            "status": lease.get("status", "UNKNOWN"),
            "reservation_id": lease.get("id"),
            "name": lease.get("name"),
            "start_date": lease.get("start_date"),
            "end_date": lease.get("end_date"),
            "created_at": lease.get("created_at"),
            "updated_at": lease.get("updated_at"),
        }
        
        # Add reservation details if available
        reservations = lease.get("reservations", [])
        if reservations:
            first_res = reservations[0]
            status_info["resource_type"] = first_res.get("resource_type")
            status_info["allocated"] = first_res.get("status") == "active"
        
        return status_info, None
        
    except Exception as e:
        return None, str(e)


def simulate_status(reservation_id: str, elapsed_seconds: float) -> dict:
    """
    Simulate lease status transitions for dry-run mode.
    Simple state machine: pending -> active (after 10s) -> complete (end time).
    """
    # Parse reservation_id to extract timestamp if it's a simulated ID
    if reservation_id.startswith("sim-lease-"):
        try:
            # Extract timestamp from simulated ID
            ts_str = reservation_id.replace("sim-lease-", "")
            created_dt = datetime.datetime.strptime(ts_str, "%Y%m%d%H%M%S")
        except Exception:
            created_dt = datetime.datetime.utcnow() - datetime.timedelta(seconds=elapsed_seconds)
    else:
        created_dt = datetime.datetime.utcnow() - datetime.timedelta(seconds=elapsed_seconds)
    
    now = datetime.datetime.utcnow()
    age_seconds = (now - created_dt).total_seconds()
    
    # State transitions
    if age_seconds < 10:
        status = "PENDING"
        allocated = False
    elif age_seconds < 3600:  # Active for first hour
        status = "ACTIVE"
        allocated = True
    else:
        status = "COMPLETE"
        allocated = True
    
    # Simulated times
    start_date = (created_dt + datetime.timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_date = (created_dt + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return {
        "status": status,
        "reservation_id": reservation_id,
        "name": f"simulated-{reservation_id}",
        "start_date": start_date,
        "end_date": end_date,
        "created_at": created_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resource_type": "physical:host",
        "allocated": allocated,
        "simulated": True
    }


def get_reservation_status(
    reservation_id: str,
    zone: Optional[str],
    wait: Optional[int],
    dry_run: bool
) -> dict:
    """
    Get status of a reservation, optionally polling until timeout.
    
    Returns dict with {ok, data, error, metrics, version}
    """
    start_time = time.time()
    poll_interval = 5  # seconds
    timeout = wait if wait else 0
    last_status = None
    poll_count = 0
    
    try:
        if not reservation_id:
            raise ValueError("reservation_id is required")
        
        # Polling loop (runs once if wait is not set)
        while True:
            elapsed = time.time() - start_time
            
            if dry_run:
                # Simulate status based on elapsed time
                status_info = simulate_status(reservation_id, elapsed)
            else:
                # Query real Blazar API
                status_info, error = get_lease_status_real(reservation_id)
                if error:
                    raise RuntimeError(f"Failed to get lease status: {error}")
                if not status_info:
                    raise RuntimeError("Lease status query returned no data")
            
            last_status = status_info
            poll_count += 1
            
            # If no wait specified, return immediately
            if not wait or wait <= 0:
                break
            
            # If we've exceeded timeout, return last status
            if elapsed >= timeout:
                break
            
            # Check if we're in a terminal state (no need to keep polling)
            if status_info.get("status") in ["COMPLETE", "ERROR", "TERMINATED"]:
                break
            
            # Sleep before next poll (but don't exceed timeout)
            remaining = timeout - elapsed
            sleep_time = min(poll_interval, remaining)
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                break
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Build response data
        data = {
            "reservation_id": last_status.get("reservation_id"),
            "status": last_status.get("status"),
            "name": last_status.get("name"),
            "start_date": last_status.get("start_date"),
            "end_date": last_status.get("end_date"),
            "created_at": last_status.get("created_at"),
            "updated_at": last_status.get("updated_at"),
            "allocated": last_status.get("allocated", False),
            "dry_run": dry_run,
        }
        
        if zone:
            data["zone"] = zone
        
        if wait:
            data["polling"] = {
                "timeout_seconds": wait,
                "poll_count": poll_count,
                "elapsed_seconds": round(elapsed, 2)
            }
        
        if last_status.get("resource_type"):
            data["resource_type"] = last_status["resource_type"]
        
        if last_status.get("simulated"):
            data["simulated"] = True
        
        return {
            "ok": True,
            "data": data,
            "error": None,
            "metrics": {"elapsed_ms": elapsed_ms},
            "version": VERSION
        }
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "ok": False,
            "data": None,
            "error": {
                "type": type(e).__name__,
                "message": str(e)
            },
            "metrics": {"elapsed_ms": elapsed_ms},
            "version": VERSION
        }


def main():
    parser = argparse.ArgumentParser(
        description="API-3: Get reservation (lease) status by ID",
        add_help=False  # Suppress help to avoid extra output
    )
    parser.add_argument("--reservation-id", required=True, help="Reservation/lease ID")
    parser.add_argument("--zone", help="Zone/site (optional, for context)")
    parser.add_argument("--wait", type=int, help="Poll for up to N seconds (default: no polling)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate status check")
    
    args = parser.parse_args()
    
    result = get_reservation_status(
        reservation_id=args.reservation_id,
        zone=args.zone,
        wait=args.wait,
        dry_run=args.dry_run
    )
    
    # Output JSON only (no other prints)
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
