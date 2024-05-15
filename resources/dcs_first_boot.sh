#!/bin/bash

source /etc/profile


# Re-generate SSH keys and access
sudo ssh-keygen -A
sudo systemctl restart sshd
echo "SSH configuration completed"

# Enable and start fan max speed
sudo systemctl enable fan_control.service
sudo systemctl start fan_control.service
echo "Fan control service enabled and started"

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

# Enable start usb3_control service after start-up
sudo systemctl enable usb3_control.service
echo "Service enabled"

# Enable usb_hub_control start service after start-up
sudo systemctl enable usb_hub_control.service
echo "Service enabled"

# Install uhubctl
cd /home/dcs_user
sudo apt install ./uhubctl_2.1.0-1_arm64.deb

# Start services
sudo systemctl start usb3_control.service
sudo systemctl start usb_hub_control.service

# rm first boot check file, so this setup runs only once
sudo rm /etc/first_boot
