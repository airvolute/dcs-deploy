#!/bin/bash
# stop when any error occures
set -e 

# lib path
SCRIPT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
LIB_PATH=$SCRIPT_PATH/../../../../lib

# Include the arg_parser.sh script
source $LIB_PATH/arg_parser.sh

init_variables "$1" "$2" "$3" "$4" "$5" "$6" "$7"

sed -i 's/ATTR{hctosys}=="1"/ATTR{hctosys}="0"/' $L4T_rootfs_path/usr/lib/udev/rules.d/50-udev-default.rules
echo "sudo hwclock --hctosys" | tee -a $L4T_rootfs_path/etc/systemd/nv.sh > /dev/null

exit 0