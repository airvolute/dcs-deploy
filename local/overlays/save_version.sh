#!/bin/bash

# This script creates a version file for the given generated flash configuration
L4T_rootfs_path=$1
target_device=$2
jetpack_version=$3
hwrev=$4
board_expansion=$5
storage=$6
rootfs_type=$7

# Get Git details (assuming this script is in a Git repository)
git_commit=$(git rev-parse HEAD 2>/dev/null || echo "N/A")
git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")

# Get current date
generated_date=$(date '+%Y-%m-%d %H:%M:%S')

# Create JSON file
json_output="{
    \"L4T_rootfs_path\": \"$L4T_rootfs_path\",
    \"target_device\": \"$target_device\",
    \"jetpack_version\": \"$jetpack_version\",
    \"hwrev\": \"$hwrev\",
    \"board_expansion\": \"$board_expansion\",
    \"storage\": \"$storage\",
    \"rootfs_type\": \"$rootfs_type\",
    \"git_commit\": \"$git_commit\",
    \"git_branch\": \"$git_branch\",
    \"generated_date\": \"$generated_date\"
}"

# Save to a JSON file
output_file="dcs_deploy.json"
echo "$json_output" > "/tmp/$output_file"

# Save it to the L4T rootfs path
sudo cp "/tmp/$output_file" "$L4T_rootfs_path/home/dcs_user/.dcs_logs/$output_file"

# Print success message
echo "Version information saved to $output_file"
