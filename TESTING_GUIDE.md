# ENVBoot Case Studies - Testing Guide

## 🧪 **Testing Strategy Overview**

This guide covers the comprehensive testing approach for the ENVBoot case studies, from unit tests to full integration testing with Chameleon Cloud.

## 🚀 **1. Unit Testing (Already Complete)**

### **What We Test**
- ✅ Repository complexity analysis
- ✅ SU estimation calculations
- ✅ Downgrade logic and policies
- ✅ Scheduling algorithms
- ✅ Configuration management
- ✅ Data model serialization

### **Run Unit Tests**
```bash
python test_all.py
```

**Expected Output**: All 6 tests should pass, validating core functionality without OpenStack dependencies.

## 🔗 **2. Integration Testing (Ready to Run)**

### **Prerequisites**
1. **Install the package**:
   ```bash
   pip install -e .
   ```

2. **Set up Chameleon credentials**:
   ```bash
   source CHI-251467-openrc.sh
   ```

3. **Verify authentication**:
   ```bash
   envboot auth-check
   ```

### **Test Each Case Study**

#### **Case 1: Base Case**
```bash
# Test with current directory
envboot cases-base .

# Test with specific repository
envboot cases-base /path/to/repo

# Save results to JSON
envboot cases-base . --output results-base.json
```

#### **Case 2: Limited Resources**
```bash
# Test with default settings
envboot cases-limited .

# Test with custom lookahead and zones
envboot cases-limited . --lookahead 24 --alt-zones "CHI@UC,CHI@TACC"

# Save results
envboot cases-limited . --output results-limited.json
```

#### **Case 3: Downgrade Scenario**
```bash
# Test with smoke test
envboot cases-downgrade . --smoke-test "python -c 'print(1+1)'"

# Test without GPU downgrade
envboot cases-downgrade . --allow-gpu-downgrade false

# Save results
envboot cases-downgrade . --output results-downgrade.json
```

#### **Case 4: Repository Complexity**
```bash
# Test with auto-detection
envboot cases-complexity .

# Test with complexity override
envboot cases-complexity . --complexity heavy

# Test with custom duration
envboot cases-complexity . --duration 6.0

# Save results
envboot cases-complexity . --output results-complexity.json
```

## 🎯 **3. Testing Scenarios**

### **Scenario A: Simple Repository**
```bash
# Create a simple test repo
mkdir test-simple
echo "print('Hello')" > test-simple/main.py
echo "requests" > test-simple/requirements.txt

# Test all case studies
envboot cases-base test-simple --output simple-base.json
envboot cases-limited test-simple --output simple-limited.json
envboot cases-downgrade test-simple --output simple-downgrade.json
envboot cases-complexity test-simple --output simple-complexity.json
```

### **Scenario B: Heavy ML Repository**
```bash
# Create a heavy ML repo
mkdir test-heavy
echo "import torch" > test-heavy/main.py
echo "torch\ntensorflow" > test-heavy/requirements.txt
echo "FROM nvidia/cuda:11.8-base" > test-heavy/Dockerfile

# Test all case studies
envboot cases-base test-heavy --output heavy-base.json
envboot cases-limited test-heavy --output heavy-limited.json
envboot cases-downgrade test-heavy --output heavy-downgrade.json
envboot cases-complexity test-heavy --output heavy-complexity.json
```

### **Scenario C: Cross-Zone Testing**
```bash
# Test limited resources with multiple zones
envboot cases-limited . \
  --lookahead 48 \
  --alt-zones "CHI@UC,CHI@TACC" \
  --output cross-zone.json
```

## 🔧 **4. Configuration Testing**

### **Test Different Policies**
```bash
# Test aggressive downgrade
export ENVBOOT_MAX_VCPU_REDUCTION=0.75
export ENVBOOT_MAX_RAM_REDUCTION=0.5
envboot cases-downgrade . --output aggressive-downgrade.json

# Test conservative downgrade
export ENVBOOT_MAX_VCPU_REDUCTION=0.25
export ENVBOOT_MAX_RAM_REDUCTION=0.1
envboot cases-downgrade . --output conservative-downgrade.json
```

### **Test Different Scheduling**
```bash
# Test fine-grained scheduling
export ENVBOOT_STEP_MINUTES=15
envboot cases-limited . --output fine-grained.json

# Test coarse scheduling
export ENVBOOT_STEP_MINUTES=120
envboot cases-limited . --output coarse-grained.json
```

## 📊 **5. Output Validation**

### **Check JSON Structure**
Each case study produces structured JSON output. Validate the format:

```bash
# Check JSON syntax
python -m json.tool results-base.json

# Extract specific fields
jq '.case' results-base.json
jq '.su_estimate_total' results-base.json
jq '.reservation.zone' results-base.json
```

### **Expected Output Fields**
```json
{
  "case": "base_case",
  "inputs": {...},
  "decisions": [...],
  "reservation": {...},
  "su_estimate_per_hour": 0.6667,
  "su_estimate_total": 2.6668,
  "slo": {...},
  "complexity_tier": "heavy"
}
```

## 🚨 **6. Error Testing**

### **Test Invalid Inputs**
```bash
# Test non-existent repository
envboot cases-base /nonexistent/repo

# Test invalid complexity override
envboot cases-base . --complexity invalid

# Test invalid duration
envboot cases-complexity . --duration -1
```

### **Test Resource Constraints**
```bash
# Test with very large resource requirements
# (This may trigger different error paths)
envboot cases-base . --complexity very_heavy
```

## 📈 **7. Performance Testing**

### **Test Large Repositories**
```bash
# Test with a large ML repository
git clone https://github.com/pytorch/pytorch.git
envboot cases-complexity pytorch --output pytorch-analysis.json
```

### **Test Long Lookahead Periods**
```bash
# Test with extended lookahead
export ENVBOOT_LOOKAHEAD_HOURS=168  # 1 week
envboot cases-limited . --output week-lookahead.json
```


## 📋 **9. Testing Checklist**

### **Before Running Case Studies**
- [ ] Package installed (`pip install -e .`)
- [ ] Credentials loaded (`source CHI-251467-openrc.sh`)
- [ ] Authentication verified (`envboot auth-check`)
- [ ] Unit tests passed (`python test_all.py`)

### **Case Study Testing**
- [ ] Base case works with simple repo
- [ ] Base case works with heavy repo
- [ ] Limited resources detects overload
- [ ] Limited resources finds alternatives
- [ ] Downgrade applies correctly
- [ ] Downgrade respects policies
- [ ] Complexity analysis accurate
- [ ] JSON output valid

### **Configuration Testing**
- [ ] Environment variables work
- [ ] Policy overrides apply
- [ ] Scheduling configs work
- [ ] Step sizes handle edge cases

