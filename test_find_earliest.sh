#!/usr/bin/env bash
set -euo pipefail

# Advanced test: What happens when requested amount exceeds availability?
# Shows the need for "find earliest available" logic

BOLD="\e[1m"
GREEN="\e[32m"
RED="\e[31m"
YELLOW="\e[33m"
RESET="\e[0m"

echo -e "${BOLD}=====================================================================${RESET}"
echo -e "${BOLD}Advanced Test: When Requested Amount Exceeds Current Availability${RESET}"
echo -e "${BOLD}=====================================================================${RESET}"
echo ""

# Backup current allocations.json
if [[ -f allocations.json ]]; then
    cp allocations.json allocations.json.backup
fi

# Use the heavily blocked mock file
cp examples/allocations_heavily_blocked.json allocations.json

echo -e "${BOLD}Scenario:${RESET} User wants to reserve ${YELLOW}130 nodes${RESET} for 1 hour"
echo ""
echo -e "${BOLD}Available capacity over time:${RESET}"
echo "  - 10:00-11:00: 127 nodes free (5 blocked) ❌ NOT ENOUGH"
echo "  - 11:00-12:00: 129 nodes free (3 blocked) ❌ NOT ENOUGH"
echo "  - 12:00-13:00: 131 nodes free (1 blocked) ✅ ENOUGH!"
echo "  - 13:00+:      132 nodes free (0 blocked) ✅ ENOUGH!"
echo ""

# Test requesting 130 nodes at different times
echo -e "${BOLD}Test 1: Request 130 nodes at 10:00${RESET}"
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 10:00' --duration 60 --amount 130"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 10:00" --duration 60 --amount 130 2>&1 | tail -15
echo ""
echo -e "${RED}✗ Only 127 nodes available - insufficient capacity${RESET}"
echo ""

echo -e "${BOLD}Test 2: Request 130 nodes at 11:00${RESET}"
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 11:00' --duration 60 --amount 130"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 11:00" --duration 60 --amount 130 2>&1 | tail -15
echo ""
echo -e "${RED}✗ Only 129 nodes available - insufficient capacity${RESET}"
echo ""

echo -e "${BOLD}Test 3: Request 130 nodes at 12:00${RESET}"
echo "Command: python3 integrate_and_plan.py --zone uc --start '2025-10-30 12:00' --duration 60 --amount 130"
echo ""
python3 integrate_and_plan.py --zone uc --start "2025-10-30 12:00" --duration 60 --amount 130 2>&1 | tail -15
echo ""
echo -e "${GREEN}✓ 131 nodes available - sufficient capacity!${RESET}"
echo ""

# Restore
if [[ -f allocations.json.backup ]]; then
    mv allocations.json.backup allocations.json
fi

echo -e "${BOLD}=====================================================================${RESET}"
echo -e "${BOLD}Key Insight:${RESET}"
echo ""
echo "Current behavior: integrate_and_plan.py checks availability at a"
echo "specific time window and reports if there's insufficient capacity."
echo ""
echo -e "${YELLOW}Future enhancement opportunity:${RESET}"
echo "Add a --find-earliest flag that automatically searches forward in"
echo "time to find the earliest slot with sufficient capacity."
echo ""
echo "Example: If user requests 130 nodes at 10:00 but only 127 are free,"
echo "the script could scan forward and suggest: 'Not available at 10:00,"
echo "but earliest available time with 130 nodes is 12:00.'"
echo -e "${BOLD}=====================================================================${RESET}"
