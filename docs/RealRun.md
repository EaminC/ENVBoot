## Real run — end to end

This guide walks you through a real lease. It creates resources, starts a server, and then cleans up.

### Before you start
- Use UTC for times. Format: YYYY-MM-DD HH:MM.
- **Load your project environment (OpenRC).** Example: source CHI-XXXX-openrc.sh
  - This sets OS_AUTH_URL and other required environment variables.
  - Without this, APIs 2, 3, 4, and 6 will fail in real mode (they need cloud credentials).
- Know your SSH keypair name (as registered in the cloud).
- Pick an image name, flavor, and network that exist at your site.
- Make sure your security group allows SSH (TCP 22). The default group often works.

Tip: Replace example values with your own. Do not paste secrets.

Note: All APIs support --dry-run for safe testing without credentials or side effects.

### 1) Create a lease
Create a lease that starts a few minutes from now and lasts one hour.

Command
- Adjust the start time to a few minutes in the future in UTC.

python3 src/api-core/api-2.py --zone uc --start "2025-11-05 12:00" --duration 60 --nodes 1 --resource-type physical:host

You will get JSON with reservation_id. Save it. Example
{
  "ok": true,
  "data": {
    "reservation_id": "a1b2c3d4-...",
    "status": "created"
  }
}

### 2) Wait for ACTIVE
Poll the lease until it becomes ACTIVE.

python3 src/api-core/api-3.py --reservation-id a1b2c3d4-... --wait 300

Example (trimmed)
{
  "ok": true,
  "data": { "status": "ACTIVE", "allocated": true }
}

### 3) Launch a server
Start one server on your lease and wait for it to be ready.

- image: Example "Ubuntu 22.04".
- flavor: Example baremetal.
- network: Example sharednet1.
- key-name: Your keypair name.

python3 src/api-core/api-6.py \
  --reservation-id a1b2c3d4-... \
  --image "Ubuntu 22.04" \
  --flavor baremetal \
  --network sharednet1 \
  --key-name mykey \
  --assign-floating-ip \
  --wait 600

Example (trimmed)
{
  "ok": true,
  "data": {
    "servers": [
      {
        "name": "envboot",
        "status": "ACTIVE",
        "fixed_ip": "10.0.0.100",
        "floating_ip": "203.0.113.10",
        "ssh_user": "ubuntu"
      }
    ]
  }
}

### 4) Connect with SSH
Use the ssh_user and IP from the output. Replace the key path with yours.

ssh ubuntu@203.0.113.10 -i ~/.ssh/mykey.pem

If you did not request a floating IP, use the fixed IP from your network.

### 5) Clean up the lease
When finished, delete the lease. You can wait until it is fully gone.

python3 src/api-core/api-4.py --reservation-id a1b2c3d4-... --confirm --wait 120

Example (trimmed)
{
  "ok": true,
  "data": { "status": "deleted" }
}

### Optional: one-shot script
There is an example script that automates these steps for a physical:host lease using the Nova path.

bash scripts/test_api6_nova_physical_host.sh

It creates a lease, waits, launches a server, prints the SSH info, and can clean up. 

The script is configurable with environment variables for easy reuse:
```bash
# Use your own parameters
KEY_NAME=mykey IMAGE="Ubuntu 22.04" FLAVOR=m1.large bash scripts/test_api6_nova_physical_host.sh
```

See scripts/README.md for all available options and troubleshooting.
