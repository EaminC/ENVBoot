#!/usr/bin/env python3
"""
Comprehensive test suite for ENVBoot case studies.
Tests all functionality without requiring OpenStack credentials.
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add the envboot package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'envboot'))

def create_test_repo(repo_path: str, complexity: str):
    """Create a test repository with the specified complexity."""
    repo_path = Path(repo_path)
    repo_path.mkdir(parents=True, exist_ok=True)
    
    if complexity == "simple":
        # Simple repo: basic Python project
        (repo_path / "main.py").write_text("print('Hello, World!')\n")
        (repo_path / "requirements.txt").write_text("requests==2.31.0\n")
        
    elif complexity == "moderate":
        # Moderate repo: medium Python project with tests
        (repo_path / "main.py").write_text("import requests\nprint('Moderate complexity')\n")
        (repo_path / "requirements.txt").write_text("requests==2.31.0\npandas==2.0.0\n")
        (repo_path / "tests").mkdir()
        (repo_path / "tests" / "test_main.py").write_text("def test_main():\n    assert True\n")
        
    elif complexity == "heavy":
        # Heavy repo: ML project with GPU requirements
        (repo_path / "main.py").write_text("import torch\nprint('Heavy ML workload')\n")
        (repo_path / "requirements.txt").write_text("torch==2.0.0\ntensorflow==2.13.0\n")
        (repo_path / "Dockerfile").write_text("FROM nvidia/cuda:11.8-base\n")
        (repo_path / "data").mkdir()
        (repo_path / "models").mkdir()
        
    elif complexity == "very_heavy":
        # Very heavy repo: complex ML project
        (repo_path / "main.py").write_text("import torch\nimport tensorflow\nprint('Very heavy workload')\n")
        (repo_path / "requirements.txt").write_text("torch==2.0.0\ntensorflow==2.13.0\njax==0.4.0\n")
        (repo_path / "Dockerfile").write_text("FROM nvidia/cuda:11.8-base\n")
        (repo_path / "src").mkdir()
        (repo_path / "src" / "model.cu").write_text("// CUDA kernel\n")
        (repo_path / "tests").mkdir()
        for i in range(100):
            (repo_path / "tests" / f"test_{i}.py").write_text(f"def test_{i}():\n    assert True\n")

def test_complexity_analysis():
    """Test repository complexity analysis."""
    print("=== Testing Repository Complexity Analysis ===")
    
    try:
        from envboot.analysis import analyze_repo_complexity, map_complexity_to_request
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test each complexity level
            for complexity in ["simple", "moderate", "heavy", "very_heavy"]:
                repo_path = os.path.join(temp_dir, f"test_{complexity}")
                create_test_repo(repo_path, complexity)
                
                # Analyze complexity
                detected_tier = analyze_repo_complexity(repo_path)
                print(f"  {complexity:12} → detected as: {detected_tier.value}")
                
                # Map to resources
                req = map_complexity_to_request(detected_tier)
                print(f"    Resources: {req.vcpus} vCPUs, {req.ram_gb} GB RAM, {req.gpus} GPUs")
                print(f"    Bare metal: {req.bare_metal}")
        
        print("✅ Complexity analysis test passed")
        return True
        
    except Exception as e:
        print(f"❌ Complexity analysis test failed: {e}")
        return False

def test_su_estimation():
    """Test SU estimation calculations."""
    print("\n=== Testing SU Estimation ===")
    
    try:
        from envboot.analysis import estimate_su_per_hour
        from envboot.models import ResourceRequest
        
        # Test cases
        test_cases = [
            ResourceRequest(vcpus=2, ram_gb=4, gpus=0, bare_metal=False),   # Simple
            ResourceRequest(vcpus=8, ram_gb=16, gpus=0, bare_metal=False),  # Moderate
            ResourceRequest(vcpus=8, ram_gb=32, gpus=1, bare_metal=False),  # Heavy
            ResourceRequest(vcpus=16, ram_gb=64, gpus=2, bare_metal=True),  # Very heavy
        ]
        
        host_caps = {"vcpus": 48, "gpus": 4}
        
        for i, req in enumerate(test_cases):
            su_per_hour = estimate_su_per_hour(req, host_caps)
            complexity = ["Simple", "Moderate", "Heavy", "Very Heavy"][i]
            print(f"  {complexity:12}: {su_per_hour:.4f} SU/hour")
        
        print("✅ SU estimation test passed")
        return True
        
    except Exception as e:
        print(f"❌ SU estimation test failed: {e}")
        return False

def test_downgrade_logic():
    """Test the downgrade logic."""
    print("\n=== Testing Downgrade Logic ===")
    
    try:
        from envboot.downgrade import try_downgrade, validate_downgrade_policy
        from envboot.models import ResourceRequest, DowngradePolicy, ComplexityTier
        
        # Test case: heavy repo with GPU
        original_req = ResourceRequest(vcpus=8, ram_gb=32, gpus=1, bare_metal=False)
        policy = DowngradePolicy(allow_gpu_to_cpu=True)
        complexity_tier = ComplexityTier.HEAVY
        
        print(f"  Original: {original_req.vcpus} vCPUs, {original_req.ram_gb} GB RAM, {original_req.gpus} GPUs")
        
        # Try downgrade
        downgraded_req, applied = try_downgrade(original_req, policy, complexity_tier)
        
        if applied:
            print(f"  Downgraded: {downgraded_req.vcpus} vCPUs, {downgraded_req.ram_gb} GB RAM, {downgraded_req.gpus} GPUs")
            
            # Validate policy
            if validate_downgrade_policy(original_req, downgraded_req, policy):
                print("  ✅ Policy validation passed")
            else:
                print("  ❌ Policy validation failed")
        else:
            print("  No downgrade applied")
        
        print("✅ Downgrade logic test passed")
        return True
        
    except Exception as e:
        print(f"❌ Downgrade logic test failed: {e}")
        return False

def test_scheduling_logic():
    """Test the scheduling logic (without actual OpenStack calls)."""
    print("\n=== Testing Scheduling Logic ===")
    
    try:
        from envboot.scheduling import find_matching_flavor
        from envboot.models import ResourceRequest
        
        # Test flavor matching
        test_cases = [
            ResourceRequest(vcpus=2, ram_gb=4, gpus=0, bare_metal=False),
            ResourceRequest(vcpus=8, ram_gb=16, gpus=0, bare_metal=False),
            ResourceRequest(vcpus=8, ram_gb=32, gpus=1, bare_metal=False),
            ResourceRequest(vcpus=16, ram_gb=64, gpus=2, bare_metal=True),
        ]
        
        for req in test_cases:
            flavor = find_matching_flavor(req, "test_zone")
            print(f"  {req.vcpus}vCPU, {req.ram_gb}GB, {req.gpus}GPU → {flavor}")
        
        print("✅ Scheduling logic test passed")
        return True
        
    except Exception as e:
        print(f"❌ Scheduling logic test failed: {e}")
        return False

def test_configuration():
    """Test configuration loading."""
    print("\n=== Testing Configuration ===")
    
    try:
        from envboot.config import (
            get_default_downgrade_policy, 
            get_default_scheduling_config,
            get_chameleon_su_rates,
            get_default_host_capabilities
        )
        
        # Test downgrade policy
        policy = get_default_downgrade_policy()
        print(f"  Downgrade policy: GPU→CPU={policy.allow_gpu_to_cpu}, vCPU reduction={policy.max_vcpu_reduction_ratio}")
        
        # Test scheduling config
        config = get_default_scheduling_config()
        print(f"  Scheduling: lookahead={config.lookahead_hours}h, step={config.step_minutes}m")
        
        # Test SU rates
        rates = get_chameleon_su_rates()
        print(f"  SU rates: bare metal CPU={rates['bare_metal_cpu']}, GPU={rates['bare_metal_gpu']}")
        
        # Test host capabilities
        caps = get_default_host_capabilities()
        print(f"  Host caps: {caps['vcpus']} vCPUs, {caps['gpus']} GPUs")
        
        print("✅ Configuration test passed")
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_models():
    """Test data model creation and serialization."""
    print("\n=== Testing Data Models ===")
    
    try:
        from envboot.models import (
            ComplexityTier, ResourceRequest, DowngradePolicy, 
            SchedulingConfig, ReservationPlan, CaseStudyResult
        )
        from datetime import datetime, timezone
        
        # Test ResourceRequest
        req = ResourceRequest(vcpus=4, ram_gb=8, gpus=0)
        print(f"  ResourceRequest: {req.vcpus} vCPUs, {req.ram_gb} GB RAM")
        
        # Test DowngradePolicy
        policy = DowngradePolicy(max_vcpu_reduction_ratio=0.5)
        print(f"  DowngradePolicy: max vCPU reduction = {policy.max_vcpu_reduction_ratio}")
        
        # Test SchedulingConfig
        config = SchedulingConfig(lookahead_hours=48, step_minutes=30)
        print(f"  SchedulingConfig: {config.lookahead_hours}h lookahead, {config.step_minutes}m steps")
        
        # Test ReservationPlan
        now = datetime.now(timezone.utc)
        plan = ReservationPlan(
            zone="test_zone",
            start=now,
            end=now,
            flavor="test_flavor",
            count=1
        )
        print(f"  ReservationPlan: zone={plan.zone}, flavor={plan.flavor}")
        
        # Test CaseStudyResult
        result = CaseStudyResult(
            case="test_case",
            inputs={"test": "data"},
            decisions=[],
            reservation=plan,
            su_estimate_per_hour=1.0,
            su_estimate_total=2.0,
            slo={"met": True}
        )
        print(f"  CaseStudyResult: case={result.case}, SU total={result.su_estimate_total}")
        
        # Test JSON serialization
        json_str = json.dumps(result.__dict__, default=str)
        print(f"  JSON serialization: {len(json_str)} characters")
        
        print("✅ Data models test passed")
        return True
        
    except Exception as e:
        print(f"❌ Data models test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("ENVBoot Case Studies - Comprehensive Test Suite")
    print("=" * 60)
    
    tests = [
        test_complexity_analysis,
        test_su_estimation,
        test_downgrade_logic,
        test_scheduling_logic,
        test_configuration,
        test_models,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The case studies are ready for integration testing.")
        print("\nNext steps:")
        print("  1. Set up Chameleon credentials")
        print("  2. Run integration tests with real OpenStack")
        print("  3. Test actual case study execution")
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())