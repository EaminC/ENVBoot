# Quick Repro Guide: Running EnvBoot APIs

This guide helps you (or a teammate) quickly reproduce the core API flows in a fresh checkout of this repo.

## Steps

**0. Set up Python environment and dependencies**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**1. Edit your OpenStack credentials**
- Copy `CHI-251467-openrc.sh` (or use your own OpenRC file)
- Edit it to match your OpenStack project/user info

**2. Source your OpenRC and authenticate**
```bash
source CHI-251467-openrc.sh
# Enter your OpenStack password if prompted
```

**3. Ensure Python can find the repo root**
```bash
export PYTHONPATH="$(pwd):$PYTHONPATH"
```

**4. Create a lease using API-2**
```bash
python src/api-core/api-2.py --zone uc --start "$(date -u -d '+3 minutes' '+%Y-%m-%d %H:%M')" --duration 45 --nodes 1
```
- You should see a JSON response with `"ok": true` and a `reservation_id`.

**5. (Optional) Override test parameters**
- You can override key settings (keypair, image, flavor, network, etc.) by exporting variables or prefixing the command:
```bash
KEY_NAME=mykey IMAGE="Ubuntu 22.04" FLAVOR=m1.large NETWORK=public bash scripts/test_api6_nova_physical_host.sh
```
- If not set, the script uses default values from `.env.example` or hardcoded defaults.

**6. Run the full demo/test script**
```bash
bash scripts/test_api6_nova_physical_host.sh
```
- This exercises all 6 APIs in sequence (lease create, status, server launch, etc.)

## Notes
- All scripts expect OpenStack environment variables (OS_*) to be set (via OpenRC).
- If you see import errors for `envboot`, make sure you set `PYTHONPATH` as above.
- For troubleshooting, see `/tmp/api*_out.json` files after running the test script.
- You can use dry-run mode for most APIs by adding `--dry-run` to the command.

---

For more details, see the main README or docs in this repo.
