# Test Scripts

## test_api6_nova_physical_host.sh

Automated end-to-end test for physical host leases using the Nova path.

### Quick start

```bash
# 1. Load OpenStack credentials
source CHI-XXXX-openrc.sh

# 2. Run with defaults (Chris keypair, CC-Ubuntu20.04 image, baremetal flavor)
bash scripts/test_api6_nova_physical_host.sh
```

### Customize with environment variables

```bash
# Use your own keypair and image
KEY_NAME=mykey IMAGE="Ubuntu 22.04" bash scripts/test_api6_nova_physical_host.sh

# Change zone and duration
ZONE=tacc DURATION=120 bash scripts/test_api6_nova_physical_host.sh

# Use different flavor and network
FLAVOR=m1.large NETWORK=mynet bash scripts/test_api6_nova_physical_host.sh

# Adjust timeouts for faster/slower environments
SERVER_WAIT=1200 SERVER_INTERVAL=20 bash scripts/test_api6_nova_physical_host.sh
```

### Available parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `KEY_NAME` | Chris | SSH keypair name registered in OpenStack |
| `IMAGE` | CC-Ubuntu20.04 | OS image name or ID |
| `FLAVOR` | baremetal | Instance flavor |
| `NETWORK` | sharednet1 | Network name or ID |
| `ZONE` | uc | Site/zone for the lease |
| `DURATION` | 45 | Lease duration in minutes |
| `START_OFFSET` | 2 | Minutes from now to start lease |
| `LEASE_WAIT` | 180 | Max seconds to wait for lease ACTIVE |
| `SERVER_WAIT` | 900 | Max seconds to wait for server ACTIVE (15 min) |
| `SERVER_INTERVAL` | 15 | Polling interval in seconds |

### What it does

1. Creates a physical:host lease (starts in 2 minutes by default)
2. Waits for the lease to become ACTIVE
3. Launches a baremetal server bound to the lease
4. Waits for the server to become ACTIVE
5. Extracts SSH connection info (IP, user, keypair)
6. Tests connectivity (ping)
7. Prints SSH command to connect
8. **Skips cleanup** - lease and server remain running

### Outputs

Check `/tmp/api*.json` for detailed JSON responses:
- `/tmp/api2_out.json` - Lease creation
- `/tmp/api3_out.json` - Lease status
- `/tmp/api6_out.json` - Server launch
- `/tmp/api4_cleanup.json` - Cleanup (only on error)

### Cleanup

The script keeps the server running. To delete the lease when done:

```bash
python3 src/api-core/api-4.py --reservation-id <LEASE_ID> --confirm
```

(The lease ID is printed at the end of the script output)

### Troubleshooting

**"Missing OS_AUTH_URL"**
- You forgot to source your OpenRC file
- Fix: `source CHI-XXXX-openrc.sh`

**"Keypair not found"**
- Your KEY_NAME doesn't exist in OpenStack
- Check: `openstack keypair list`
- Fix: Create keypair or use existing name

**"Image not found"**
- Your IMAGE doesn't exist at this site
- Check: `openstack image list | grep -i ubuntu`
- Fix: Use correct image name

**"Server timeout"**
- Baremetal takes longer than expected
- Fix: Increase `SERVER_WAIT=1200` (20 minutes)

**"No floating IP"**
- Some sites don't support floating IPs for baremetal
- The script will use fixed IP (requires VPN or tenant network access)
