#!/bin/bash
device=$(cat /sys/devices/soc0/soc_id)

# reset the ethernet switch, this is needed only on dcs2.0, therefore we check the device id, xavier is not compatible with dcs2.0
if [[ "$device" == "35" ]]; then
    echo 331 > /sys/class/gpio/export
    echo out > /sys/class/gpio/PCC.03/direction
    echo 0 > /sys/class/gpio/PCC.03/value
    sleep 1
    echo 1 > /sys/class/gpio/PCC.03/value
fi
