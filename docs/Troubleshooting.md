## Troubleshooting

### Dry-run vs Real mode

All APIs support two modes:

**Dry-run mode** (--dry-run flag)
- Safe to test anytime. No credentials needed.
- Returns simulated data.
- No changes to your cloud resources.
- Exit code 0 on success.

**Real mode** (no --dry-run flag)
- Requires OpenStack credentials (OS_AUTH_URL and others).
- Creates, modifies, or queries real cloud resources.
- APIs 2, 3, 4, 6 need credentials. API 1 uses local data files.
- Exit code 0 on success, 1 for invalid args, 2 for backend errors.

### Common errors

**"Missing OS_AUTH_URL environment variable"**
- You forgot to source your OpenRC file.
- Fix: Run `source CHI-XXXX-openrc.sh` (replace with your project file).

**"Failed to get lease status: ..."**
- Your credentials expired or lease ID is wrong.
- Fix: Check the reservation ID. Re-source your OpenRC if needed.

**"Image not found" or "Flavor not found"**
- The name you used does not exist at your site.
- Fix: Check available images and flavors in your cloud dashboard.

**"No valid host was found"**
- Nova cannot schedule the server. Lease may not be ACTIVE yet.
- Fix: Wait for the lease to be ACTIVE (use API 3). Check that you're using the right resource-type.

### Testing without credentials

Use --dry-run on any API to test the command format and see simulated output.

Examples:
```bash
python3 src/api-core/api-1.py --zone uc --start "2025-11-06 18:00" --duration 60 --dry-run
python3 src/api-core/api-2.py --zone uc --start "2025-11-06 19:00" --duration 60 --nodes 1 --dry-run
python3 src/api-core/api-6.py --reservation-id test-123 --image ubuntu --flavor baremetal --network sharednet1 --key-name test --dry-run
```

All will return ok=true with simulated data.

### Getting help

Check individual API docs:
- src/api-core/docs/api-1.md through api-6.md

Check the full workflow:
- docs/RealRun.md
- docs/QuickGuide.md
