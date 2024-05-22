#!/bin/bash
# launch the usb hub in the case that it was not properly initialized
i2cset -y 0 0x2d 0xAA 0x55 0x00 i

sleep 1
# disable USB port 6 so Cube can be connected via serial
sudo uhubctl -a off -p 6
