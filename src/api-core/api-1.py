#!/usr/bin/env python3
"""
api-1.py: Check available capacity for a given zone and time window.

Callable CLI tool for EnvAgent-plus framework.
Returns structured JSON to stdout with schema: {ok, data, error, metrics, version}
Exit code 0 if ok=true, nonzero otherwise.
"""

import argparse
import datetime
import json
import sys
import time
from typing import Dict, List, Optional, Any

VERSION = "1.0.0"


def load_json_safe(path: str) -> Optional[dict]:
    """Load JSON file, return None on error (silent)."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


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


def check_time_overlap(start1: str, end1: str, start2: str, end2: str) -> bool:
    """Return True if two time ranges overlap."""
    s1 = datetime.datetime.strptime(start1, "%Y-%m-%dT%H:%M:%SZ")
    e1 = datetime.datetime.strptime(end1, "%Y-%m-%dT%H:%M:%SZ")
    s2 = datetime.datetime.strptime(start2, "%Y-%m-%dT%H:%M:%SZ")
    e2 = datetime.datetime.strptime(end2, "%Y-%m-%dT%H:%M:%SZ")
    
    return s1 < e2 and e1 > s2


def build_node_map(
    nodes_json: dict,
    resource_map: dict
) -> tuple:
    """Build a map of nodes by UUID and zone (site)."""
    node_map = {}
    zone_map = {}
    
    def extract_site_from_links(links: list) -> Optional[str]:
        for link in links:
            href = link.get("href", "")
            if href.startswith("/sites/"):
                parts = href.split("/")
                if len(parts) >= 3:
                    return parts[2]
        return None
    
    for node in nodes_json.get("items", []):
        uuid = node["uid"]
        site_id = extract_site_from_links(node.get("links", []))
        
        node_info = {
            "uuid": uuid,
            "hostname": node["node_name"],
            "cluster": node.get("cluster", "unknown"),
            "site": site_id or "unknown",
            "resource_id": next((rid for rid, val in resource_map.items() 
                               if val == uuid or val == node["node_name"]), None)
        }
        node_map[uuid] = node_info
        zone_map[uuid] = site_id or "unknown"
    
    return node_map, zone_map


def find_available_nodes(
    node_map: Dict[str, Any],
    zone_map: Dict[str, str],
    allocations: List[dict],
    desired_zone: str,
    desired_start: str,
    desired_end: str
) -> List[dict]:
    """Find nodes in the zone with no reservation overlap."""
    free_nodes = []
    
    # Build allocation index by resource_id
    alloc_by_resource = {}
    for alloc in allocations:
        resource_id = str(alloc.get("resource_id", ""))
        if not resource_id:
            continue
        if resource_id not in alloc_by_resource:
            alloc_by_resource[resource_id] = []
        reservations = alloc.get("reservations", [])
        alloc_by_resource[resource_id].extend(reservations)
    
    # Check each node in the desired zone
    for uuid, node in node_map.items():
        if zone_map.get(uuid) != desired_zone:
            continue
        
        if not node.get("resource_id"):
            continue
        
        is_free = True
        for reservation in alloc_by_resource.get(node["resource_id"], []):
            start = reservation.get("start_date")
            end = reservation.get("end_date")
            if not start or not end:
                continue
                
            if check_time_overlap(
                normalize_datetime(start),
                normalize_datetime(end),
                desired_start,
                desired_end
            ):
                is_free = False
                break
        
        if is_free:
            free_nodes.append(node)
    
    return free_nodes


def check_capacity(zone: str, start: str, duration: int, dry_run: bool) -> dict:
    """
    Check available capacity for the given zone and time window.
    
    Returns dict with {ok, data, error, metrics, version}
    """
    start_time = time.time()
    
    try:
        # Normalize start time
        desired_start = normalize_datetime(start)
        
        # Calculate end time
        if duration < 1 or duration > 44640:
            raise ValueError("Duration must be between 1 and 44640 minutes (31 days)")
        
        start_dt = datetime.datetime.strptime(desired_start, "%Y-%m-%dT%H:%M:%SZ")
        end_dt = start_dt + datetime.timedelta(minutes=duration)
        desired_end = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # In dry-run mode, simulate capacity data
        if dry_run:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "ok": True,
                "data": {
                    "zone": zone,
                    "start": desired_start,
                    "end": desired_end,
                    "duration_minutes": duration,
                    "available_nodes": 5,  # Simulated
                    "nodes": [
                        {"uuid": "sim-uuid-1", "hostname": "sim-node-1"},
                        {"uuid": "sim-uuid-2", "hostname": "sim-node-2"},
                        {"uuid": "sim-uuid-3", "hostname": "sim-node-3"},
                        {"uuid": "sim-uuid-4", "hostname": "sim-node-4"},
                        {"uuid": "sim-uuid-5", "hostname": "sim-node-5"},
                    ],
                    "dry_run": True
                },
                "error": None,
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION
            }
        
        # Real mode: load data files
        allocations = load_json_safe("allocations.json")
        nodes = load_json_safe("examples/api_samples/uc_chameleon_nodes.json")
        resource_map = load_json_safe("resource_map.json")
        
        if not allocations or not nodes or not resource_map:
            raise FileNotFoundError("Required data files not found (allocations.json, nodes, resource_map)")
        
        # Build node and zone maps
        node_map, zone_map = build_node_map(nodes, resource_map)
        
        # Validate zone exists
        available_zones = sorted(set(zone_map.values()))
        if zone not in available_zones:
            raise ValueError(f"Zone '{zone}' not found. Available: {', '.join(available_zones)}")
        
        # Find available nodes
        free_nodes = find_available_nodes(
            node_map, zone_map, allocations,
            zone, desired_start, desired_end
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return {
            "ok": True,
            "data": {
                "zone": zone,
                "start": desired_start,
                "end": desired_end,
                "duration_minutes": duration,
                "available_nodes": len(free_nodes),
                "nodes": [
                    {
                        "uuid": n["uuid"],
                        "hostname": n["hostname"],
                        "cluster": n.get("cluster"),
                        "site": n.get("site")
                    }
                    for n in free_nodes
                ],
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
        description="API-1: Check available capacity for a zone and time window",
        add_help=False  # Suppress help to avoid extra output
    )
    parser.add_argument("--zone", required=True, help="Zone/site (e.g., uc, tacc, nu)")
    parser.add_argument("--start", required=True, help="Start time (YYYY-MM-DD HH:MM)")
    parser.add_argument("--duration", type=int, required=True, help="Duration in minutes")
    parser.add_argument("--dry-run", action="store_true", help="Simulate capacity check")
    
    args = parser.parse_args()
    
    result = check_capacity(
        zone=args.zone,
        start=args.start,
        duration=args.duration,
        dry_run=args.dry_run
    )
    
    # Output JSON only (no other prints)
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
