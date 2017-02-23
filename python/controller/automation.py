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

"""

Automate WSPR and auxiliary equipment to control rig and antennas.
The programs reads from a control file with instructions to receive
and transmit on various bands for various cycle times with variable
parameters.

"""

class Automate:
    
    """
    
    The script file is a csv file.
    
    The first two entries in the file are special.
        Run: repeat n (where n > 0) | loop (until the program is terminated) | once (execute once and exit)
        Stop: idle (on exit set WSPR to IDLE mode | continue (on exit leave WSPR running as of the last command)
    Each subsequent line is a command.
        band,       # From the band enumeration
        tx,         # True == 20% TX cycle | False == 0% TX cycle
        antenna,    # From the antenna enumeration (what this means is implementation dependent)
        cycles,     # The number of complete RX cycles to perform before moving to the next command
        spot,       # True == upload spots, False == do not upload spots
        radio       # Internal == manage the radio via CAT | External == WSPR or something else is managing the radio
        
    The file will execute line by line and then obey the Run/Stop entries.
    
    A log file is written to enable subsequent analysis of the results.
    Two versions of the file are written:
        A human readable version using the standard log package.
        A machine readable version for automatic analysis.
        
        format - starttimestamp, endtimestamp, command (as in script file)
        
    This machine readable log file together with a download of the spots file for the last day from wsprnet
    can/will be used to generate analysis files.
    
    """
        
    def __init__(self, filePath):
        
        self.__scriptPath = scriptPath
        
    def parseScript(self):
        
        """
        Parse the script file into an internal structure of the following form:
        
            {
                S_RUN: [S_REPEAT|S_LOOP|S_ONCE, param, param, ...],
                S_STOP: S_IDLE | S_CONTINUE,
                S_COMMANDS: [
                    [band, tx, antenna, cycles, spot, radio],
                    [ ... ],
                    ...
                ]
            }
            
        """
        
        