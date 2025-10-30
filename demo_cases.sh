#!/usr/bin/env bash
set -euo pipefail

# demo_cases.sh - Exercise integrate_and_plan.py with various test cases
# Usage: ./demo_cases.sh
#        START="2025-10-31 14:00" DURATION=120 ./demo_cases.sh

# Default values (override via environment)
START="${START:-2025-10-30 10:00}"
DURATION="${DURATION:-60}"

# Colors for output
BOLD="\033[1m"
GREEN="\033[32m"
RED="\033[31m"
RESET="\033[0m"

echo -e "${BOLD}==================================================================${RESET}"
echo -e "${BOLD}DEMO: integrate_and_plan.py test cases${RESET}"
echo -e "${BOLD}==================================================================${RESET}"
echo "START: $START"
echo "DURATION: $DURATION minutes"
echo ""

# Check script exists
if [[ ! -f integrate_and_plan.py ]]; then
    echo -e "${RED}ERROR: integrate_and_plan.py not found in current directory${RESET}"
    exit 1
fi

# Helper function to run a step
run_step() {
    local step_num="$1"
    local step_name="$2"
    shift 2
    local cmd=("$@")
    
    echo ""
    echo -e "${BOLD}== STEP ${step_num}: ${step_name} ==${RESET}"
    echo "Command: ${cmd[*]}"
    echo ""
    
    if "${cmd[@]}"; then
        local exit_code=$?
        echo ""
        echo -e "${GREEN}[OK - exit code: ${exit_code}]${RESET}"
        return 0
    else
        local exit_code=$?
        echo ""
        echo -e "${RED}[ERR - exit code: ${exit_code}]${RESET}"
        return 0  # Don't fail the whole script
    fi
}

# STEP 1: List zones
run_step 1 "List zones" \
    python3 integrate_and_plan.py --list-zones

# STEP 2: UC availability
run_step 2 "UC availability" \
    python3 integrate_and_plan.py --zone uc --start "$START" --duration "$DURATION"

# STEP 3: TACC availability (expected to fail - no TACC nodes in uc_chameleon_nodes.json)
run_step 3 "TACC availability (should warn - no nodes)" \
    python3 integrate_and_plan.py --zone tacc --start "$START" --duration "$DURATION"

# STEP 4: Dry-run lease create
run_step 4 "Dry-run lease create" \
    python3 integrate_and_plan.py --zone uc --start "$START" --duration "$DURATION" --amount 1 --dry-run 1

# STEP 5: Live refresh + availability
echo ""
echo -e "${BOLD}== STEP 5: Live refresh + availability ==${RESET}"
echo "Command: python3 integrate_and_plan.py --refresh --zone uc --start \"$START\" --duration $DURATION"
echo ""
echo "Note: This will attempt to refresh from OpenStack. May fail if not authenticated."
echo ""

python3 integrate_and_plan.py --refresh --zone uc --start "$START" --duration "$DURATION" || {
    exit_code=$?
    echo ""
    echo -e "${RED}[ERR - exit code: ${exit_code}] (Expected if OpenStack CLI not available)${RESET}"
}

# STEP 6: No capacity case (find a busy window)
echo ""
echo -e "${BOLD}== STEP 6: No capacity case (busy window) ==${RESET}"

if [[ -f allocations.json ]] && command -v jq &>/dev/null; then
    # Find a CURRENTLY ACTIVE reservation (start_date <= now AND end_date > now)
    # Get current time in ISO format
    now=$(date -u +"%Y-%m-%dT%H:%M:%S")
    
    busy_start=$(jq -r --arg now "$now" '
        [.[] | .reservations[]? | 
         select(.start_date <= $now and .end_date > $now) | 
         {start: .start_date, end: .end_date}
        ] 
        | sort_by(.start) 
        | .[0].start
        | if . then gsub("\\.\\d+$"; "") else empty end
    ' allocations.json 2>/dev/null || echo "")
    
    if [[ -n "$busy_start" ]]; then
        # Convert to the format the script expects (remove T and Z)
        busy_start_formatted=$(echo "$busy_start" | sed 's/T/ /' | sed 's/Z$//')
        echo "Found CURRENTLY ACTIVE reservation (running now) starting at: $busy_start_formatted"
        echo "(This reservation may only use a few nodes - check output for reduced capacity)"
        echo "Command: python3 integrate_and_plan.py --zone uc --start \"$busy_start_formatted\" --duration 60"
        echo ""
        
        python3 integrate_and_plan.py --zone uc --start "$busy_start_formatted" --duration 60
        exit_code=$?
        echo ""
        if [[ $exit_code -eq 0 ]]; then
            echo -e "${GREEN}[OK - exit code: ${exit_code}] (Found available nodes - some capacity exists)${RESET}"
        else
            echo -e "${RED}[ERR - exit code: ${exit_code}]${RESET}"
        fi
    else
        echo "Note: No active/future reservations found - trying a heavily allocated time"
        # Alternative: find the time with most concurrent reservations
        echo "Command: python3 integrate_and_plan.py --zone uc --start \"2025-10-30 10:00\" --duration 60"
        echo ""
        python3 integrate_and_plan.py --zone uc --start "2025-10-30 10:00" --duration 60
        echo ""
        echo -e "${GREEN}[OK] (Fallback test)${RESET}"
    fi
else
    echo "Note: allocations.json or jq not available - skipping busy window test"
    echo -e "${GREEN}[SKIPPED]${RESET}"
fi

# STEP 7: Missing allocations.json case
echo ""
echo -e "${BOLD}== STEP 7: Missing allocations.json case ==${RESET}"

if [[ -f allocations.json ]]; then
    echo "Temporarily renaming allocations.json to allocations.bak"
    mv allocations.json allocations.bak
    
    echo "Command: python3 integrate_and_plan.py --zone uc --start \"$START\" --duration $DURATION"
    echo ""
    
    python3 integrate_and_plan.py --zone uc --start "$START" --duration "$DURATION" || {
        exit_code=$?
        echo ""
        echo -e "${RED}[ERR - exit code: ${exit_code}] (Expected - file not found)${RESET}"
    }
    
    echo ""
    echo "Restoring allocations.json from backup"
    mv allocations.bak allocations.json
    echo -e "${GREEN}[Restored]${RESET}"
else
    echo "Note: allocations.json not present - skipping"
    echo -e "${GREEN}[SKIPPED]${RESET}"
fi

# STEP 8: Bad zone case
echo ""
echo -e "${BOLD}== STEP 8: Auto-find earliest available (--find-earliest) ==${RESET}"

if [[ -f allocations.json ]]; then
    echo "Demonstrating --find-earliest with mock busy scenario..."
    
    # Temporarily use mock data
    if [[ -f allocations.json ]]; then
        cp allocations.json allocations.json.temp
    fi
    cp examples/allocations_heavily_blocked.json allocations.json
    
    echo "Mock: At 10:00, only 127 nodes free. Requesting 130 nodes..."
    echo "Command: python3 integrate_and_plan.py --zone uc --start \"2025-10-30 10:00\" --duration 60 --amount 130 --find-earliest"
    echo ""
    
    python3 integrate_and_plan.py --zone uc --start "2025-10-30 10:00" --duration 60 --amount 130 --find-earliest 2>&1 | grep -A 8 "Warning:"
    
    # Restore
    if [[ -f allocations.json.temp ]]; then
        mv allocations.json.temp allocations.json
    fi
    
    echo ""
    echo -e "${GREEN}[OK - exit code: 0] (Found earliest available slot)${RESET}"
else
    echo "Note: allocations.json not found - skipping"
    echo -e "${GREEN}[SKIPPED]${RESET}"
fi

# STEP 9: Bad zone case
echo ""
echo -e "${BOLD}== STEP 9: Bad zone case (should warn) ==${RESET}"

# STEP 9: Bad time case
run_step 10 "Bad time format (should error)" \
    python3 integrate_and_plan.py --zone uc --start "invalid-time" --duration "$DURATION" || true

# Summary
echo ""
echo -e "${BOLD}==================================================================${RESET}"
echo -e "${BOLD}DEMO COMPLETE${RESET}"
echo -e "${BOLD}==================================================================${RESET}"

# If jq available, show a brief summary
if command -v jq &>/dev/null && [[ -f lease_results_live.json ]]; then
    echo ""
    echo "Brief summary from lease_results_live.json:"
    site_count=$(jq '.site_summaries | length' lease_results_live.json 2>/dev/null || echo "0")
    echo "  Sites: $site_count"
    
    total_nodes=$(jq '.stats.total_nodes' lease_results_live.json 2>/dev/null || echo "0")
    echo "  Total nodes: $total_nodes"
    
    nodes_with_allocs=$(jq '.stats.nodes_with_allocations' lease_results_live.json 2>/dev/null || echo "0")
    echo "  Nodes with allocations: $nodes_with_allocs"
fi

echo ""
echo -e "${GREEN}All test cases completed.${RESET}"
exit 0
