#!/bin/bash

# Command to activate USB 3 capability 
usb3_command="i2cset -y 0 0x1d 0x09 0x00"

retry_limit=5
retry_count=0

while [ $retry_count -lt $retry_limit ]; do
    echo "Attempting to activate USB 3 capability (Attempt $((retry_count + 1)))..."
    $usb3_command
    
    # Check if the command succeeded
    if [ $? -eq 0 ]; then
        echo "USB 3 capability activated successfully."
        exit 0
    else
        echo "Failed to activate USB 3 capability. Retrying..."
    fi

    retry_count=$((retry_count + 1))
    sleep 1
done

echo "Failed to activate USB 3 capability after $retry_limit attempts."
exit 1
