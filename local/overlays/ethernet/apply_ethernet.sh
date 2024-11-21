#!/bin/bash
# stop when any error occures
set -e 

help() {
    echo "Appply scripts needs one mandatory parameter - L4T_rootfs_path!"
    echo "optional parameter - resources_path"
}

if [ -z $1 ]; then
    help
    exit 1
fi

L4T_rootfs_path=$1

script_path=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
echo "script_path: $script_path"

resources_path=${2:-$script_path/resources}
echo "resouce path: $resources_path"

# # create first boot file
# first_boot_file_path=${L4T_rootfs_path}/etc/first_boot
# sudo touch first_boot_file_path

# Setup systemd first boot
service_destination=${L4T_rootfs_path}/etc/systemd/system
# Bin destination
bin_destination=${L4T_rootfs_path}/usr/local/bin
# uhubctl destination
uhubctl_destination=${L4T_rootfs_path}/home/dcs_user

# FIRST_BOOT service
sudo cp ${resources_path}/ethernet_switch_control.service ${service_destination}/
sudo cp ${resources_path}/ethernet_switch_control.sh ${bin_destination}/
sudo chmod +x ${bin_destination}/ethernet_switch_control.sh

sudo ln -sf /etc/systemd/system/ethernet_switch_control.service ${service_destination}/multi-user.target.wants/ethernet_switch_control.service
