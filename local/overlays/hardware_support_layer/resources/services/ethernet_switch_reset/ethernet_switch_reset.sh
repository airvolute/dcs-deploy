#!/bin/bash

# This script is used to control the ethernet switch on the board.
# The ethernet switch is connected to the GPIO PCC.03.
# The GPIO PCC.03 is used to control the power of the ethernet switch.
# The needs to be reset when the board is powered on, so the ethernet switch can work properly and enumarate the ethernet ports.

device=$(cat /sys/devices/soc0/soc_id)

kernel_version_major=$(uname -r | cut -d. -f1)
kernel_version_minor=$(uname -r | cut -d. -f2)

# Check if kernel version is above 5.10
if [ $kernel_version_major -gt 5 ] || [ $kernel_version_major -eq 5 -a $kernel_version_minor -gt 10 ]; then
    gpioset 1 15=0
    sleep 1
    gpioset 1 15=1
else
    echo 331 > /sys/class/gpio/export
    echo out > /sys/class/gpio/PCC.03/direction
    echo 0 > /sys/class/gpio/PCC.03/value
    sleep 1
    echo 1 > /sys/class/gpio/PCC.03/value
    echo PCC.03 > /sys/class/gpio/unexport
fi
