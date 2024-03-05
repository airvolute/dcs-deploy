#!/bin/bash
device=$(cat /sys/devices/soc0/soc_id)

if [[ "$device" == "35" ]]; then
    echo 331 > /sys/class/gpio/export
    echo out > /sys/class/gpio/PCC.03/direction
    echo 0 > /sys/class/gpio/PCC.03/value
    echo 1 > /sys/class/gpio/PCC.03/value
    
    i2cset -y 0 0x2d 0xAA 0x55 0x00 i
    sleep 1
fi

sudo uhubctl -a off -p 6

