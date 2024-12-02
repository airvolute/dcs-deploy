#!/bin/bash
# stop when any error occures
set -e 

# This script should not create any files, it should only modify the files in the L4T rootfs
L4T_rootfs_path=$1
target_device=$2
jetpack_version=$3
hwrev=$4
board_expansion=$5
storage=$6
rootfs_type=$7

# Check if path exists
if [ ! -d "$L4T_rootfs_path" ]; then
    echo "Error: L4T rootfs path does not exist"
    exit 1
fi

sed -i 's/ATTR{hctosys}=="1"/ATTR{hctosys}="0"/' $L4T_rootfs_path/usr/lib/udev/rules.d/50-udev-default.rules
echo "sudo hwclock --hctosys" | tee -a $L4T_rootfs_path/etc/systemd/nv.sh > /dev/null

exit 0