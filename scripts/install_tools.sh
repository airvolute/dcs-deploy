#/bin/bash
#install requirements

set -xe

install_command() {
    local command=$1
    local install_command=$2
    
    if [ -z ${install_command} ]; then 
        install_command=$command
    fi
    if [ -z $(which $command) ]; then
        sudo apt install ${install_command}
    fi
}


if [ $# == 0 ]; then
    echo "./init.sh <Linux_for_Tegra direcrory>"
    echo "  please specify 'Linux_for_Tegra' directory as first parameter!"
    exit 1
fi

L4T=$(realpath $1)
if [ ! -d $L4T ]; then
    echo "wrong path $L4T"
    exit 2
fi

#check if python3 is installed 

install_command python3
#install python command as python3
install_command python python-is-python3

sudo sed -i 's/python /python3 /g' ${L4T}/tools/l4t_flash_prerequisites.sh

#/home/$USER/.dcs_deploy/flash/$1/Linux_for_Tegra/tools/l4t_flash_prerequisites.sh
${L4T}/tools/l4t_flash_prerequisites.sh



