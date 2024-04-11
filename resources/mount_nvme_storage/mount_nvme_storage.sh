#!/bin/bash

# The location where you want to mount the secondary NVMe drive
mount_location="/home/dcs_user/nvme_data_storage"

# The NVMe device that the system is booted from (root device)
booted_nvme=$(findmnt -n -o SOURCE --target /)

# List all NVMe devices and exclude the booted device
nvme_devices=$(ls /dev/nvme*n1 | grep -v "$booted_nvme")

# Check if there are any NVMe devices to mount
if [ -z "$nvme_devices" ]; then
    echo "No secondary NVMe devices found."
    exit 1
fi

# Loop through available NVMe devices
for device in $nvme_devices; do
    # Check if the NVMe device is already mounted
    if findmnt -S "$device" > /dev/null; then
        echo "$device is already mounted."
        continue
    fi

    # Create the mount point if it doesn't exist
    if [ ! -d "$mount_location" ]; then
        sudo mkdir -p "$mount_location"
    fi

    # Format the NVMe device to a filesystem of your choice, for example, ext4
    # Warning: This will erase the data on the device
    # sudo mkfs.ext4 "$device"

    # Mount the NVMe device
    sudo mount "$device" "$mount_location"

    echo "$device has been mounted to $mount_location"
    # Assuming only one secondary NVMe is to be mounted, break the loop after mounting
    break
done

