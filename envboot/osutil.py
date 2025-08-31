# envboot/osutil.py
import os
from dotenv import load_dotenv
from openstack import connection
from keystoneauth1 import session as ks
from keystoneauth1.identity.v3 import Password, OidcPassword
from blazarclient import client as blazar_client

def _auth_from_env():
    auth_url = os.environ["OS_AUTH_URL"]
    username = os.environ["OS_USERNAME"]
    password = os.environ["OS_PASSWORD"]

    project_id = os.environ.get("OS_PROJECT_ID")
    project_name = os.environ.get("OS_PROJECT_NAME")

    if os.environ.get("OS_AUTH_TYPE", "") == "v3oidcpassword":
        client_secret = os.environ.get("OS_CLIENT_SECRET")
        if client_secret in (None, "", "none", "None"):
            client_secret = None  # public client

        scope = os.environ.get("OS_OIDC_SCOPE", "openid profile email")

        return OidcPassword(
            auth_url=auth_url,
            identity_provider=os.environ["OS_IDENTITY_PROVIDER"],   # "chameleon"
            protocol=os.environ["OS_PROTOCOL"],                     # "openid"
            discovery_endpoint=os.environ["OS_DISCOVERY_ENDPOINT"],
            client_id=os.environ["OS_CLIENT_ID"],
            client_secret=os.environ.get("OS_CLIENT_SECRET", "none"),
            access_token_type=os.environ.get("OS_ACCESS_TOKEN_TYPE", "access_token"),
            username=username,
            password=password,
            project_id=project_id,
            project_name=project_name,
            scope=scope,   
        )
    else:
        # Legacy password flow (non-OIDC)
        return Password(
            auth_url=auth_url,
            username=username,
            password=password,
            project_id=project_id,
            project_name=project_name,
            user_domain_name=os.environ.get("OS_USER_DOMAIN_NAME", "Default"),
            project_domain_name=os.environ.get("OS_PROJECT_DOMAIN_NAME", "Default"),
        )

def conn():
    load_dotenv(override=False)
    auth = _auth_from_env()
    sess = ks.Session(auth=auth)
    return connection.Connection(session=sess, region_name=os.environ.get("OS_REGION_NAME"), identity_interface="public")

def blz():
    """Return an authenticated Blazar client using the same Keystone session."""
    load_dotenv(override=False)
    auth = _auth_from_env()
    sess = ks.Session(auth=auth)
    return blazar_client.Client(1, session=sess)

def blazar_list_hosts():
    """List Blazar hosts with capacity information."""
    try:
        blazar = blz()
        # Try the correct Blazar host API
        hosts = blazar.os_host.list()
        return hosts
    except AttributeError:
        # Fallback: try to get host info from leases/reservations
        try:
            leases = blazar.lease.list()
            # Extract host info from active leases
            hosts = []
            for lease in leases:
                if lease.get('status') in ['ACTIVE', 'STARTED']:
                    for reservation in lease.get('reservations', []):
                        if reservation.get('resource_type') == 'physical:host':
                            host_id = reservation.get('resource_id')
                            if host_id:
                                hosts.append({
                                    'id': host_id,
                                    'vcpus': 48,  # Default assumption
                                    'gpus': 4,    # Default assumption
                                    'zone': 'current'  # Default zone
                                })
            return hosts
        except Exception as e:
            print(f"Warning: Could not list hosts via fallback method: {e}")
            return []

def blazar_list_leases():
    """List Blazar leases with proper error handling."""
    try:
        blazar = blz()
        return blazar.lease.list()
    except Exception as e:
        print(f"Warning: Could not list leases: {e}")
        return []
