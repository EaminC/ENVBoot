import subprocess
import time
from typing import Optional, Tuple
from .models import ResourceRequest, DowngradePolicy, ComplexityTier

def try_downgrade(
    req: ResourceRequest, 
    policy: DowngradePolicy,
    complexity_tier: ComplexityTier
) -> Tuple[ResourceRequest, bool]:
    """
    Try to downgrade resources according to policy.
    Returns (downgraded_request, downgrade_applied)
    """
    
    # Never downgrade GPU for heavy/very_heavy repos if they have GPU frameworks
    if complexity_tier in [ComplexityTier.HEAVY, ComplexityTier.VERY_HEAVY] and req.gpus > 0:
        if not policy.allow_gpu_to_cpu:
            print("Policy prevents GPU to CPU downgrade for heavy/very_heavy repos")
            return req, False
    
    downgraded = req
    changes_made = False
    
    # Try vCPU reduction
    if req.vcpus > 1:  # Don't go below 1 vCPU
        max_reduction = int(req.vcpus * policy.max_vcpu_reduction_ratio)
        if max_reduction > 0:
            new_vcpus = max(1, req.vcpus - max_reduction)
            if new_vcpus < req.vcpus:
                downgraded.vcpus = new_vcpus
                changes_made = True
                print(f"Downgraded vCPUs: {req.vcpus} → {new_vcpus}")
    
    # Try RAM reduction
    if req.ram_gb > 1:  # Don't go below 1 GB
        max_reduction = int(req.ram_gb * policy.max_ram_reduction_ratio)
        if max_reduction > 0:
            new_ram = max(1, req.ram_gb - max_reduction)
            if new_ram < req.ram_gb:
                downgraded.ram_gb = new_ram
                changes_made = True
                print(f"Downgraded RAM: {req.ram_gb} GB → {new_ram} GB")
    
    # Try GPU to CPU downgrade (if policy allows)
    if req.gpus > 0 and policy.allow_gpu_to_cpu:
        if complexity_tier not in [ComplexityTier.HEAVY, ComplexityTier.VERY_HEAVY]:
            downgraded.gpus = 0
            changes_made = True
            print(f"Downgraded GPUs: {req.gpus} → 0 (CPU only)")
    
    # Try bare metal to KVM downgrade (if applicable)
    if req.bare_metal and not policy.require_pass_smoketest:
        # Only if we're not requiring smoke tests (simplified logic)
        downgraded.bare_metal = False
        changes_made = True
        print("Downgraded: bare metal → KVM")
    
    return downgraded, changes_made

def run_smoke_test(
    command: str,
    timeout_seconds: int = 300
) -> Tuple[bool, str]:
    """
    Run a smoke test command to verify downgraded resources are sufficient.
    Returns (success, output)
    """
    if not command:
        print("No smoke test command provided, skipping test")
        return True, "No test command"
    
    print(f"Running smoke test: {command}")
    print(f"Timeout: {timeout_seconds} seconds")
    
    try:
        # Run the command with timeout
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        
        success = result.returncode == 0
        output = result.stdout + result.stderr
        
        if success:
            print("✅ Smoke test passed")
        else:
            print(f"❌ Smoke test failed with return code {result.returncode}")
            print(f"Output: {output}")
        
        return success, output
        
    except subprocess.TimeoutExpired:
        print(f"❌ Smoke test timed out after {timeout_seconds} seconds")
        return False, "Timeout expired"
    except Exception as e:
        print(f"❌ Smoke test failed with error: {e}")
        return False, str(e)

def calculate_duration_increase(
    original_duration_hours: float,
    policy: DowngradePolicy
) -> float:
    """Calculate increased duration to compensate for downgraded resources."""
    max_increase = original_duration_hours * policy.max_duration_increase_ratio
    return min(max_increase, original_duration_hours * 2.0)  # Cap at 2x

def validate_downgrade_policy(
    original_req: ResourceRequest,
    downgraded_req: ResourceRequest,
    policy: DowngradePolicy
) -> bool:
    """Validate that the downgrade follows the policy constraints."""
    
    # Check vCPU reduction
    vcpu_reduction = (original_req.vcpus - downgraded_req.vcpus) / original_req.vcpus
    if vcpu_reduction > policy.max_vcpu_reduction_ratio:
        print(f"vCPU reduction {vcpu_reduction:.2%} exceeds policy limit {policy.max_vcpu_reduction_ratio:.2%}")
        return False
    
    # Check RAM reduction
    ram_reduction = (original_req.ram_gb - downgraded_req.ram_gb) / original_req.ram_gb
    if ram_reduction > policy.max_ram_reduction_ratio:
        print(f"RAM reduction {ram_reduction:.2%} exceeds policy limit {policy.max_ram_reduction_ratio:.2%}")
        return False
    
    # Check minimum resource requirements
    if downgraded_req.vcpus < 1:
        print("vCPUs cannot go below 1")
        return False
    
    if downgraded_req.ram_gb < 1:
        print("RAM cannot go below 1 GB")
        return False
    
    return True
