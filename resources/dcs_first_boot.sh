#!/bin/bash

source /etc/profile

# Setup Doodle Radio
if [[ -n $MAV_SYS_ID && -n $DOODLE_RADIO_IP ]]; then
  echo "Setting up Doodle Radio"
  chmod +x /home/dcs_user/airvolute-doodle-setup/initial_setup.sh
  sudo /home/dcs_user/airvolute-doodle-setup/initial_setup.sh n $UAV_DOODLE_IP $DOODLE_RADIO_IP
fi

# Re-generate SSH keys
sudo ssh-keygen -A
echo "SSH keys re-generated"

# Enable start usb3_control service after start-up
sudo systemctl enable usb3_control.service
echo "USB3 control service enabled"

# Enable usb_hub_control start service after start-up
sudo systemctl enable usb_hub_control.service
echo "USB hub scontrol service enabled"

# Install uhubctl
cd /home/dcs_user
sudo apt install ./uhubctl_2.1.0-1_arm64.deb
echo "Uhubctl installed"

# Start services
sudo systemctl start usb3_control.service
sudo systemctl start usb_hub_control.service

# Disable nvgetty to be able to use UART
sudo systemctl disable nvgetty.service
echo "nvgetty disabled"

# rm first boot check file, so this setup runs only once
sudo rm /etc/first_boot
