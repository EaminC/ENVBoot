## integrate_and_plan.py - Quick Reference for --find-earliest

### What is --find-earliest?

The `--find-earliest` flag automatically searches forward in time to find the earliest slot with sufficient capacity when your requested time doesn't have enough available nodes.

### Usage Examples

#### Basic Usage
```bash
# Request 130 nodes at 10:00 - if unavailable, find earliest slot
python3 integrate_and_plan.py \
  --zone uc \
  --start "2025-10-30 10:00" \
  --duration 60 \
  --amount 130 \
  --find-earliest
```

#### With Custom Search Window
```bash
# Search up to 48 hours ahead (default is 168 hours / 7 days)
python3 integrate_and_plan.py \
  --zone uc \
  --start "2025-10-30 10:00" \
  --duration 60 \
  --amount 130 \
  --find-earliest \
  --max-search-hours 48
```

### How It Works

1. **First Check**: Checks availability at your requested time
2. **If Insufficient**: Scans forward in 1-hour increments
3. **Finds Earliest**: Returns first slot with enough nodes
4. **Provides Command**: Gives you exact command to run for that time

### Example Output

```
⚠️  Warning: Only 127 nodes available, but 130 requested.

Searching for earliest slot with 130 nodes...
Scanning up to 168 hours ahead...

✓ Found sufficient capacity!
  Earliest time: 2025-10-30T12:00:00Z (2 hours from requested time)
  Available nodes: 131

To reserve at this time, run:
  python3 integrate_and_plan.py --zone uc --start "2025-10-30 12:00" --duration 60 --amount 130 --dry-run 0
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--find-earliest` | (flag) | Enable automatic search for earliest available slot |
| `--max-search-hours` | 168 | Maximum hours to search ahead (168 = 7 days) |
| `--amount` | 1 | Number of nodes required |

### When to Use

✅ **Use --find-earliest when:**
- You need specific capacity but are flexible on timing
- Planning ahead and want to find optimal reservation windows
- Automating reservation workflows
- Working during busy periods

❌ **Don't use --find-earliest when:**
- You have a strict deadline (specific time required)
- Just checking current availability
- Using --dry-run to explore options

### Testing

Run the comprehensive test suite:
```bash
./test_find_earliest_feature.sh
```

Or test with mock busy data:
```bash
./test_busy_zones.sh
```

### Related Flags

- `--zone` - Specify which site/zone to search (uc, tacc, nu, etc.)
- `--list-zones` - Show available zones
- `--refresh` - Pull latest allocation data before searching
- `--dry-run 0` - Actually create the lease (default is 1 for preview)

### Tips

1. **Combine with --refresh**: Get real-time availability data
   ```bash
   python3 integrate_and_plan.py --refresh --find-earliest --zone uc --start "2025-10-30 10:00" --amount 100
   ```

2. **Check multiple zones**: If one zone is busy, try another
   ```bash
   # Try UC first
   python3 integrate_and_plan.py --find-earliest --zone uc --start "2025-10-30 10:00" --amount 100
   
   # If no slots found, try TACC
   python3 integrate_and_plan.py --find-earliest --zone tacc --start "2025-10-30 10:00" --amount 100
   ```

3. **Limit search window for urgent needs**: Use --max-search-hours to avoid suggestions too far in the future
   ```bash
   python3 integrate_and_plan.py --find-earliest --max-search-hours 24 --zone uc --start "2025-10-30 10:00" --amount 100
   ```
