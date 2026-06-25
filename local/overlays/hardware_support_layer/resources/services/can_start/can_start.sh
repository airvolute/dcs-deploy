#!/bin/bash

# Load can drivers and start can0
modprobe can
modprobe can_raw
modprobe mttcan

# Create symlink for can0 to /dev/airvolute/can0
ln -sf /sys/class/net/can0 /dev/airvolute/can0