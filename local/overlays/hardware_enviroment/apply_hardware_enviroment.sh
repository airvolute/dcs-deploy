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
# hardware_service_destination=${L4T_rootfs_path}/etc/systemd/system

# sudo mkdir -p $hardware_service_destination
# Bin destination
bin_destination=${L4T_rootfs_path}/usr/local/bin
# uhubctl destination
uhubctl_destination=${L4T_rootfs_path}/home/dcs_user

# JSON file setup

json_file="${L4T_rootfs_path}/home/dcs_user/.dcs_deploy_data.json"

# Ensure the directory structure exists
sudo mkdir -p "$(dirname "$json_file")"

# Initialize or validate JSON file
initialize_json_file() {
    if [ ! -f "$json_file" ]; then
        echo '{"services":[],"binaries":[]}' | sudo tee "$json_file" > /dev/null
        echo "Initialized JSON file at $json_file"
    else
        # Validate existing file structure
        echo "Validating existing JSON file: $json_file"
        valid_structure=$(sudo jq 'has("services") and has("binaries")' "$json_file" || echo "false")
        if [ "$valid_structure" != "true" ]; then
            echo "Invalid JSON structure. Reinitializing file."
            echo '{"services":[],"binaries":[]}' | sudo tee "$json_file" > /dev/null
        fi
    fi
}

# Add a service to JSON
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

# Initialize the JSON file
initialize_json_file
# Copy services and update JSON
sudo cp ${resources_path}/handle_hardware_services.service ${service_destination}/
add_service_to_json "/etc/systemd/system/handle_hardware_services.service"

sudo cp ${resources_path}/handle_hardware_services.sh ${bin_destination}/
sudo chmod +x ${bin_destination}/handle_hardware_services.sh
add_binary_to_json "/usr/local/bin/handle_hardware_services.sh"

# Dummy example service, add services like this********************************
sudo cp ${resources_path}/dummy_hw/dummy_hw.service ${service_destination}/
add_service_to_json "/etc/systemd/system/dummy_hw.service"

sudo cp ${resources_path}/dummy_hw/dummy_hw.sh ${bin_destination}/
sudo chmod +x ${bin_destination}/dummy_hw.sh
add_binary_to_json "/usr/local/bin/dummy_hw.sh"
#******************************************************************************


sudo ln -sf /etc/systemd/system/handle_hardware_services.service ${service_destination}/multi-user.target.wants/handle_hardware_services.service