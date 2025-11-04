#!/usr/bin/env python3
"""
api-2.py: Create a reservation (lease) for a given zone and time window.

Callable CLI tool for EnvAgent-plus framework.
Returns structured JSON to stdout with schema: {ok, data, error, metrics, version}
Exit code 0 if ok=true, nonzero otherwise.
"""

import argparse
import datetime
import json
import os
import sys
import time
from typing import Optional, Tuple

VERSION = "1.0.0"


def normalize_datetime(dt_str: str) -> str:
    """Convert various datetime formats to UTC ISO 8601 without fractional seconds."""
    if not dt_str:
        raise ValueError("Empty datetime string")
    
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(dt_str, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    
    raise ValueError(f"Unrecognized datetime format: {dt_str}")


def create_lease_real(
    name: str,
    start_date: str,
    end_date: str,
    resource_type: str,
    amount: int
) -> Tuple[Optional[str], Optional[str]]:
    """
    Create a lease using Blazar API.
    Returns (lease_id, error_message). On success, error_message is None.
    """
    try:
        from envboot.osutil import blz
    except ImportError:
        return None, "envboot.osutil module not found (required for real lease creation)"
    
    # Convert ISO format to datetime
    start = datetime.datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ")
    end = datetime.datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ")
    
    # Format dates for Blazar
    start_str = start.strftime("%Y-%m-%d %H:%M")
    end_str = end.strftime("%Y-%m-%d %H:%M")
    
    try:
        # Create lease using Blazar API
        lease = blz().lease.create(
            name=name,
            start=start_str,
            end=end_str,
            reservations=[{
                "resource_type": resource_type,
                "min": amount,
                "max": amount,
                "resource_properties": '[]',
                "hypervisor_properties": '[]'
            }],
            events=[]
        )
        return lease["id"], None
    except KeyError as e:
        missing = str(e).strip("'")
        msg = (
            f"Missing required OpenStack environment variable: {missing}. "
            "Hint: source your OpenRC or set OS_* variables."
        )
        return None, msg
    except Exception as e:
        return None, str(e)


def create_reservation(
    zone: str,
    start: str,
    duration: int,
    nodes: int,
    name: Optional[str],
    dry_run: bool,
    resource_type: str,
) -> dict:
    """
    Create a reservation for the given zone and time window.
    
    Returns dict with {ok, data, error, metrics, version}
    """
    start_time = time.time()
    
    try:
        # Normalize start time
        desired_start = normalize_datetime(start)
        
        # Calculate end time
        if duration < 1 or duration > 44640:
            raise ValueError("Duration must be between 1 and 44640 minutes (31 days)")
        
        if nodes < 1:
            raise ValueError("Number of nodes must be at least 1")
        
        start_dt = datetime.datetime.strptime(desired_start, "%Y-%m-%dT%H:%M:%SZ")
        end_dt = start_dt + datetime.timedelta(minutes=duration)
        desired_end = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Generate reservation name if not provided
        if not name:
            name = f"envboot-api2-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
        # In dry-run mode, simulate reservation creation
        if dry_run:
            elapsed_ms = int((time.time() - start_time) * 1000)
            fake_reservation_id = f"sim-lease-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            
            return {
                "ok": True,
                "data": {
                    "reservation_id": fake_reservation_id,
                    "name": name,
                    "zone": zone,
                    "start": desired_start,
                    "end": desired_end,
                    "duration_minutes": duration,
                    "nodes_requested": nodes,
                    "resource_type": resource_type,
                    "status": "simulated",
                    "dry_run": True
                },
                "error": None,
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION
            }
        
        # Real mode: check preconditions
        now_utc = datetime.datetime.utcnow()
        if start_dt <= now_utc:
            raise ValueError("Start date must be later than current UTC time")
        
        if not os.environ.get("OS_AUTH_URL"):
            raise ValueError(
                "Missing OS_AUTH_URL environment variable. "
                "Source your OpenRC (e.g., 'source CHI-<project>-openrc.sh')"
            )
        
        # Create the lease
        lease_id, error = create_lease_real(
            name=name,
            start_date=desired_start,
            end_date=desired_end,
            resource_type=resource_type,
            amount=nodes
        )
        
        if error:
            raise RuntimeError(f"Lease creation failed: {error}")
        
        if not lease_id:
            raise RuntimeError("Lease creation returned no ID")
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return {
            "ok": True,
            "data": {
                "reservation_id": lease_id,
                "name": name,
                "zone": zone,
                "start": desired_start,
                "end": desired_end,
                "duration_minutes": duration,
                "nodes_requested": nodes,
                "resource_type": resource_type,
                "status": "created",
                "dry_run": False
            },
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
        description="API-2: Create a reservation (lease) for a zone and time window",
        add_help=False  # Suppress help to avoid extra output
    )
    parser.add_argument("--zone", required=True, help="Zone/site (e.g., uc, tacc, nu)")
    parser.add_argument("--start", required=True, help="Start time (YYYY-MM-DD HH:MM)")
    parser.add_argument("--duration", type=int, required=True, help="Duration in minutes")
    parser.add_argument("--nodes", type=int, required=True, help="Number of nodes to reserve")
    parser.add_argument("--name", help="Reservation name (auto-generated if not provided)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate reservation creation")
    parser.add_argument(
        "--resource-type",
        choices=["virtual:instance", "physical:host"],
        default="physical:host",
        help="Resource type for the lease (default: physical:host)"
    )
    
    args = parser.parse_args()
    
    result = create_reservation(
        zone=args.zone,
        start=args.start,
        duration=args.duration,
        nodes=args.nodes,
        name=args.name,
        dry_run=args.dry_run,
        resource_type=args.resource_type,
    )
    
    # Output JSON only (no other prints)
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
