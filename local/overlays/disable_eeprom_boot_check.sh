#!/bin/bash
#https://docs.nvidia.com/jetson/archives/r35.4.1/DeveloperGuide/text/HR/JetsonModuleAdaptationAndBringUp/JetsonOrinNxNanoSeries.html#eeprom-modifications
set -o pipefail
#set -e

#set -o xtrace

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
source ${SCRIPT_DIR}/lib/arg_parser.sh

init_variables $@

L4T_dir="${L4T_rootfs_path%/}/.."
L4T_ver=${jetpack_version}

dts_file="${L4T_dir}/bootloader/t186ref/BCT/tegra234-mb2-bct-misc-p3767-0000.dts"
# test version
echo $target_device | grep -q "orin"
if [[ $? != 0 ]]; then
    echo "Not supported device $target_device"
    exit 1
fi


[ ! -f $dts_file ] && echo "file $dts_file missing!" && exit 2

sed -i 's/cvm_eeprom_read_size = <0x100>/cvm_eeprom_read_size = <0x0>/g' ${dts_file}

grep -q "cvm_eeprom_read_size = <0x0>" ${dts_file} && echo "Ready! eeprom reading disabled for boot!"
