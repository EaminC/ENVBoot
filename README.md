# EnvBoot# ENVBoot

# ENVBoot

Modular CLI tools for OpenStack and Blazar workflows. Check capacity, create leases, launch servers, and manage cloud resources with simple JSON APIs.conda create -n envboot python=3.10

conda activate envboot

## What this repo contains

pip install python-openstackclient

Six command-line tools (API-1 through API-6) that work together:pip install git+https://github.com/chameleoncloud/python-blazarclient@chameleoncloud/2023.1



1. **api-1** - Check available capacity in a zone

2. **api-2** - Create a reservation (lease)#passcode provided from Chameleon Authentication Portal

3. **api-3** - Check lease status and wait for ACTIVE#https://chameleoncloud.readthedocs.io/en/latest/technical/cli/authentication.html#:~:text=password%20via%20the-,Chameleon%20Authentication%20Portal,-.%20The%20password%20you

4. **api-4** - Delete a lease

5. **api-5** - Provision code locally (prepare workspace)source CHI-251467-openrc.sh

6. **api-6** - Launch servers and get SSH info

#reserve

Each tool outputs structured JSON. Use them individually or chain them together.openstack reservation lease create \

  --reservation min=1,max=1,resource_type=vir:host,resource_properties='["=", "$node_type", "compute_skylake"]' \

## Quick Start  --start-date "2025-07-26 01:27" \ UTC time

  --end-date "2025-07-26 18:00" \

### 1. Clone the repo  my-first-lease



```bash

git clone https://github.com/EaminC/ENVBoot.git#instance

cd ENVBootPUBLIC_NETWORK_ID=$(openstack network show public -c id -f value)

```openstack reservation lease create --reservation resource_type=virtual:floatingip,network_id=${PUBLIC_NETWORK_ID},amount=1 --start-date "2025-07-26 03:14" --end-date "2025-07-26 03:15" my-first-fip-lease

openstack server create \

### 2. Create a Python virtual environment--image CC-Ubuntu20.04-20230224 \

--flavor baremetal \

```bash--key-name EnvGym \

python3 -m venv .venv--nic net-id=a772a899-ff3d-420b-8b31-1c485092481a \

source .venv/bin/activate--hint reservation=71c0c7e8-775f-449b-90e0-bf97d638c128 \

```my-instance



### 3. Install dependencies



```bashopenstack floating ip create public --description "testing"

pip install -r requirements.txt

```openstack server add floating ip <server-id> <floating-ip>



### 4. Load OpenStack credentialseg

openstack server add floating ip 709a3f17-7730-45da-9c17-c9a63c3c1b44 129.114.108.114

Download your OpenRC file from your OpenStack dashboard. Then source it:



```bash

source CHI-XXXX-openrc.sh

```## Chris

# ENVBoot (Phase 0)

Or copy `config/openrc-TEMPLATE.sh`, fill in your credentials, and source that.

A tiny CLI to verify you can authenticate to **Chameleon Cloud’s OpenStack**.

### 5. Run preflight checks

## What’s here now

```bash

bash scripts/preflight.sh* `envboot ping` — sanity check

```* `envboot auth-check` — verifies your OpenStack credentials and prints your project



This verifies:> Later phases will add resource discovery, reservations (Blazar), and launching bare metal.

- Python 3.8+ and required packages installed

- OpenStack credentials loaded## Requirements

- Keypair exists

- Security group allows SSH (TCP/22)* Python **3.10+**

- Images, networks, and flavors available* Chameleon account with access to your project (e.g. `CHI-251467`) at **CHI\@UC**

* A **CLI password** (application password) created in the Chameleon portal

### 6. Try a dry-run

## Install (one-time)

Test the tools without creating real resources:

```bash

```bashpip install -e .

python3 src/api-core/api-1.py --zone uc --start "2025-11-07 12:00" --duration 60 --dry-run```

```

## Authenticate (pick ONE per new terminal)

Output:

```json### Option A — OpenRC (official)

{

  "ok": true,1. In Chameleon (project `CHI-251467`, site `CHI@UC`): **API Access → Download OpenStack RC File (v3)**

  "data": {2. In your terminal:

    "zone": "uc",

    "available_nodes": 5,   ```bash

    "dry_run": true   source CHI-251467-openrc.sh   # paste your CLI password when prompted

  }   envboot auth-check            # expect: OK project: CHI-251467 (...)

}   ```

```

### Option B — `.env` (simple for this app)

### 7. Run a real workflow

1. Create local config (non-secrets):

Create a lease, wait for it, launch a server, and clean up:

   ```bash

```bash   cp .env.example .env

# Check capacity   # edit .env → set OS_USERNAME=your_email@school.edu

python3 src/api-core/api-1.py --zone uc --start "2025-11-07 14:00" --duration 60   ```

2. Each new terminal:

# Create lease

python3 src/api-core/api-2.py --zone uc --start "2025-11-07 14:00" --duration 60 --nodes 1 \   ```bash

  > lease.json   read -srp "Chameleon CLI password: " OS_PASSWORD; echo

   export OS_PASSWORD

# Extract lease ID   envboot auth-check

LEASE_ID=$(jq -r '.data.reservation_id' lease.json)   ```



# Wait for ACTIVE## Quickstart

python3 src/api-core/api-3.py --reservation-id $LEASE_ID --wait 300

```bash

# Launch server# install once

python3 src/api-core/api-6.py \pip install python-blazarclient

  --reservation-id $LEASE_ID \pip install -e .

  --image CC-Ubuntu20.04 \

  --flavor baremetal \# EITHER: OpenRC

  --network sharednet1 \source CHI-251467-openrc.sh

  --key-name Chris \envboot ping

  --assign-floating-ip \envboot auth-check

  --wait 900 \

  > server.json# OR: .env

cp .env.example .env

# Get SSH commandread -srp "Chameleon CLI password: " OS_PASSWORD; echo

jq -r '"ssh -i ~/.ssh/\(.data.servers[0].key_name).pem \(.data.servers[0].ssh_user)@\(.data.servers[0].floating_ip // .data.servers[0].fixed_ip)"' server.jsonexport OS_PASSWORD

envboot ping

# Clean up when doneenvboot auth-check

python3 src/api-core/api-4.py --reservation-id $LEASE_ID --confirm```

```

## Commands (Phase 0)

### 8. Or use an automated end-to-end script

```bash

```bashenvboot ping         # prints "pong"

# Virtual machineenvboot auth-check   # prints your project if auth works

bash scripts/e2e-virtual.sh```



# Bare metal

bash scripts/e2e-baremetal.sh## Mock Resource Availability API (demo)

```

A minimal FastAPI server that simulates resource availability and reservations using in-memory data. Useful for demoing time-shift and zone-change decisions.

## Cloud Prerequisites

Quickstart:

Before running real workflows, ensure you have:

1) Install deps

### Required

```bash

- **OpenStack credentials** - Source your OpenRC filepip install -r requirements.txt

- **SSH keypair** - Create one in your OpenStack project (default name: "Chris")```

  ```bash

  openstack keypair create --public-key ~/.ssh/id_rsa.pub Chris2) Run the server

  ```

- **Security group with SSH** - Default group must allow TCP/22```bash

  ```bashuvicorn demo_api:app_ --reload --port 8000

  openstack security group rule create --protocol tcp --dst-port 22 --ingress default```

  ```

3) Check availability (current blocked, zone-b free now)

### Available in your cloud

```bash

- **Image** - OS image like "CC-Ubuntu20.04" or "Ubuntu 22.04"curl "http://127.0.0.1:8000/availability?region=current&start=2025-09-02T00:10:00Z&duration_hours=4&threshold=1&alt_zones=zone-b&step_minutes=30&lookahead_hours=24"

- **Flavor** - Instance size like "baremetal", "m1.medium", "m1.large"```

- **Network** - Network name like "sharednet1" or "private"

Expected: decision="zone_change" with selection.zone="zone-b".

Check what's available:

```bash4) Reserve the returned slot

openstack image list | grep CC-

openstack flavor list```bash

openstack network listcurl -X POST http://127.0.0.1:8000/reserve \

```   -H 'Content-Type: application/json' \

   -d '{"zone":"zone-b","start":"2025-09-02T00:10:00Z","end":"2025-09-02T04:10:00Z"}'

## Configuration```



### Environment variablesIf capacity is exceeded, the endpoint returns 409.



Copy `config/.env.example` to `config/.env` and customize:

```bash
cp config/.env.example config/.env
nano config/.env
```

Default values:
```bash
KEY_NAME=Chris
IMAGE=CC-Ubuntu20.04
FLAVOR=baremetal
NETWORK=sharednet1
```

Scripts will use these unless you override via environment variables:

```bash
KEY_NAME=mykey IMAGE="Ubuntu 22.04" bash scripts/e2e-virtual.sh
```

### OpenStack credentials

Option 1: Download OpenRC from your dashboard and source it.

Option 2: Copy `config/openrc-TEMPLATE.sh`, fill in your values, and source it:

```bash
cp config/openrc-TEMPLATE.sh config/openrc.sh
# Edit config/openrc.sh with your credentials
source config/openrc.sh
```

## Resource Types

APIs support two lease types:

- **virtual:instance** - Virtual machines (VMs)
- **physical:host** - Bare metal servers

For physical:host leases, api-6 uses Nova with Blazar reservation hints by default. This schedules the server on your reserved hardware.

## Troubleshooting

### "Missing OS_AUTH_URL"

You forgot to source your OpenRC file.

**Fix:**
```bash
source config/openrc.sh
```

### "No valid host was found"

The lease is not ACTIVE yet, or there are no nodes available.

**Fix:**
1. Wait for the lease to become ACTIVE (use api-3 with --wait)
2. Check capacity before creating the lease (use api-1)

### "Image not found" or "Flavor not found"

The name you used does not exist at your site.

**Fix:**
```bash
openstack image list
openstack flavor list
```

Use exact names from the output.

### "Keypair not found"

Your keypair does not exist in OpenStack.

**Fix:**
```bash
openstack keypair create --public-key ~/.ssh/id_rsa.pub YourKeyName
```

### Floating IP is null

Some sites don't support floating IPs for baremetal, or allocation failed.

**Workaround:**
- Use the fixed IP (requires VPN or tenant network access)
- Remove `--assign-floating-ip` from api-6 calls

### Server timeout

Bare metal provisioning can take 10-20 minutes.

**Fix:**
Increase wait timeout:
```bash
--wait 1200  # 20 minutes
```

## Documentation

- **API docs**: `src/api-core/docs/api-1.md` through `api-6.md`
- **Quick guide**: `docs/QuickGuide.md`
- **Real run walkthrough**: `docs/RealRun.md`
- **Troubleshooting**: `docs/Troubleshooting.md`
- **Test scripts**: `scripts/README.md`

## API Examples

### API-1: Check capacity

```bash
python3 src/api-core/api-1.py --zone uc --start "2025-11-07 12:00" --duration 60
```

Returns available nodes in the zone for that time window.

### API-2: Create lease

```bash
python3 src/api-core/api-2.py \
  --zone uc \
  --start "2025-11-07 14:00" \
  --duration 120 \
  --nodes 1 \
  --resource-type physical:host
```

Creates a lease and returns the reservation ID.

### API-3: Check status

```bash
python3 src/api-core/api-3.py --reservation-id <LEASE_ID> --wait 300
```

Polls until the lease is ACTIVE or timeout.

### API-6: Launch server

```bash
python3 src/api-core/api-6.py \
  --reservation-id <LEASE_ID> \
  --image CC-Ubuntu20.04 \
  --flavor baremetal \
  --network sharednet1 \
  --key-name Chris \
  --wait 900
```

Launches a server and returns SSH connection info.

### API-4: Delete lease

```bash
python3 src/api-core/api-4.py --reservation-id <LEASE_ID> --confirm
```

Deletes the lease and associated resources.

## Project Structure

```
ENVBoot/
├── src/api-core/         # CLI tools (api-1 through api-6)
│   └── docs/             # Per-API documentation
├── envboot/              # Python package (optional features)
├── scripts/              # Test and automation scripts
│   ├── preflight.sh      # Pre-flight checks
│   ├── e2e-virtual.sh    # End-to-end VM test
│   └── e2e-baremetal.sh  # End-to-end bare metal test
├── config/               # Configuration templates
│   ├── .env.example      # Environment variable defaults
│   └── openrc-TEMPLATE.sh # OpenStack credentials template
├── docs/                 # General documentation
└── requirements.txt      # Python dependencies
```

## Contributing

When adding new features:
1. Keep JSON output schema consistent: `{ok, data, error, metrics, version}`
2. Support `--dry-run` for safe testing
3. Use exit codes: 0=success, 1=invalid args, 2=backend error
4. Add docs in `src/api-core/docs/`

## License

See LICENSE file for details.
