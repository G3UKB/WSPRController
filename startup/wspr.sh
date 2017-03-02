#!/bin/bash

echo "Starting WSPR system..."

# Start WSPR
cd /home/pi/wspr
python3 wspr.py&

# Start the automation controller
cd /home/pi/Projects/WSPRController/trunk/python/controller
python3 automation.py ../scripts/script-1.txt /dev/ttyACM0
