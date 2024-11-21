#!/bin/bash

# The new folder you want to add to UnitPath
NEW_FOLDER="/etc/systemd/system/hardware"

# Ensure the new folder exists
if [ ! -d "$NEW_FOLDER" ]; then
    echo "Creating new folder: $NEW_FOLDER"
    sudo mkdir -p "$NEW_FOLDER"
fi

# Get the current UnitPath
CURRENT_UNIT_PATH=$(systemctl show --property=UnitPath | cut -d'=' -f2)

# Check if the new folder is already in UnitPath
if [[ "$CURRENT_UNIT_PATH" == *"$NEW_FOLDER"* ]]; then
    echo "The folder $NEW_FOLDER is already included in UnitPath."
    exit 0
fi

# Append the new folder to UnitPath
UPDATED_UNIT_PATH="$NEW_FOLDER $CURRENT_UNIT_PATH"

# Update /etc/systemd/system.conf
echo "Updating /etc/systemd/system.conf with the new UnitPath..."
sudo sed -i '/^#\?UnitPath=/d' /etc/systemd/system.conf
echo "UnitPath=$UPDATED_UNIT_PATH" | sudo tee -a /etc/systemd/system.conf

# Reload systemd to apply the changes
echo "Reloading systemd daemon..."
sudo systemctl daemon-reexec

echo "UnitPath updated successfully! New UnitPath:"
systemctl show --property=UnitPath

sudo systemctl start dummy_hw.service

