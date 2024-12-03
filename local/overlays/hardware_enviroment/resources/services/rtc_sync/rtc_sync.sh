#!/bin/bash

# Function to check network connectivity
check_network() {
    if ping -c 1 -W 1 8.8.8.8 > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to get the current system time as seconds since epoch
get_system_time() {
    date +%s
}

# Function to get the RTC time as seconds since epoch
get_rtc_time() {
    sudo hwclock --rtc=/dev/rtc0 --get | xargs -I {} date -d "{}" +%s
}

# Function to compare and update RTC if needed
sync_time_if_needed() {
    echo "Checking if RTC needs to be synchronized..."

    # Get system time and RTC time
    system_time=$(get_system_time)
    rtc_time=$(get_rtc_time)

    # Allowable time difference in seconds (to avoid minor drift issues)
    allowable_diff=1

    # Compare the times
    if (( system_time > rtc_time + allowable_diff )) || (( system_time < rtc_time - allowable_diff )); then
        echo "System time and RTC time differ. Updating RTC..."
        sudo hwclock --rtc=/dev/rtc0 -w
        echo "RTC updated with the current system time."
    else
        echo "RTC is already synchronized with system time. No update needed."
    fi
}

# Main script logic
echo "Monitoring network status..."
while true; do
    if check_network; then
        echo "Network detected!"
        sync_time_if_needed
        break
    else
        sleep 30
    fi
done
