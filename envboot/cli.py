import os, json
import time
from datetime import datetime, timedelta, timezone
from keystoneauth1 import session as ks
from pathlib import Path
import typer
from .osutil import conn, blz
from .models import (
    ComplexityTier, ResourceRequest, DowngradePolicy, 
    SchedulingConfig, ReservationPlan, CaseStudyResult
)
from .analysis import (
    analyze_repo_complexity, map_complexity_to_request, 
    estimate_su_per_hour, get_default_duration_hours
)
from .scheduling import (
    detect_overload_in_zone, find_available_window, 
    find_matching_flavor, create_reservation
)
from .downgrade import (
    try_downgrade, run_smoke_test, 
    calculate_duration_increase, validate_downgrade_policy
)

app = typer.Typer(no_args_is_help=True)

@app.command()
def ping():
    """Sanity check command."""
    typer.echo("pong")

@app.command("auth-check")
def auth_check():
    """Verify OpenStack credentials work."""
    try:
        c = conn()
        proj = c.identity.get_project(c.current_project_id)
        typer.echo(f"OK project: {proj.name} ({proj.id})")
    except Exception as e:
        typer.echo(f"Auth failed: {e}")
        raise typer.Exit(1)

@app.command("instances")
def instances():
    """List current instances with details."""
    c = conn()
    instances_list = []
    for s in c.compute.servers():
        instances_list.append({
            "id": s.id,
            "name": s.name,
            "status": s.status,
            "created": s.created,
            "addresses": s.addresses,
            "flavor": s.flavor.get("original_name") if s.flavor else None,
            "key_name": s.key_name
        })
    typer.echo(json.dumps(instances_list, indent=2))

@app.command("flavors")
def flavors():
    """List available flavors."""
    c = conn()
    flavors_list = []
    for f in c.compute.flavors():
        flavors_list.append({
            "id": f.id,
            "name": f.name,
            "vcpus": f.vcpus,
            "ram_mb": f.ram,
            "disk_gb": f.disk
        })
    typer.echo(json.dumps(flavors_list, indent=2))

@app.command("doctor")
def doctor():
    required = [
        "OS_AUTH_URL","OS_AUTH_TYPE","OS_USERNAME","OS_PROTOCOL",
        "OS_IDENTITY_PROVIDER","OS_DISCOVERY_ENDPOINT","OS_CLIENT_ID","OS_REGION_NAME"
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        typer.echo(f"Missing envs: {', '.join(missing)}")
        raise typer.Exit(1)

    # mask sensitive
    def mask(v): 
        if v is None: return None
        return v[:2] + "****" if len(v) > 6 else "****"

    print(json.dumps({
        "auth_url": os.environ.get("OS_AUTH_URL"),
        "auth_type": os.environ.get("OS_AUTH_TYPE"),
        "username": os.environ.get("OS_USERNAME"),
        "project_id": os.environ.get("OS_PROJECT_ID"),
        "project_name": os.environ.get("OS_PROJECT_NAME"),
        "region": os.environ.get("OS_REGION_NAME"),
        "client_id": os.environ.get("OS_CLIENT_ID"),
        "client_secret_present": bool(os.environ.get("OS_CLIENT_SECRET")),
        "scope": os.environ.get("OS_OIDC_SCOPE", "openid profile email"),
    }, indent=2))

    try:
        # build the exact same auth as conn()
        from .osutil import _auth_from_env
        auth = _auth_from_env()
        sess = ks.Session(auth=auth)
        # force an auth to get a token
        tok = sess.get_token()
        print("Token OK (truncated):", mask(tok))
    except Exception as e:
        print("Auth error:", e)
        raise typer.Exit(1)


def _ensure_floating_ip(c, server):
    """Minimal floating IP assigner for Phase 1.
    Assumes a public network named 'public' and attaches an available IP.
    """
    pub = c.network.find_network("public", ignore_missing=False)
    # Check existing attached FIP
    for ip in c.network.ips():
        if getattr(ip, "port_id", None) and getattr(ip, "floating_ip_address", None):
            return ip.floating_ip_address
    # Allocate new and attach
    ip = c.network.create_ip(floating_network_id=pub.id)
    c.compute.add_floating_ip_to_server(server, ip.floating_ip_address)
    return ip.floating_ip_address


@app.command("demo-fixed")
def demo_fixed(
    flavor: str = typer.Option("baremetal", help="Flavor name to use (e.g., 'baremetal')"),
    key_name: str = typer.Option("Chris", help="Nova keypair name to inject"),
):
    """Phase 1: bring up a bare metal instance with fixed params and print SSH."""
    c = conn()
    # 1) Create lease with a near-now window and node_type
    start_dt = datetime.now(timezone.utc) + timedelta(minutes=2)
    end_dt = start_dt + timedelta(hours=4)
    start_str = start_dt.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")

    lease = blz().lease.create(
        name="envboot-demo",
        start=start_str,
        end=end_str,
        reservations=[{
            "resource_type": "physical:host",
            "min": 1, "max": 1,
            "resource_properties": '[]',
            "hypervisor_properties": '[]'
        }],
        events=[]
    )
    reservation_id = lease["reservations"][0]["id"]

    # Wait for lease to become ACTIVE before booting
    lease_id = lease["id"]
    deadline = time.time() + 600  # up to 10 minutes
    while time.time() < deadline:
        cur = blz().lease.get(lease_id)
        status = cur.get("status")
        if status in ("ACTIVE", "STARTED"):
            break
        time.sleep(5)
    else:
        raise typer.Exit(code=1)

    # 2) Boot server with scheduler hint
    img = c.compute.find_image("CC-Ubuntu22.04", ignore_missing=False)
    flv = c.compute.find_flavor(flavor, ignore_missing=False)
    net = c.network.find_network("sharednet1", ignore_missing=False)

    server = c.compute.create_server(
        name="envboot-fixed",
        image_id=img.id,
        flavor_id=flv.id,
        networks=[{"uuid": net.id}],
        key_name=key_name,
        scheduler_hints={"reservation": reservation_id},
    )
    # Wait for server with longer timeout for bare metal
    typer.echo(f"Waiting for server {server.id} to become ACTIVE...")
    deadline = time.time() + 600  # 10 minutes
    while time.time() < deadline:
        server = c.compute.get_server(server.id)
        if server.status == "ACTIVE":
            break
        elif server.status == "ERROR":
            raise typer.Exit(code=1)
        typer.echo(f"Status: {server.status}, waiting...")
        time.sleep(60)
    else:
        raise typer.Exit(code=1)
    fip = _ensure_floating_ip(c, server)
    typer.echo(f"ssh -i ~/.ssh/{key_name}.pem ubuntu@{fip}")

@app.command("cases")
def cases():
    """Case studies for resource allocation and charging in Chameleon."""
    typer.echo("Available case studies:")
    typer.echo("  base      - Base case: sufficient resources, direct acquisition")
    typer.echo("  limited   - Limited resources: detect overload, find alternatives")
    typer.echo("  downgrade - Downgrade scenario: adapt resources to availability")
    typer.echo("  complexity - Repo complexity analysis and resource mapping")

@app.command("cases-base")
def case_base(
    repo_path: str = typer.Argument(".", help="Path to repository to analyze"),
    complexity: str = typer.Option(None, "--complexity", help="Override complexity tier"),
    key_name: str = typer.Option("Chris", help="Nova keypair name to inject"),
    output_file: str = typer.Option(None, "--output", help="JSON output file path"),
):
    """Case 1: Base case - Agent analysis requires hardware, resources sufficient, agent acquires access."""
    
    typer.echo("=== Case Study 1: Base Case ===")
    
    # Analyze repository complexity
    if complexity:
        try:
            complexity_tier = ComplexityTier(complexity)
            typer.echo(f"Using override complexity: {complexity}")
        except ValueError:
            typer.echo(f"Invalid complexity tier: {complexity}")
            raise typer.Exit(1)
    else:
        typer.echo(f"Analyzing repository complexity for: {repo_path}")
        complexity_tier = analyze_repo_complexity(repo_path)
        typer.echo(f"Detected complexity: {complexity_tier.value}")
    
    # Map to resource requirements
    req = map_complexity_to_request(complexity_tier)
    duration_hours = get_default_duration_hours(complexity_tier)
    
    typer.echo(f"Resource requirements: {req.vcpus} vCPUs, {req.ram_gb} GB RAM, {req.gpus} GPUs")
    typer.echo(f"Duration: {duration_hours} hours")
    
    # Create reservation
    start_time = datetime.now(timezone.utc) + timedelta(minutes=2)
    end_time = start_time + timedelta(hours=duration_hours)
    
    plan = ReservationPlan(
        zone="current",
        start=start_time,
        end=end_time,
        flavor="auto",
        count=1
    )
    
    # Create the actual reservation
    typer.echo("Creating Blazar reservation...")
    lease = create_reservation(plan, req, f"envboot-base-{complexity_tier.value}")
    
    # Calculate SU estimates
    host_caps = {"vcpus": 48, "gpus": 4}  # Default assumptions
    su_per_hour = estimate_su_per_hour(req, host_caps)
    su_total = su_per_hour * duration_hours
    
    typer.echo(f"SU estimate: {su_per_hour:.4f} per hour, {su_total:.4f} total")
    
    # Create result
    result = CaseStudyResult(
        case="base_case",
        inputs={
            "repo_path": repo_path,
            "complexity_tier": complexity_tier.value,
            "resource_request": {
                "vcpus": req.vcpus,
                "ram_gb": req.ram_gb,
                "gpus": req.gpus,
                "bare_metal": req.bare_metal
            },
            "duration_hours": duration_hours
        },
        decisions=[],
        reservation=plan,
        su_estimate_per_hour=su_per_hour,
        su_estimate_total=su_total,
        slo={"start_by": start_time.isoformat(), "met": True},
        complexity_tier=complexity_tier
    )
    
    # Output results
    typer.echo("\n=== Results ===")
    typer.echo(f"Reservation created: {plan.lease_id}")
    typer.echo(f"Zone: {plan.zone}")
    typer.echo(f"Start: {plan.start}")
    typer.echo(f"End: {plan.end}")
    typer.echo(f"Flavor: {plan.flavor}")
    typer.echo(f"SU cost: {su_total:.4f}")
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result.__dict__, f, indent=2, default=str)
        typer.echo(f"Results saved to: {output_file}")

@app.command("cases-limited")
def case_limited(
    repo_path: str = typer.Argument(".", help="Path to repository to analyze"),
    complexity: str = typer.Option(None, "--complexity", help="Override complexity tier"),
    key_name: str = typer.Option("Chris", help="Nova keypair name to inject"),
    output_file: str = typer.Option(None, "--output", help="JSON output file path"),
    lookahead_hours: int = typer.Option(72, "--lookahead", help="Hours to look ahead for availability"),
    alt_zones: str = typer.Option("", "--alt-zones", help="Comma-separated alternative zones"),
):
    """Case 2: Limited resources - Agent detects resource shortage and reserves in different time/zone."""
    
    typer.echo("=== Case Study 2: Limited Resources ===")
    
    # Parse alternative zones
    zone_list = [z.strip() for z in alt_zones.split(",")] if alt_zones else []
    
    # Analyze repository complexity
    if complexity:
        try:
            complexity_tier = ComplexityTier(complexity)
            typer.echo(f"Using override complexity: {complexity}")
        except ValueError:
            typer.echo(f"Invalid complexity tier: {complexity}")
            raise typer.Exit(1)
    else:
        typer.echo(f"Analyzing repository complexity for: {repo_path}")
        complexity_tier = analyze_repo_complexity(repo_path)
        typer.echo(f"Detected complexity: {complexity_tier.value}")
    
    # Map to resource requirements
    req = map_complexity_to_request(complexity_tier)
    duration_hours = get_default_duration_hours(complexity_tier)
    
    typer.echo(f"Resource requirements: {req.vcpus} vCPUs, {req.ram_gb} GB RAM, {req.gpus} GPUs")
    typer.echo(f"Duration: {duration_hours} hours")
    
    # Configure scheduling
    config = SchedulingConfig(
        lookahead_hours=lookahead_hours,
        alt_zones=zone_list
    )
    
    # Check current zone for overload
    current_zone = "current"  # This would come from environment or config
    typer.echo(f"Checking for resource overload in zone: {current_zone}")
    
    start_time = datetime.now(timezone.utc) + timedelta(minutes=2)
    end_time = start_time + timedelta(hours=duration_hours)
    
    overload_detected = detect_overload_in_zone(current_zone, req, start_time, end_time)
    
    if overload_detected is True:
        typer.echo("❌ Resource overload detected in current zone")
        typer.echo("Searching for alternative time windows and zones...")
        
        # Find available window
        plan = find_available_window(req, duration_hours, config, current_zone)
        
        if plan:
            typer.echo(f"✅ Found available window in zone: {plan.zone}")
            typer.echo(f"   Start: {plan.start}")
            typer.echo(f"   End: {plan.end}")
            
            # Create reservation
            lease = create_reservation(plan, req, f"envboot-limited-{complexity_tier.value}")
            
            # Calculate SU estimates
            host_caps = {"vcpus": 48, "gpus": 4}
            su_per_hour = estimate_su_per_hour(req, host_caps)
            su_total = su_per_hour * duration_hours
            
            # Determine decision type
            decisions = []
            if plan.zone != current_zone:
                decisions.append({"type": "zone_change", "from": current_zone, "to": plan.zone})
            else:
                time_shift = int((plan.start - start_time).total_seconds() / 60)
                decisions.append({"type": "time_shift", "minutes": time_shift})
            
            result = CaseStudyResult(
                case="limited_resources_subcase_A",
                inputs={
                    "repo_path": repo_path,
                    "complexity_tier": complexity_tier.value,
                    "resource_request": {
                        "vcpus": req.vcpus,
                        "ram_gb": req.ram_gb,
                        "gpus": req.gpus,
                        "bare_metal": req.bare_metal
                    },
                    "duration_hours": duration_hours,
                    "scheduling_config": {
                        "lookahead_hours": lookahead_hours,
                        "alt_zones": zone_list
                    }
                },
                decisions=decisions,
                reservation=plan,
                su_estimate_per_hour=su_per_hour,
                su_estimate_total=su_total,
                slo={"start_by": start_time.isoformat(), "met": True},
                complexity_tier=complexity_tier
            )
            
            # Output results
            typer.echo("\n=== Results ===")
            typer.echo(f"Reservation created: {plan.lease_id}")
            typer.echo(f"Zone: {plan.zone}")
            typer.echo(f"Start: {plan.start}")
            typer.echo(f"End: {plan.end}")
            typer.echo(f"Flavor: {plan.flavor}")
            typer.echo(f"SU cost: {su_total:.4f}")
            
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(result.__dict__, f, indent=2, default=str)
                typer.echo(f"Results saved to: {output_file}")
        else:
            typer.echo("❌ No available windows found in any zone")
            raise typer.Exit(1)
    elif overload_detected is None:
        typer.echo("⚠️  Cannot determine overload status, attempting time/zone search optimistically...")
        
        # Try to find available window anyway
        plan = find_available_window(req, duration_hours, config, current_zone)
        
        if plan:
            typer.echo(f"✅ Found available window in zone: {plan.zone}")
            typer.echo(f"   Start: {plan.start}")
            typer.echo(f"   End: {plan.end}")
            
            # Create reservation
            lease = create_reservation(plan, req, f"envboot-limited-{complexity_tier.value}")
            
            # Calculate SU estimates
            host_caps = {"vcpus": 48, "gpus": 4}
            su_per_hour = estimate_su_per_hour(req, host_caps)
            su_total = su_per_hour * duration_hours
            
            # Determine decision type
            decisions = []
            if plan.zone != current_zone:
                decisions.append({"type": "zone_change", "from": current_zone, "to": plan.zone})
            else:
                time_shift = int((plan.start - start_time).total_seconds() / 60)
                decisions.append({"type": "time_shift", "minutes": time_shift})
            
            decisions.append({"type": "undetermined_overload_attempted_search"})
            
            result = CaseStudyResult(
                case="limited_resources_subcase_A",
                inputs={
                    "repo_path": repo_path,
                    "complexity_tier": complexity_tier.value,
                    "resource_request": {
                        "vcpus": req.vcpus,
                        "ram_gb": req.ram_gb,
                        "gpus": req.gpus,
                        "bare_metal": req.bare_metal
                    },
                    "duration_hours": duration_hours,
                    "scheduling_config": {
                        "lookahead_hours": lookahead_hours,
                        "alt_zones": zone_list
                    }
                },
                decisions=decisions,
                reservation=plan,
                su_estimate_per_hour=su_per_hour,
                su_estimate_total=su_total,
                slo={"start_by": start_time.isoformat(), "met": True},
                complexity_tier=complexity_tier
            )
            
            # Output results
            typer.echo("\n=== Results ===")
            typer.echo(f"Reservation created: {plan.lease_id}")
            typer.echo(f"Zone: {plan.zone}")
            typer.echo(f"Start: {plan.start}")
            typer.echo(f"End: {plan.end}")
            typer.echo(f"Flavor: {plan.flavor}")
            typer.echo(f"SU cost: {su_total:.4f}")
            
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(result.__dict__, f, indent=2, default=str)
                typer.echo(f"Results saved to: {output_file}")
        else:
            typer.echo("❌ No available windows found in any zone")
            raise typer.Exit(1)
    else:
        typer.echo("✅ No overload detected, proceeding with base case")
        # Fall back to base case logic
        case_base(repo_path, complexity, key_name, output_file)

@app.command("cases-downgrade")
def case_downgrade(
    repo_path: str = typer.Argument(".", help="Path to repository to analyze"),
    complexity: str = typer.Option(None, "--complexity", help="Override complexity tier"),
    key_name: str = typer.Option("Chris", help="Nova keypair name to inject"),
    output_file: str = typer.Option(None, "--output", help="JSON output file path"),
    smoke_test: str = typer.Option("", "--smoke-test", help="Command to run as smoke test"),
    allow_gpu_downgrade: bool = typer.Option(True, "--allow-gpu-downgrade", help="Allow GPU to CPU downgrade"),
):
    """Case 3: Downgrade scenario - Current resources don't fully meet requirements, agent decides downgrade is acceptable."""
    
    typer.echo("=== Case Study 3: Downgrade Scenario ===")
    
    # Analyze repository complexity
    if complexity:
        try:
            complexity_tier = ComplexityTier(complexity)
            typer.echo(f"Using override complexity: {complexity}")
        except ValueError:
            typer.echo(f"Invalid complexity tier: {complexity}")
            raise typer.Exit(1)
    else:
        typer.echo(f"Analyzing repository complexity for: {repo_path}")
        complexity_tier = analyze_repo_complexity(repo_path)
        typer.echo(f"Detected complexity: {complexity_tier.value}")
    
    # Map to original resource requirements
    original_req = map_complexity_to_request(complexity_tier)
    original_duration = get_default_duration_hours(complexity_tier)
    
    typer.echo(f"Original requirements: {original_req.vcpus} vCPUs, {original_req.ram_gb} GB RAM, {original_req.gpus} GPUs")
    typer.echo(f"Original duration: {original_duration} hours")
    
    # Configure downgrade policy
    policy = DowngradePolicy(
        allow_gpu_to_cpu=allow_gpu_downgrade,
        require_pass_smoketest=bool(smoke_test)
    )
    
    # Try downgrade
    typer.echo("Attempting resource downgrade...")
    downgraded_req, downgrade_applied = try_downgrade(original_req, policy, complexity_tier)
    
    if downgrade_applied:
        typer.echo("✅ Downgrade applied successfully")
        
        # Validate downgrade follows policy
        if not validate_downgrade_policy(original_req, downgraded_req, policy):
            typer.echo("❌ Downgrade violates policy constraints")
            raise typer.Exit(1)
        
        # Run smoke test if required
        smoke_test_result = None
        if policy.require_pass_smoketest and smoke_test:
            typer.echo("Running smoke test to validate downgrade...")
            success, output = run_smoke_test(smoke_test)
            
            smoke_test_result = {
                "ran": True,
                "passed": success,
                "command": smoke_test,
                "output": output
            }
            
            if not success:
                typer.echo("❌ Smoke test failed, downgrade not acceptable")
                raise typer.Exit(1)
        
        # Calculate adjusted duration
        adjusted_duration = calculate_duration_increase(original_duration, policy)
        typer.echo(f"Adjusted duration: {adjusted_duration} hours")
        
        # Create reservation with downgraded resources
        start_time = datetime.now(timezone.utc) + timedelta(minutes=2)
        end_time = start_time + timedelta(hours=adjusted_duration)
        
        plan = ReservationPlan(
            zone="current",
            start=start_time,
            end=end_time,
            flavor="auto",
            count=1
        )
        
        # Create the actual reservation
        typer.echo("Creating Blazar reservation with downgraded resources...")
        lease = create_reservation(plan, downgraded_req, f"envboot-downgrade-{complexity_tier.value}")
        
        # Calculate SU estimates
        host_caps = {"vcpus": 48, "gpus": 4}
        su_per_hour = estimate_su_per_hour(downgraded_req, host_caps)
        su_total = su_per_hour * adjusted_duration
        
        # Create result
        result = CaseStudyResult(
            case="downgrade_scenario",
            inputs={
                "repo_path": repo_path,
                "complexity_tier": complexity_tier.value,
                "original_request": {
                    "vcpus": original_req.vcpus,
                    "ram_gb": original_req.ram_gb,
                    "gpus": original_req.gpus,
                    "bare_metal": original_req.bare_metal
                },
                "downgraded_request": {
                    "vcpus": downgraded_req.vcpus,
                    "ram_gb": downgraded_req.ram_gb,
                    "gpus": downgraded_req.gpus,
                    "bare_metal": downgraded_req.bare_metal
                },
                "original_duration_hours": original_duration,
                "adjusted_duration_hours": adjusted_duration,
                "policy": {
                    "allow_gpu_to_cpu": policy.allow_gpu_to_cpu,
                    "max_vcpu_reduction_ratio": policy.max_vcpu_reduction_ratio,
                    "max_ram_reduction_ratio": policy.max_ram_reduction_ratio,
                    "max_duration_increase_ratio": policy.max_duration_increase_ratio,
                    "require_pass_smoketest": policy.require_pass_smoketest
                }
            },
            decisions=[{"type": "downgrade", "applied": True}],
            reservation=plan,
            su_estimate_per_hour=su_per_hour,
            su_estimate_total=su_total,
            slo={"start_by": start_time.isoformat(), "met": True},
            smoke_test=smoke_test_result,
            complexity_tier=complexity_tier
        )
        
        # Output results
        typer.echo("\n=== Results ===")
        typer.echo(f"Reservation created: {plan.lease_id}")
        typer.echo(f"Zone: {plan.zone}")
        typer.echo(f"Start: {plan.start}")
        typer.echo(f"End: {plan.end}")
        typer.echo(f"Flavor: {plan.flavor}")
        typer.echo(f"SU cost: {su_total:.4f}")
        typer.echo(f"Downgrade savings: {estimate_su_per_hour(original_req, host_caps) * original_duration - su_total:.4f} SU")
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(result.__dict__, f, indent=2, default=str)
            typer.echo(f"Results saved to: {output_file}")
    else:
        typer.echo("No downgrade applied, proceeding with original requirements")
        # Fall back to base case logic
        case_base(repo_path, complexity, key_name, output_file)

@app.command("cases-complexity")
def case_complexity(
    repo_path: str = typer.Argument(".", help="Path to repository to analyze"),
    complexity: str = typer.Option(None, "--complexity", help="Override complexity tier"),
    key_name: str = typer.Option("Chris", help="Nova keypair name to inject"),
    output_file: str = typer.Option(None, "--output", help="JSON output file path"),
    duration_override: float = typer.Option(None, "--duration", help="Override reservation duration in hours"),
):
    """Case 4: Repo complexity vs. resource reservation - Match repository complexity to resource choice."""
    
    typer.echo("=== Case Study 4: Repository Complexity Analysis ===")
    
    # Analyze repository complexity
    if complexity:
        try:
            complexity_tier = ComplexityTier(complexity)
            typer.echo(f"Using override complexity: {complexity}")
        except ValueError:
            typer.echo(f"Invalid complexity tier: {complexity}")
            raise typer.Exit(1)
    else:
        typer.echo(f"Analyzing repository complexity for: {repo_path}")
        complexity_tier = analyze_repo_complexity(repo_path)
        typer.echo(f"Detected complexity: {complexity_tier.value}")
    
    # Map to resource requirements
    req = map_complexity_to_request(complexity_tier)
    duration_hours = duration_override or get_default_duration_hours(complexity_tier)
    
    typer.echo(f"Complexity tier: {complexity_tier.value}")
    typer.echo(f"Resource requirements: {req.vcpus} vCPUs, {req.ram_gb} GB RAM, {req.gpus} GPUs")
    typer.echo(f"Reservation duration: {duration_hours} hours")
    typer.echo(f"Resource type: {'Bare metal' if req.bare_metal else 'KVM'}")
    
    # Create reservation
    start_time = datetime.now(timezone.utc) + timedelta(minutes=2)
    end_time = start_time + timedelta(hours=duration_hours)
    
    plan = ReservationPlan(
        zone="current",
        start=start_time,
        end=end_time,
        flavor="auto",
        count=1
    )
    
    # Create the actual reservation
    typer.echo("Creating Blazar reservation...")
    lease = create_reservation(plan, req, f"envboot-complexity-{complexity_tier.value}")
    
    # Calculate SU estimates
    host_caps = {"vcpus": 48, "gpus": 4}
    su_per_hour = estimate_su_per_hour(req, host_caps)
    su_total = su_per_hour * duration_hours
    
    # Create result
    result = CaseStudyResult(
        case="repo_complexity_mapping",
        inputs={
            "repo_path": repo_path,
            "complexity_tier": complexity_tier.value,
            "resource_request": {
                "vcpus": req.vcpus,
                "ram_gb": req.ram_gb,
                "gpus": req.gpus,
                "bare_metal": req.bare_metal
            },
            "duration_hours": duration_hours,
            "duration_override": duration_override
        },
        decisions=[],
        reservation=plan,
        su_estimate_per_hour=su_per_hour,
        su_estimate_total=su_total,
        slo={"start_by": start_time.isoformat(), "met": True},
        complexity_tier=complexity_tier
    )
    
    # Output results
    typer.echo("\n=== Results ===")
    typer.echo(f"Reservation created: {plan.lease_id}")
    typer.echo(f"Zone: {plan.zone}")
    typer.echo(f"Start: {plan.start}")
    typer.echo(f"End: {plan.end}")
    typer.echo(f"Flavor: {plan.flavor}")
    typer.echo(f"SU cost: {su_total:.4f}")
    typer.echo(f"Complexity-based resource mapping: ✅")
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result.__dict__, f, indent=2, default=str)
        typer.echo(f"Results saved to: {output_file}")


def main():
    app()
