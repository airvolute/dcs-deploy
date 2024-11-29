#!/bin/bash

# Command to initialize the USB hub
initialize_hub_command="i2cset -y 0 0x2d 0xAA 0x55 0x00 i"

retry_limit=5
retry_count=0

while [ $retry_count -lt $retry_limit ]; do
    echo "Attempting to initialize the USB hub (Attempt $((retry_count + 1)))..."
    $initialize_hub_command

    # Check if the command succeeded
    if [ $? -eq 0 ]; then
        echo "USB hub initialized successfully."
        exit 0
    else
        echo "Failed to initialize the USB hub. Retrying..."
    fi

    retry_count=$((retry_count + 1))
    sleep 1
done

echo "Failed to initialize the USB hub after $retry_limit attempts."
exit 1
