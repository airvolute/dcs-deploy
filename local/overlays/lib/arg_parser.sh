#!/bin/bash
# arg_parser.sh - Extended Library for the 

init_variables() {
    L4T_rootfs_path=$1
    target_device=$2
    jetpack_version=$3
    hwrev=$4
    board_expansion=$5
    storage=$6
    rootfs_type=$7

    validate_initialization
    validate_L4T_rootfs_path
}

# Function to validate that L4T_rootfs_path exists
validate_L4T_rootfs_path() {
    if [ -z "$L4T_rootfs_path" ]; then
        echo "Error: L4T_rootfs_path is not set."
        exit 1
    fi

    if [ ! -d "$L4T_rootfs_path" ]; then
        echo "Error: L4T_rootfs_path does not exist: $L4T_rootfs_path"
        exit 1
    fi
}

# Function to validate that all initialization variables are set
validate_initialization() {
    if [ -z "$L4T_rootfs_path" ] || [ -z "$target_device" ] || [ -z "$jetpack_version" ] ||
       [ -z "$hwrev" ] || [ -z "$board_expansion" ] || [ -z "$storage" ] || [ -z "$rootfs_type" ]; then
        echo "Error: One or more initialization variables are not set."
        echo "Ensure all variables are provided during initialization:"
        echo "L4T_rootfs_path, target_device, jetpack_version, hwrev, board_expansion, storage, rootfs_type"
        exit 1
    fi
}

# Function to display all variables
print_variables() {
    echo "L4T_rootfs_path: $L4T_rootfs_path"
    echo "target_device: $target_device"
    echo "jetpack_version: $jetpack_version"
    echo "hwrev: $hwrev"
    echo "board_expansion: $board_expansion"
    echo "storage: $storage"
    echo "rootfs_type: $rootfs_type"
}
