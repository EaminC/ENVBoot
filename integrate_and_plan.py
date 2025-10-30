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
        # Execute the exact CLI with shell redirection as requested
        cmd = "openstack reservation allocation list host -f json > allocations.json"
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            text=True,
            capture_output=True,
        )
        print("Pulled latest allocations.json from OpenStack")
        return True
    except subprocess.CalledProcessError as e:
        print("Warning: Failed to pull latest allocations.json from OpenStack; continuing with existing file.")
        if e.stderr:
            print("stderr:", e.stderr)
        return False
    except Exception as e:
        print(f"Warning: Unexpected error refreshing allocations: {e}. Continuing with existing file.")
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
    """Build a map of nodes by UUID and zone (site)."""
    node_map = {}  # uuid → node info
    zone_map = {}  # uuid → zone (site ID)
    
    # Helper function to extract site ID from node links
    def extract_site_from_links(links: list) -> Optional[str]:
        """Extract site ID from links array (e.g., /sites/uc/clusters/...)"""
        for link in links:
            href = link.get("href", "")
            # Pattern: /sites/{site_id}/...
            if href.startswith("/sites/"):
                parts = href.split("/")
                if len(parts) >= 3:
                    return parts[2]  # site_id is at index 2
        return None
    
    # Index nodes with their cluster/site info
    for node in nodes_json.get("items", []):
        uuid = node["uid"]
        
        # Extract site from node's links
        site_id = extract_site_from_links(node.get("links", []))
        
        node_info = {
            "uuid": uuid,
            "hostname": node["node_name"],
            "cluster": node.get("cluster", "unknown"),
            "site": site_id or "unknown",
            # Add resource_id if we have it in the map
            "resource_id": next((rid for rid, val in resource_map.items() 
                               if val == uuid or val == node["node_name"]), None)
        }
        node_map[uuid] = node_info
        
        # Map UUID to site (zone)
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

def find_earliest_available_slot(
    node_map: Dict[str, Any],
    zone_map: Dict[str, str],
    allocations: List[dict],
    desired_zone: str,
    start_time: str,
    duration_minutes: int,
    required_amount: int,
    max_search_hours: int = 168  # Default: search up to 7 days ahead
) -> Optional[Tuple[str, int]]:
    """
    Search forward in time to find the earliest slot with sufficient capacity.
    
    Returns: (earliest_start_time, available_count) or None if not found
    """
    # Parse the start time
    start_dt = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
    duration = datetime.timedelta(minutes=duration_minutes)
    
    # Search in 1-hour increments
    search_increment = datetime.timedelta(hours=1)
    max_search_time = start_dt + datetime.timedelta(hours=max_search_hours)
    
    current_search_time = start_dt
    
    while current_search_time <= max_search_time:
        current_start = current_search_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        current_end = (current_search_time + duration).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Check availability at this time slot
        available = find_available_nodes(
            node_map,
            zone_map,
            allocations,
            desired_zone,
            current_start,
            current_end
        )
        
        # If we found enough nodes, return this slot
        if len(available) >= required_amount:
            return (current_start, len(available))
        
        # Move to next time slot
        current_search_time += search_increment
    
    # Couldn't find a slot within the search window
    return None

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
    parser.add_argument("--zone", default=os.getenv("ZONE", "uc"),
                       help="Site/zone to search for available nodes (uc, tacc, nu, ncar, edge, nrp, or 'unknown' for unmapped nodes)")
    parser.add_argument("--list-zones", action="store_true",
                       help="List available zones and exit")
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
    parser.add_argument("--find-earliest", action="store_true",
                       help="If insufficient capacity at requested time, search forward to find earliest available slot")
    parser.add_argument("--max-search-hours", type=int,
                       default=int(os.getenv("MAX_SEARCH_HOURS", "168")),
                       help="Maximum hours to search ahead when using --find-earliest (default: 168 = 7 days)")
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
    
    # Show available zones/sites
    available_zones = sorted(set(zone_map.values()))
    zone_counts = {zone: sum(1 for z in zone_map.values() if z == zone) for zone in available_zones}
    print(f"Available zones: {', '.join(f'{z} ({zone_counts[z]} nodes)' for z in available_zones)}")
    
    # If user just wants to list zones, show detail and exit
    if args.list_zones:
        print("\nDetailed zone breakdown:")
        for zone in available_zones:
            print(f"\n  Zone: {zone}")
            print(f"    Total nodes: {zone_counts[zone]}")
            # Count nodes with resource mappings
            mapped = sum(1 for uuid, z in zone_map.items() 
                        if z == zone and node_map[uuid].get("resource_id"))
            print(f"    Mapped to allocations: {mapped}")
            print(f"    Unmapped: {zone_counts[zone] - mapped}")
        sys.exit(0)
    
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
    
    # Validate zone exists
    if args.zone not in zone_counts:
        print(f"\nWarning: Zone '{args.zone}' not found in loaded nodes.")
        print(f"Available zones: {', '.join(available_zones)}")
        print("No nodes to search.")
        sys.exit(0)
    
    free_nodes = find_available_nodes(
        node_map, zone_map, allocations,
        args.zone, desired_start, desired_end
    )
    
    if not free_nodes:
        print("\nNo available nodes found in the specified zone and time window.")
        
        # If --find-earliest is enabled, search forward for availability
        if args.find_earliest:
            print(f"\nSearching for earliest available slot with {args.amount} nodes...")
            print(f"Scanning up to {args.max_search_hours} hours ahead...")
            
            result = find_earliest_available_slot(
                node_map,
                zone_map,
                allocations,
                args.zone,
                desired_start,
                args.duration,
                args.amount,
                args.max_search_hours
            )
            
            if result:
                earliest_start, available_count = result
                # Parse and format the time for display
                earliest_dt = datetime.datetime.strptime(earliest_start, "%Y-%m-%dT%H:%M:%SZ")
                original_dt = datetime.datetime.strptime(desired_start, "%Y-%m-%dT%H:%M:%SZ")
                hours_ahead = int((earliest_dt - original_dt).total_seconds() / 3600)
                
                print(f"\n✓ Found availability!")
                print(f"  Earliest time: {earliest_start} ({hours_ahead} hours from requested time)")
                print(f"  Available nodes: {available_count}")
                print(f"\nTo reserve at this time, run:")
                print(f"  python3 integrate_and_plan.py --zone {args.zone} --start \"{earliest_dt.strftime('%Y-%m-%d %H:%M')}\" --duration {args.duration} --amount {args.amount} --dry-run 0")
            else:
                print(f"\n✗ No available slots found within {args.max_search_hours} hours.")
                print("Try:")
                print("  - Reducing --amount (requested node count)")
                print("  - Increasing --max-search-hours")
                print("  - Choosing a different --zone")
        else:
            print("Try another zone or shift the start time.")
            print("Tip: Use --find-earliest to automatically search for the next available slot.")
        
        sys.exit(0)
    
    # 6. Report findings
    print(f"\nFound {len(free_nodes)} available nodes:")
    for node in free_nodes[:5]:  # Show first 5
        site_info = f" [site: {node.get('site', 'unknown')}]" if node.get('site') else ""
        print(f"  - {node['hostname']} (UUID: {node['uuid']}){site_info}")
    if len(free_nodes) > 5:
        print(f"  ... and {len(free_nodes)-5} more")
    
    # Check if we have enough nodes for the requested amount
    if len(free_nodes) < args.amount:
        print(f"\n⚠️  Warning: Only {len(free_nodes)} nodes available, but {args.amount} requested.")
        
        # If --find-earliest is enabled, search forward for sufficient capacity
        if args.find_earliest:
            print(f"\nSearching for earliest slot with {args.amount} nodes...")
            print(f"Scanning up to {args.max_search_hours} hours ahead...")
            
            result = find_earliest_available_slot(
                node_map,
                zone_map,
                allocations,
                args.zone,
                desired_start,
                args.duration,
                args.amount,
                args.max_search_hours
            )
            
            if result:
                earliest_start, available_count = result
                # Parse and format the time for display
                earliest_dt = datetime.datetime.strptime(earliest_start, "%Y-%m-%dT%H:%M:%SZ")
                original_dt = datetime.datetime.strptime(desired_start, "%Y-%m-%dT%H:%M:%SZ")
                hours_ahead = int((earliest_dt - original_dt).total_seconds() / 3600)
                
                print(f"\n✓ Found sufficient capacity!")
                print(f"  Earliest time: {earliest_start} ({hours_ahead} hours from requested time)")
                print(f"  Available nodes: {available_count}")
                print(f"\nTo reserve at this time, run:")
                print(f"  python3 integrate_and_plan.py --zone {args.zone} --start \"{earliest_dt.strftime('%Y-%m-%d %H:%M')}\" --duration {args.duration} --amount {args.amount} --dry-run 0")
                sys.exit(0)
            else:
                print(f"\n✗ No slots with {args.amount} nodes found within {args.max_search_hours} hours.")
                print("Try:")
                print("  - Reducing --amount (requested node count)")
                print("  - Increasing --max-search-hours")
                print("  - Choosing a different --zone")
                sys.exit(1)
        else:
            print("Cannot proceed with lease creation - insufficient capacity.")
            print("Tip: Use --find-earliest to automatically search for the next available slot.")
            sys.exit(1)
    
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