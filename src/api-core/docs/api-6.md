## API 6 — Launch servers and get SSH info

### What it does
Starts servers tied to your lease. Reports IPs and the SSH user.

### When to use it
After the lease is ACTIVE. When you are ready to run on nodes.

### Inputs
- reservation-id: Lease ID.
- image: Image name or ID.
- flavor: Flavor name or ID.
- network: Network name or ID.
- key-name: Your SSH keypair name.
- sec-groups: Comma list of security groups. Default: default.
- count: Number of servers. Default: 1.
- name-prefix: Server name prefix. Default: envboot.
- userdata: Path to a cloud-init file. Optional.
- assign-floating-ip: Add floating IPs. Optional.
- wait: Seconds to wait for ACTIVE. Default: 0.
- interval: Polling step in seconds. Default: 5.
- dry-run: Simulate without launching.
- bm-image, bm-ssh-user, force-ironic: Advanced options for bare metal.

### What you get back
A JSON object. It includes:
- ok: true or false.
- data.reservation_id.
- data.servers: List with server_id, name, status, fixed_ip, floating_ip, ssh_user, key_name.
- data.wait: Only when wait is used.
- error: Details when ok=false.
- metrics.elapsed_ms and version.

### Commands
Dry run:
```bash
python3 src/api-core/api-6.py \
  --reservation-id sim-lease-20251105120000 \
  --image "Ubuntu 22.04" \
  --flavor baremetal \
  --network sharednet1 \
  --key-name mykey \
  --assign-floating-ip \
  --dry-run
```
Real run:
```bash
python3 src/api-core/api-6.py \
  --reservation-id ce0891d0-0345-4931-b2b2-07235fb4bde1 \
  --image "CC-Ubuntu20.04" \
  --flavor baremetal \
  --network sharednet1 \
  --key-name Chris \
  --assign-floating-ip \
  --wait 900 \
  --interval 15
```

### Example result
{
  "ok": true,
  "data": {
    "reservation_id": "sim-lease-20251105120000",
    "servers": [
      {
        "server_id": "fake-1",
        "name": "envboot",
        "status": "simulated",
        "fixed_ip": "10.0.0.100",
        "floating_ip": "203.0.113.10",
        "ssh_user": "ubuntu",
        "key_name": "mykey"
      }
    ],
    "dry_run": true
  },
  "error": null,
  "metrics": {"elapsed_ms": 18},
  "version": "1.0.0"
}

Real run
- For physical:host leases, this tool uses the reservation binding under the hood. See docs/RealRun.md for a full example and cleanup.
