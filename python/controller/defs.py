#!/usr/bin/env python3
#
# defs.py
# 
# Copyright (C) 2017 by G3UKB Bob Cowdery
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#    
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#    
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#    
#  The author can be reached by email at:   
#     bob@bobcowdery.plus.com
#

import sys, os
sys.path.append(os.path.join('..','..','..','..','Common','trunk','python'))
from commondefs import *

# ===============================================================================
# Network
CMD_IP = '127.0.0.1'
CMD_PORT = 10000
EVNT_IP = '127.0.0.1'
EVNT_PORT = 10001

# ===============================================================================
# Timeouts
EVNT_TIMEOUT = 5

# ===============================================================================
# Internal structure for script files

# RUN section
S_RUN = 'srun'
S_REPEAT = 'srepeat'
S_LOOP = 'sloop'
S_ONCE = 'sonce'

# Stop section
S_STOP = 'sstop'
S_IDLE = 'sidle'
S_CONTINUE = 'scontinue'

# Power section
S_POWER = 'spower'

# Command section
S_COMMANDS = 'scommands'
# Offsets into command structure
C_START = 0
C_STOP = 1
C_BAND = 2
C_TX = 3
C_PWR = 4
C_ANTENNA = 5
C_CYCLES = 6
C_SPOT = 7
C_RADIO = 8

DISP_CONTINUE = 0
DISP_COMPLETE = 1
DISP_RECOVERABLE_ERROR = 2
DISP_NONRECOVERABLE_ERROR = 3
DISP_NEW_INDEX = 4

# ===============================================================================
# Low Pass Filters
# Pin to relay allocation
# Each relay pair shorts the input and output LPF jumpers
PIN_160_1 = 13  # Rly 3
PIN_160_2 = 21  # Rly 6
PIN_80_1 = 6    # Rly 2
PIN_80_2 = 20   # Rly 5
PIN_40_1 = 5    # Rly 1
PIN_40_2 = 26   # Rly 4

# ===============================================================================
# Radio definitions
R_INTERNAL = 'rinternal'
R_EXTERNAL = 'rexternal'

# CAT settings
CAT_SETTINGS = {
    VARIANT: CAT_VARIANTS[0],
    NETWORK: [
        # ip, port
        None, None
    ],
    SERIAL: [
        #com port, baud rate
        None, '19200'
    ],
    SELECT: CAT_SERIAL #CAT_UDP | CAT_SERIAL
}

# ===============================================================================
# Band definitions
B_160   = 'B_160'
B_80    = 'B_80'
B_60    = 'B_60'
B_40    = 'B_40'
B_30    = 'B_30'
B_20    = 'B_20'
B_17    = 'B_17'
B_15    = 'B_15'
B_12    = 'B_12'
B_10    = 'B_10'
B_6     = 'B_6'
B_4     = 'B_4'
B_2     = 'B_2'

# Band lookup
# Key = entry in script file
# Value = id to be used internally
BAND_TO_INTERNAL = {
    '160':  B_160,
    '80':   B_80,
    '60':   B_60,
    '40':   B_40,
    '30':   B_30,
    '20':   B_20,
    '17':   B_17,
    '15':   B_15,
    '12':   B_12,
    '10':   B_10,
    '6':    B_6,
    '4':    B_4,
    '2':    B_2,       
}

# Key = entry in internal table
# Value = id to be used externally (i.e. WSPR)
BAND_TO_EXTERNAL = {
    B_160:  2,
    B_80:    3,
    B_60:    4,
    B_40:    5,
    B_30:    6,
    B_20:    7,
    B_17:    8,
    B_15:    9,
    B_12:    10,
    B_10:    11,
    B_6:     12,
    B_4:     13,
    B_2:     14,       
}

# Convert the band to a frequency for WSPR operation on that band
BAND_TO_FREQ = {
    B_160:  1.8366,
    B_80:    3.5926,
    B_60:    5.2872,
    B_40:    7.0386,
    B_30:    10.1387,
    B_20:    14.0956,
    B_17:    18.1046,
    B_15:    21.0946,
    B_12:    24.9246,
    B_10:    28.1246,
    B_6:     50.2930,
    B_4:     70.0286,
    B_2:     144.4890,          
}

# ===============================================================================
# Antenna definitions
# Note this depends on what you have available and what switching arrangement you have

A_LOOP_160 = 'A_LOOP_160'
A_LOOP_80 = 'A_LOOP_80'
A_EFD_80_10 = 'A_EFD_80_10'
A_DIPOLE_6_4_2 = 'A_DIPOLE_6_4_2'
A_VERT_6_4_2 = 'A_VERT_6_4_2'

ANTENNA_TO_INTERNAL = {
    '160m-loop':        A_LOOP_160,
    '80m-loop':         A_LOOP_80,
    '80m-10m-EFD':      A_EFD_80_10,
    '6-4-2m-dipole':    A_DIPOLE_6_4_2,
    '6-4-2m-vert':      A_VERT_6_4_2,
}

# These are the relay switching instructions for the 7100 HF and 7100 VU antenna sockets
RELAY_ON = 'relayon'
RELAY_OFF = 'relayoff'
RELAY_NA = 'rna'

ANTENNA_TO_HF_MATRIX = {
    A_LOOP_160:     {1: RELAY_ON, 2:RELAY_NA, 3: RELAY_OFF, 4: RELAY_NA},
    A_LOOP_80:      {1: RELAY_ON, 2:RELAY_NA, 3: RELAY_OFF, 4: RELAY_NA},
    A_EFD_80_10:    {1: RELAY_OFF, 2:RELAY_NA, 3: RELAY_OFF, 4: RELAY_NA},
    A_DIPOLE_6_4_2: {1: RELAY_NA, 2:RELAY_ON, 3: RELAY_ON, 4: RELAY_ON},
    A_VERT_6_4_2:   {1: RELAY_NA, 2:RELAY_OFF, 3: RELAY_ON, 4: RELAY_ON},
}

ANTENNA_TO_VU_MATRIX = {
    A_DIPOLE_6_4_2: {1: RELAY_NA, 2:RELAY_ON, 3: RELAY_NA, 4: RELAY_OFF},
    A_VERT_6_4_2:   {1: RELAY_NA, 2:RELAY_OFF, 3: RELAY_NA, 4: RELAY_OFF},
}

# Default parameters
ANT_CTRL_RELAY_DEFAULT_STATE = {1: RELAY_OFF, 2:RELAY_OFF, 3: RELAY_OFF, 4: RELAY_OFF, 5: RELAY_OFF, 6: RELAY_OFF}
ANT_CTRL_ARDUINO_ADDR = ('192.168.1.178', 8888)
ANT_CTRL_ARDUINO_EVNT_PORT = 8889

# Loop Controller (part of Antenna defs) ===============
# Default parameters
LOOP_CTRL_RELAY_DEFAULT_STATE = {1: RELAY_OFF, 2:RELAY_OFF, 3: RELAY_OFF, 4: RELAY_OFF}
LOOP_CTRL_ARDUINO_ADDR = ('192.168.1.177', 8888)

ANTENNA_TO_LOOP_MATRIX = {
    A_LOOP_160: {1: RELAY_OFF, 2:RELAY_OFF, 3: RELAY_OFF, 4: RELAY_OFF},
    A_LOOP_80:   {1: RELAY_ON, 2:RELAY_ON, 3: RELAY_OFF, 4: RELAY_OFF},
}

L_SETPOINTS = 'lsetpoints'
L_BAND = 'lband'
L_POSITION = 'lposition'

ANTENNA_TO_LOOP_POSITION = {
    #                       MAX, MIN            TUNE
    A_LOOP_160: {L_SETPOINTS: (843, 73), L_BAND: (100, 150), L_POSITION: 129},
    A_LOOP_80:  {L_SETPOINTS: (843, 73), L_BAND: (20, 80), L_POSITION: 46}
}

# Set slow to medium
MOTOR_SPEED = 75