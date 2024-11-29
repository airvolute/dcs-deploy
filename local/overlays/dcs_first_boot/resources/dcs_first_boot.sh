#!/bin/bash

source /etc/profile

# Re-generate SSH keys and access
sudo ssh-keygen -A
sudo systemctl restart sshd
echo "SSH configuration completed"

sudo usermod -a -G i2c dcs_user
sudo usermod -a -G gpio dcs_user
sudo usermod -a -G dialout dcs_user
sudo usermod -a -G spi dcs_user
sudo udevadm control --reload-rules && udevadm trigger

if [ -f "/usr/local/bin/handle_hardware_services.sh" ]; then
    if ! sudo /usr/local/bin/handle_hardware_services.sh; then
        echo "Error: handle_hardware_services.sh execution failed."
        exit 1
    fi
else
    echo "Error: handle_hardware_services.sh not found."
fi

# rm first boot check file, so this setup runs only once
sudo rm /etc/first_boot
