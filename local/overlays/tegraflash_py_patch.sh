#!/bin/bash

set -o pipefail
set -e

# This script creates a version file for the given generated flash configuration
L4T_rootfs_path=$1
target_device=$2
jetpack_version=$3
hwrev=$4
board_expansion=$5
storage=$6
rootfs_type=$7
L4T_dir="$L4T_rootfs_path/.."

if [ $jetpack_version != "512" ]; then
    echo "unspported jetpack version $jetpack_version. Exitting..."
    exit 0
fi
# Path to the target file
TARGET_FILE="${L4T_dir}/bootloader/tegraflash_impl_t234.py"

# Check if the file exists
if [ ! -f "$TARGET_FILE" ]; then
    echo "ERROR: File not found: $TARGET_FILE"
    exit 1
fi

# Make a backup before modification
cp "$TARGET_FILE" "${TARGET_FILE}.bak"
echo "Backup created: ${TARGET_FILE}.bak"

# Perform in-place replacement
sed -i 's/getiterator(\s*'\''file'\''\s*)/iter('"'"'file'"'"')/g' "$TARGET_FILE"

# Confirm modification
if grep -q "iter('file')" "$TARGET_FILE"; then
    echo "Successfully updated 'getiterator' to 'iter' in $TARGET_FILE"
    exit 0
else
    echo "Update failed. Please check manually."
    exit 1
fi
