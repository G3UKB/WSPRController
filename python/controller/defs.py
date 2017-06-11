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
sys.path.append(os.path.join('..','..','..','Common','python'))
from commondefs import *

# ===============================================================================
# Paths
WSPRRYPI_PATH = '/home/pi/Projects/WsprryPi/wspr'
FCDCTL_PATH = '/home/pi/Projects/fcdctl/fcdctl'
WSPR_PATH = '/home/pi/wspr'

# ===============================================================================
# WSPR sockets
CMD_IP = '127.0.0.1'
CMD_PORT = 10000
EVNT_IP = '127.0.0.1'
EVNT_PORT = 10001

# ===============================================================================
# Timeouts
EVNT_TIMEOUT = 5

# ===============================================================================
# Internal constants for script files

SEQ         = 'SEQ'         # Start a sequence
ENDSEQ      = 'ENDSEQ'      # End of loop
TIME        = 'TIME'        # Start a time banded section
ENDTIME     = 'ENDTIME'     # End a time banded section
PAUSE       = 'PAUSE'       # Pause the script file
MSG         = 'MSG'         # Output a message
COMPLETE    = 'COMPLETE'    # Script complete

LPF         = 'LPF'         # Commands related to the LPF filters
LPF_160     = 'LPF-160'
LPF_80      = 'LPF-80'
LPF_40      = 'LPF-40'

ANTENNA     = 'ANTENNA'     # Commands related to antenna switching
SWITCH      = 'SWITCH'      # Switch route
SWR         = 'SWR'         # Check SWR
LOOP        = 'LOOP'        # Commands related to the loop switching and tuning
LOOP_INIT   = 'LOOP_INIT'   # Initialise the loop system
LOOP_BAND   = 'LOOP_BAND'   # Tune to the WSPR freq for the band
LOOP_ADJUST = 'LOOP_ADJUST' # Fine tune

RADIO       = 'RADIO'       # CAT commands to external radios
CAT         = 'CAT'
FREQ        = 'FREQ'
MODE        = 'MODE'

WSPR        = 'WSPR'        # Commands related to WSPR
INVOKE      = 'INVOKE'      # Invoke WSPR if not running. Must be running before any other WSPR command.
RESET       = 'RESET'       # Reset
IDLE        = 'IDLE'        # Set idle on/off, i.e stop RX/TX

BAND        = 'BAND'        # Set band for reporting
B_160       = 'B-160'
B_80        = 'B-80'
B_40        = 'B-40'

TX          = 'TX'          # Set TX to 20% or 0%
POWER       = 'POWER'       # Adjust power output when using external radio TX
CYCLES      = 'CYCLES'      # Wait for n receive cycles
SPOT        = 'SPOT'        # Set spotting on/off.

WSPRRY              = 'WSPRRY'            # Commands related to WsprryPi
WSPRRY_OPTIONS      = 'WSPRRY_OPTIONS'      # Selection of -p -s -f -r -x -o -t -n. Must be set before START.
WSPRRY_CALLSIGN     = 'WSPRRY_CALLSIGN'     # Set callsign for tx data. Must be set before START.
WSPRRY_LOCATOR      = 'WSPRRY_LOCATOR'      # Set locator for tx data. Must be set before START.
WSPRRY_PWR          = 'WSPRRY_PWR'          # Set Tx power in dBm for tx data. Must be set before START.
WSPRRY_START        = 'WSPRRY_START'        # Start WsprryPi with the given frequency sequence and settings.
WSPRRY_WAIT         = 'WSPRRY_WAIT'         # Wait for WsprryPi to terminate
WSPRRY_KILL         = 'WSPRRY_KILL'         # Uncerimoneously kill WsprryPi (this may not work on Windows)
WSPRRY_STOP         = 'WSPRRY_STOP'         # Stop WsprryPI if running.

FCD         = 'FCD'         # Commands related to the FunCubeDonglePro+
FREQ        = 'FREQ'        # Set the FCDPro+ frequency.
LNA         = 'LNA'         # Set the FCDPro+ LNA gain, 0 == off, 1 == on.
MIXER       = 'MIXER'       # Set the FCDPro+ MIXER gain, 0 == off, 1 == on.
IF          = 'IF'          # Set the FCDPro+ IF gain, 0-59 dB.
STATUS      = 'STATUS'      # Show status
   
# Script Execution result codes
DISP_CONTINUE = 0
DISP_COMPLETE = 1
DISP_RECOVERABLE_ERROR = 2
DISP_NONRECOVERABLE_ERROR = 3
DISP_NEW_INDEX = 4

# Constants for state structure
SEQ = 'SEQ'
CYCLES = 'CYCLES'
CAT = 'CAT'
WSPPRY = 'WSPPRY'
                
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
# CAT variants
FT_817ND = 'FT-817ND'
IC7100 = 'IC7100'

# CAT settings
CAT_SETTINGS = {
    VARIANT: None,
    NETWORK: [
        # ip, port
        None, None
    ],
    SERIAL: [
        #com port, baud rate
        None, None
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
    B_160:   2,
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
    B_160:   1.8366,
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
    B_2:     144.4885,          
}

# Offset to account for FCD IF of 12KHz
FCD_IF = 0.012

# ===============================================================================
# Antenna definitions
# Note this depends on what you have available and what switching arrangement you have
# Switching works on a route basis i.e. an antenna to an RX input or a TX output or both

# Antennas available
A_LOOP = 'A_LOOP'
A_LOOP_160 = 'A_LOOP_160'
A_LOOP_80 = 'A_LOOP_80'
A_LOOP_40 = 'A_LOOP_40'
A_EFD_80_10 = 'A_EFD_80_10'
A_DIPOLE_6_4_2 = 'A_DIPOLE_6_4_2'
A_VERT_6_4_2 = 'A_VERT_6_4_2'

# Sources/sinks available
SS_FCD_PRO_PLUS = 'SS_FCD_PRO_PLUS'
SS_WSPRRYPI = 'SS_WSPRRYPI'
SS_IC7100 = 'SS_IC7100'
SS_VNA = 'SS_VNA'

# Map antenna name in the script file to the internal name
ANTENNA_TO_INTERNAL = {
    '160-80m-loop':     A_LOOP,
    '80m-10m-EFD':      A_EFD_80_10,
    '6-4-2m-dipole':    A_DIPOLE_6_4_2,
    '6-4-2m-vert':      A_VERT_6_4_2,
}
# Map source/sink name in the script file to the internal name
SS_TO_INTERNAL = {
    'FCD-Pro-Plus':     SS_FCD_PRO_PLUS,
    'RPi-WsprryPi':     SS_WSPRRYPI,
    'IC-7100':          SS_IC7100,
}

# These are the relay switching instructions for the above routings
RELAY_ON = 'relayon'
RELAY_OFF = 'relayoff'
RELAY_NA = 'rna'

ANTENNA_TO_SS_ROUTE = {
    '%s:%s' % (A_EFD_80_10, SS_FCD_PRO_PLUS):   {1: RELAY_OFF, 2:RELAY_NA, 3:RELAY_NA, 4:RELAY_OFF, 5:RELAY_NA, 6:RELAY_NA},
    '%s:%s' % (A_EFD_80_10, SS_WSPRRYPI):       {1: RELAY_NA, 2:RELAY_OFF, 3:RELAY_NA, 4:RELAY_ON, 5:RELAY_ON, 6:RELAY_NA},
    '%s:%s' % (A_EFD_80_10, SS_IC7100):         {1: RELAY_NA, 2:RELAY_ON, 3:RELAY_ON, 4:RELAY_ON, 5:RELAY_ON, 6:RELAY_NA},
    '%s:%s' % (A_LOOP, SS_FCD_PRO_PLUS):        {1: RELAY_ON, 2:RELAY_NA, 3:RELAY_NA, 4:RELAY_NA, 5:RELAY_NA, 6:RELAY_ON},
    '%s:%s' % (A_LOOP, SS_WSPRRYPI):            {1: RELAY_NA, 2:RELAY_OFF, 3:RELAY_NA, 4:RELAY_NA, 5:RELAY_OFF, 6:RELAY_OFF},
    '%s:%s' % (A_LOOP, SS_IC7100):              {1: RELAY_NA, 2:RELAY_ON, 3:RELAY_OFF, 4:RELAY_NA, 5:RELAY_OFF, 6:RELAY_OFF},
    # Tuning aid
    '%s:%s' % (A_EFD_80_10, SS_VNA):            {1: RELAY_NA, 2:RELAY_ON, 3:RELAY_ON, 4:RELAY_ON, 5:RELAY_ON, 6:RELAY_NA},
    '%s:%s' % (A_LOOP, SS_VNA):                 {1: RELAY_NA, 2:RELAY_ON, 3:RELAY_ON, 4:RELAY_NA, 5:RELAY_OFF, 6:RELAY_OFF},
}

# Default parameters
ANT_CTRL_RELAY_DEFAULT_STATE = {1: RELAY_OFF, 2:RELAY_OFF, 3: RELAY_OFF, 4: RELAY_OFF, 5: RELAY_OFF, 6: RELAY_OFF}
ANT_CTRL_ARDUINO_ADDR = ('192.168.1.178', 8888)
ANT_CTRL_ARDUINO_EVNT_PORT = 8889

# Loop Controller (part of Antenna defs) ===============
# Default parameters
LOOP_CTRL_RELAY_DEFAULT_STATE = {1: RELAY_OFF, 2:RELAY_OFF, 3: RELAY_OFF, 4: RELAY_OFF}
LOOP_CTRL_ARDUINO_ADDR = ('192.168.1.177', 8888)

ANTENNA_TO_LOOP_INTERNAL = {
    'LOOP-160': A_LOOP_160,
    'LOOP-80': A_LOOP_80,
    'LOOP-40': A_LOOP_40
}

ANTENNA_TO_LOOP_MATRIX = {
    A_LOOP_160: {1: RELAY_OFF, 2:RELAY_OFF, 3: RELAY_OFF, 4: RELAY_OFF},
    A_LOOP_80:   {1: RELAY_ON, 2:RELAY_ON, 3: RELAY_OFF, 4: RELAY_OFF},
}

# ===============================================================================
# VNA definitions

# Net interface defs
VNA_RQST_IP = '192.168.1.108'
VNA_RQST_PORT = 10002

VNA_LOCAL_IP = '127,0,0,1'
VNA_REPLY_PORT = 10003

VNA_TIMEOUT = 5.0
VNA_BUFFER = 1024

# Types
RQST_FRES = 'fres'
RQST_FSWR = 'fswr'
RQST_SCAN = 'scan'

WSPRRY_TO_FREQ = {
    '160m':   1836600,
    '80m':    3592600,
    '60m':    5287200,
    '40m':    7038600,
    '30m':    10138700,
    '20m':    14095600,
    '17m':    18104600,
    '15m':    21094600,
    '12m':    24924600,
    '10m':    28124600,
    '6m':     50293000,
    '4m':     70028600,
    '2m':     144488500,          
}