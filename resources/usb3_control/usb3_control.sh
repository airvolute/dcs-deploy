#!/bin/bash

# activate usb 3 capability of usb c connector
i2cset -y 0 0x1d 0x09 0x00

