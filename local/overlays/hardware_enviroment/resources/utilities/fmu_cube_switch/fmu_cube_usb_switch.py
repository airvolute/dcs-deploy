import os
import time
import sys

usb_mux_gpio = [314, "gpio314"]

def run_command(command):
    result = os.system(command)
    if result != 0:
        print(f"Command failed: {command}")
        sys.exit(1)

def export_gpio(gpio_kernel_number):
    run_command(f'echo {gpio_kernel_number[0]} | sudo tee /sys/class/gpio/export')
    time.sleep(0.1)

def unexport_gpio(gpio_kernel_number):
    run_command(f'echo {gpio_kernel_number[0]} | sudo tee /sys/class/gpio/unexport')

def set_direction(gpio_kernel_number, direction):
    if direction in ["in", "out"]:
        run_command(f'echo {direction} | sudo tee /sys/class/gpio/{gpio_kernel_number[1]}/direction')
    else:
        print("Wrong gpio direction to set!")

def write_gpio(gpio_kernel_number, value):
    if value in [1, 0]:
        run_command(f'echo {value} | sudo tee /sys/class/gpio/{gpio_kernel_number[1]}/value')
    else:
        print("Wrong gpio value to set!")

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
    export_gpio(usb_mux_gpio)
    set_direction(usb_mux_gpio, "out")
    if device == 'fmu':
        write_gpio(usb_mux_gpio, 1)
    elif device == 'cube':
        write_gpio(usb_mux_gpio, 0)
    else:
        raise ValueError("Invalid device selection. Choose 'fmu' or 'cube'.")
    unexport_gpio(usb_mux_gpio)
    reset_usb()

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ['cube', 'fmu']:
        print("Usage: sudo python fmu_cube_usb_switch.py [cube/fmu]")
        sys.exit(1)

    enable_device(sys.argv[1])
    time.sleep(3)
