# ENVBoot Case Studies for Resource Allocation and Charging in Chameleon

This document describes the four case studies implemented in ENVBoot for demonstrating intelligent resource allocation and charging strategies in the Chameleon Cloud environment.

## Overview

The case studies demonstrate how an intelligent agent can analyze repository complexity, detect resource constraints, and make optimal decisions about resource allocation, timing, and cost management using Chameleon's Blazar reservation system and SU-based charging model.

## Case Study 1: Base Case

**Scenario**: Agent analysis requires hardware, resources are sufficient, agent acquires access directly.

**Implementation**: `envboot cases-base [REPO_PATH]`

**What it does**:
- Analyzes repository complexity automatically
- Maps complexity to appropriate resource requirements
- Creates Blazar reservation for immediate use
- Calculates SU consumption estimates
- Outputs human-readable results and JSON artifacts

**Example**:
```bash
envboot cases-base /path/to/repo --output results-base.json
```

**Expected Output**:
```
=== Case Study 1: Base Case ===
Analyzing repository complexity for: /path/to/repo
Detected complexity: heavy
Resource requirements: 8 vCPUs, 32 GB RAM, 1 GPUs
Duration: 4.0 hours
Creating Blazar reservation...
SU estimate: 0.6667 per hour, 2.6668 total

=== Results ===
Reservation created: lease-12345
Zone: current
Start: 2024-01-15 10:02:00+00:00
End: 2024-01-15 14:02:00+00:00
Flavor: g1.kvm.1
SU cost: 2.6668
```

## Case Study 2: Limited Resources (Sub-case A)

**Scenario**: Agent detects resource shortage in current zone and reserves resources in a different available time or zone.

**Implementation**: `envboot cases-limited [REPO_PATH]`

**What it does**:
- Detects existing resource overload in current zone
- Searches for alternative time windows (up to 72 hours ahead)
- If no time available, searches alternative zones
- Creates reservation in optimal location/time
- Tracks decision path (time shift vs. zone change)

**Options**:
- `--lookahead 72`: Hours to look ahead for availability
- `--alt-zones "zoneA,zoneB,zoneC"`: Alternative zones to consider

**Example**:
```bash
envboot cases-limited /path/to/repo --lookahead 48 --alt-zones "CHI@UC,CHI@TACC" --output results-limited.json
```

**Expected Output**:
```
=== Case Study 2: Limited Resources ===
Detected complexity: heavy
Resource requirements: 8 vCPUs, 32 GB RAM, 1 GPUs
Duration: 4.0 hours
Checking for resource overload in zone: current
❌ Resource overload detected in current zone
Searching for alternative time windows and zones...
✅ Found available window in zone: CHI@TACC
   Start: 2024-01-15 12:00:00+00:00
   End: 2024-01-15 16:00:00+00:00
Creating Blazar reservation...
```

## Case Study 3: Downgrade Scenario

**Scenario**: Current resources don't fully meet requirements, agent analysis decides a slight downgrade is acceptable and works.

**Implementation**: `envboot cases-downgrade [REPO_PATH]`

**What it does**:
- Attempts resource downgrade according to policy
- Never downgrades GPU for heavy/very_heavy repos with GPU frameworks
- Allows vCPU reduction up to 50%, RAM reduction up to 25%
- Runs smoke test to validate downgrade (if provided)
- Increases duration to compensate for reduced resources
- Calculates cost savings

**Options**:
- `--smoke-test "python test.py"`: Command to run as smoke test
- `--allow-gpu-downgrade`: Allow GPU to CPU downgrade

**Example**:
```bash
envboot cases-downgrade /path/to/repo --smoke-test "python -c 'import torch; print(torch.cuda.is_available())'" --output results-downgrade.json
```

**Expected Output**:
```
=== Case Study 3: Downgrade Scenario ===
Original requirements: 8 vCPUs, 32 GB RAM, 1 GPUs
Original duration: 4.0 hours
Attempting resource downgrade...
Downgraded vCPUs: 8 → 4
Downgraded RAM: 32 GB → 24 GB
✅ Downgrade applied successfully
Running smoke test to validate downgrade...
✅ Smoke test passed
Adjusted duration: 6.0 hours
Creating Blazar reservation with downgraded resources...
SU cost: 0.3334
Downgrade savings: 1.3334 SU
```

## Case Study 4: Repository Complexity Analysis

**Scenario**: Match repository complexity to resource choice with intelligent mapping.

**Implementation**: `envboot cases-complexity [REPO_PATH]`

**What it does**:
- Analyzes repository using deterministic scoring system
- Maps complexity tiers to appropriate resource profiles
- Creates reservations with complexity-appropriate duration
- Demonstrates cost optimization through intelligent resource selection

**Options**:
- `--duration 8.0`: Override reservation duration in hours

**Example**:
```bash
envboot cases-complexity /path/to/repo --duration 6.0 --output results-complexity.json
```

**Expected Output**:
```
=== Case Study 4: Repository Complexity Analysis ===
Complexity tier: heavy
Resource requirements: 8 vCPUs, 32 GB RAM, 1 GPUs
Reservation duration: 6.0 hours
Resource type: KVM
Creating Blazar reservation...
SU cost: 4.0002
Complexity-based resource mapping: ✅
```

## Repository Complexity Scoring

The system uses a deterministic scoring algorithm to categorize repositories:

### Scoring Signals
- **GPU Frameworks** (+3): `torch`, `tensorflow`, `jax`, `cuda`, `cupy`, `pytorch-lightning`
- **CUDA Files** (+2): Presence of `.cu` files
- **NVIDIA Docker** (+2): Dockerfile with NVIDIA base images
- **Build System** (+1): `Dockerfile`, `Makefile`, `CMakeLists.txt`
- **Large Codebase** (+1): >500 files or >50k lines of code
- **Large Files** (+1): Any file >500 MB
- **Test Footprint** (+1): >50 test/CI files

### Complexity Tiers
- **Simple** (0-1): KVM, 2 vCPU, 4 GB RAM, 1 hour
- **Moderate** (2-3): KVM, 8 vCPU, 16 GB RAM, 2 hours
- **Heavy** (4-5): KVM, 8 vCPU, 32 GB RAM, 1 GPU, 4 hours
- **Very Heavy** (6+): Bare-metal GPU node or KVM with 2 GPUs, 8 hours

## SU Charging Model

Based on Chameleon's flat-rate SU system:

- **Bare-metal CPU host**: 1.0 SU/hour
- **Bare-metal GPU/FPGA node**: 2.0 SU/hour
- **KVM CPU**: 1.0 × (vcpus / host_vcpus) SU/hour
- **KVM GPU**: 2.0 × (gpus / host_gpus) SU/hour

### Example Calculations
- **Simple repo**: 2/48 vCPUs = 0.0417 SU/hour
- **Moderate repo**: 8/48 vCPUs = 0.1667 SU/hour
- **Heavy repo**: 8/48 vCPUs + 1/4 GPU = 0.1667 + 0.5 = 0.6667 SU/hour
- **Very heavy repo**: Bare-metal GPU = 2.0 SU/hour

## Configuration

### Environment Variables
```bash
# Downgrade Policy
ENVBOOT_ALLOW_GPU_DOWNGRADE=true
ENVBOOT_MAX_VCPU_REDUCTION=0.5
ENVBOOT_MAX_RAM_REDUCTION=0.25
ENVBOOT_MAX_DURATION_INCREASE=2.0
ENVBOOT_REQUIRE_SMOKE_TEST=true

# Scheduling
ENVBOOT_LOOKAHEAD_HOURS=72
ENVBOOT_STEP_MINUTES=30
ENVBOOT_PREFERRED_ZONE=current
ENVBOOT_ALT_ZONES=CHI@UC,CHI@TACC

# Host Capabilities (for SU calculations)
ENVBOOT_HOST_VCPUS=48
ENVBOOT_HOST_GPUS=4
ENVBOOT_HOST_RAM_GB=192
ENVBOOT_HOST_DISK_GB=1000
```

### Output Format

All case studies produce structured JSON output:

```json
{
  "case": "base_case",
  "inputs": {
    "repo_path": "/path/to/repo",
    "complexity_tier": "heavy",
    "resource_request": {
      "vcpus": 8,
      "ram_gb": 32,
      "gpus": 1,
      "bare_metal": false
    },
    "duration_hours": 4.0
  },
  "decisions": [],
  "reservation": {
    "zone": "current",
    "start": "2024-01-15T10:02:00+00:00",
    "end": "2024-01-15T14:02:00+00:00",
    "flavor": "g1.kvm.1",
    "count": 1,
    "lease_id": "lease-12345"
  },
  "su_estimate_per_hour": 0.6667,
  "su_estimate_total": 2.6668,
  "slo": {
    "start_by": "2024-01-15T10:02:00+00:00",
    "met": true
  },
  "complexity_tier": "heavy"
}
```

## Usage Examples

### Quick Start
```bash
# Analyze current directory
envboot cases-base .

# Analyze specific repository with complexity override
envboot cases-base /path/to/ml-repo --complexity heavy

# Test limited resources scenario
envboot cases-limited . --lookahead 24

# Test downgrade with smoke test
envboot cases-downgrade . --smoke-test "python -c 'print(1+1)'"

# Analyze complexity with custom duration
envboot cases-complexity . --duration 12.0
```

### Batch Analysis
```bash
# Analyze multiple repositories
for repo in repo1 repo2 repo3; do
    envboot cases-base $repo --output results-${repo}.json
done

# Compare different scenarios
envboot cases-base . --output base.json
envboot cases-limited . --output limited.json
envboot cases-downgrade . --output downgrade.json
```

## Future Extensions

1. **Sub-case B**: Artificial traffic jam simulation
2. **Dynamic pricing**: Support for future KVM flavor-specific rates
3. **Multi-zone optimization**: Intelligent zone selection based on cost and availability
4. **Predictive scheduling**: Machine learning-based resource demand forecasting
5. **Cost optimization**: Multi-objective optimization for cost vs. performance

## Troubleshooting

### Common Issues
- **Authentication errors**: Check OpenStack credentials and environment variables
- **Resource not found**: Verify zone names and resource availability
- **Smoke test failures**: Ensure test commands are appropriate for downgraded resources
- **Complexity detection**: Check repository structure and file permissions

### Debug Mode
Set `ENVBOOT_DEBUG=true` for verbose logging and detailed error messages.

## Contributing

The case studies are designed to be extensible. New scenarios can be added by:
1. Creating new CLI commands in `cli.py`
2. Adding supporting functions in the appropriate modules
3. Updating the configuration system in `config.py`
4. Adding tests and documentation

## References

- [Chameleon SU Charging Model](https://chameleoncloud.org/learn/frequently-asked-questions/#toc-what-are-the-units-of-an-allocation-and-how-am-i-charged-)
- [Blazar Reservation API](https://docs.openstack.org/api-ref/reservation/)
- [OpenStack Python SDK](https://docs.openstack.org/openstacksdk/)
- [ENVBoot Project](https://github.com/chameleoncloud/envboot)
