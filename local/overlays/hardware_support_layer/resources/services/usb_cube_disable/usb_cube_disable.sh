#!/bin/bash

# Check if port 6 exists
check_port_exists() {
    uhubctl | grep -q "Port 6" 
    return $?
}

# Disable USB port 6
disable_usb_port() {
    sudo uhubctl -a off -p 6
}

retry_limit=5
retry_count=0

while [ $retry_count -lt $retry_limit ]; do
    if check_port_exists; then
        echo "Port 6 detected. Attempting to disable..."
        disable_usb_port

        # Check if the disable command was successful
        if [ $? -eq 0 ]; then
            echo "Port 6 disabled successfully."
            exit 0
        else
            echo "Failed to disable Port 6. Retrying..."
        fi
    else
        echo "Port 6 not detected. Retrying..."
    fi

    retry_count=$((retry_count + 1))
    sleep 1
done

echo "Failed to disable Port 6 after $retry_limit attempts."
exit 1
