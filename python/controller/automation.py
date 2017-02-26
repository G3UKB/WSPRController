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

import os, sys, socket, traceback
import threading
from time import sleep

from defs import *
# We need to pull in antennaControl and cat from the Common project
sys.path.append(os.path.join('..','..','..','..','Common','trunk','python'))
import antcontrol
import cat

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
        
        # Create command socket
        self.__cmdSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Start the event thread
        self.__eventThrd = EventThrd(self.__evntCallback)
        self.__eventThrd.start()
        
        # Create the event objects
        self.__bandEvt = threading.Event()
        self.__cycleEvt = threading.Event()
        self.__catEvt = threading.Event()
        self.__relayEvt = threading.Event()
        
        # Instance vars
        self.__waitingBandNo = None
        self.__catRunning = False
        
        # Create the antenna controller
        self.__antControl = antcontrol.AntControl(ARDUINO_ADDR, RELAY_DEFAULT_STATE, self.__antControlCallback)
    
        # Create the CAT controller
        self.__cat = cat.CAT(IC7100, CAT_SETTINGS)
        if self.__cat.start_thrd():
            self.__catRunning = True
        self.__cat.set_callback(self.__catCallback)    
        
    def terminate(self):
        """ Terminate and exit """
        
        self.__eventThrd.terminate()
        self.__eventThrd.join()
        self.__cat.terminate()
    
    # =================================================================================
    # Main processing     
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
            return
        try:    
            # Process file
            cmd, value = lines[0].split(':')
            if cmd.lower() == 'run':
                if 'repeat' in value.lower():
                    cmd, value = value.split(' ')
                    try:
                        count = int(value)
                    except Exception as e:
                        print('Syntax is REPEAT n[nnn..], found %s' % (lines[0]))
                        return False
                    self.__script[S_RUN] = [S_REPEAT, count]
                elif 'loop' in value.lower():
                    self.__script[S_RUN] = [S_LOOP, None]
                elif 'once' in value.lower():
                    self.__script[S_RUN] = [S_ONCE, None]
                else:
                    print("'RUN' line must contain REPEAT, LOOP or ONCE")
                    return False, None
            else:
                print("First line in the script file must be 'RUN'")
                return False, None
            
            cmd, value = lines[1].split(':')
            if cmd.lower() == 'stop':
                if 'idle' in value.lower():
                    self.__script[S_STOP] = S_IDLE
                elif 'continue' in value.lower():
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
                line = line.strip('\n\r')
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
    
    def executeScript(self):
        """ Execute according to the internal structure"""
        
        try:
            # Get the iteration instruction.
            if self.__script[S_RUN][0] == S_REPEAT:
                iterationCount = self.__script[S_RUN][1]
            elif self.__script[S_RUN][0] == S_LOOP:
                iterationCount = -1
            else:
                iterationCount = 1
            # Get the termination instruction.    
            if self.__script[S_STOP] == S_IDLE:
                idle = True
            else:
                idle = False   
            while True:
                # Do one run through the script
                # if we hit an error we report on the instruction and the error then skip the line
                # and attempt to carry on.
                for instruction in self.__script[S_COMMANDS]:
                    sleep(3)
                    # Unpack
                    band, tx, antenna, cycles, spot, radio = instruction                    
                    # This will only return when the band change completes
                    if not self.__doBand(band):
                        continue
                    if not self.__doTx(tx):
                        continue
                    if not self.__doAntenna(antenna, band):
                        continue
                    if not self.__doSpot(spot):
                        continue
                    if not self.__doRadio(radio, band):
                        continue
                    # This will only return when the cycles are complete
                    if not self.__doCycles(cycles):
                        continue
                if iterationCount > 1:
                    iterationCount -= 1
                elif iterationCount != -1:
                    # Time to go
                    if idle:
                        # Requested to put WSPR into IDLE
                        self.__doIdle(True)
                    break                    
        
        except Exception as e:
            print('Error in script execution [%s][%s]' % (str(e), traceback.format_exc()))
            return False
    
        return True
    
    # =================================================================================
    # Callback
    def __evntCallback(self, evnt):
        """
        Process event from WSPR
        
        Arguments:
            evnt    --  'band:n'
                        'cycle'
        
        """
        
        if 'band' in evnt:
            if self.__waitingBandNo != None:            
                _, bandNo = evnt.split(':')
                if bandNo == self.__waitingBandNo:
                    self.__bandEvt.set()
        elif 'cycle' in evnt:
            self.__cycleEvt.set()
    
    def __antControlCallback(self, msg):
        """
        Callbacks from antenna control
        
        Arguments:
            msg    --  msg to report
        
        """
        
        if 'success' in msg:
            self.__relayEvt.set()
        
    def __catCallback(self, msg):
        """
        Callbacks from CAT control
        
        Arguments:
            msg    --  msg to report
        
        """
        
        if msg[0]:
            self.__catEvt.set()
        else:
            print('CAT reported: ', msg)
        
    # =================================================================================
    # Execution functions
    def __doBand(self, band):
        """
        Instruct WSPR to change band.
        Wait for the band changed event as it will only do this when IDLE
        
        Arguments:
            band    --  the internal band id
            
        """
        
        # Tell the event what we are waiting for
        self.__waitingBandNo = BAND_TO_EXTERNAL[band]
        
        # Send the UDP command to WSPR to change band
        self.__cmdSock.sendto(('band:%d' % BAND_TO_EXTERNAL[band]).encode('utf-8'), (CMD_IP, CMD_PORT))
        # Wait for WSPR to change bands
        # This can take up to 2m as switching occurs during IDLE
        timeout = EVNT_TIMEOUT * 30 # Allow 150s
        if not self.__bandEvt.wait(EVNT_TIMEOUT):
            timeout -= EVNT_TIMEOUT
            if timeout <= 0:
                # Timeout waiting for the band switch
                print('Timeout waiting for WSPR to switch bands!')
                return False
        self.__bandEvt.clear()
        self.__waitingBandNo = None
        return True
             
    def __doTx(self, tx):
        """
        Instruct WSPR to set the TX feature to 0% or 20%
        
        Arguments:
            tx    --  True = 20%, False = 0%
            
        """
        
        if tx: cmd = 1
        else: cmd = 0
        self.__cmdSock.sendto(('tx:%d' % cmd).encode('utf-8'), (CMD_IP, CMD_PORT))
    
    def __doAntenna(self, antenna, band):
        """
        Instruct the antenna switching module to switch to the given antenna
        Note this depends on the band
        
        Arguments:
            antenna     --  the internal antenna name
            band        --  the internal band name
            
        """
        
        if band == B_2: table = ANTENNA_TO_VU_MATRIX
        else: table = ANTENNA_TO_HF_MATRIX
        
        matrix = table[antenna]
        for relay, state in matrix.items():
            if relay != RELAY_NA:
                self.__antControl.set_relay(relay, state)
                if not self.__relayEvt.wait(EVNT_TIMEOUT):
                    print('Timeout waiting for antenna changeover to respond to relay change!')
                    return False
                self.__relayEvt.clear()
        return True
    
    def __doSpot(self, spot):
        """
        Instruct WSPR to set the spot feature on or off
        
        Arguments:
            spot    --  True = ON, False = OFF
            
        """
        
        if spot: cmd = 1
        else: cmd = 0
        self.__cmdSock.sendto(('upload:%d' % cmd).encode('utf-8'), (CMD_IP, CMD_PORT))
    
    def __doRadio(self, radio, band):
        """
        If external then do nothing.
        If internal then use a CAT command to change the radio frequency.
        The band idntifies the frequency via a lookup table.
        
        Arguments:
            radio    --  R_INTERNAL or R_EXTERNAL
            band     --  the internal band name
            
            
        """
        
        if radio == R_INTERNAL:
            # Check connectivity
            if not self.__catRunning:
                if self.__cat.start_thrd():
                    self.__catRunning = True
                else:
                    return False
                    
            # Get the frequency for the band
            dialFrequency = BAND_TO_FREQ[band]
            self.__catEvt.clear()
            self.__cat.do_command(CAT_MODE_SET, MODE_USB)
            #if not self.__catEvt.wait(EVNT_TIMEOUT):
            if not self.__catEvt.wait(10):
                print('Timeout waiting for radio to respond to mode change!')
                return False
            self.__catEvt.clear()
            self.__cat.do_command(CAT_FREQ_SET, dialFrequency)
            #if not self.__catEvt.wait(EVNT_TIMEOUT):
            if not self.__catEvt.wait(10):
                print('Timeout waiting for radio to respond to frequency change!')
                return False
            self.__catEvt.clear()
            return True                
    
    def __doCycles(self, cycles, tx):
        """
        Wait for WSPR to execute 'cycles' cycles.
        A cycle is either an RX cycle or an RX followed by a TX cycle
        
        Arguments:
            cycles    --  the number of cycles to wait for
            tx        --  True if running TX cycles
            
        """
        
        # Cycles are 2 mins for an RX and 2 mins for a TX
        # Calculate the total timeout for the number of cycles
        # Add extra as we could be idle waiting to start
        txtime = 0
        if tx: txtime = (EVNT_TIMEOUT * 24) * cycles/5
        timeout = int((EVNT_TIMEOUT * 24 * cycles) + txtime)
        # Add extra 2m as we could be idle waiting to start
        timeout = timeout + 120
        cycleCount = cycles
        while True:
            if not self.__cycleEvt.wait(EVNT_TIMEOUT):
                timeout -= EVNT_TIMEOUT
                if timeout <= 0:
                    # Timeout waiting for the cycle count
                    print('Timeout waiting for WSPR to complete %d cycles. Aborted at cycle %d!' % (cycles, cycleCount))
                    return False
            self.__cycleEvt.clear()
            cycleCount -= 1
            if cycleCount <= 0:
                # All done
                break
        return True
    
    def __doIdle(self, state):
        """
        Instruct WSPR to enter the IDLE mode.
        
        Arguments:
            state    --  True == IDLE
            
        """
        
        if state: cmd = 1
        else: cmd = 0
        self.__cmdSock.sendto(('idle:%d' % cmd).encode('utf-8'), (CMD_IP, CMD_PORT))
    
"""

Event thread.
Receive events from WSPR.

"""
class EventThrd (threading.Thread):
    
    def __init__(self, callback):
        """
        Constructor
        
        Arguments
            callback    -- callback here for event notifications
        """

        super(EventThrd, self).__init__()
        
        self.__callback = callback
        
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__sock.bind((EVNT_IP, EVNT_PORT))
        self.__sock.settimeout(3)
        
        self.__terminate = False
    
    def terminate(self):
        """ Terminate thread """
        
        self.__terminate = True
        
    def run(self):
        # Listen for events
        while not self.__terminate:
            try:
                data, addr = self.__sock.recvfrom(100)
            except socket.timeout:
                continue
            asciidata = data.decode(encoding='UTF-8')
            self.__callback(asciidata)

       
#======================================================================================================================
# Main code
def main():
    
    app = None
    try:
        # The application
        print('Starting automation run...')
        app = Automate(os.path.join('..', 'scripts', 'script-1.txt'))
        # Parse the file
        r, struct = app.parseScript()
        if r:
            #print (struct)
            r = app.executeScript()
            if not r:
                print('Execution error!')
        else:
            print('Error in parse!')
        if app != None: app.terminate()
        sys.exit(0)
    except KeyboardInterrupt:
        print('User terminated - exiting')
        if app != None: app.terminate()
        sys.exit()    
    except Exception as e:
        print ('Application Exception [%s][%s] - exiting' % (str(e), traceback.format_exc()))
        if app != None: app.terminate()
        sys.exit()  
    print('Automation run complete - exiting')
    sys.exit()
    
# Entry point       
if __name__ == '__main__':
    main()            