#!/bin/bash

# Boost jetson clocks
jetson_clocks 

# Stop the fan control service
systemctl stop nvfancontrol

# Add simple ramp for fan control
for pwm in {0..255..1}; do
    echo $pwm | sudo tee /sys/devices/platform/pwm-fan/hwmon/hwmon*/pwm*
    sleep 0.01
done
