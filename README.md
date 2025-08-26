# ENVBoot
# ENVBoot
conda create -n envboot python=3.10
conda activate envboot

pip install python-openstackclient
pip install git+https://github.com/chameleoncloud/python-blazarclient@chameleoncloud/2023.1


#passcode provided from Chameleon Authentication Portal
#https://chameleoncloud.readthedocs.io/en/latest/technical/cli/authentication.html#:~:text=password%20via%20the-,Chameleon%20Authentication%20Portal,-.%20The%20password%20you

source CHI-251467-openrc.sh

#reserve
openstack reservation lease create \
  --reservation min=1,max=1,resource_type=vir:host,resource_properties='["=", "$node_type", "compute_skylake"]' \
  --start-date "2025-07-26 01:27" \ UTC time
  --end-date "2025-07-26 18:00" \
  my-first-lease


#instance
PUBLIC_NETWORK_ID=$(openstack network show public -c id -f value)
openstack reservation lease create --reservation resource_type=virtual:floatingip,network_id=${PUBLIC_NETWORK_ID},amount=1 --start-date "2025-07-26 03:14" --end-date "2025-07-26 03:15" my-first-fip-lease
openstack server create \
--image CC-Ubuntu20.04-20230224 \
--flavor baremetal \
--key-name EnvGym \
--nic net-id=a772a899-ff3d-420b-8b31-1c485092481a \
--hint reservation=71c0c7e8-775f-449b-90e0-bf97d638c128 \
my-instance



openstack floating ip create public --description "testing"

openstack server add floating ip <server-id> <floating-ip>

eg
openstack server add floating ip 709a3f17-7730-45da-9c17-c9a63c3c1b44 129.114.108.114




## Chris
# ENVBoot (Phase 0)

A tiny CLI to verify you can authenticate to **Chameleon Cloud’s OpenStack**.

## What’s here now

* `envboot ping` — sanity check
* `envboot auth-check` — verifies your OpenStack credentials and prints your project

> Later phases will add resource discovery, reservations (Blazar), and launching bare metal.

## Requirements

* Python **3.10+**
* Chameleon account with access to your project (e.g. `CHI-251467`) at **CHI\@UC**
* A **CLI password** (application password) created in the Chameleon portal

## Install (one-time)

```bash
pip install -e .
```

## Authenticate (pick ONE per new terminal)

### Option A — OpenRC (official)

1. In Chameleon (project `CHI-251467`, site `CHI@UC`): **API Access → Download OpenStack RC File (v3)**
2. In your terminal:

   ```bash
   source CHI-251467-openrc.sh   # paste your CLI password when prompted
   envboot auth-check            # expect: OK project: CHI-251467 (...)
   ```

### Option B — `.env` (simple for this app)

1. Create local config (non-secrets):

   ```bash
   cp .env.example .env
   # edit .env → set OS_USERNAME=your_email@school.edu
   ```
2. Each new terminal:

   ```bash
   read -srp "Chameleon CLI password: " OS_PASSWORD; echo
   export OS_PASSWORD
   envboot auth-check
   ```

## Quickstart

```bash
# install once
pip install -e .

# EITHER: OpenRC
source CHI-251467-openrc.sh
envboot ping
envboot auth-check

# OR: .env
cp .env.example .env
read -srp "Chameleon CLI password: " OS_PASSWORD; echo
export OS_PASSWORD
envboot ping
envboot auth-check
```

## Commands (Phase 0)

```bash
envboot ping         # prints "pong"
envboot auth-check   # prints your project if auth works
```

## .env.example

```ini
# Chameleon CHI@UC (non-secret settings)
OS_AUTH_URL=https://chi.uc.chameleoncloud.org:5000/v3
OS_IDENTITY_API_VERSION=3
OS_INTERFACE=public
OS_REGION_NAME=CHI@UC

# OIDC
OS_AUTH_TYPE=v3oidcpassword
OS_PROTOCOL=openid
OS_IDENTITY_PROVIDER=chameleon
OS_DISCOVERY_ENDPOINT=https://auth.chameleoncloud.org/auth/realms/chameleon/.well-known/openid-configuration
OS_CLIENT_ID=keystone-uc-prod
OS_CLIENT_SECRET=none
OS_ACCESS_TOKEN_TYPE=access_token

# Identity (per user)
OS_USERNAME=you@example.edu

# Project (team-shared)
OS_PROJECT_ID=62f12f9c6a28478b976f680a6fa2fa9a

# IMPORTANT: do NOT put OS_PASSWORD here
```
