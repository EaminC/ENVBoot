import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from .models import ResourceRequest, ReservationPlan, SchedulingConfig
from .osutil import blz, blazar_list_leases
try:
    from dateutil import parser as dtp
except ImportError:
    dtp = None

def detect_overload_in_zone(
    zone: str, 
    req: ResourceRequest, 
    start_time: datetime, 
    end_time: datetime
) -> Optional[bool]:
    """Detect if a zone has resource overload in the specified time window.
    
    Uses Blazar leases API to check for overlapping reservations as suggested by Yiming Cheng.
    
    Returns:
        True: Overload detected (existing leases overlap our time window)
        False: No overload (sufficient resources available)
        None: Cannot determine (API error or insufficient data)
    """
    from .osutil import blazar_list_leases
    
    # Check existing leases in the time window using Blazar API
    try:
        leases = blazar_list_leases()
        if not leases:
            print(f"Warning: Could not list leases")
            return None
    except Exception as e:
        print(f"Warning: Could not access Blazar leases API: {e}")
        return None
    
    # Track overlapping reservations
    overlapping_reservations = []
    
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
                    if resource_type == 'physical:host':
                        # This is a physical host reservation that overlaps our window
                        overlapping_reservations.append({
                            'lease_id': lease.get('id'),
                            'lease_name': lease.get('name'),
                            'start': lease_start.isoformat(),
                            'end': lease_end.isoformat(),
                            'resource_type': resource_type,
                            'count': reservation.get('min', 1)
                        })
                        
        except Exception as e:
            print(f"Warning: Could not parse lease {lease.get('id', 'unknown')} times: {e}")
            continue
    
    # Determine overload status
    if overlapping_reservations:
        print(f"❌ Resource overload detected in zone {zone}:")
        print(f"  Found {len(overlapping_reservations)} overlapping reservations:")
        for res in overlapping_reservations:
            print(f"    - {res['lease_name']} ({res['resource_type']} x{res['count']})")
            print(f"      {res['start']} → {res['end']}")
        return True
    else:
        print(f"✅ No overload detected in zone {zone}")
        return False

def find_available_window(
    req: ResourceRequest,
    duration_hours: float,
    config: SchedulingConfig,
    current_zone: str
) -> Optional[ReservationPlan]:
    """Find an available time window, first in current zone, then in alternatives."""
    
    # Try current zone first with time shifting
    start_time = datetime.now(timezone.utc) + timedelta(minutes=2)
    end_time = start_time + timedelta(hours=duration_hours)
    
    # Look ahead in current zone using timedelta-based iteration
    cursor = start_time
    deadline = start_time + timedelta(hours=config.lookahead_hours)
    step = timedelta(minutes=config.step_minutes)
    
    while cursor <= deadline:
        test_start = cursor
        test_end = test_start + timedelta(hours=duration_hours)
        
        if config.start_by and test_start > config.start_by:
            break
            
        if not detect_overload_in_zone(current_zone, req, test_start, test_end):
            # Found available window in current zone
            return ReservationPlan(
                zone=current_zone,
                start=test_start,
                end=test_end,
                flavor="auto",  # Will be determined later
                count=1
            )
        
        cursor += step
    
    # If no window found in current zone, try alternative zones
    if config.alt_zones:
        for alt_zone in config.alt_zones:
            if alt_zone == current_zone:
                continue
                
            # Try immediate start in alternative zone
            test_start = start_time
            test_end = test_start + timedelta(hours=duration_hours)
            
            if not detect_overload_in_zone(alt_zone, req, test_start, test_end):
                return ReservationPlan(
                    zone=alt_zone,
                    start=test_start,
                    end=test_end,
                    flavor="auto",
                    count=1
                )
    
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
