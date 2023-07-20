#!/bin/bash

# Enable start usb3_control service after start-up
sudo systemctl enable usb3_control.service
echo "Service enabled"

# Enable usb_hub_control start service after start-up
sudo systemctl enable usb_hub_control.service
echo "Service enabled"

# Install uhubctl
cd /home/dcs_user
sudo apt install ./uhubctl_2.1.0-1_arm64.deb

# rm first boot check file, so this setup runs only once
sudo rm /etc/first_boot
