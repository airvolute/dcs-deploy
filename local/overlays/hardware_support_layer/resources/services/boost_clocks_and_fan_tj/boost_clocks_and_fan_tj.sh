#!/bin/bash

TJ_ZONE="$(grep -il tj /sys/class/thermal/thermal_zone*/type | xargs dirname)"

# Boost jetson clocks
jetson_clocks 

# Stop the fan control service
systemctl stop nvfancontrol

# Set thermal zone to user_space for not overriding the fan control
echo "user_space" > "${TJ_ZONE}/policy"
ret="$?"
if [ "${ret}" -ne "0" ]; then
	echo "Error: Failed to switch to user_space for Tj thermal zone!"
	return
fi

# Add simple ramp for fan control
for pwm in {0..255..1}; do
    echo $pwm | sudo tee /sys/devices/platform/pwm-fan/hwmon/hwmon*/pwm*
    sleep 0.01
done
