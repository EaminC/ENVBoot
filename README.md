# ENVBoot
# ENVBoot
conda create -n envboot python=3.10
conda activate envboot

pip install python-openstackclient
pip install git+https://github.com/chameleoncloud/python-blazarclient@chameleoncloud/2023.1


#passcode provided from Chameleon Authentication Portal
#https://chameleoncloud.readthedocs.io/en/latest/technical/cli/authentication.html#:~:text=password%20via%20the-,Chameleon%20Authentication%20Portal,-.%20The%20password%20you

source CHI-251467-openrc.sh

#reserve
openstack reservation lease create \
  --reservation min=1,max=1,resource_type=vir:host,resource_properties='["=", "$node_type", "compute_skylake"]' \
  --start-date "2025-07-26 01:27" \ UTC time
  --end-date "2025-07-26 18:00" \
  my-first-lease


#instance
PUBLIC_NETWORK_ID=$(openstack network show public -c id -f value)
openstack reservation lease create --reservation resource_type=virtual:floatingip,network_id=${PUBLIC_NETWORK_ID},amount=1 --start-date "2025-07-26 03:14" --end-date "2025-07-26 03:15" my-first-fip-lease
openstack server create \
--image CC-Ubuntu20.04-20230224 \
--flavor baremetal \
--key-name EnvGym \
--nic net-id=a772a899-ff3d-420b-8b31-1c485092481a \
--hint reservation=71c0c7e8-775f-449b-90e0-bf97d638c128 \
my-instance



openstack floating ip create public --description "testing"

openstack server add floating ip <server-id> <floating-ip>

eg
openstack server add floating ip 709a3f17-7730-45da-9c17-c9a63c3c1b44 129.114.108.114
