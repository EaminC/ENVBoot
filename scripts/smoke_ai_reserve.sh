#!/bin/sh
#
# Smoke test for envboot CLI AI reserve flows.
#
# Usage:
#   scripts/smoke_ai_reserve.sh [--output-prefix /tmp/envboot-ai]
#
# Notes:
# - Runs a suite of checks:
#     1) FINAL (SIMPLE) using forge source
#     2) DOWNGRADE (GPU/HEAVY) using forge source with ENVBOOT_FAKE_GPU=1
#     3) CPU-only downgrade (no GPU path) via forge source
#     4) GPU→CPU allowed downgrade using cases-downgrade on a fake GPU repo
#     5) Smoke-test required: fail and succeed variants using cases-downgrade
#     6) Complexity review mode parsing
# - Asserts on stdout using grep/awk; exits non-zero on failure.
# - If --output-prefix is provided, writes CLI JSON outputs and stdout logs under that prefix.
# - Requires FORGE_API_KEY and valid OpenStack auth for reservation creation.

set -eu

OUT_PREFIX=""
if [ "${1-}" = "--output-prefix" ] && [ -n "${2-}" ]; then
  OUT_PREFIX="$2"
  shift 2
fi

ok() { printf "[OK] %s\n" "$1"; }
fail() { printf "[FAIL] %s\n" "$1"; }

overall_rc=0

run_final_simple() {
  name="FINAL (SIMPLE)"
  cmd="python -m envboot.cli ai-reserve --source forge --mode final"
  if [ -n "$OUT_PREFIX" ]; then
    out_json="${OUT_PREFIX}-final.json"
    cmd="$cmd --output $out_json"
  fi

  if [ -n "$OUT_PREFIX" ]; then
    stdout_log="${OUT_PREFIX}-final.stdout"
    # shellcheck disable=SC2090
    sh -c "$cmd" >"$stdout_log" 2>&1 || true
    output=$(cat "$stdout_log")
  else
    # Capture stdout
    # shellcheck disable=SC2090
    output=$(sh -c "$cmd" 2>&1 || true)
  fi

  rc=0
  echo "$output" | grep -q "AI chose: 2 vCPUs" || { fail "$name: expected 'AI chose: 2 vCPUs'"; rc=1; }
  echo "$output" | grep -q " 0 GPUs" || { fail "$name: expected '0 GPUs'"; rc=1; }
  echo "$output" | grep -q "Flavor: g1.kvm.2" || { fail "$name: expected 'Flavor: g1.kvm.2'"; rc=1; }
  echo "$output" | grep -q "\u00d7 multiplier 1.00" || echo "$output" | grep -q "× multiplier 1.00" || { fail "$name: expected '× multiplier 1.00'"; rc=1; }

  if [ $rc -eq 0 ]; then ok "$name"; else overall_rc=1; fi
}

run_downgrade_gpu() {
  name="DOWNGRADE (GPU/HEAVY)"
  cmd="ENVBOOT_FAKE_GPU=1 python -m envboot.cli ai-reserve --source forge --mode downgrade"
  if [ -n "$OUT_PREFIX" ]; then
    out_json="${OUT_PREFIX}-downgrade.json"
    cmd="$cmd --output $out_json"
  fi

  if [ -n "$OUT_PREFIX" ]; then
    stdout_log="${OUT_PREFIX}-downgrade.stdout"
    # shellcheck disable=SC2090
    sh -c "$cmd" >"$stdout_log" 2>&1 || true
    output=$(cat "$stdout_log")
  else
    # shellcheck disable=SC2090
    output=$(sh -c "$cmd" 2>&1 || true)
  fi

  rc=0
  echo "$output" | grep -q "AI chose: 8 vCPUs" || { fail "$name: expected 'AI chose: 8 vCPUs'"; rc=1; }
  echo "$output" | grep -q " 1 GPUs" || { fail "$name: expected '1 GPUs'"; rc=1; }
  echo "$output" | grep -q "Flavor: g1.kvm.1" || { fail "$name: expected 'Flavor: g1.kvm.1'"; rc=1; }

  # Extract the multiplier from the Duration line and assert > 1.0 and <= 2.0
  mult=$(printf "%s\n" "$output" | grep '^Duration:' | tail -n 1 | awk -F'multiplier ' 'NF>1{val=$2; sub(/[^0-9.].*$/, "", val); print val}')
  if [ -z "${mult}" ]; then
    fail "$name: could not parse duration multiplier"
    rc=1
  else
    # Use awk for floating-point comparison: >1.0 and <=2.0
    echo "$mult" | awk 'BEGIN{ok=0} {if ($1>1.0 && $1<=2.0) ok=1} END{exit ok?0:1}' || { fail "$name: multiplier $mult not in (1.0, 2.0]"; rc=1; }
  fi

  if [ $rc -eq 0 ]; then ok "$name"; else overall_rc=1; fi
}

run_downgrade_cpu_only() {
  name="DOWNGRADE (CPU-only)"
  cmd="python -m envboot.cli ai-reserve --source forge --mode downgrade"
  if [ -n "$OUT_PREFIX" ]; then
    out_json="${OUT_PREFIX}-downgrade-cpu.json"
    cmd="$cmd --output $out_json"
  fi

  if [ -n "$OUT_PREFIX" ]; then
    stdout_log="${OUT_PREFIX}-downgrade-cpu.stdout"
    sh -c "$cmd" >"$stdout_log" 2>&1 || true
    output=$(cat "$stdout_log")
  else
    output=$(sh -c "$cmd" 2>&1 || true)
  fi

  rc=0
  # Just sanity: parsing worked and we chose something
  echo "$output" | grep -q "\[ok\] Loaded AI bundle" || { fail "$name: loader did not report ok"; rc=1; }
  echo "$output" | grep -q "AI chose:" || { fail "$name: missing 'AI chose:' line"; rc=1; }
  echo "$output" | grep -q "Flavor:" || { fail "$name: missing 'Flavor:' line"; rc=1; }
  if [ $rc -eq 0 ]; then ok "$name"; else overall_rc=1; fi
}

make_fake_gpu_repo() {
  repo="$1"
  mkdir -p "$repo" || true
  # Minimal GPU-ish signals
  printf "torch==2.2.0\n" >"$repo/requirements.txt"
  : >"$repo/kernel.cu"
}

run_cases_downgrade_gpu_to_cpu() {
  name="CASES DOWNGRADE (GPU→CPU allowed)"
  repo="/tmp/gpu-smoke"
  make_fake_gpu_repo "$repo"
  out_json=""
  cmd="python -m envboot.cli cases-downgrade $repo --allow-gpu-downgrade True --smoke-test 'python -c \"print(1)\"'"
  if [ -n "$OUT_PREFIX" ]; then
    out_json="${OUT_PREFIX}-cases-downgrade.json"
    cmd="$cmd --output $out_json"
  fi

  # Run and capture RC
  if [ -n "$OUT_PREFIX" ]; then
    stdout_log="${OUT_PREFIX}-cases-downgrade.stdout"
    sh -c "$cmd" >"$stdout_log" 2>&1
    rc_cmd=$?
    output=$(cat "$stdout_log")
  else
    output=$(sh -c "$cmd" 2>&1)
    rc_cmd=$?
  fi

  rc=0
  if [ $rc_cmd -ne 0 ]; then
    fail "$name: command failed ($rc_cmd)"
    overall_rc=1
    return
  fi

  # If we have a JSON output, assert GPU dropped to 0
  if [ -n "$out_json" ] && [ -f "$out_json" ]; then
    py="import json,sys;d=json.load(open(sys.argv[1]));orig=d['inputs']['original_request']['gpus'];down=d['inputs']['downgraded_request']['gpus'];print(orig,down);exit(0 if (orig>=1 and down==0) else 1)"
    if python -c "$py" "$out_json"; then
      :
    else
      fail "$name: expected original gpus>=1 and downgraded gpus==0"
      rc=1
    fi
  else
    # Fallback: look for success messages
    echo "$output" | grep -q "Downgrade applied successfully" || { fail "$name: downgrade not applied"; rc=1; }
  fi

  if [ $rc -eq 0 ]; then ok "$name"; else overall_rc=1; fi
}

run_cases_downgrade_smoke_fail() {
  name="CASES DOWNGRADE (smoke-test required fail)"
  cmd="python -m envboot.cli cases-downgrade . --smoke-test 'false'"
  if [ -n "$OUT_PREFIX" ]; then
    stdout_log="${OUT_PREFIX}-cases-downgrade-fail.stdout"
    sh -c "$cmd" >"$stdout_log" 2>&1; rc_cmd=$?
    output=$(cat "$stdout_log")
  else
    output=$(sh -c "$cmd" 2>&1); rc_cmd=$?
  fi
  if [ $rc_cmd -ne 0 ]; then
    ok "$name"
  else
    fail "$name: expected non-zero exit due to smoke test failure"; overall_rc=1
  fi
}

run_cases_downgrade_smoke_pass() {
  name="CASES DOWNGRADE (smoke-test required pass)"
  cmd="python -m envboot.cli cases-downgrade . --smoke-test 'python -c \"print(1)\"'"
  if [ -n "$OUT_PREFIX" ]; then
    stdout_log="${OUT_PREFIX}-cases-downgrade-pass.stdout"
    sh -c "$cmd" >"$stdout_log" 2>&1; rc_cmd=$?
    output=$(cat "$stdout_log")
  else
    output=$(sh -c "$cmd" 2>&1); rc_cmd=$?
  fi
  if [ $rc_cmd -eq 0 ]; then
    ok "$name"
  else
    fail "$name: expected zero exit with passing smoke test"; overall_rc=1
  fi
}

run_complexity_mode() {
  name="AI-RESERVE (complexity mode)"
  cmd="python -m envboot.cli ai-reserve --source forge --mode complexity"
  if [ -n "$OUT_PREFIX" ]; then
    out_json="${OUT_PREFIX}-complexity.json"
    cmd="$cmd --output $out_json"
  fi
  if [ -n "$OUT_PREFIX" ]; then
    stdout_log="${OUT_PREFIX}-complexity.stdout"
    sh -c "$cmd" >"$stdout_log" 2>&1; rc_cmd=$?
    output=$(cat "$stdout_log")
  else
    output=$(sh -c "$cmd" 2>&1); rc_cmd=$?
  fi
  rc=0
  if [ $rc_cmd -ne 0 ]; then
    fail "$name: command failed ($rc_cmd)"; overall_rc=1; return
  fi
  echo "$output" | grep -q "AI chose:" || { fail "$name: missing 'AI chose:' line"; rc=1; }
  if [ $rc -eq 0 ]; then ok "$name"; else overall_rc=1; fi
}

run_final_simple
run_downgrade_gpu
run_downgrade_cpu_only
run_cases_downgrade_gpu_to_cpu
run_cases_downgrade_smoke_fail
run_cases_downgrade_smoke_pass
run_complexity_mode

if [ $overall_rc -eq 0 ]; then
  printf "\nAll smoke tests passed.\n"
else
  printf "\nSome smoke tests failed.\n" >&2
fi

exit $overall_rc
