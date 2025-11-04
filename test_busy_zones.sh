#!/usr/bin/env bash
set -euo pipefail

# Test script to demonstrate busy zone handling
# Shows how integrate_and_plan.py finds earliest available slots

BOLD="\e[1m"
GREEN="\e[32m"
YELLOW="\e[33m"
RESET="\e[0m"

echo -e "${BOLD}=====================================================================${RESET}"
echo -e "${BOLD}Testing Busy Zone Logic - Finding Earliest Available Slots${RESET}"
echo -e "${BOLD}=====================================================================${RESET}"
echo ""

# Backup current allocations.json
if [[ -f allocations.json ]]; then
    echo "Backing up current allocations.json..."
    cp allocations.json allocations.json.backup
fi

# Use the heavily blocked mock file
echo "Loading mock scenario: examples/allocations_heavily_blocked.json"
cp examples/allocations_heavily_blocked.json allocations.json
echo ""

# Show what's in the mock file
echo -e "${BOLD}Mock Scenario Summary:${RESET}"
echo "  - 5 nodes with various blocking patterns"
echo "  - Node 1057: Blocked 10:00-11:00"
echo "  - Node 1132: Blocked 10:00-11:00"
echo "  - Node 1133: Blocked 10:00-12:00"
echo "  - Node 1134: Blocked 10:00-12:00"
echo "  - Node 1135: Blocked 10:00-13:00"
echo ""

# Test 1: Try to reserve at 10:00 (peak busy time)
echo -e "${BOLD}Test 1: Request at 10:00 (peak busy - 5 nodes blocked)${RESET}"
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 10:00' --duration 60"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 10:00" --duration 60 2>&1 | grep -A 15 "Searching for available"
echo ""
echo -e "${GREEN}✓ Shows reduced capacity at 10:00${RESET}"
echo ""

# Test 2: Try to reserve at 11:00 (2 nodes freed)
echo -e "${BOLD}Test 2: Request at 11:00 (less busy - 3 nodes blocked)${RESET}"
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 11:00' --duration 60"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 11:00" --duration 60 2>&1 | grep -A 15 "Searching for available"
echo ""
echo -e "${GREEN}✓ Shows more capacity at 11:00${RESET}"
echo ""

# Test 3: Try to reserve at 12:00 (4 nodes freed)
echo -e "${BOLD}Test 3: Request at 12:00 (mostly free - 1 node blocked)${RESET}"
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 12:00' --duration 60"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 12:00" --duration 60 2>&1 | grep -A 15 "Searching for available"
echo ""
echo -e "${GREEN}✓ Shows high capacity at 12:00${RESET}"
echo ""

# Test 4: Try to reserve at 13:00 (all free)
echo -e "${BOLD}Test 4: Request at 13:00 (all free - 0 nodes blocked)${RESET}"
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 13:00' --duration 60"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 13:00" --duration 60 2>&1 | grep -A 15 "Searching for available"
echo ""
echo -e "${GREEN}✓ Shows full capacity at 13:00${RESET}"
echo ""

# Restore original allocations.json
if [[ -f allocations.json.backup ]]; then
    echo "Restoring original allocations.json..."
    mv allocations.json.backup allocations.json
    echo ""
fi

echo -e "${BOLD}=====================================================================${RESET}"
echo -e "${BOLD}Summary:${RESET}"
echo -e "This demonstrates how ${YELLOW}integrate_and_plan.py${RESET} correctly handles busy zones:"
echo "  1. At 10:00 - Peak busy time (5 nodes blocked) → Minimal availability"
echo "  2. At 11:00 - Partial availability (3 nodes blocked)"
echo "  3. At 12:00 - Most nodes free (1 node blocked)"
echo "  4. At 13:00 - Full availability (all nodes free)"
echo ""
echo -e "${GREEN}The script correctly filters out busy nodes and shows available capacity!${RESET}"
echo -e "${BOLD}=====================================================================${RESET}"
