import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from .models import ResourceRequest, ReservationPlan, SchedulingConfig
from .osutil import blz, blazar_list_leases
try:
    from dateutil import parser as dtp
except ImportError:
    dtp = None

def capacity_available(
    zone: str,
    start_time: datetime,
    end_time: datetime,
    leases: Optional[List[Dict[str, Any]]],
    zone_capacity: Optional[Dict[str, int]],
    need: int = 1,
    verbose: bool = False,
) -> Optional[bool]:
    """Return True if requested capacity (need) fits in zone for [start,end),
    False if not available, or None if indeterminate.

    - Uses provided leases (fixture mode). If leases is None, attempts live API.
    - Only counts reservations with status ACTIVE/STARTED that overlap window.
    - Only counts reservations of resource_type 'physical:host' in the target zone.
    - Zone capacity defaults to 1 when not provided.
    """
    from .osutil import blazar_list_leases
    """Detect if a zone has resource overload in the specified time window.
    
    Uses Blazar leases API to check for overlapping reservations as suggested by Yiming Cheng.
    
    Returns:
        True: Overload detected (existing leases overlap our time window)
        False: No overload (sufficient resources available)
        None: Cannot determine (API error or insufficient data)
    """
    # Use injected leases if provided; otherwise query live Blazar API
    if leases is None:
        try:
            leases = blazar_list_leases()
            if not leases:
                if verbose:
                    print(f"Warning: Could not list leases")
                return None
        except Exception as e:
            if verbose:
                print(f"Warning: Could not access Blazar leases API: {e}")
            return None
    else:
        # Fixture mode: make sure it's a list
        if not isinstance(leases, list):
            if verbose:
                print("Warning: leases fixture is not a list")
            return None
        if len(leases) == 0:
            # Empty fixture -> cannot conclude capacity; caller may choose optimistic search
            if verbose:
                print(f"Warning: leases fixture empty; cannot determine capacity in zone {zone}")
            return None
    
    # Track overlapping reservations and total count vs capacity
    overlapping_reservations: List[Dict[str, Any]] = []
    overlapping_count = 0
    cap = 1
    if zone_capacity and isinstance(zone_capacity, dict):
        try:
            cap = int(zone_capacity.get(zone, 1))
        except Exception:
            cap = 1
    
    # Check each lease for time overlap
    for lease in leases:
        # Only consider active/started leases
        if lease.get('status') not in ['ACTIVE', 'STARTED']:
            continue
            
        # Parse lease times defensively using dateutil for robust parsing
        try:
            if dtp is None:
                # Fallback to basic datetime parsing if dateutil not available
                lease_start_str = lease.get('start') or lease.get('start_date')
                lease_end_str = lease.get('end') or lease.get('end_date')
                
                if not lease_start_str or not lease_end_str:
                    continue
                    
                # Handle both formats: "YYYY-MM-DD HH:MM" and ISO8601
                if 'T' in lease_start_str:
                    # ISO8601 format
                    lease_start = datetime.fromisoformat(lease_start_str.replace('Z', '+00:00'))
                    lease_end = datetime.fromisoformat(lease_end_str.replace('Z', '+00:00'))
                else:
                    # "YYYY-MM-DD HH:MM" format
                    lease_start = datetime.strptime(lease_start_str, "%Y-%m-%d %H:%M")
                    lease_end = datetime.strptime(lease_end_str, "%Y-%m-%d %H:%M")
            else:
                # Use dateutil for maximum compatibility
                lease_start_str = lease.get('start') or lease.get('start_date')
                lease_end_str = lease.get('end') or lease.get('end_date')
                
                if not lease_start_str or not lease_end_str:
                    continue
                    
                lease_start = dtp.parse(lease_start_str)
                lease_end = dtp.parse(lease_end_str)
            
            # Ensure timezone awareness
            if lease_start.tzinfo is None:
                lease_start = lease_start.replace(tzinfo=timezone.utc)
            if lease_end.tzinfo is None:
                lease_end = lease_end.replace(tzinfo=timezone.utc)
            
            # Check if lease overlaps with our requested time window
            if (start_time < lease_end and end_time > lease_start):
                # Time overlap detected - check resource type
                for reservation in lease.get('reservations', []):
                    resource_type = reservation.get('resource_type')
                    # Determine reservation zone: reservation -> lease -> default 'current'
                    res_zone = reservation.get('zone') or lease.get('zone') or 'current'
                    # Only count reservations for the target zone
                    if res_zone != zone:
                        continue
                    if resource_type == 'physical:host':
                        # This is a physical host reservation that overlaps our window
                        count = int(reservation.get('min', 1) or 1)
                        overlapping_count += count
                        overlapping_reservations.append({
                            'lease_id': lease.get('id'),
                            'lease_name': lease.get('name'),
                            'start': lease_start.isoformat(),
                            'end': lease_end.isoformat(),
                            'resource_type': resource_type,
                            'count': count,
                            'zone': res_zone,
                        })
                        
        except Exception as e:
            print(f"Warning: Could not parse lease {lease.get('id', 'unknown')} times: {e}")
            continue
    
    # Determine availability using capacity
    if verbose:
        if overlapping_reservations:
            print(f"Found {len(overlapping_reservations)} overlapping reservations in zone {zone}:")
            for res in overlapping_reservations:
                print(f"  - {res['lease_name']} ({res['resource_type']} x{res['count']}) [{res['zone']}]")
                print(f"    {res['start']} → {res['end']}")
            print(f"Total overlapping count in zone {zone}: {overlapping_count} (capacity={cap})")
        else:
            print(f"✅ No overlapping reservations detected in zone {zone}")

    # available if after adding need we do not exceed capacity
    return (overlapping_count + need) <= cap


def detect_overload_in_zone(
    zone: str,
    req: ResourceRequest,
    start_time: datetime,
    end_time: datetime,
    leases: Optional[List[Dict[str, Any]]] = None,
    zone_capacity: Optional[Dict[str, int]] = None,
    verbose: bool = True,
) -> Optional[bool]:
    """Wrapper returning True if overloaded (i.e., not enough capacity for need=1)."""
    avail = capacity_available(zone, start_time, end_time, leases, zone_capacity, need=1, verbose=verbose)
    if avail is None:
        return None
    return not avail

def find_available_window(
    req: ResourceRequest,
    duration_hours: float,
    config: SchedulingConfig,
    current_zone: str,
    leases: Optional[List[Dict[str, Any]]] = None,
    zone_capacity: Optional[Dict[str, int]] = None,
    start_override: Optional[datetime] = None,
) -> Optional[ReservationPlan]:
    """Find an available time window, first in current zone, then in alternatives."""
    
    # Try current zone first with time shifting
    start_time = start_override or (datetime.now(timezone.utc) + timedelta(minutes=2))
    end_time = start_time + timedelta(hours=duration_hours)
    
    # Build zone order: current first, then alternatives (deduped)
    alt_zones = [z for z in (config.alt_zones or []) if z != current_zone]
    zones_to_check = [current_zone] + alt_zones

    # 1) Try desired start across zones: if primary is overloaded, check alts at same time
    for z in zones_to_check:
        if capacity_available(z, start_time, end_time, leases, zone_capacity, need=1, verbose=False):
            return ReservationPlan(
                zone=z,
                start=start_time,
                end=end_time,
                flavor="auto",
                count=1
            )

    # 2) Time-shift search: scan forward with step, checking all zones per step
    cursor = start_time + timedelta(minutes=config.step_minutes)
    deadline = start_time + timedelta(hours=config.lookahead_hours)
    step = timedelta(minutes=config.step_minutes)

    while cursor <= deadline:
        test_start = cursor
        test_end = test_start + timedelta(hours=duration_hours)

        if config.start_by and test_start > config.start_by:
            break

        for z in zones_to_check:
            if capacity_available(z, test_start, test_end, leases, zone_capacity, need=1, verbose=False):
                return ReservationPlan(
                    zone=z,
                    start=test_start,
                    end=test_end,
                    flavor="auto",
                    count=1
                )

        cursor += step

    return None


def find_matching_flavor(
    req: ResourceRequest,
    zone: str
) -> Optional[str]:
    """Find a flavor that matches the resource requirements."""
    # This is a simplified implementation
    # In practice, you'd query OpenStack flavors and match them to requirements
    
    if req.bare_metal:
        if req.gpus > 0:
            return "g1.h100.pci.1"  # Example GPU bare metal flavor
        else:
            return "baremetal"  # Example CPU bare metal flavor
    else:
        # KVM flavors - simplified mapping
        if req.gpus > 0:
            return "g1.kvm.1"  # Example KVM GPU flavor
        elif req.vcpus >= 16:
            return "g1.kvm.16"
        elif req.vcpus >= 8:
            return "g1.kvm.8"
        elif req.vcpus >= 4:
            return "g1.kvm.4"
        else:
            return "g1.kvm.2"
    
    return None

def create_reservation(
    plan: ReservationPlan,
    req: ResourceRequest,
    name: str = "envboot-case-study"
) -> Dict[str, Any]:
    """Create a Blazar reservation based on the plan."""
    blazar = blz()
    
    # Find matching flavor
    flavor = find_matching_flavor(req, plan.zone)
    if not flavor:
        raise ValueError(f"No suitable flavor found for requirements: {req}")
    
    # Format dates for Blazar
    start_str = plan.start.strftime("%Y-%m-%d %H:%M")
    end_str = plan.end.strftime("%Y-%m-%d %H:%M")
    
    # Create lease
    lease = blazar.lease.create(
        name=name,
        start=start_str,
        end=end_str,
        reservations=[{
            "resource_type": "physical:host",  # Chameleon Blazar only supports physical:host
            "min": 1,
            "max": 1,
            "resource_properties": '[]',
            "hypervisor_properties": '[]'
        }],
        events=[]
    )
    
    # Update plan with actual IDs
    plan.lease_id = lease["id"]
    plan.reservation_id = lease["reservations"][0]["id"]
    plan.flavor = flavor
    
    return lease
