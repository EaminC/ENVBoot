#!/usr/bin/env bash
#
# OpenStack OpenRC Template
#
# Download your OpenRC file from your OpenStack dashboard:
#   1. Log in to your OpenStack web interface
#   2. Go to: API Access or Identity → Application Credentials
#   3. Download "OpenStack RC File v3"
#   4. Paste the contents below (replacing this template)
#   5. Source this file: source config/openrc.sh
#
# Example OpenRC structure (REPLACE WITH YOUR ACTUAL VALUES):
#
# export OS_AUTH_URL=https://your-keystone-url:5000/v3
# export OS_PROJECT_ID=your_project_id
# export OS_PROJECT_NAME="your_project_name"
# export OS_USER_DOMAIN_NAME="Default"
# export OS_PROJECT_DOMAIN_ID="default"
# export OS_USERNAME="your_username"
# export OS_PASSWORD="your_password"
# export OS_REGION_NAME="RegionOne"
# export OS_INTERFACE=public
# export OS_IDENTITY_API_VERSION=3
#
# For OIDC-based authentication (e.g., Chameleon):
# export OS_AUTH_TYPE=v3oidcpassword
# export OS_IDENTITY_PROVIDER=chameleon
# export OS_PROTOCOL=openid
# export OS_DISCOVERY_ENDPOINT=https://auth.chameleoncloud.org/auth/realms/chameleon/.well-known/openid-configuration
# export OS_CLIENT_ID=your_client_id
# export OS_CLIENT_SECRET=  # Optional, leave empty for public client
# export OS_ACCESS_TOKEN_TYPE=access_token
# export OS_OIDC_SCOPE="openid profile email"

echo "⚠️  This is a template file. Replace with your actual OpenRC contents."
echo "Download from your OpenStack dashboard: API Access → OpenStack RC File v3"
