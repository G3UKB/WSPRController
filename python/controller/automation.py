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

import os, sys, traceback

from defs import *

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
        
    def __init__(self, scriptPath):
        
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
        self.__script = {}
        
        try:
            f = open(self.__scriptPath)
            lines = f.readlines()
        except Exception as e:
            print('Error in file access [%s][%s]' % (self.__scriptPath, str(e)))
        
        try:    
            # Process file
            cmd, value = lines[0].split(':')
            if cmd.lower() == 'run':
                if value.lower().contains('repeat'):
                    cmd, value = value.split(' ')
                    try:
                        count = int(value)
                    except Exception as e:
                        print('Syntax is REPEAT n[nnn..], found %s' % (lines[0]))
                        return False
                    self.__script[S_RUN] = [S_REPEAT, count]
                elif value.lower().contains('loop'):
                    self.__script[S_RUN] = [S_LOOP, None]
                elif value.lower().contains('once'):
                    self.__script[S_RUN] = [S_ONCE, None]
                else:
                    print("'RUN' line must contain REPEAT, LOOP or ONCE")
                    return False, None
            else:
                print("First line in the script file must be 'RUN'")
                return False, None
            
            cmd, value = lines[1].split(':')
            if cmd.lower() == 'stop':
                if value.lower().contains('idle'):
                    self.__script[S_STOP] = S_IDLE
                elif value.lower().contains('continue'):
                    self.__script[S_STOP] = S_CONTINUE
                else:
                    print("'STOP' line must contain IDLE or CONTINUE")
                    return False, None
            else:
                print("Second line in the script file must be 'STOP'")
                return False, None
            
            # Process command lines
            self.__script[S_COMMANDS] = []
            n = -1
            for line in lines:
                n += 1
                if n==0 or n==1: continue
                self.__script[S_COMMANDS].append([])
                toks = line.split(',')
                if len(toks) != 6:
                    print('Line %d in script file contains %d tokens, expected 6 [%s]' % (n, len(toks, line)))
                    return False, None
                # Line contains [band, tx, antenna, cycles, spot, radio]
                # Translate the items into an internal representation
                # Process BAND
                if toks[C_BAND] in BAND_TO_INTERNAL:
                    self.__script[S_COMMANDS][n-2].append(BAND_TO_INTERNAL[toks[C_BAND]])
                else:
                    print('Invalid band %s at line %d' % (toks[C_BAND], n))
                    return False, None
                # Process TX
                if toks[C_TX].lower() == 'false': tx = False
                elif toks[C_TX].lower() == 'true': tx = True
                else:
                    print('Invalid TX %s at line %d' % (toks[C_TX], n))
                    return False, None
                self.__script[S_COMMANDS][n-2].append(tx)
                # Process ANTENNA
                if toks[C_ANTENNA] in ANTENNA_TO_INTERNAL:
                    self.__script[S_COMMANDS][n-2].append(ANTENNA_TO_INTERNAL[toks[C_ANTENNA]])
                else:
                    print('Invalid antenna name %s at line %d' % (toks[C_ANTENNA], n))
                    return False, None
                # Process CYCLES
                try:
                    cycles = int(toks[C_CYCLES])
                    self.__script[S_COMMANDS][n-2].append(cycles)
                except Exception as e:
                    print('Invalid cycles number %s at line %d' % (toks[C_CYCLES], n))
                    return False, None
                # Process SPOT
                if toks[C_SPOT].lower() == 'false': spot = False
                elif toks[C_SPOT].lower() == 'true': spot = True
                else:
                    print('Invalid SPOT %s at line %d' % (toks[C_SPOT], n))
                    return False, None
                self.__script[S_COMMANDS][n-2].append(spot)
                # Process RADIO
                if toks[C_RADIO].lower() == 'internal': radio = R_INTERNAL
                elif toks[C_RADIO].lower() == 'external': radio = R_EXTERNAL
                else:
                    print('Invalid RADIO %s at line %d' % (toks[C_RADIO], n))
                    return False, None
                self.__script[S_COMMANDS][n-2].append(radio)
        except Exception as e:
            print('Error in file processing [%s][%s][%s]' % (self.__scriptPath, str(e), traceback.format_exc()))
            return False, None
        
        return True, self.__script
                
#======================================================================================================================
# Main code
def main():
    
    try:
        # The application 
        app = Automate('..\\scripts\\script-1.txt')
        # Run application
        r, struct = app.parseScript()
        print (struct)
        sys.exit(0)
        
    except Exception as e:
        print ('Exception','Exception [%s][%s]' % (str(e), traceback.format_exc()))
 
# Entry point       
if __name__ == '__main__':
    main()            