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

if [ ! -f /etc/udev/rules.d/11-csi.rules ] ; then
    sudo touch /etc/udev/rules.d/11-csi.rules
    echo 'SUBSYSTEM=="video4linux", ATTRS{name}=="vi-output, ov9281_devel 30-0060", SYMLINK+="av-ov9218-camera-csia"' | sudo tee -a /etc/udev/rules.d/11-csi.rules
    echo 'SUBSYSTEM=="video4linux", ATTRS{name}=="vi-output, tc358743 32-000f", SYMLINK+="av-tc358743-camera-csib"' | sudo tee -a /etc/udev/rules.d/11-csi.rules
    echo 'SUBSYSTEM=="video4linux", ATTRS{name}=="vi-output, ov9281_devel 31-0060", SYMLINK+="av-ov9218-camera-csic"' | sudo tee -a /etc/udev/rules.d/11-csi.rules
    echo 'SUBSYSTEM=="video4linux", ATTRS{name}=="vi-output, imx477 33-001a", SYMLINK+="av-imx477-camera-csid"' | sudo tee -a /etc/udev/rules.d/11-csi.rules
    echo 'SUBSYSTEM=="video4linux", ATTRS{name}=="vi-output, ov9281_devel 34-0060", SYMLINK+="av-ov9218-camera-csif"' | sudo tee -a /etc/udev/rules.d/11-csi.rules
    echo 'SUBSYSTEM=="video4linux", ATTRS{name}=="vi-output, ov9281_devel 35-0060", SYMLINK+="av-ov9218-camera-csie"' | sudo tee -a /etc/udev/rules.d/11-csi.rules
fi
sudo usermod -a -G i2c dcs_user
sudo usermod -a -G gpio dcs_user
sudo usermod -a -G dialout dcs_user
sudo udevadm control --reload-rules && udevadm trigger

# FYI: name firmware you want to flash the CUBE with to arducopter_fw.apj 
# and move it to home/dcs_user
if [ -f /home/dcs_user/uploader.py ] && [ -f /home/dcs_user/arducopter_stribog_fw.apj ]; then
echo "Flashing CUBE"
  sudo systemctl stop mavlink-router.service
  sudo -u dcs_user python /home/dcs_user/uploader.py --port /dev/ttyTHS0 --baud-bootloader-flash "921600" --baud-flightstack "921600" /home/dcs_user/arducopter_stribog_fw.apj
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

# Enable and start the NVMe storage service
sudo systemctl enable mount_nvme_storage.service
sudo systemctl start mount_nvme_storage.service
echo "NVMe storage service enabled and started"


# Install uhubctl
cd /home/dcs_user
sudo apt install ./uhubctl_2.1.0-1_arm64.deb
echo "Uhubctl installed"
cd ~

# Start services
sudo systemctl start usb3_control.service
sudo systemctl start usb_hub_control.service

# Install and use mavlink_sys_id_set
cd /home/dcs_user
sudo apt install ./mavlink_sys_id_set-1.0.0-Linux.deb
mavlink_sys_id_set /dev/ttyTHS0 921600 $MAV_SYS_ID 1 0

# rm first boot check file, so this setup runs only once
sudo rm /etc/first_boot
