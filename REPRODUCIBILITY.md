# Reproducibility Audit & Checklist

## Prerequisites Audit (from code scan)

### OpenStack Environment Variables

**Required for APIs 2, 3, 4, 6 (real mode):**
- `OS_AUTH_URL` - Keystone endpoint
- `OS_USERNAME` - Your username
- `OS_PASSWORD` - Your password
- `OS_PROJECT_ID` or `OS_PROJECT_NAME` - Project identifier

**Optional:**
- `OS_REGION_NAME` - Region (e.g., "CHI@UC")
- `OS_USER_DOMAIN_NAME` - Default: "Default"
- `OS_PROJECT_DOMAIN_NAME` - Default: "Default"

**For OIDC authentication (Chameleon):**
- `OS_AUTH_TYPE=v3oidcpassword`
- `OS_IDENTITY_PROVIDER` - e.g., "chameleon"
- `OS_PROTOCOL` - e.g., "openid"
- `OS_DISCOVERY_ENDPOINT` - OIDC discovery URL
- `OS_CLIENT_ID` - Client ID
- `OS_CLIENT_SECRET` - Optional for public clients
- `OS_ACCESS_TOKEN_TYPE` - Default: "access_token"
- `OS_OIDC_SCOPE` - Default: "openid profile email"

### Cloud Artifacts

**Must exist in your OpenStack project:**
- SSH keypair (default: "Chris") - `openstack keypair create`
- Security group allowing TCP/22 (default: "default")
- Network (default: "sharednet1") - `openstack network list`
- Image (default: "CC-Ubuntu20.04") - `openstack image list`
- Flavor (default: "baremetal") - `openstack flavor list`

**Optional:**
- Floating IP pool (for `--assign-floating-ip`)

### Lease Resource Types

- `virtual:instance` - Virtual machines via Nova
- `physical:host` - Bare metal via Nova + Blazar reservation hints

**Note:** api-6 uses Nova by default for both types. For physical:host, it passes `reservation.id` as a scheduler hint. Use `--force-ironic` only if explicit Ironic provisioning is required.

### Python Dependencies

**Minimum (Python 3.8+):**
```
openstacksdk>=1.0.0
python-blazarclient>=3.0.0
python-dotenv>=1.0.0
keystoneauth1>=5.0.0
```

**Optional (envboot package features):**
```
typer>=0.9.0
openai>=1.0.0
pandas>=2.0.0
fastapi>=0.100.0
uvicorn>=0.23.0
```

### External CLI Tools

- `jq` - JSON parser (used by test scripts)
- `openstack` - OpenStack CLI (optional, for manual checks)

### Local Data Files (optional)

**API-1 in real mode requires:**
- `allocations.json` - Allocation/reservation data
- `examples/api_samples/uc_chameleon_nodes.json` - Node metadata
- `resource_map.json` - Resource ID mapping

**API-1 with --dry-run:** No files needed (simulates data).

**APIs 2-6:** Do not require local data files.

## Before You Run - Checklist

### 1. Environment Setup
- [ ] Python 3.8 or higher installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `jq` installed (for scripts: `apt install jq` or `brew install jq`)

### 2. OpenStack Credentials
- [ ] OpenRC file downloaded from dashboard
- [ ] OpenRC file sourced (`source config/openrc.sh`)
- [ ] Verify: `echo $OS_AUTH_URL` returns a URL

### 3. Cloud Resources
- [ ] SSH keypair created (`openstack keypair list`)
- [ ] Security group allows TCP/22 (`openstack security group rule list default`)
- [ ] Know your network name (`openstack network list`)
- [ ] Know your image name (`openstack image list | grep CC-`)
- [ ] Know your flavor name (`openstack flavor list`)

### 4. Configuration (optional)
- [ ] Copy `config/.env.example` to `config/.env`
- [ ] Edit `config/.env` with your keypair/image/flavor/network names

### 5. Verification
- [ ] Run `bash scripts/preflight.sh` - all checks pass
- [ ] Test dry-run: `python3 src/api-core/api-1.py --zone uc --start "2025-11-07 12:00" --duration 60 --dry-run`

## Quick Venv Setup

```bash
# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install deps
pip install -r requirements.txt

# Verify
python3 -c "import openstacksdk; print('✓ openstacksdk installed')"
```

## Files Added for Reproducibility

- `README.md` - Top-level quick start guide
- `requirements.txt` - Updated with minimal deps
- `config/.env.example` - Default configuration
- `config/openrc-TEMPLATE.sh` - OpenStack credentials template
- `scripts/preflight.sh` - Pre-flight checks (read-only)
- `scripts/e2e-virtual.sh` - Virtual machine end-to-end test
- `scripts/e2e-baremetal.sh` - Bare metal end-to-end test
- `REPRODUCIBILITY.md` - This audit document

## For Yiming (or any new teammate)

**Start here:**
1. Clone the repo
2. Follow README.md "Quick Start" section (steps 1-6)
3. Run `bash scripts/preflight.sh`
4. If checks pass, try: `bash scripts/e2e-virtual.sh`

**If you hit issues:**
- Check `docs/Troubleshooting.md`
- Run preflight again to see what's missing
- Customize `config/.env` for your environment
