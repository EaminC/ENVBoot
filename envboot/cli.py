import os, json
import time
from datetime import datetime, timedelta, timezone
from keystoneauth1 import session as ks
from pathlib import Path
import typer
from .osutil import conn, blz

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


def main():
    app()
