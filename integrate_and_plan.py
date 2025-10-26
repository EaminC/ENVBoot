#!/usr/bin/env python3

import argparse
import datetime
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

def load_json(path: str, description: str = "JSON") -> dict:
    """Load and parse a JSON file with friendly error handling."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {description} file not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {description} file {path}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading {description} file {path}: {e}")
        sys.exit(1)

def refresh_allocations() -> bool:
    """Refresh allocations.json from OpenStack. Return True if successful."""
    try:
        result = subprocess.run(
            ["openstack", "reservation", "allocation", "list", "host", "-f", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        with open("allocations.json", "w") as f:
            f.write(result.stdout)
        print("Successfully refreshed allocations from OpenStack")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running OpenStack command: {e}")
        print("stderr:", e.stderr)
        return False
    except Exception as e:
        print(f"Error refreshing allocations: {e}")
        return False

def normalize_datetime(dt_str: str) -> str:
    """Convert various datetime formats to UTC ISO 8601 without fractional seconds."""
    if not dt_str:
        raise ValueError("Empty datetime string")
    
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",  # Blazar format
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M"  # User input format
    ]
    
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(dt_str, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    
    raise ValueError(f"Unrecognized datetime format: {dt_str}")

def parse_duration(minutes: int) -> datetime.timedelta:
    """Convert minutes to timedelta, validating the input."""
    if minutes < 1:
        raise ValueError("Duration must be at least 1 minute")
    if minutes > 44640:  # 31 days
        raise ValueError("Duration cannot exceed 31 days (44640 minutes)")
    return datetime.timedelta(minutes=minutes)

def check_time_overlap(
    start1: str,
    end1: str,
    start2: str,
    end2: str
) -> bool:
    """Return True if two time ranges overlap."""
    # Convert ISO strings to datetime objects
    s1 = datetime.datetime.strptime(start1, "%Y-%m-%dT%H:%M:%SZ")
    e1 = datetime.datetime.strptime(end1, "%Y-%m-%dT%H:%M:%SZ")
    s2 = datetime.datetime.strptime(start2, "%Y-%m-%dT%H:%M:%SZ")
    e2 = datetime.datetime.strptime(end2, "%Y-%m-%dT%H:%M:%SZ")
    
    return s1 < e2 and e1 > s2

def build_node_map(
    nodes_json: dict,
    clusters_json: dict,
    sites_json: dict,
    resource_map: dict
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Build a map of nodes by UUID and zone."""
    node_map = {}  # uuid → node info
    zone_map = {}  # uuid → zone
    
    # Extract zones from sites
    site_zones = {}  # site_id → list of zones
    for site in sites_json.get("items", []):
        site_zones[site["uid"]] = []
        # TODO: Extract zones for this site
    
    # Index nodes with their cluster/site info
    for node in nodes_json.get("items", []):
        uuid = node["uid"]
        node_info = {
            "uuid": uuid,
            "hostname": node["node_name"],
            "cluster": node.get("cluster", "unknown"),
            # Add resource_id if we have it in the map
            "resource_id": next((rid for rid, val in resource_map.items() 
                               if val == uuid or val == node["node_name"]), None)
        }
        node_map[uuid] = node_info
        
        # TODO: Determine zone based on cluster/site mapping
        zone_map[uuid] = "current"  # Default for now
    
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
    
    # First, build allocation index by resource_id
    alloc_by_resource = defaultdict(list)
    for alloc in allocations:
        resource_id = str(alloc.get("resource_id", ""))
        if not resource_id:
            continue
        reservations = alloc.get("reservations", [])
        alloc_by_resource[resource_id].extend(reservations)
    
    # Check each node in the desired zone
    for uuid, node in node_map.items():
        if zone_map.get(uuid) != desired_zone:
            continue
        
        # Skip if we can't identify this node in allocations
        if not node.get("resource_id"):
            continue
        
        # Check all reservations for overlap
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

def create_lease(
    name: str,
    start_date: str,
    end_date: str,
    resource_type: str,
    amount: int
) -> Optional[str]:
    """Create a lease using Blazar API. Return lease_id if successful."""
    from envboot.osutil import blz
    
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
        
        return lease["id"]
        
    except Exception as e:
        print(f"Error creating lease: {e}")
        return None

def append_audit_record(
    audit_file: str,
    record: dict
) -> None:
    """Append a JSON record to the audit file."""
    try:
        with open(audit_file, "a") as f:
            json.dump(record, f)
            f.write("\n")
    except Exception as e:
        print(f"Warning: Could not write audit record: {e}")

def main():
    parser = argparse.ArgumentParser(description="Analyze node availability and create leases")
    parser.add_argument("--refresh", action="store_true",
                       help="Refresh allocations from OpenStack before processing")
    parser.add_argument("--zone", default=os.getenv("ZONE", "current"),
                       help="Zone to search for available nodes")
    parser.add_argument("--start", default=os.getenv("DESIRED_START"),
                       help="Desired start time (YYYY-MM-DD HH:MM)")
    parser.add_argument("--duration", type=int,
                       default=int(os.getenv("DURATION_MIN", "60")),
                       help="Duration in minutes")
    parser.add_argument("--resource-type",
                       default=os.getenv("RESOURCE_TYPE", "physical:host"),
                       choices=["physical:host", "flavor:instance"],
                       help="Type of resource to reserve")
    parser.add_argument("--amount", type=int,
                       default=int(os.getenv("AMOUNT", "1")),
                       help="Number of resources to reserve")
    parser.add_argument("--dry-run", type=int,
                       default=int(os.getenv("DRY_RUN", "1")),
                       choices=[0, 1],
                       help="1 to print what would be done, 0 to create lease")
    
    args = parser.parse_args()
    
    # 1. Refresh allocations if requested
    if args.refresh:
        if not refresh_allocations():
            print("Warning: Could not refresh allocations, using existing file")
    
    # 2. Load all input files
    print("\nLoading input files...")
    allocations = load_json("allocations.json", "allocations")
    nodes = load_json("examples/api_samples/uc_chameleon_nodes.json", "nodes")
    clusters = load_json("examples/api_samples/uc_clusters.json", "clusters")
    sites = load_json("examples/api_samples/sites.json", "sites")
    resource_map = load_json("resource_map.json", "resource map")
    
    # 3. Build node and zone maps
    print("\nProcessing node and zone information...")
    node_map, zone_map = build_node_map(nodes, clusters, sites, resource_map)
    
    # 4. Parse and validate time window
    if not args.start:
        print("Error: No start time provided. Use --start or DESIRED_START")
        sys.exit(1)
    
    try:
        # Normalize start time
        desired_start = normalize_datetime(args.start)
        
        # Calculate end time
        duration = parse_duration(args.duration)
        start_dt = datetime.datetime.strptime(desired_start, "%Y-%m-%dT%H:%M:%SZ")
        end_dt = start_dt + duration
        desired_end = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        
    except ValueError as e:
        print(f"Error: Invalid time specification: {e}")
        sys.exit(1)
    
    # 5. Find available nodes
    print(f"\nSearching for available nodes in zone '{args.zone}'...")
    print(f"Time window: {desired_start} to {desired_end}")
    
    free_nodes = find_available_nodes(
        node_map, zone_map, allocations,
        args.zone, desired_start, desired_end
    )
    
    if not free_nodes:
        print("\nNo available nodes found in the specified zone and time window.")
        print("Try another zone or shift the start time.")
        sys.exit(0)
    
    # 6. Report findings
    print(f"\nFound {len(free_nodes)} available nodes:")
    for node in free_nodes[:5]:  # Show first 5
        print(f"  - {node['hostname']} (UUID: {node['uuid']})")
    if len(free_nodes) > 5:
        print(f"  ... and {len(free_nodes)-5} more")
    
    # 7. Create lease if requested
    if not args.dry_run:
        print("\nCreating lease...")
        lease_name = f"envboot-auto-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
        lease_id = create_lease(
            lease_name,
            desired_start,
            desired_end,
            args.resource_type,
            args.amount
        )
        
        if lease_id:
            print(f"Successfully created lease: {lease_id}")
            
            # Record the action
            audit_record = {
                "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "zone": args.zone,
                "lease_id": lease_id,
                "start": desired_start,
                "end": desired_end,
                "hosts": [node["hostname"] for node in free_nodes]
            }
            append_audit_record("reserve_audit.jsonl", audit_record)
        else:
            print("Failed to create lease")
            sys.exit(1)
    else:
        print("\nDry run - no lease created")

if __name__ == "__main__":
    main()