#!/bin/bash
# stop when any error occures
set -e 

# lib path
SCRIPT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
LIB_PATH=$SCRIPT_PATH/../../../../lib

# Include the arg_parser.sh script
source $LIB_PATH/arg_parser.sh

init_variables "$1" "$2" "$3" "$4" "$5" "$6" "$7"

sed -i 's/< PM_CONFIG DEFAULT=2 >/ < PM_CONFIG DEFAULT=0 >/g' "$L4T_rootfs_path/etc/nvpmodel/nvpmodel_p3767_0003.conf"

exit 0