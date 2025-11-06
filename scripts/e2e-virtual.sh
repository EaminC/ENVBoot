#!/usr/bin/env bash
#
# e2e-virtual.sh - End-to-end test for virtual:instance leases
#
# Creates a virtual instance lease, launches a VM, and provides SSH info.
# Reads config/.env if present, or uses defaults.
#
# Usage:
#   bash scripts/e2e-virtual.sh
#
#   Override with environment variables:
#   KEY_NAME=mykey IMAGE="Ubuntu 22.04" bash scripts/e2e-virtual.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load config/.env if it exists
if [ -f "$PROJECT_ROOT/config/.env" ]; then
    source "$PROJECT_ROOT/config/.env"
fi

# Configuration with defaults
KEY_NAME="${KEY_NAME:-Chris}"
IMAGE="${IMAGE:-CC-Ubuntu22.04}"
FLAVOR="${FLAVOR:-m1.medium}"
NETWORK="${NETWORK:-sharednet1}"
ZONE="${ZONE:-uc}"
DURATION="${DURATION:-60}"
START_OFFSET="${START_OFFSET:-2}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

cleanup_on_exit() {
    local exit_code=$?
    if [ -n "$RES_ID" ] && [ "$exit_code" -ne 0 ]; then
        log_warn "Script failed. Cleaning up lease $RES_ID..."
        python3 "$PROJECT_ROOT/src/api-core/api-4.py" \
            --reservation-id "$RES_ID" \
            --confirm \
            --treat-not-found-as-ok \
            > /tmp/api4_cleanup.json 2>&1 || true
    fi
}

trap cleanup_on_exit EXIT

echo "================================================================"
echo "  End-to-End Test: Virtual Instance"
echo "================================================================"
log_info "Configuration:"
log_info "  Zone: $ZONE"
log_info "  Duration: $DURATION minutes"
log_info "  Image: $IMAGE"
log_info "  Flavor: $FLAVOR"
log_info "  Network: $NETWORK"
log_info "  Keypair: $KEY_NAME"
echo ""

# Step 1: Create lease
log_info "Step 1/5: Creating virtual:instance lease..."
START_TIME="$(date -u -d "+${START_OFFSET} minutes" '+%Y-%m-%d %H:%M')"

python3 "$PROJECT_ROOT/src/api-core/api-2.py" \
    --zone "$ZONE" \
    --start "$START_TIME" \
    --duration "$DURATION" \
    --nodes 1 \
    --resource-type virtual:instance \
    > /tmp/api2_out.json

RES_ID=$(jq -r '.data.reservation_id // empty' /tmp/api2_out.json)
if [ -z "$RES_ID" ]; then
    log_error "Failed to create lease"
    cat /tmp/api2_out.json | jq '.'
    exit 1
fi

log_info "✓ Lease created: $RES_ID"

# Step 2: Wait for ACTIVE
log_info "Step 2/5: Waiting for lease ACTIVE (timeout: 3 min)..."

python3 "$PROJECT_ROOT/src/api-core/api-3.py" \
    --reservation-id "$RES_ID" \
    --wait 180 \
    > /tmp/api3_out.json

LEASE_STATUS=$(jq -r '.data.status // empty' /tmp/api3_out.json)
if [ "$LEASE_STATUS" != "ACTIVE" ]; then
    log_error "Lease not ACTIVE: $LEASE_STATUS"
    exit 1
fi

log_info "✓ Lease is ACTIVE"

# Step 3: Launch VM
log_info "Step 3/5: Launching VM..."

python3 "$PROJECT_ROOT/src/api-core/api-6.py" \
    --reservation-id "$RES_ID" \
    --image "$IMAGE" \
    --flavor "$FLAVOR" \
    --network "$NETWORK" \
    --key-name "$KEY_NAME" \
    --assign-floating-ip \
    --wait 300 \
    --interval 10 \
    > /tmp/api6_out.json

SERVER_OK=$(jq -r '.ok' /tmp/api6_out.json)
if [ "$SERVER_OK" != "true" ]; then
    log_error "VM launch failed"
    cat /tmp/api6_out.json | jq '.'
    exit 1
fi

log_info "✓ VM launched successfully"

# Step 4: Extract SSH info
log_info "Step 4/5: Extracting SSH info..."

SERVER_ID=$(jq -r '.data.servers[0].server_id' /tmp/api6_out.json)
SERVER_STATUS=$(jq -r '.data.servers[0].status' /tmp/api6_out.json)
FIXED_IP=$(jq -r '.data.servers[0].fixed_ip // empty' /tmp/api6_out.json)
FLOATING_IP=$(jq -r '.data.servers[0].floating_ip // empty' /tmp/api6_out.json)
SSH_USER=$(jq -r '.data.servers[0].ssh_user' /tmp/api6_out.json)

IP_TO_USE="${FLOATING_IP:-$FIXED_IP}"

echo ""
echo "================================================================"
echo "  SSH Connection"
echo "================================================================"
echo ""
echo "  ssh -i ~/.ssh/${KEY_NAME}.pem ${SSH_USER}@${IP_TO_USE}"
echo ""
echo "  Server: $SERVER_ID (${SERVER_STATUS})"
echo "  IP: $IP_TO_USE"
echo ""
echo "================================================================"
echo ""

# Step 5: Cleanup
log_info "Step 5/5: Cleaning up..."

python3 "$PROJECT_ROOT/src/api-core/api-4.py" \
    --reservation-id "$RES_ID" \
    --confirm \
    --wait 120 \
    > /tmp/api4_out.json

DELETE_STATUS=$(jq -r '.data.status' /tmp/api4_out.json)
log_info "✓ Cleanup complete (status: $DELETE_STATUS)"

echo ""
log_info "End-to-end test passed!"
exit 0
