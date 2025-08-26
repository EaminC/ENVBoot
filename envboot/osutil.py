# envboot/osutil.py
import os
from dotenv import load_dotenv
from openstack import connection
from openstack.config import OpenStackConfig  
from keystoneauth1 import session as ks
from keystoneauth1.identity.v3 import Password, OidcPassword

from keystoneauth1.identity.v3 import Password, OidcPassword

def _auth_from_env():
    auth_url = os.environ["OS_AUTH_URL"]
    username = os.environ["OS_USERNAME"]
    password = os.environ["OS_PASSWORD"]

    project_id = os.environ.get("OS_PROJECT_ID")
    project_name = os.environ.get("OS_PROJECT_NAME")

    if os.environ.get("OS_AUTH_TYPE", "") == "v3oidcpassword":
        # OIDC (no user_domain_name / project_domain_name here)
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
