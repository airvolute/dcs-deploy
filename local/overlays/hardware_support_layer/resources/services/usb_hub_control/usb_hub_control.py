# Copyright (c) 2025 Airvolute s.r.o.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.

import smbus2
import time
import sys
import os
from smbus2 import SMBus, i2c_msg


# GPIO with numbers
cam_mclk0 = [440, "PP.00"]
cam_mclk1 = [441, "PP.01"]
cam_mclk2 = [453, "PQ.05"]
serial1_rts = [460, "PR.04"]
serial1_cts = [461, "PR.05"]
pwm_out1 = [433, "PN.01"]
pwm_out2 = [391, "PH.00"]
se_ext_drdy = [492, "PAC.06"]
fmu_drdy = [486, "PAC.00"]
imu_drdy = [397, "PH.06"]
gpio_exp4 = [312, "gpio312"]
gpio_exp5 = [313, "gpio313"]
usb_mux_gpio = [314, "gpio314"]
usb_hub_nrst = [454, "PQ.06"]
usb_hub_vbusdet = [341, "PEE.02"]
eth_swt_nrst = [331, "PCC.03"]
can_stby = [446, "PP.06"]

def set_gpiod(chipname, line_offset, value):
    chip = gpiod.Chip(chipname)
    line = chip.get_line(line_offset)

    line.request(consumer="usb-hub-control", type=gpiod.LINE_REQ_DIR_OUT, default_val=value)

    line.release()
    chip.close()

# To export_gpio function, gpios are transfered as their numbers. After export their GPIO names (f.e. PA.00) are used
def export_gpio(gpio_kernel_number):
    command = 'echo ' + str(gpio_kernel_number[0]) + ' > /sys/class/gpio/export'
    os.system(command)
    time.sleep(0.1)


def unexport_gpio(gpio_kernel_number):
    command = 'echo ' + str(gpio_kernel_number[0]) + ' > /sys/class/gpio/unexport'
    os.system(command)


def set_direction(gpio_kernel_number, direction):
    if direction == "in" or direction == "out":
        command = 'echo ' + direction + ' > /sys/class/gpio/' + gpio_kernel_number[1] + '/direction'
        os.system(command)
    else:
        print("Wrong gpio direction to set !")


def write_gpio(gpio_kernel_number, value):
    if value == 1 or value == 0:
        command = 'echo ' + str(value) + ' > /sys/class/gpio/' + gpio_kernel_number[1] + '/value'
        os.system(command)
    else:
        print("Wrong gpio value to set !")


def read_gpio(gpio_kernel_number):
    command = 'cat /sys/class/gpio/' + gpio_kernel_number[1] + '/value'
    ret1 = subprocess.check_output(command, shell=True)
    return ret1[0]


def usb2534_write_cfg_register(i2c_bus, device_address, register_address, value):
    '''
    register_address = 2byte (0x0000)
    value = 1byte (0x00)

    Function written following Microchip's AN.26.18 pg.4
    https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ApplicationNotes/ApplicationNotes/00001801C.pdf
    '''
    if register_address < 0 or register_address > 0xFFFF:
        raise ValueError("Register address must be a 2-byte value (0-65535).")
    reg_msb = (register_address >> 8) & 0xFF
    reg_lsb = register_address & 0xFF


    bus = smbus2.SMBus(i2c_bus)
    wr_data1 = [0x00, 0x00, 0x05, 0x00, 0x02, reg_msb, reg_lsb, value]
    wr_data2 = [0x99, 0x37, 0x00]
    write_msg1 = i2c_msg.write(device_address, wr_data1)
    write_msg2 = i2c_msg.write(device_address, wr_data2)
    try:
        bus.i2c_rdwr(write_msg1, write_msg2)
        bus.close()
    except Exception as e:
        print(f"Error write cfg register: {e}")
        bus.close()


def usb2534_read_cfg_register(i2c_bus, device_address, register_address):
    '''
    register_address = 2byte (0x0000)

    Function written following Microchip's AN.26.18 pg.4
    https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ApplicationNotes/ApplicationNotes/00001801C.pdf
    '''
    if register_address < 0 or register_address > 0xFFFF:
        raise ValueError("Register address must be a 2-byte value (0-65535).")
    reg_msb = (register_address >> 8) & 0xFF
    reg_lsb = register_address & 0xFF


    bus = smbus2.SMBus(i2c_bus)
    wr_data1 = [0x00, 0x00, 0x04, 0x01, 0x01, reg_msb, reg_lsb]
    wr_data2 = [0x99, 0x37, 0x00]
    wr_data3 = [0x00, 0x04]
    write_msg1 = i2c_msg.write(device_address, wr_data1)
    write_msg2 = i2c_msg.write(device_address, wr_data2)
    write_msg3 = i2c_msg.write(device_address, wr_data3)
    read_msg = i2c_msg.read(device_address, 2)
    try:
        bus.i2c_rdwr(write_msg1, write_msg2, write_msg3, read_msg)
        bus.close()
    except Exception as e:
        print(f"Error read cfg register: {e}")
        bus.close()

    return list(read_msg)[1]


def usb2534_write_runtime_register(i2c_bus, device_address, register_address, value):
    bus = smbus2.SMBus(i2c_bus)
    wr_data = [register_address, value]
    write_msg= i2c_msg.write(device_address, wr_data)
    try:
        bus.i2c_rdwr(write_msg)
        bus.close()
    except Exception as e:
        print(f"Error write runtime register: {e}")
        bus.close()


def usb2534_read_runtime_register(i2c_bus, device_address, register_address):
    bus = smbus2.SMBus(i2c_bus)
    wr_data = [register_address]
    write_msg= i2c_msg.write(device_address, wr_data)
    read_msg = i2c_msg.read(device_address, 1)
    try:
        bus.i2c_rdwr(write_msg, read_msg)
        bus.close()
    except Exception as e:
        print(f"Error read runtime register: {e}")
        bus.close()

    return list(read_msg)[0]


def usb2534_start_hub(i2c_bus, device_address):
    '''
    Start USB HUB by I2C command write 0x00 to 0xAA55 register
    '''
    bus = smbus2.SMBus(i2c_bus)
    wr_data1 = [0xAA, 0x55, 0x00]
    write_msg1 = i2c_msg.write(device_address, wr_data1)
    try:
        bus.i2c_rdwr(write_msg1)
        bus.close()
    except Exception as e:
        print(f"Error write cfg register: {e}")
        bus.close()

bus_number = 0
dev_addr = 0x2d
dev_addr_run = 0x2c

print("Reseting USB HUB...")
kernel_version = os.popen("uname -r").read().strip()

version_tuple = tuple(map(int, kernel_version.split('-')[0].split('.')))

if version_tuple > (5, 10, 120):
    try:
        import gpiod
    except ImportError:
        print("Error: The required 'python3-libgpiod' package is not installed.")
        print("sudo apt install python3-libgpiod")
        exit(1)

    set_gpiod("gpiochip0", 106, 0)
    time.sleep(0.5)
    set_gpiod("gpiochip1", 25, 0)
    time.sleep(1)
    set_gpiod("gpiochip0", 106, 1)
    set_gpiod("gpiochip1", 25, 1)
else:
    export_gpio(usb_hub_nrst)
    export_gpio(usb_hub_vbusdet)
    set_direction(usb_hub_nrst, 'out')
    set_direction(usb_hub_vbusdet, 'out')
    
    # reset hub
    write_gpio(usb_hub_vbusdet, 0)
    time.sleep(0.5)
    write_gpio(usb_hub_nrst, 0)
    
    time.sleep(1)
    
    write_gpio(usb_hub_vbusdet, 1)
    write_gpio(usb_hub_nrst, 1)
    unexport_gpio(usb_hub_nrst)
    unexport_gpio(usb_hub_vbusdet)


print("Setting up USB HUB through I2C...")

################################################I2C TESTING ################################
read_reg = 0x00

#Time delay > 300ms has to be there after reseting the HUB !!!
time.sleep(0.4)

#HUB_CFG1 (Default = 0x9B)
usb2534_write_cfg_register(bus_number, dev_addr, 0x3006, 0x9B)

#HUB_CFG2 (Default = 0x20 | 0x28 - COMPOUND enabled)
usb2534_write_cfg_register(bus_number, dev_addr, 0x3007, 0x28)

#HUB_CFG3 (Default = 0x08 | PRTMAP_EN = 0, STRING_EN = 1 : 0x01)
usb2534_write_cfg_register(bus_number, dev_addr, 0x3008, 0x01)

#NON-REMOVABLE DEVICE (default = 0x06 | PORT 4 non-removable : 0x10)
usb2534_write_cfg_register(bus_number, dev_addr, 0x3009, 0x10)

#USB2_HUB_CTL (default = 0x00 | LPM_DISABLE = 1 : 0x02 )
usb2534_write_cfg_register(bus_number, dev_addr, 0x3104, 0x02)

#INTERNAL_PORT (Allow enumeration of 5.th internal port - solves issue with other device enumeration)
usb2534_write_cfg_register(bus_number, dev_addr, 0x4130, 0x01)


#----PORT 1 SETUP----
#HSIC_P1_CFG (default 0x00, Power mode = 1 : 0x01)
#usb2534_write_cfg_register(bus_number, dev_addr, 0x6643, 0x01)

#PORT_CFG_SEL_1 (default = 0x01 | PERMANENT = 1 : 0x10 )
#usb2534_write_cfg_register(bus_number, dev_addr, 0x3C00, 0x10)

#--PORT 4 SETUP---
#HSIC_P4_CFG (default 0x00, Power mode = 1 : 0x01)
#usb2534_write_cfg_register(bus_number, dev_addr, 0x7243, 0x01)

#PORT_CFG_SEL_4 (default = 0x01 | PERMANENT = 1 : 0x10 )
#usb2534_write_cfg_register(bus_number, dev_addr, 0x3C0C, 0x10)




read_reg = usb2534_read_cfg_register(bus_number, dev_addr, 0x3006)
print("Read 0x3006 register value:", hex(read_reg))
read_reg = usb2534_read_cfg_register(bus_number, dev_addr, 0x3007)
print("Read 0x3007 register value:", hex(read_reg))
read_reg = usb2534_read_cfg_register(bus_number, dev_addr, 0x3008)
print("Read 0x3008 register value:", hex(read_reg))
read_reg = usb2534_read_cfg_register(bus_number, dev_addr, 0x3009)
print("Read 0x3009 register value:", hex(read_reg))
read_reg = usb2534_read_cfg_register(bus_number, dev_addr, 0x3104)
print("Read 0x3104 register value:", hex(read_reg))
read_reg = usb2534_read_cfg_register(bus_number, dev_addr, 0x3C0C)
print("Read 0x3C0C register value:", hex(read_reg))

#Start USB HUB by command
usb2534_start_hub(bus_number, dev_addr)



#RUNTIME SECTION
'''
Errata sheet
https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/Errata/USB253x-USB3x13-USB46x4-Errata-80000583E.pdf
'''
#ERRATA NUMBER11 fix (in config)
# REg 3128 ext. descriptor
#usb2534_write_cfg_register(bus_number, dev_addr, 0x3128, 0x03)
# REg 3129 ext. descriptor
#usb2534_write_cfg_register(bus_number, dev_addr, 0x3129, 0x06)

#ERRATA NUMBER12 fix (in runtime)
#usb2534_write_runtime_register(bus_number, dev_addr_run, 0xE9, 0x00)
#read_reg= usb2534_read_runtime_register(bus_number, dev_addr_run, 0xE9)
#print("Read 0xE9 register value:", hex(read_reg))