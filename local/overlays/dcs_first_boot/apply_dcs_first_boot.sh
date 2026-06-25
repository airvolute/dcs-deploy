#!/bin/bash
# stop when any error occures
set -o pipefail
set -e 

help() {
    echo "Appply scripts needs one mandatory parameter - L4T_rootfs_path!"
}

add_service_to_json() {
    local service_path=$1
    sudo jq --arg path "$service_path" \
        'if .services | index($path) then . else .services += [$path] end' \
        "$json_file" | sudo tee "$json_file.tmp" > /dev/null
    sudo mv "$json_file.tmp" "$json_file"
    echo "Added service to JSON: $service_path"
}

add_binary_to_json() {
    local binary_path=$1
    sudo jq --arg path "$binary_path" \
        'if .binaries | index($path) then . else .binaries += [$path] end' \
        "$json_file" | sudo tee "$json_file.tmp" > /dev/null
    sudo mv "$json_file.tmp" "$json_file"
    echo "Added binary to JSON: $binary_path"
}

L4T_rootfs_path=$1
target_device=$2
jetpack_version=$3
hwrev=$4
board_expansion=$5
storage=$6
rootfs_type=$7

# Check if L4T_rootfs_path exists and is valid path
if [ ! -d "$L4T_rootfs_path" ]; then
    echo "Error: L4T_rootfs_path '$L4T_rootfs_path' does not exist."
    exit 1
fi

# JSON file setup
json_file="${L4T_rootfs_path}/home/dcs_user/Airvolute/logs/dcs-deploy/dcs_deploy_data.json"

script_path=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
echo "script_path: $script_path"

resources_path="$script_path/resources"
echo "resouce path: $resources_path"
if [ ! -d "$resources_path" ]; then
    echo "Error: resources path '$resources_path' does not exist."
    exit 1
fi
# Create first boot file
first_boot_file_path=${L4T_rootfs_path}/etc/first_boot
sudo touch $first_boot_file_path

# Setup systemd first boot
service_destination=${L4T_rootfs_path}/etc/systemd/system
# Bin destination
bin_destination=${L4T_rootfs_path}/usr/local/bin

# FIRST_BOOT service
sudo cp ${resources_path}/dcs_first_boot.service ${service_destination}/
sudo cp ${resources_path}/dcs_first_boot.sh ${bin_destination}/
sudo chmod +x ${bin_destination}/dcs_first_boot.sh

sudo ln -sf /etc/systemd/system/dcs_first_boot.service ${service_destination}/multi-user.target.wants/dcs_first_boot.service

# Add service to JSON
# Check if JSON file exists if not create it
if [ ! -f "$json_file" ]; then
    echo "JSON file does not exist, creating new one."
    sudo mkdir -p "$(dirname "$json_file")"
    sudo touch "$json_file"
    sudo chmod 666 "$json_file"
    echo "{}" | sudo tee "$json_file" > /dev/null
fi

add_service_to_json "/etc/systemd/system/dcs_first_boot.service"
add_binary_to_json "/usr/local/bin/dcs_first_boot.sh"
