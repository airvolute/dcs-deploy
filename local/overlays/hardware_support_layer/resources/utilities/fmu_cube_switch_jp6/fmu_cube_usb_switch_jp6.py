import os
import time
import sys

def run_command(command):
    result = os.system(command)
    if result != 0:
        print(f"Command failed: {command}")
        sys.exit(1)

def detect_usb_path():
    """
    Detects the correct path for USB drivers (either /drivers or /hub/drivers).
    """
    if os.path.exists('/sys/bus/usb/drivers/unbind'):
        return '/sys/bus/usb/drivers'
    elif os.path.exists('/sys/bus/usb/drivers/hub/unbind'):
        return '/sys/bus/usb/drivers/hub'
    else:
        print("Error: Unable to detect USB driver path.")
        sys.exit(1)

def reset_usb():
    usb_path = detect_usb_path()
    run_command(f'echo -n "1-0:1.0" | sudo tee {usb_path}/unbind')
    run_command(f'echo -n "1-0:1.0" | sudo tee {usb_path}/bind')

def enable_device(device):
    if device == 'fmu':
        # Set GPIO4=1
        run_command('sudo gpioset gpiochip2 4=1')
    elif device == 'cube':
        # Set GPIO4=0
        run_command('sudo gpioset gpiochip2 4=0')
    else:
        raise ValueError("Invalid device selection. Choose 'fmu' or 'cube'.")

    reset_usb()

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ['cube', 'fmu']:
        print("Usage: sudo python fmu_cube_usb_switch.py [cube/fmu]")
        sys.exit(1)

    enable_device(sys.argv[1])
    time.sleep(3)
