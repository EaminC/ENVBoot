import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from .models import ResourceRequest, ReservationPlan, SchedulingConfig
from .osutil import blz

def detect_overload_in_zone(
    zone: str, 
    req: ResourceRequest, 
    start_time: datetime, 
    end_time: datetime
) -> bool:
    """Detect if a zone has resource overload in the specified time window."""
    blazar = blz()
    
    # Get all hosts in the zone
    try:
        hosts = blazar.os_host.list()
    except Exception as e:
        print(f"Warning: Could not list hosts in zone {zone}: {e}")
        return False
    
    # Filter hosts by zone (assuming zone info is in host properties)
    zone_hosts = []
    for host in hosts:
        # This is a simplified approach - in practice, you'd need to map
        # OpenStack availability zones to Blazar host properties
        if hasattr(host, 'zone') and host.zone == zone:
            zone_hosts.append(host)
    
    if not zone_hosts:
        print(f"No hosts found in zone {zone}")
        return False
    
    # Check existing leases in the time window
    start_str = start_time.strftime("%Y-%m-%d %H:%M")
    end_str = end_time.strftime("%Y-%m-%d %H:%M")
    
    try:
        leases = blazar.lease.list()
    except Exception as e:
        print(f"Warning: Could not list leases: {e}")
        return False
    
    # Calculate resource requirements for the time period
    total_needed_vcpus = req.vcpus
    total_needed_gpus = req.gpus
    
    # Check if any host has insufficient free resources
    for host in zone_hosts:
        host_vcpus = getattr(host, 'vcpus', 48)  # Default assumption
        host_gpus = getattr(host, 'gpus', 4)     # Default assumption
        
        # Calculate allocated resources during the time window
        allocated_vcpus = 0
        allocated_gpus = 0
        
        for lease in leases:
            if lease.get('status') in ['ACTIVE', 'STARTED']:
                # Check if lease overlaps with our time window
                lease_start = datetime.strptime(lease['start'], "%Y-%m-%d %H:%M")
                lease_end = datetime.strptime(lease['end'], "%Y-%m-%d %H:%M")
                
                if (start_time < lease_end and end_time > lease_start):
                    # Time overlap detected
                    for reservation in lease.get('reservations', []):
                        if reservation.get('resource_type') == 'physical:host':
                            # This is a simplified calculation
                            allocated_vcpus += reservation.get('min', 1) * host_vcpus
                            allocated_gpus += reservation.get('min', 1) * host_gpus
        
        free_vcpus = host_vcpus - allocated_vcpus
        free_gpus = host_gpus - allocated_gpus
        
        if free_vcpus < total_needed_vcpus or free_gpus < total_needed_gpus:
            print(f"Host {host.id} in zone {zone} has insufficient resources:")
            print(f"  Need: {total_needed_vcpus} vCPUs, {total_needed_gpus} GPUs")
            print(f"  Free: {free_vcpus} vCPUs, {free_gpus} GPUs")
            return True
    
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
