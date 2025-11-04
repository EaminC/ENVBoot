#!/usr/bin/env python3
"""
api-6.py: Launch servers bound to a Blazar lease and return SSH connection info.

Callable CLI tool for EnvAgent-plus framework.
Returns structured JSON to stdout with schema: {ok, data, error, metrics, version}
Exit codes:
  0 = ok true
  1 = invalid args or local error
  2 = backend error (OpenStack API) or timeout
"""

import argparse
import json
import sys
import time
from typing import Optional, List, Dict, Tuple

VERSION = "1.0.0"

def _extract_http_status(err: Exception) -> Optional[int]:
    """Best-effort extraction of HTTP status code from exception."""
    msg = str(err) or ""
    for code in (400, 401, 403, 404, 409, 500, 503):
        if f" {code} " in f" {msg} " or f"({code})" in msg or f"{code}:" in msg:
            return code
    for attr in ("http_status", "status_code", "code"):
        val = getattr(err, attr, None)
        if isinstance(val, int):
            return val
    return None

def _guess_ssh_user(image_name: str) -> str:
    """Guess SSH user from image name."""
    name_lower = image_name.lower()
    if "ubuntu" in name_lower:
        return "ubuntu"
    elif "centos" in name_lower:
        return "centos"
    elif "rocky" in name_lower or "alma" in name_lower:
        return "cloud-user"
    elif "debian" in name_lower:
        return "debian"
    elif "fedora" in name_lower:
        return "fedora"
    return "unknown"

def _resolve_image(conn, image: str) -> Optional[str]:
    """Resolve image name or ID to ID."""
    try:
        img = conn.compute.find_image(image)
        return img.id if img else None
    except Exception:
        return None

def _resolve_flavor(conn, flavor: str) -> Optional[str]:
    """Resolve flavor name or ID to ID."""
    try:
        flv = conn.compute.find_flavor(flavor)
        return flv.id if flv else None
    except Exception:
        return None

def _resolve_network(conn, network: str) -> Optional[str]:
    """Resolve network name or ID to ID."""
    try:
        net = conn.network.find_network(network)
        return net.id if net else None
    except Exception:
        return None

def _get_lease_info(lease_id: str) -> Tuple[Optional[dict], Optional[str]]:
    """Fetch lease info from Blazar and return (lease_dict, error)."""
    try:
        from envboot.osutil import blz
        lease = blz().lease.get(lease_id)
        # Normalize to dict if it's a resource object
        if hasattr(lease, 'to_dict'):
            lease = lease.to_dict()
        return lease, None
    except Exception as e:
        return None, str(e)

def _lease_type_and_nodes(lease: dict) -> Tuple[Optional[str], List[str]]:
    """Infer lease resource_type and any reserved node IDs from reservations."""
    rtype = None
    nodes: List[str] = []
    try:
        reservations = lease.get('reservations') or []
        for r in reservations:
            rt = r.get('resource_type') or r.get('resource_type'.replace('-', '_'))
            if not rtype:
                rtype = rt
            # Try common fields that may carry the reserved resource ID
            rid = r.get('resource_id') or r.get('resource') or r.get('id')
            if rt == 'physical:host' and rid:
                nodes.append(str(rid))
    except Exception:
        pass
    return rtype, nodes


def _lease_reservation_ids(lease: dict) -> List[str]:
    """Return list of reservation IDs from the lease (reservations[].id)."""
    rids: List[str] = []
    try:
        for r in lease.get('reservations') or []:
            rid = r.get('id')
            if rid:
                rids.append(str(rid))
    except Exception:
        pass
    return rids


def _boot_servers_real(
    conn,
    reservation_id: str,
    image_id: str,
    flavor_id: str,
    network_id: str,
    key_name: str,
    sec_groups: List[str],
    count: int,
    name_prefix: str,
    userdata: Optional[str],
) -> Tuple[List[Dict], Optional[str]]:
    """Boot servers with Blazar lease binding. Returns (server_list, error_message)."""
    servers: List[Dict] = []
    try:
        # Build scheduler hints to bind to Blazar lease
        # Standard Blazar integration uses: {"reservation": "<lease_id>"}
        # Try both common keys used by Nova-Blazar integration
        hints = {"reservation": reservation_id, "blazar:reservation": reservation_id}

        for i in range(count):
            server_name = f"{name_prefix}-{i+1}" if count > 1 else name_prefix
            try:
                # Build server creation parameters
                server_params = {
                    "name": server_name,
                    "image_id": image_id,
                    "flavor_id": flavor_id,
                    "networks": [{"uuid": network_id}],
                    "key_name": key_name,
                    "security_groups": [{"name": sg} for sg in sec_groups],
                    "scheduler_hints": hints,
                }
                # Only add userdata if it's provided
                if userdata:
                    server_params["user_data"] = userdata

                server = conn.compute.create_server(**server_params)
                servers.append({
                    "server_id": server.id,
                    "name": server.name,
                    "status": getattr(server, "status", None),
                })
            except Exception as e:
                return servers, f"Failed to boot server {i+1}: {str(e)}"

        return servers, None
    except Exception as e:
        return servers, str(e)

def _wait_for_servers(conn, servers: List[Dict], timeout: int, interval: int) -> Tuple[List[Dict], int]:
    """Poll servers until ACTIVE or timeout. Returns (updated_servers, poll_count)."""
    deadline = time.time() + timeout
    poll_count = 0
    while time.time() < deadline:
        all_active = True
        for srv in servers:
            try:
                server = conn.compute.get_server(srv["server_id"])
                srv["status"] = server.status
                if server.status not in ("ACTIVE", "ERROR"):
                    all_active = False
            except Exception:
                srv["status"] = "ERROR"
        poll_count += 1
        if all_active:
            break
        time.sleep(interval)
    return servers, poll_count

def _get_server_ips(conn, server_id: str, network_name: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Get fixed and floating IPs for a server. Returns (fixed_ip, floating_ip)."""
    try:
        server = conn.compute.get_server(server_id)
        fixed_ip = None
        floating_ip = None
        
        # Extract IPs from addresses
        addresses = server.addresses or {}
        for net, addrs in addresses.items():
            for addr in addrs:
                if addr.get("OS-EXT-IPS:type") == "fixed" and not fixed_ip:
                    fixed_ip = addr.get("addr")
                elif addr.get("OS-EXT-IPS:type") == "floating":
                    floating_ip = addr.get("addr")
        
        return fixed_ip, floating_ip
    except Exception:
        return None, None

def _allocate_floating_ip(conn, server_id: str) -> Optional[str]:
    """Allocate and associate a floating IP. Returns floating IP or None."""
    try:
        # Find or create floating IP
        floating_ip = conn.network.create_ip(floating_network_id=None)  # Use default external network
        # Associate with server
        conn.compute.add_floating_ip_to_server(server_id, floating_ip.floating_ip_address)
        return floating_ip.floating_ip_address
    except Exception:
        # Fallback: try to find available floating IP pool
        try:
            floating_ip = conn.network.create_ip()
            conn.compute.add_floating_ip_to_server(server_id, floating_ip.floating_ip_address)
            return floating_ip.floating_ip_address
        except Exception:
            return None

def _baremetal_activate_and_ips(
    conn,
    node_id: str,
    image_id: str,
    wait: int,
    interval: int,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Provision a bare metal node to ACTIVE with image and return (status, fixed_ip, floating_ip).
    Returns status string (ACTIVE|ERROR|timeout), fixed_ip, floating_ip (None if not assigned).
    """
    try:
        # Ensure instance_info has image_source
        try:
            conn.baremetal.update_node(node_id, instance_info={"image_source": image_id})
        except Exception:
            # best-effort; some deployments accept image via deploy step only
            pass

        # Trigger provision to active
        conn.baremetal.set_node_provision_state(node_id, target='active')

        # Wait for ACTIVE
        deadline = time.time() + max(0, int(wait))
        poll = 0
        status = None
        while True:
            node = conn.baremetal.get_node(node_id)
            status = getattr(node, 'provision_state', None)
            if wait <= 0 or status == 'active' or status == 'deployed':
                break
            if time.time() >= deadline:
                return 'timeout', None, None
            time.sleep(max(1, int(interval)))
            poll += 1

        # Discover fixed IP via MAC address of baremetal ports -> matching Neutron port
        fixed_ip = None
        floating_ip = None
        try:
            bm_ports = list(conn.baremetal.ports(node=node_id))
        except Exception:
            bm_ports = []
        for bmp in bm_ports:
            mac = getattr(bmp, 'address', None)
            if not mac:
                continue
            try:
                # Find neutron ports matching MAC
                for p in conn.network.ports(mac_address=mac):
                    fips = getattr(p, 'fixed_ips', []) or []
                    for f in fips:
                        ip = f.get('ip_address')
                        if ip:
                            fixed_ip = ip
                            break
                    if fixed_ip:
                        break
            except Exception:
                continue
            if fixed_ip:
                break

        # We don't auto-assign floating IP here; higher-level flow can do that by port if needed
        # Return status mapping
        final_status = 'ACTIVE' if (status in ('active', 'deployed')) else (status or 'UNKNOWN')
        return final_status, fixed_ip, floating_ip
    except Exception:
        return 'ERROR', None, None

def launch_servers(
    reservation_id: str,
    image: str,
    flavor: str,
    network: str,
    key_name: str,
    sec_groups: str,
    count: int,
    name_prefix: str,
    userdata_path: Optional[str],
    assign_floating_ip: bool,
    wait: int,
    interval: int,
    dry_run: bool,
) -> Tuple[dict, int]:
    """Launch servers and return (result_json, exit_code)."""
    t0 = time.time()
    
    try:
        if not reservation_id or not image or not flavor or not network or not key_name:
            raise ValueError("reservation_id, image, flavor, network, and key_name are required")
        
        sec_groups_list = [sg.strip() for sg in sec_groups.split(",") if sg.strip()] or ["default"]
        
        # Read userdata if provided
        userdata = None
        if userdata_path:
            try:
                with open(userdata_path, "r") as f:
                    userdata = f.read()
            except Exception as e:
                raise ValueError(f"Failed to read userdata file: {str(e)}")
        
        # Dry-run simulation
        if dry_run:
            elapsed_ms = int((time.time() - t0) * 1000)
            servers = []
            for i in range(count):
                server_name = f"{name_prefix}-{i+1}" if count > 1 else name_prefix
                servers.append({
                    "server_id": f"fake-{i+1}",
                    "name": server_name,
                    "status": "simulated",
                    "fixed_ip": f"10.0.0.{100+i}",
                    "floating_ip": f"203.0.113.{10+i}" if assign_floating_ip else None,
                    "ssh_user": _guess_ssh_user(image),
                    "key_name": key_name,
                })
            return {
                "ok": True,
                "data": {
                    "reservation_id": reservation_id,
                    "servers": servers,
                    "dry_run": True,
                },
                "error": None,
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION,
            }, 0
        
        # Real mode: check lease type first
        lease, lerr = _get_lease_info(reservation_id)
        if lerr or not lease:
            raise ValueError(f"Failed to get lease info: {lerr or 'unknown error'}")

        lease_type, bm_nodes = _lease_type_and_nodes(lease)
        reservation_ids = _lease_reservation_ids(lease)

        from envboot.osutil import conn as get_conn
        conn = get_conn()
        
        # Branch by lease type
        if lease_type == 'physical:host' and force_ironic_flag:
            # Bare metal path (forced)
            if not args_bm_image:
                raise ValueError("--bm-image is required for physical:host lease")
            bm_image_id = _resolve_image(conn, args_bm_image)
            if not bm_image_id:
                raise ValueError(f"Bare metal image not found: {args_bm_image}")

            servers = []
            # Limit to requested count if provided and nodes available
            target_nodes = bm_nodes[:max(1, int(count))] if bm_nodes else []
            if not target_nodes:
                elapsed_ms = int((time.time() - t0) * 1000)
                return {
                    "ok": False,
                    "data": {
                        "reservation_id": reservation_id,
                        "servers": [],
                        "dry_run": False,
                    },
                    "error": {"type": "NotFound", "message": "No reserved nodes found in lease"},
                    "metrics": {"elapsed_ms": elapsed_ms},
                    "version": VERSION,
                }, 2

            for idx, node_id in enumerate(target_nodes, start=1):
                status, fixed_ip, floating_ip = _baremetal_activate_and_ips(
                    conn, node_id, bm_image_id, wait, interval
                )
                server_entry = {
                    "server_id": node_id,
                    "name": f"{name_prefix}-{idx}",
                    "status": status,
                    "fixed_ip": fixed_ip,
                    "floating_ip": None,  # set below if assigned
                    "ssh_user": bm_ssh_user,
                    "key_name": key_name,
                }
                # Assign floating IP if requested and we have a fixed IP
                if assign_floating_ip and fixed_ip:
                    try:
                        # Find the neutron port for this IP to attach FIP
                        port_for_ip = None
                        for p in conn.network.ports():
                            fips = getattr(p, 'fixed_ips', []) or []
                            if any(fi.get('ip_address') == fixed_ip for fi in fips):
                                port_for_ip = p
                                break
                        if port_for_ip:
                            f = conn.network.create_ip(port_id=port_for_ip.id)
                            server_entry["floating_ip"] = getattr(f, 'floating_ip_address', None)
                    except Exception:
                        # best-effort
                        pass
                servers.append(server_entry)

            # Evaluate outcome
            any_timeout = any(s.get("status") == "timeout" for s in servers)
            any_error = any(s.get("status") == "ERROR" for s in servers)
            elapsed_ms = int((time.time() - t0) * 1000)
            data = {
                "reservation_id": reservation_id,
                "servers": servers,
                "dry_run": False,
            }
            if wait > 0:
                data["wait"] = {
                    "timeout_seconds": wait,
                    "interval_seconds": interval,
                    "poll_count": None,
                }
            if any_timeout or any_error:
                return {
                    "ok": False,
                    "data": data,
                    "error": {"type": "Timeout" if any_timeout else "ServerError", "message": "One or more bare metal nodes failed or timed out"},
                    "metrics": {"elapsed_ms": elapsed_ms},
                    "version": VERSION,
                }, 2

            return {
                "ok": True,
                "data": data,
                "error": None,
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION,
            }, 0
        else:
            # Virtual instance path (Nova) as before
            # Resolve image, flavor, network
            image_id = _resolve_image(conn, image)
            if not image_id:
                raise ValueError(f"Image not found: {image}")
            
            flavor_id = _resolve_flavor(conn, flavor)
            if not flavor_id:
                raise ValueError(f"Flavor not found: {flavor}")
            
            network_id = _resolve_network(conn, network)
            if not network_id:
                raise ValueError(f"Network not found: {network}")
            
            # Decide scheduler hint id (use reservation.id for physical:host)
            hint_id = reservation_id
            if lease_type == 'physical:host' and reservation_ids:
                hint_id = reservation_ids[0]

            # Boot servers via Nova
            servers, err = _boot_servers_real(
                conn, hint_id, image_id, flavor_id, network_id,
                key_name, sec_groups_list, count, name_prefix, userdata
            )
        
        if err:
            elapsed_ms = int((time.time() - t0) * 1000)
            fake_exc = Exception(err)
            status = _extract_http_status(fake_exc)
            msg_low = (err or "").lower()
            if "no valid host was found" in msg_low or "no valid host" in msg_low:
                etype = "NoValidHost"
            else:
                etype = {
                    400: "BadRequest",
                    401: "Unauthorized",
                    403: "Forbidden",
                    404: "NotFound",
                    409: "Conflict",
                    500: "ServerError",
                    503: "ServiceUnavailable",
                }.get(status, "BackendError")
            return {
                "ok": False,
                "data": {
                    "reservation_id": reservation_id,
                    "servers": servers,
                    "dry_run": False,
                },
                "error": {"type": etype, "message": err},
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION,
            }, 2
        
        # Wait for ACTIVE if requested
        poll_count = 0
        if wait > 0:
            servers, poll_count = _wait_for_servers(conn, servers, wait, interval)
        
        # Get IPs and assign floating IPs if requested
        ssh_user = _guess_ssh_user(image)
        for srv in servers:
            fixed_ip, floating_ip = _get_server_ips(conn, srv["server_id"])
            srv["fixed_ip"] = fixed_ip
            srv["floating_ip"] = floating_ip
            
            if assign_floating_ip and not floating_ip:
                floating_ip = _allocate_floating_ip(conn, srv["server_id"])
                srv["floating_ip"] = floating_ip
            
            srv["ssh_user"] = ssh_user
            srv["key_name"] = key_name
        
        # Check for timeouts or errors
        any_timeout = any(s.get("status") not in ("ACTIVE", "ERROR", "simulated") for s in servers)
        any_error = any(s.get("status") == "ERROR" for s in servers)
        
        elapsed_ms = int((time.time() - t0) * 1000)
        data = {
            "reservation_id": reservation_id,
            "servers": servers,
            "dry_run": False,
        }
        if wait > 0:
            data["wait"] = {
                "timeout_seconds": wait,
                "interval_seconds": interval,
                "poll_count": poll_count,
            }
        
        if any_timeout or any_error:
            return {
                "ok": False,
                "data": data,
                "error": {"type": "Timeout" if any_timeout else "ServerError", "message": "One or more servers failed or timed out"},
                "metrics": {"elapsed_ms": elapsed_ms},
                "version": VERSION,
            }, 2
        
        return {
            "ok": True,
            "data": data,
            "error": None,
            "metrics": {"elapsed_ms": elapsed_ms},
            "version": VERSION,
        }, 0
        
    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "ok": False,
            "data": None,
            "error": {"type": type(e).__name__, "message": str(e)},
            "metrics": {"elapsed_ms": elapsed_ms},
            "version": VERSION,
        }, 1

def main():
    parser = argparse.ArgumentParser(
        description="API-6: Launch servers bound to a Blazar lease with SSH connection info",
        add_help=False
    )
    parser.add_argument("--reservation-id", required=True, help="Blazar lease/reservation ID")
    parser.add_argument("--image", required=True, help="Image name or ID")
    parser.add_argument("--flavor", required=True, help="Flavor name or ID")
    parser.add_argument("--network", required=True, help="Network name or ID")
    parser.add_argument("--key-name", required=True, help="SSH keypair name")
    parser.add_argument("--sec-groups", default="default", help="Comma-separated security groups (default: default)")
    parser.add_argument("--count", type=int, default=1, help="Number of servers to launch (default: 1)")
    parser.add_argument("--name-prefix", default="envboot", help="Server name prefix (default: envboot)")
    parser.add_argument("--userdata", help="Path to cloud-init user-data file")
    parser.add_argument("--assign-floating-ip", action="store_true", help="Allocate and assign floating IPs")
    parser.add_argument("--wait", type=int, default=0, help="Wait for ACTIVE status (seconds, default: 0)")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval (seconds, default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate launch without side effects")
    # Bare metal specific options
    parser.add_argument("--bm-image", help="Glance image name or ID for bare metal provisioning")
    parser.add_argument("--bm-ssh-user", default="ubuntu", help="SSH user for bare metal image (default: ubuntu)")
    parser.add_argument("--force-ironic", action="store_true", help="Force Ironic provisioning for physical:host leases (default: Nova with reservation hint)")
    
    args = parser.parse_args()
    
    # Thread CLI-only bare metal options via globals captured in launch function via closure variables
    global args_bm_image, bm_ssh_user, force_ironic_flag
    args_bm_image = args.bm_image
    bm_ssh_user = args.bm_ssh_user
    force_ironic_flag = args.force_ironic

    result, exit_code = launch_servers(
        reservation_id=args.reservation_id,
        image=args.image,
        flavor=args.flavor,
        network=args.network,
        key_name=args.key_name,
        sec_groups=args.sec_groups,
        count=args.count,
        name_prefix=args.name_prefix,
        userdata_path=args.userdata,
        assign_floating_ip=args.assign_floating_ip,
        wait=args.wait,
        interval=args.interval,
        dry_run=args.dry_run,
    )
    
    print(json.dumps(result, indent=2))
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
