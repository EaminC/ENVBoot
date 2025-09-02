import os
import re
from pathlib import Path
from typing import Dict, Any, Tuple
from .models import ComplexityTier, ResourceRequest


def analyze_repo_complexity_with_signals(repo_path: str) -> Tuple[ComplexityTier, Dict[str, Any]]:
    """Same logic as analyze_repo_complexity, but also returns the signals dict."""
    tier = analyze_repo_complexity(repo_path)
    repo_path = Path(repo_path)
    signals: Dict[str, Any] = {}
    score = 0

    # GPU frameworks
    for req_file in ["requirements.txt", "pyproject.toml"]:
        req_path = repo_path / req_file
        if req_path.exists():
            content = req_path.read_text().lower()
            gpu_frameworks = ["torch", "tensorflow", "jax", "cuda", "cupy", "pytorch-lightning"]
            found = [f for f in gpu_frameworks if f in content]
            if found:
                score += 3
                signals["gpu_frameworks"] = found

    # CUDA files
    cuda_files = list(repo_path.rglob("*.cu"))
    if cuda_files:
        score += 2
        signals["cuda_files"] = len(cuda_files)

    # Build system files
    build_files = ["Dockerfile", "Makefile", "CMakeLists.txt"]
    found_build = [f for f in build_files if (repo_path / f).exists()]
    if found_build:
        score += 1
        signals["build_files"] = found_build

    # NVIDIA base image in Dockerfile
    dockerfile_path = repo_path / "Dockerfile"
    if dockerfile_path.exists() and "nvidia" in dockerfile_path.read_text().lower():
        score += 2
        signals["nvidia_docker"] = True

    # File/LOC counts
    total_files = 0
    total_loc = 0
    for file_path in repo_path.rglob("*"):
        if file_path.is_file() and not file_path.name.startswith('.'):
            total_files += 1
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    total_loc += len(f.readlines())
            except:
                pass
    if total_files > 500 or total_loc > 50000:
        score += 1
        signals["large_codebase"] = {"files": total_files, "loc": total_loc}

    # Test footprint
    test_files = list(repo_path.rglob("*test*.py")) + list(repo_path.rglob("tests/*"))
    ci_files = list(repo_path.rglob(".github/*")) + list(repo_path.rglob(".gitlab-ci*")) + list(repo_path.rglob("*.yml"))
    total_tests = len(test_files) + len(ci_files)
    if total_tests > 50:
        score += 1
        signals["test_footprint"] = total_tests

    signals["final_score"] = score
    signals["tier"] = tier.value
    return tier, signals


def analyze_repo_complexity(repo_path: str) -> ComplexityTier:
    """Analyze repository complexity using deterministic scoring."""
    repo_path = Path(repo_path)
    if not repo_path.exists():
        raise ValueError(f"Repository path does not exist: {repo_path}")
    
    score = 0
    signals = {}
    
    # Check for GPU frameworks in requirements files
    for req_file in ["requirements.txt", "pyproject.toml"]:
        req_path = repo_path / req_file
        if req_path.exists():
            content = req_path.read_text().lower()
            gpu_frameworks = ["torch", "tensorflow", "jax", "cuda", "cupy", "pytorch-lightning"]
            found_frameworks = [f for f in gpu_frameworks if f in content]
            if found_frameworks:
                score += 3
                signals["gpu_frameworks"] = found_frameworks
    
    # Check for CUDA or .cu files
    cuda_files = list(repo_path.rglob("*.cu"))
    if cuda_files:
        score += 2
        signals["cuda_files"] = len(cuda_files)
    
    # Check for build system files
    build_files = ["Dockerfile", "Makefile", "CMakeLists.txt"]
    found_build_files = [f for f in build_files if (repo_path / f).exists()]
    if found_build_files:
        score += 1
        signals["build_files"] = found_build_files
    
    # Check for Dockerfile with NVIDIA base images
    dockerfile_path = repo_path / "Dockerfile"
    if dockerfile_path.exists():
        content = dockerfile_path.read_text().lower()
        if "nvidia" in content:
            score += 2
            signals["nvidia_docker"] = True
    
    # Count total files and estimate LOC
    total_files = 0
    total_loc = 0
    large_files = []
    
    for file_path in repo_path.rglob("*"):
        if file_path.is_file() and not file_path.name.startswith('.'):
            total_files += 1
            try:
                # Count lines (rough LOC estimate)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = len(f.readlines())
                    total_loc += lines
                
                # Check for large files
                file_size = file_path.stat().st_size
                if file_size > 500 * 1024 * 1024:  # 500 MB
                    large_files.append((file_path.name, file_size))
            except:
                pass
    
    if total_files > 500 or total_loc > 50000:
        score += 1
        signals["large_codebase"] = {"files": total_files, "loc": total_loc}
    
    if large_files:
        score += 1
        signals["large_files"] = large_files
    
    # Check for data directories
    data_dirs = [d for d in repo_path.iterdir() if d.is_dir() and d.name.lower() in ["data", "datasets", "models"]]
    if data_dirs:
        signals["data_dirs"] = [d.name for d in data_dirs]
    
    # Count tests
    test_files = list(repo_path.rglob("*test*.py")) + list(repo_path.rglob("tests/*"))
    ci_files = list(repo_path.rglob(".github/*")) + list(repo_path.rglob(".gitlab-ci*")) + list(repo_path.rglob("*.yml"))
    total_tests = len(test_files) + len(ci_files)
    
    if total_tests > 50:
        score += 1
        signals["test_footprint"] = total_tests
    
    # Determine tier
    if score <= 1:
        tier = ComplexityTier.SIMPLE
    elif score <= 3:
        tier = ComplexityTier.MODERATE
    elif score <= 5:
        tier = ComplexityTier.HEAVY
    else:
        tier = ComplexityTier.VERY_HEAVY
    
    signals["final_score"] = score
    signals["tier"] = tier.value
    
    return tier

def map_complexity_to_request(tier: ComplexityTier) -> ResourceRequest:
    """Map complexity tier to default resource requirements."""
    if tier == ComplexityTier.SIMPLE:
        return ResourceRequest(vcpus=2, ram_gb=4, gpus=0, disk_gb=20, bare_metal=False)
    elif tier == ComplexityTier.MODERATE:
        return ResourceRequest(vcpus=8, ram_gb=16, gpus=0, disk_gb=40, bare_metal=False)
    elif tier == ComplexityTier.HEAVY:
        return ResourceRequest(vcpus=8, ram_gb=32, gpus=1, disk_gb=80, bare_metal=False)
    elif tier == ComplexityTier.VERY_HEAVY:
        return ResourceRequest(vcpus=16, ram_gb=64, gpus=2, disk_gb=160, bare_metal=True)
    else:
        raise ValueError(f"Unknown complexity tier: {tier}")

def estimate_su_per_hour(req: ResourceRequest, host_caps: Dict[str, Any]) -> float:
    """Estimate SU consumption per hour based on Chameleon charging model."""
    if req.bare_metal:
        # Bare metal: 1.0 SU/hour for CPU, 2.0 SU/hour for GPU/FPGA
        if req.gpus > 0:
            return 2.0
        else:
            return 1.0
    else:
        # KVM: proportional to host resources
        host_vcpus = host_caps.get("vcpus", 48)  # Default assumption
        host_gpus = host_caps.get("gpus", 4)     # Default assumption
        
        cpu_su = 1.0 * (req.vcpus / host_vcpus)
        gpu_su = 2.0 * (req.gpus / host_gpus) if req.gpus > 0 else 0
        
        return cpu_su + gpu_su

def get_default_duration_hours(tier: ComplexityTier) -> float:
    """Get default reservation duration based on complexity tier."""
    if tier == ComplexityTier.SIMPLE:
        return 1.0
    elif tier == ComplexityTier.MODERATE:
        return 2.0
    elif tier == ComplexityTier.HEAVY:
        return 4.0
    elif tier == ComplexityTier.VERY_HEAVY:
        return 8.0
    else:
        return 2.0  # Default fallback
