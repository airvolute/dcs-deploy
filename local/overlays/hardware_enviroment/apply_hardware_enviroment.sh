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
target_device=$2
jetpack_version=$3
hwrev=$4
storage=$5
rootfs_type=$6

echo "Rootfs Path: $L4T_rootfs_path"
echo "Target Device: $target_device"
echo "Jetpack Version: $jetpack_version"
echo "HW Revision: $hwrev"
echo "Storage: $storage"
echo "Rootfs Type: $rootfs_type"

script_path=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
echo "script_path: $script_path"

resources_path=$script_path/resources
echo "resouce path: $resources_path"

# Setup systemd first boot
service_destination=${L4T_rootfs_path}/etc/systemd/system
hardware_service_destination=${L4T_rootfs_path}/etc/systemd/system

sudo mkdir -p $hardware_service_destination
# Bin destination
bin_destination=${L4T_rootfs_path}/usr/local/bin
# uhubctl destination
uhubctl_destination=${L4T_rootfs_path}/home/dcs_user
# Handling service
sudo cp ${resources_path}/handle_hardware_services.service ${service_destination}/
sudo cp ${resources_path}/handle_hardware_services.sh ${bin_destination}/
sudo chmod +x ${bin_destination}/handle_hardware_services.sh

# Dummy example service*******************************************************
sudo cp ${resources_path}/dummy_hw/dummy_hw.service ${hardware_service_destination}/
sudo cp ${resources_path}/dummy_hw/dummy_hw.sh ${bin_destination}/
sudo chmod +x ${bin_destination}/dummy_hw.sh
#*****************************************************************************


sudo ln -sf /etc/systemd/system/handle_hardware_services.service ${service_destination}/multi-user.target.wants/handle_hardware_services.service