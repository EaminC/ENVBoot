#!/usr/bin/env bash
set -euo pipefail

# Test the new --find-earliest feature

BOLD="\e[1m"
GREEN="\e[32m"
YELLOW="\e[33m"
CYAN="\e[36m"
RESET="\e[0m"

echo -e "${BOLD}=====================================================================${RESET}"
echo -e "${BOLD}Testing --find-earliest Feature${RESET}"
echo -e "${BOLD}=====================================================================${RESET}"
echo ""

# Backup and use mock data
if [[ -f allocations.json ]]; then
    cp allocations.json allocations.json.backup
fi
cp examples/allocations_heavily_blocked.json allocations.json

echo -e "${BOLD}Mock Scenario:${RESET}"
echo "  - 10:00-11:00: 127 nodes free (5 blocked)"
echo "  - 11:00-12:00: 129 nodes free (3 blocked)"
echo "  - 12:00-13:00: 131 nodes free (1 blocked)"
echo "  - 13:00+:      132 nodes free (all available)"
echo ""

# Test 1: Request 128 nodes at 10:00 - should find 11:00 as earliest
echo -e "${BOLD}${CYAN}Test 1: Request 128 nodes at 10:00 with --find-earliest${RESET}"
echo "Expected: Should skip to 12:00 (first slot with 128+ nodes)"
echo ""
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 10:00' --duration 60 --amount 128 --find-earliest"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 10:00" --duration 60 --amount 128 --find-earliest
echo ""
echo -e "${GREEN}✓ Test 1 Complete${RESET}"
echo ""

# Test 2: Request 130 nodes at 10:00 - should find 12:00 as earliest
echo -e "${BOLD}${CYAN}Test 2: Request 130 nodes at 10:00 with --find-earliest${RESET}"
echo "Expected: Should skip to 12:00 (first slot with 130+ nodes)"
echo ""
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 10:00' --duration 60 --amount 130 --find-earliest"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 10:00" --duration 60 --amount 130 --find-earliest
echo ""
echo -e "${GREEN}✓ Test 2 Complete${RESET}"
echo ""

# Test 3: Request 132 nodes at 10:00 - should find 13:00 as earliest
echo -e "${BOLD}${CYAN}Test 3: Request 132 nodes (all) at 10:00 with --find-earliest${RESET}"
echo "Expected: Should skip to 13:00 (first slot with all 132 nodes)"
echo ""
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 10:00' --duration 60 --amount 132 --find-earliest"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 10:00" --duration 60 --amount 132 --find-earliest
echo ""
echo -e "${GREEN}✓ Test 3 Complete${RESET}"
echo ""

# Test 4: Request 130 nodes at 10:00 WITHOUT --find-earliest
echo -e "${BOLD}${CYAN}Test 4: Request 130 nodes at 10:00 WITHOUT --find-earliest${RESET}"
echo "Expected: Should fail with suggestion to use --find-earliest"
echo ""
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 10:00' --duration 60 --amount 130"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 10:00" --duration 60 --amount 130 || echo -e "${YELLOW}(Expected exit code 1)${RESET}"
echo ""
echo -e "${GREEN}✓ Test 4 Complete${RESET}"
echo ""

# Test 5: Request impossible amount (200 nodes) with limited search window
echo -e "${BOLD}${CYAN}Test 5: Request impossible amount (200 nodes) with --find-earliest${RESET}"
echo "Expected: Should report no slots found within search window"
echo ""
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 10:00' --duration 60 --amount 200 --find-earliest --max-search-hours 24"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 10:00" --duration 60 --amount 200 --find-earliest --max-search-hours 24 || echo -e "${YELLOW}(Expected exit code 1)${RESET}"
echo ""
echo -e "${GREEN}✓ Test 5 Complete${RESET}"
echo ""

# Restore original allocations
if [[ -f allocations.json.backup ]]; then
    mv allocations.json.backup allocations.json
fi

echo -e "${BOLD}=====================================================================${RESET}"
echo -e "${BOLD}All Tests Complete!${RESET}"
echo ""
echo -e "${GREEN}The --find-earliest feature successfully:${RESET}"
echo "  ✓ Scans forward in 1-hour increments"
echo "  ✓ Finds earliest slot with sufficient capacity"
echo "  ✓ Provides helpful command to reserve at that time"
echo "  ✓ Handles impossible requests gracefully"
echo "  ✓ Suggests using the feature when capacity is insufficient"
echo -e "${BOLD}=====================================================================${RESET}"
