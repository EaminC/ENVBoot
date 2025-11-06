#!/usr/bin/env bash
#
# preflight.sh - Pre-flight checks for EnvBoot API tools
#
# Verifies environment is ready to run API scripts.
# READ-ONLY: does not modify cloud resources.
#
# Usage:
#   bash scripts/preflight.sh

set -u

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

echo "================================================================"
echo "  EnvBoot Pre-flight Checks"
echo "================================================================"
echo ""

# Check 1: Python version
echo -n "Checking Python version... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
        echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"
    else
        echo -e "${RED}✗${NC} Python $PYTHON_VERSION (need >= 3.8)"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}✗${NC} python3 not found"
    ERRORS=$((ERRORS + 1))
fi

# Check 2: jq
echo -n "Checking jq (JSON parser)... "
if command -v jq &> /dev/null; then
    echo -e "${GREEN}✓${NC} $(jq --version)"
else
    echo -e "${RED}✗${NC} jq not found (install: apt install jq)"
    ERRORS=$((ERRORS + 1))
fi

# Check 3: openstack CLI
echo -n "Checking openstack CLI... "
if command -v openstack &> /dev/null; then
    echo -e "${GREEN}✓${NC} installed"
else
    echo -e "${YELLOW}⚠${NC} openstack CLI not found (optional, install: pip install python-openstackclient)"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""
echo "OpenStack Environment:"
echo "───────────────────────────────────────────────────────────────"

# Check 4: Required OS_* environment variables
REQUIRED_VARS=("OS_AUTH_URL" "OS_USERNAME" "OS_PASSWORD")
OPTIONAL_VARS=("OS_PROJECT_NAME" "OS_PROJECT_ID" "OS_REGION_NAME")

for var in "${REQUIRED_VARS[@]}"; do
    echo -n "  $var: "
    if [ -n "${!var:-}" ]; then
        # Mask password
        if [ "$var" = "OS_PASSWORD" ]; then
            echo -e "${GREEN}✓${NC} (set)"
        else
            echo -e "${GREEN}✓${NC} ${!var}"
        fi
    else
        echo -e "${RED}✗${NC} not set"
        ERRORS=$((ERRORS + 1))
    fi
done

for var in "${OPTIONAL_VARS[@]}"; do
    echo -n "  $var: "
    if [ -n "${!var:-}" ]; then
        echo -e "${GREEN}✓${NC} ${!var}"
    else
        echo -e "${YELLOW}⚠${NC} not set (optional)"
    fi
done

# Special check for OIDC
if [ "${OS_AUTH_TYPE:-}" = "v3oidcpassword" ]; then
    echo ""
    echo "  OIDC authentication detected:"
    for var in "OS_IDENTITY_PROVIDER" "OS_PROTOCOL" "OS_DISCOVERY_ENDPOINT" "OS_CLIENT_ID"; do
        echo -n "    $var: "
        if [ -n "${!var:-}" ]; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗${NC} not set"
            ERRORS=$((ERRORS + 1))
        fi
    done
fi

echo ""

# If no OS_* vars, suggest sourcing OpenRC
if [ -z "${OS_AUTH_URL:-}" ]; then
    echo -e "${YELLOW}→${NC} No OpenStack credentials found."
    echo -e "  ${BLUE}Solution:${NC} source config/openrc.sh (or your OpenRC file)"
    echo ""
fi

# Check 5: Cloud resources (if credentials available)
if [ -n "${OS_AUTH_URL:-}" ] && command -v openstack &> /dev/null; then
    echo "Cloud Resources (quick check):"
    echo "───────────────────────────────────────────────────────────────"
    
    # Check keypair
    KEY_NAME="${KEY_NAME:-Chris}"
    echo -n "  Keypair '$KEY_NAME': "
    if openstack keypair show "$KEY_NAME" &>/dev/null; then
        echo -e "${GREEN}✓${NC} exists"
    else
        echo -e "${RED}✗${NC} not found"
        echo "    ${BLUE}Create:${NC} openstack keypair create --public-key ~/.ssh/id_rsa.pub $KEY_NAME"
        ERRORS=$((ERRORS + 1))
    fi
    
    # Check security group SSH rule
    echo -n "  Security group 'default' TCP/22: "
    if openstack security group rule list default --protocol tcp --ingress -f value 2>/dev/null | grep -q "22:22"; then
        echo -e "${GREEN}✓${NC} SSH allowed"
    else
        echo -e "${YELLOW}⚠${NC} SSH rule not found"
        echo "    ${BLUE}Add rule:${NC} openstack security group rule create --protocol tcp --dst-port 22 --ingress default"
        WARNINGS=$((WARNINGS + 1))
    fi
    
    # List available images (first 5 with CC- prefix)
    echo ""
    echo -n "  Available images (CC-* prefix): "
    IMAGE_COUNT=$(openstack image list --format value -c Name 2>/dev/null | grep -c "^CC-" || echo "0")
    if [ "$IMAGE_COUNT" -gt 0 ]; then
        echo -e "${GREEN}$IMAGE_COUNT found${NC}"
        echo "    $(openstack image list --format value -c Name 2>/dev/null | grep "^CC-" | head -5 | sed 's/^/    - /')"
    else
        echo -e "${YELLOW}⚠${NC} none found (check: openstack image list)"
        WARNINGS=$((WARNINGS + 1))
    fi
    
    # List networks (first 3)
    echo ""
    echo -n "  Available networks: "
    NET_COUNT=$(openstack network list --format value -c Name 2>/dev/null | wc -l)
    if [ "$NET_COUNT" -gt 0 ]; then
        echo -e "${GREEN}$NET_COUNT found${NC}"
        openstack network list --format value -c Name 2>/dev/null | head -3 | sed 's/^/    - /'
    else
        echo -e "${YELLOW}⚠${NC} none found"
        WARNINGS=$((WARNINGS + 1))
    fi
    
    # List flavors (first 5)
    echo ""
    echo -n "  Available flavors: "
    FLAVOR_COUNT=$(openstack flavor list --format value -c Name 2>/dev/null | wc -l)
    if [ "$FLAVOR_COUNT" -gt 0 ]; then
        echo -e "${GREEN}$FLAVOR_COUNT found${NC}"
        openstack flavor list --format value -c Name 2>/dev/null | head -5 | sed 's/^/    - /'
    else
        echo -e "${YELLOW}⚠${NC} none found"
        WARNINGS=$((WARNINGS + 1))
    fi
    
    echo ""
fi

# Check 6: Python packages
echo "Python Dependencies:"
echo "───────────────────────────────────────────────────────────────"
PYTHON_DEPS=("openstacksdk" "python-dotenv" "keystoneauth1")
for pkg in "${PYTHON_DEPS[@]}"; do
    echo -n "  $pkg: "
    if python3 -c "import ${pkg//-/_}" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} installed"
    else
        echo -e "${RED}✗${NC} not installed"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# Final summary
echo "================================================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ Pre-flight checks passed!${NC}"
    echo ""
    echo "Ready to run API scripts. Try:"
    echo "  python3 src/api-core/api-1.py --zone uc --start \"2025-11-07 12:00\" --duration 60 --dry-run"
    echo ""
    exit 0
else
    echo -e "${RED}✗ $ERRORS error(s), $WARNINGS warning(s)${NC}"
    echo ""
    echo "Fix errors before running API scripts."
    if [ -z "${OS_AUTH_URL:-}" ]; then
        echo ""
        echo "Quick fix:"
        echo "  1. source config/openrc.sh"
        echo "  2. pip install -r requirements.txt"
        echo "  3. bash scripts/preflight.sh"
    fi
    echo ""
    exit 1
fi
