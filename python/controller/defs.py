#!/usr/bin/env python3
#
# automation.py
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

# Command section
S_COMMANDS = 'scommands'
# Offsets into command structure
C_BAND = 0
C_TX = 1
C_ANTENNA = 2
C_CYCLES = 3
C_SPOTspot = 4
C_RADIO = 5

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
    '80':   B80,
    '60':   B60,
    '40':   B40,
    '30':   B30,
    '20':   B20,
    '17':   B17,
    '15':   B15,
    '12':   B12,
    '10':   B6,
    '6':    B6,
    '4':    B4,
    '2':    B2,       
}

# Key = entry in internal table
# Value = id to be used externally (i.e. WSPR)
BAND_TO_EXTERNAL = {
    B_160:  2,
    B80:    3,
    B60:    4,
    B40:    5,
    B30:    6,
    B20:    7,
    B17:    8,
    B15:    9,
    B12:    10,
    B6:     11,
    B6:     12,
    B4:     13,
    B2:     14,       
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
ANTENNA_TO_HF_MATRIX = {
    A_LOOP_160:     {1: R_ON, 2:R_NA, 3: R_OFF, 4: R_NA},
    A_LOOP_80:      {1: R_ON, 2:R_NA, 3: R_OFF, 4: R_NA},
    A_EFD_80_10:    {1: R_OFF, 2:R_NA, 3: R_OFF, 4: R_NA},
    A_DIPOLE_6_4_2: {1: R_NA, 2:R_ON, 3: R_ON, 4: R_ON},
    A_VERT_6_4_2:   {1: R_NA, 2:R_OFF, 3: R_ON, 4: R_ON},
}

ANTENNA_TO_VU_MATRIX = {
    A_DIPOLE_6_4_2: {1: R_NA, 2:R_ON, 3: R_NA, 4: R_OFF},
    A_VERT_6_4_2:   {1: R_NA, 2:R_OFF, 3: R_NA, 4: R_OFF},
}