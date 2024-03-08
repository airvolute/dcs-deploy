#!/bin/bash

source /etc/profile

# Setup Doodle Radio
if [[ -n $MAV_SYS_ID && -n $DOODLE_RADIO_IP ]]; then
  echo "Setting up Doodle Radio"
  chmod +x /home/dcs_user/airvolute-doodle-setup/initial_setup.sh
  sudo /home/dcs_user/airvolute-doodle-setup/initial_setup.sh n $UAV_DOODLE_IP $DOODLE_RADIO_IP
fi

# Re-generate SSH keys and access
sudo ssh-keygen -A
sudo systemctl restart sshd
echo "SSH configuration completed"

# Enable and start fan max speed
sudo systemctl enable fan_control.service
sudo systemctl start fan_control.service
echo "Fan control service enabled and started"

# TODO: add CUBE flashing process somewhere here
# Recommendations:
# - Do this BEFORE running usb_hub_control service
# - STOP mavlink-router.service before flashing
# - START mavlink-router.service after flashing
# - Continue with the rest of the setup
# - Maybe do this as a separate script, which is run after first boot, but before dcs_first_boot.sh
# DEV VERSION - this expects all necessary files to be in /home/dcs_user
# It is not decided yet if we want this to be in specific public repo or anything for now
# FIXME: there is an error could not open port /dev/ttyTHS0: [Errno 13] Permission denied: '/dev/ttyTHS0'
# needs to be fixed maybe moving lines 66-76 from this script before this script
if [ -f /home/dcs_user/uploader.py ] && [ -f /home/dcs_user/arducopter_COP_4_4_3.apj ]; then
echo "Flashing CUBE"
  sudo systemctl stop mavlink-router.service
  sudo -u dcs_user python /home/dcs_user/uploader.py --port /dev/ttyTHS0 --baud-bootloader-flash "921600" --baud-flightstack "921600" /home/dcs_user/arducopter_COP_4_4_3.apj
  sudo systemctl start mavlink-router.service
else
  echo "CUBE flash files missing, not flashing CUBE!"
fi

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
cd ~

# Start services
sudo systemctl start usb3_control.service
sudo systemctl start usb_hub_control.service

# Disable nvgetty to be able to use UART
sudo systemctl disable nvgetty.service
sudo systemctl stop nvgetty.service
echo "nvgetty disabled and stopped"

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

# Install and use mavlink_sys_id_set
cd /home/dcs_user
sudo apt install ./mavlink_sys_id_set-1.0.0-Linux.deb
mavlink_sys_id_set /dev/ttyTHS0 921600 $MAV_SYS_ID 1 0

# rm first boot check file, so this setup runs only once
sudo rm /etc/first_boot
