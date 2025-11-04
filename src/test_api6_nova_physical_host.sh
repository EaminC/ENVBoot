#!/usr/bin/env bash
#
# test_api6_nova_physical_host.sh
# Full automated test for api-6.py Nova path with physical:host leases
#
# Prerequisites:
# - OpenStack credentials sourced (OS_* environment variables)
# - Keypair "Chris" exists
# - Default security group allows TCP/22
# - Image "CC-Ubuntu20.04" available
# - Network "sharednet1" accessible
# - Flavor "baremetal" available
#
# Usage:
#   bash scripts/test_api6_nova_physical_host.sh
#
# Outputs:
#   - /tmp/api2_out.json (lease creation)
#   - /tmp/api3_out.json (lease status)
#   - /tmp/api6_out.json (server launch)
#   - /tmp/api4_out.json (lease deletion)
#

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Cleanup function (runs on exit)
cleanup_on_exit() {
    local exit_code=$?
    if [ -n "$RES_ID" ] && [ "$exit_code" -ne 0 ]; then
        log_warn "Script failed. Attempting to clean up lease $RES_ID..."
        python3 "$PROJECT_ROOT/src/api-core/api-4.py" \
            --reservation-id "$RES_ID" \
            --confirm \
            --treat-not-found-as-ok \
            > /tmp/api4_cleanup.json 2>&1 || true
        log_info "Cleanup attempt completed. Check /tmp/api4_cleanup.json"
    fi
}

trap cleanup_on_exit EXIT

# Step 1: Create physical:host lease
log_info "Step 1/6: Creating physical:host lease (start ~2 min, duration 45 min, 1 node)..."
START_TIME="$(date -u -d '+2 minutes' '+%Y-%m-%d %H:%M')"

python3 "$PROJECT_ROOT/src/api-core/api-2.py" \
    --zone uc \
    --start "$START_TIME" \
    --duration 45 \
    --nodes 1 \
    --resource-type physical:host \
    > /tmp/api2_out.json

if [ $? -ne 0 ]; then
    log_error "Failed to create lease. Check /tmp/api2_out.json"
    exit 1
fi

# Extract and validate lease ID
RES_ID=$(jq -r '.data.reservation_id // empty' /tmp/api2_out.json)
if [ -z "$RES_ID" ]; then
    log_error "Failed to extract reservation_id from api-2 output"
    cat /tmp/api2_out.json | jq '.'
    exit 1
fi

LEASE_OK=$(jq -r '.ok' /tmp/api2_out.json)
if [ "$LEASE_OK" != "true" ]; then
    log_error "Lease creation returned ok=false"
    cat /tmp/api2_out.json | jq '.'
    exit 1
fi

log_info "✓ Lease created successfully"
log_info "  Reservation ID: $RES_ID"
log_info "  Resource type: $(jq -r '.data.resource_type' /tmp/api2_out.json)"
log_info "  Start: $(jq -r '.data.start' /tmp/api2_out.json)"
log_info "  End: $(jq -r '.data.end' /tmp/api2_out.json)"

# Step 2: Wait for lease to become ACTIVE
log_info "Step 2/6: Waiting for lease to become ACTIVE (timeout: 5 minutes)..."

python3 "$PROJECT_ROOT/src/api-core/api-3.py" \
    --reservation-id "$RES_ID" \
    --wait 300 \
    > /tmp/api3_out.json

if [ $? -ne 0 ]; then
    log_error "Failed to check lease status. Check /tmp/api3_out.json"
    exit 1
fi

LEASE_STATUS=$(jq -r '.data.status // empty' /tmp/api3_out.json)
if [ "$LEASE_STATUS" != "ACTIVE" ]; then
    log_error "Lease did not become ACTIVE. Current status: $LEASE_STATUS"
    cat /tmp/api3_out.json | jq '.'
    exit 1
fi

log_info "✓ Lease is now ACTIVE"

# Step 3: Launch baremetal instance via Nova (using reservation.id hint)
log_info "Step 3/6: Launching baremetal instance via api-6 (Nova path with reservation hint)..."
log_info "  Image: CC-Ubuntu20.04"
log_info "  Flavor: baremetal"
log_info "  Network: sharednet1"
log_info "  Keypair: Chris"
log_info "  Wait timeout: 10 minutes"

python3 "$PROJECT_ROOT/src/api-core/api-6.py" \
    --reservation-id "$RES_ID" \
    --image CC-Ubuntu20.04 \
    --flavor baremetal \
    --network sharednet1 \
    --key-name Chris \
    --sec-groups "default" \
    --assign-floating-ip \
    --wait 600 \
    --interval 10 \
    > /tmp/api6_out.json

if [ $? -ne 0 ]; then
    log_error "api-6 exited with non-zero code. Check /tmp/api6_out.json"
    cat /tmp/api6_out.json | jq '.'
    exit 1
fi

SERVER_OK=$(jq -r '.ok' /tmp/api6_out.json)
if [ "$SERVER_OK" != "true" ]; then
    log_error "Server launch returned ok=false"
    ERROR_TYPE=$(jq -r '.error.type // "Unknown"' /tmp/api6_out.json)
    ERROR_MSG=$(jq -r '.error.message // "No message"' /tmp/api6_out.json)
    log_error "  Error type: $ERROR_TYPE"
    log_error "  Message: $ERROR_MSG"
    cat /tmp/api6_out.json | jq '.'
    exit 1
fi

log_info "✓ Server launch succeeded"

# Step 4: Extract server details and SSH info
log_info "Step 4/6: Extracting server details and SSH connection info..."

SERVER_ID=$(jq -r '.data.servers[0].server_id // empty' /tmp/api6_out.json)
SERVER_STATUS=$(jq -r '.data.servers[0].status // empty' /tmp/api6_out.json)
FIXED_IP=$(jq -r '.data.servers[0].fixed_ip // empty' /tmp/api6_out.json)
FLOATING_IP=$(jq -r '.data.servers[0].floating_ip // empty' /tmp/api6_out.json)
SSH_USER=$(jq -r '.data.servers[0].ssh_user // "ubuntu"' /tmp/api6_out.json)
KEY_NAME=$(jq -r '.data.servers[0].key_name // "Chris"' /tmp/api6_out.json)

log_info "  Server ID: $SERVER_ID"
log_info "  Status: $SERVER_STATUS"
log_info "  Fixed IP: ${FIXED_IP:-<none>}"
log_info "  Floating IP: ${FLOATING_IP:-<none>}"
log_info "  SSH User: $SSH_USER"
log_info "  Key Name: $KEY_NAME"

if [ "$SERVER_STATUS" != "ACTIVE" ]; then
    log_warn "Server status is not ACTIVE (current: $SERVER_STATUS)"
    log_warn "Server may still be building or encountered an error"
fi

# Determine which IP to use
IP_TO_USE="${FLOATING_IP}"
if [ -z "$IP_TO_USE" ]; then
    IP_TO_USE="${FIXED_IP}"
    log_warn "No floating IP assigned; using fixed IP (requires VPN or jump host)"
fi

if [ -z "$IP_TO_USE" ]; then
    log_error "No IP address available for SSH connection"
    exit 1
fi

# Step 5: Test connectivity (optional ping)
log_info "Step 5/6: Testing connectivity to $IP_TO_USE..."
if ping -c 2 -W 3 "$IP_TO_USE" > /dev/null 2>&1; then
    log_info "✓ Server is reachable via ping"
else
    log_warn "Server did not respond to ping (may be normal for baremetal provisioning)"
    log_warn "SSH may still work once cloud-init completes"
fi

# Print SSH command
echo ""
echo "================================================================"
echo "  SSH Connection Info"
echo "================================================================"
echo ""
echo "  Server is ready for SSH access:"
echo ""
echo "    ssh -o StrictHostKeyChecking=no -i ~/.ssh/Chris.pem ${SSH_USER}@${IP_TO_USE}"
echo ""
echo "  (Adjust the private key path as needed for your keypair 'Chris')"
echo ""
if [ -z "$FLOATING_IP" ]; then
    echo "  Note: Using fixed IP. Ensure you're on the tenant network or VPN."
    echo ""
fi
echo "================================================================"
echo ""

# Step 6: Cleanup - delete the lease (DISABLED - keeping server running)
log_info "Step 6/6: Skipping cleanup - server and lease will remain active"
log_warn "Remember to manually delete the lease when done:"
log_warn "  python3 src/api-core/api-4.py --reservation-id $RES_ID --confirm"
echo ""

# Uncomment below to enable automatic cleanup:
# log_info "Step 6/6: Cleaning up - deleting lease $RES_ID..."
#
# python3 "$PROJECT_ROOT/src/api-core/api-4.py" \
#     --reservation-id "$RES_ID" \
#     --confirm \
#     --wait 120 \
#     --interval 5 \
#     > /tmp/api4_out.json
#
# if [ $? -ne 0 ]; then
#     log_error "Lease deletion failed. Check /tmp/api4_out.json"
#     exit 1
# fi
#
# DELETE_OK=$(jq -r '.ok' /tmp/api4_out.json)
# DELETE_STATUS=$(jq -r '.data.status // empty' /tmp/api4_out.json)
#
# if [ "$DELETE_OK" = "true" ]; then
#     log_info "✓ Lease deleted successfully (status: $DELETE_STATUS)"
# else
#     log_warn "Lease deletion returned ok=false (status: $DELETE_STATUS)"
#     cat /tmp/api4_out.json | jq '.'
# fi

# Summary
echo ""
echo "================================================================"
echo "  Test Summary"
echo "================================================================"
echo ""
echo "  ✓ Lease created and became ACTIVE"
echo "  ✓ Baremetal instance launched via Nova (reservation hint)"
echo "  ✓ Server reached status: $SERVER_STATUS"
echo "  ✓ SSH connection info extracted"
echo "  ! Lease cleanup SKIPPED - server is still running"
echo ""
echo "  Server details:"
echo "    - Lease ID: $RES_ID"
echo "    - Server ID: $SERVER_ID"
echo "    - IP: $IP_TO_USE"
echo "    - SSH: ssh -i ~/.ssh/Chris.pem ${SSH_USER}@${IP_TO_USE}"
echo ""
echo "  To delete the lease when done:"
echo "    python3 src/api-core/api-4.py --reservation-id $RES_ID --confirm"
echo ""
echo "  Logs available in:"
echo "    - /tmp/api2_out.json (lease creation)"
echo "    - /tmp/api3_out.json (lease status)"
echo "    - /tmp/api6_out.json (server launch)"
echo ""
echo "================================================================"
echo ""

log_info "All tests passed successfully!"
exit 0
