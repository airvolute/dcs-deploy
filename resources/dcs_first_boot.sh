#!/bin/bash

source /etc/profile

# Setup Doodle Radio
if [[ -n $MAV_SYS_ID && -n $DOODLE_RADIO_IP ]]; then
  echo "Setting up Doodle Radio"
  chmod +x /home/dcs_user/airvolute-doodle-setup/initial_setup.sh
  sudo /home/dcs_user/airvolute-doodle-setup/initial_setup.sh n $UAV_DOODLE_IP $DOODLE_RADIO_IP
fi

# TODO: set SYS ID with C++ mavlink app

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
# TODO: set power mode - nvpmodel does not work, use /etc/nvpmodel.conf instead
# TODO: set fan to max level and clocks to max level - jetsonclocks --fan

# Set correct permissions and udev rules
if [ ! -f /etc/udev/rules.d/61-jetson-common.rules ] ; then
    sudo touch /etc/udev/rules.d/61-jetson-common.rules
    echo 'KERNEL=="gpiochip*", SUBSYSTEM=="gpio", MODE="0660", GROUP="gpio"' | sudo tee -a /etc/udev/rules.d/61-jetson-common.rules
    echo 'KERNEL=="i2c*", SUBSYSTEM=="i2c", MODE="0660", GROUP="i2c"' | sudo tee -a /etc/udev/rules.d/61-jetson-common.rules
    echo 'KERNEL=="/dev/ttyTHS0*", SUBSYSTEM=="dialout", MODE="0660", GROUP="dialout"' | sudo tee -a /etc/udev/rules.d/61-jetson-common.rules
fi

sudo usermod -a -G i2c dcs_user
sudo usermod -a -G gpio dcs_user
sudo usermod -a -G dialout dcs_user
sudo udevadm control --reload-rules && udevadm trigger



# rm first boot check file, so this setup runs only once
sudo rm /etc/first_boot
