#!/bin/bash

# Load spidev drivers
# While this can be done from device tree, it will produce some errors in the logs

modprobe spidev