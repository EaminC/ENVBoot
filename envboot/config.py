import os
from typing import Dict, Any
from .models import DowngradePolicy, SchedulingConfig

def get_default_downgrade_policy() -> DowngradePolicy:
    """Get default downgrade policy from environment or use defaults."""
    return DowngradePolicy(
        allow_gpu_to_cpu=os.environ.get("ENVBOOT_ALLOW_GPU_DOWNGRADE", "true").lower() == "true",
        max_vcpu_reduction_ratio=float(os.environ.get("ENVBOOT_MAX_VCPU_REDUCTION", "0.5")),
        max_ram_reduction_ratio=float(os.environ.get("ENVBOOT_MAX_RAM_REDUCTION", "0.25")),
        max_duration_increase_ratio=float(os.environ.get("ENVBOOT_MAX_DURATION_INCREASE", "2.0")),
        require_pass_smoketest=os.environ.get("ENVBOOT_REQUIRE_SMOKE_TEST", "true").lower() == "true"
    )

def get_default_scheduling_config() -> SchedulingConfig:
    """Get default scheduling configuration from environment or use defaults."""
    alt_zones_str = os.environ.get("ENVBOOT_ALT_ZONES", "")
    alt_zones = [z.strip() for z in alt_zones_str.split(",")] if alt_zones_str else []
    
    return SchedulingConfig(
        lookahead_hours=int(os.environ.get("ENVBOOT_LOOKAHEAD_HOURS", "72")),
        step_minutes=int(os.environ.get("ENVBOOT_STEP_MINUTES", "30")),  # More granular: 30 minutes
        preferred_zone=os.environ.get("ENVBOOT_PREFERRED_ZONE", "current"),
        alt_zones=alt_zones,
        start_by=None  # Could be parsed from ENVBOOT_START_BY if needed
    )

def get_chameleon_su_rates() -> Dict[str, float]:
    """Get Chameleon SU rates for different resource types."""
    return {
        "bare_metal_cpu": 1.0,      # 1 SU/hour for bare metal CPU
        "bare_metal_gpu": 2.0,      # 2 SU/hour for bare metal GPU/FPGA
        "kvm_cpu_ratio": 1.0,       # 1 SU/hour * (vcpus / host_vcpus)
        "kvm_gpu_ratio": 2.0,       # 2 SU/hour * (gpus / host_gpus)
        "floating_ip": 0.0,         # No additional SU cost for floating IPs
        "vlan": 0.0                 # No additional SU cost for VLANs
    }

def get_default_host_capabilities() -> Dict[str, Any]:
    """Get default host capabilities for SU calculations."""
    return {
        "vcpus": int(os.environ.get("ENVBOOT_HOST_VCPUS", "48")),
        "gpus": int(os.environ.get("ENVBOOT_HOST_GPUS", "4")),
        "ram_gb": int(os.environ.get("ENVBOOT_HOST_RAM_GB", "192")),
        "disk_gb": int(os.environ.get("ENVBOOT_HOST_DISK_GB", "1000"))
    }

def get_complexity_thresholds() -> Dict[str, int]:
    """Get complexity scoring thresholds."""
    return {
        "gpu_frameworks_score": 3,
        "cuda_files_score": 2,
        "nvidia_docker_score": 2,
        "build_files_score": 1,
        "large_codebase_score": 1,
        "large_files_score": 1,
        "test_footprint_score": 1,
        "simple_threshold": 1,
        "moderate_threshold": 3,
        "heavy_threshold": 5
    }

def get_flavor_mappings() -> Dict[str, Dict[str, Any]]:
    """Get mappings from resource requirements to OpenStack flavors."""
    return {
        "bare_metal_gpu": {
            "flavor": "g1.h100.pci.1",
            "vcpus": 16,
            "ram_gb": 64,
            "gpus": 2,
            "bare_metal": True
        },
        "bare_metal_cpu": {
            "flavor": "baremetal",
            "vcpus": 16,
            "ram_gb": 64,
            "gpus": 0,
            "bare_metal": True
        },
        "kvm_gpu": {
            "flavor": "g1.kvm.1",
            "vcpus": 8,
            "ram_gb": 32,
            "gpus": 1,
            "bare_metal": False
        },
        "kvm_16": {
            "flavor": "g1.kvm.16",
            "vcpus": 16,
            "ram_gb": 64,
            "gpus": 0,
            "bare_metal": False
        },
        "kvm_8": {
            "flavor": "g1.kvm.8",
            "vcpus": 8,
            "ram_gb": 32,
            "gpus": 0,
            "bare_metal": False
        },
        "kvm_4": {
            "flavor": "g1.kvm.4",
            "vcpus": 4,
            "ram_gb": 16,
            "gpus": 0,
            "bare_metal": False
        },
        "kvm_2": {
            "flavor": "g1.kvm.2",
            "vcpus": 2,
            "ram_gb": 8,
            "gpus": 0,
            "bare_metal": False
        }
    }
