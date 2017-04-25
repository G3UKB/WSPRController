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

# System imports
import os, sys, socket, traceback
import threading
from time import sleep
import datetime
import math
import logging
import logging.handlers

# Application imports
from defs import *
# We need to pull in antennacontrol, loopcontrol and cat from the Common project
sys.path.append(os.path.join('..','..','..','..','Common','trunk','python'))
import antcontrol
import loopcontrol
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
        RUN: REPEAT n (where n > 0) | LOOP (until the program is terminated) | ONCE (execute once and exit)
        STOP: idle (on exit set WSPR to IDLE mode | continue (on exit leave WSPR running as of the last command)
        POWER: n.n (where n.n is the TX power in watts)
    Each subsequent line is a command.
        band,       # From the band enumeration
        tx,         # True == 20% TX cycle | False == 0% TX cycle
        power       # Actual output power required in watts
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
        
    def __init__(self, scriptPath, COMPort):
        
        self.__scriptPath = scriptPath
        self.__comPort = COMPort
        
        CAT_SETTINGS[SERIAL][0] = self.__comPort
        
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
        self.__loopEvt = threading.Event()
        
        # Instance vars
        self.__waitingBandNo = None
        self.__catRunning = False
        
        # Create the antenna controller
        self.__antControl = antcontrol.AntControl(ANT_CTRL_ARDUINO_ADDR, ANT_CTRL_RELAY_DEFAULT_STATE, self.__antControlCallback)
        
        # Create the loop controller
        self.__loopControl = loopcontrol.LoopControl(LOOP_CTRL_ARDUINO_ADDR, self.__loopControlCallback, self.__loopEvntCallback)
        # Allow full 180 for the moment
        self.__loopControl.setLowSetpoint(0)
        self.__loopControl.setHighSetpoint(180)
        # Low to medium speed
        self.__loopControl.speed(MOTOR_SPEED)
        
        # Create the CAT controller
        self.__cat = cat.CAT(IC7100, CAT_SETTINGS)
        if self.__cat.start_thrd():
            self.__catRunning = True
        self.__cat.set_callback(self.__catCallback)
        
        # Set up logging
        self.__logger = logging.getLogger('auto')
        self.__logger.setLevel(logging.INFO)
        format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)-5s - %(message)s")
        if not os.path.exists(os.path.join('..', 'logs')):
            os.mkdir(os.path.join('..', 'logs'))
        handler = logging.handlers.RotatingFileHandler(os.path.join('..', 'logs', 'auto.log'), maxBytes=100000, backupCount=5)
        handler.setLevel(logging.INFO)
        handler.setFormatter(format)
        self.__logger.addHandler(handler)
        
        self.__logger.log (logging.INFO, '\n\n\n\nSession starting...')
        
    def terminate(self):
        """ Terminate and exit """
        
        self.__eventThrd.terminate()
        self.__eventThrd.join()
        self.__cat.terminate()
        self.__loopControl.terminate()
    
    # =================================================================================
    # Main processing     
    def parseScript(self):
        
        """
        Parse the script file into an internal structure of the following form:
        
            {
                S_RUN: [S_REPEAT|S_LOOP|S_ONCE, param, param, ...],
                S_STOP: S_IDLE | S_CONTINUE,
                S_POWER: n.n watts,
                S_COMMANDS: [
                    [start, end, band, tx, power, antenna, cycles, spot, radio],
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
                print("Line 1 in the script file must be 'RUN'")
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
                print("Line 2 in the script file must be 'STOP'")
                return False, None
            
            cmd, value = lines[2].split(':')
            if cmd.lower() == 'power':
                try:
                    value = float(value)
                    self.__script[S_POWER] = value
                except Exception:
                    print('POWER line must have a value numerical power')
                    return False, None
            else:
                print("Line 3 in the script file must be 'POWER'")
                return False, None    
                
            # Process command lines
            self.__script[S_COMMANDS] = []
            n = -1
            for line in lines:
                line = line.strip('\n\r')
                n += 1
                if n==0 or n==1 or n==2: continue
                self.__script[S_COMMANDS].append([])
                toks = line.split(',')
                if len(toks) != 9:
                    print('Line %d in script file contains %d tokens, expected 9 [%s]' % (n, len(toks), line))
                    return False, None
                # Line contains [start, end, band, tx, power, antenna, cycles, spot, radio]
                # Translate the items into an internal representation
                # process TIME
                if int(toks[C_START]) < 0 or int(toks[C_START]) > 23 or int(toks[C_STOP]) < 0 or int(toks[C_STOP]) > 23:
                    print('Invalid timespan %s, %s at line %d' % (toks[C_START], toks[C_STOP], n))
                    return False, None
                self.__script[S_COMMANDS][n-3].append(int(toks[C_START]))
                self.__script[S_COMMANDS][n-3].append(int(toks[C_STOP]))
                # Process BAND
                if toks[C_BAND] in BAND_TO_INTERNAL:
                    self.__script[S_COMMANDS][n-3].append(BAND_TO_INTERNAL[toks[C_BAND]])
                else:
                    print('Invalid band %s at line %d' % (toks[C_BAND], n))
                    return False, None
                # Process TX
                if toks[C_TX].lower() == 'false': tx = False
                elif toks[C_TX].lower() == 'true': tx = True
                else:
                    print('Invalid TX %s at line %d' % (toks[C_TX], n))
                    return False, None
                self.__script[S_COMMANDS][n-3].append(tx)
                # Process power
                if float(toks[C_PWR]) >= 0.001 and float(toks[C_PWR]) <= 5.0:
                    if float(toks[C_PWR]) > self.__script[S_POWER]:
                        print('Power level in line %d is greater than the available TX power!' % (n))
                        return False, None
                    self.__script[S_COMMANDS][n-3].append(float(toks[C_PWR]))
                else:
                    print('Power must be between 0.001 and 5.0 watts')
                    return False, None
                # Process ANTENNA
                if toks[C_ANTENNA] in ANTENNA_TO_INTERNAL:
                    self.__script[S_COMMANDS][n-3].append(ANTENNA_TO_INTERNAL[toks[C_ANTENNA]])
                else:
                    print('Invalid antenna name %s at line %d' % (toks[C_ANTENNA], n))
                    return False, None
                # Process CYCLES
                try:
                    cycles = int(toks[C_CYCLES])
                    self.__script[S_COMMANDS][n-3].append(cycles)
                except Exception as e:
                    print('Invalid cycles number %s at line %d' % (toks[C_CYCLES], n))
                    return False, None
                # Process SPOT
                if toks[C_SPOT].lower() == 'false': spot = False
                elif toks[C_SPOT].lower() == 'true': spot = True
                else:
                    print('Invalid SPOT %s at line %d' % (toks[C_SPOT], n))
                    return False, None
                self.__script[S_COMMANDS][n-3].append(spot)
                # Process RADIO
                if toks[C_RADIO].lower() == 'internal': radio = R_INTERNAL
                elif toks[C_RADIO].lower() == 'external': radio = R_EXTERNAL
                else:
                    print('Invalid RADIO %s at line %d' % (toks[C_RADIO], n))
                    return False, None
                self.__script[S_COMMANDS][n-3].append(radio)
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
            # Make sure we are not idle
            self.__doIdle(False)
            while True:
                # Do one run through the script
                # if we hit an error we report on the instruction and the error then skip the line
                # and attempt to carry on.
                for instruction in self.__script[S_COMMANDS]:
                    sleep(3)
                    # Unpack
                    startHour, stopHour, band, tx, power, antenna, cycles, spot, radio = instruction
                    print('Processing: ', startHour, stopHour, band, tx, power, antenna, cycles, spot, radio, ' ...')
                    # Check if time to run this cycle
                    runCycle = False
                    currentHour = datetime.datetime.now().hour
                    if (startHour == 0 and stopHour == 0):
                        # This means all day
                        runCycle = True
                    elif stopHour < startHour:
                        # Crossing midnight
                        if currentHour <= stopHour:
                            # Past midnight
                            runCycle = True
                        else:
                            # Before midnight
                            if currentHour >= startHour:
                                runCycle = True
                    else:
                        # Normal progression
                        if startHour <= currentHour and stopHour >= currentHour:
                            runCycle = True
                    if not runCycle: continue
                    
                    # Run starting
                    self.__logger.log (logging.INFO, 'Running -- StartHr: %s, StopHr: %s, Band: %s, TX: %s, Power: %s, Antenna: %s, Cycles: %s, Spot: %s, Radio: %s' % (startHour, stopHour, band, tx, power, antenna, cycles, spot, radio))
                    # This will only return when the band change completes
                    if not self.__doBand(band):
                        self.__doReset()
                        print('Band failed')
                        continue
                    sleep(0.1)
                    print('Done Band')
                    if not self.__doTx(tx, power):
                        self.__doReset()
                        print('TX failed')
                        continue
                    sleep(0.1)
                    print('Done TX')
                    if not self.__doAntenna(antenna, band):
                        self.__doReset()
                        print('Antenna failed')
                        continue
                    sleep(0.1)
                    print('Done Antenna')
                    if not self.__doSpot(spot):
                        self.__doReset()
                        print('Spot failed')
                        continue
                    sleep(0.1)
                    print('Done Spot')
                    if not self.__doRadio(radio, band):
                        self.__doReset()
                        print('Radio failed')
                        continue
                    sleep(0.1)
                    print('Done Radio')
                    # This will only return when the cycles are complete
                    if not self.__doCycles(cycles, tx):
                        self.__doReset()
                        print('Cycle failed')
                        continue
                    sleep(0.1)
                    self.__logger.log (logging.INFO, '--Run complete--')
                    print('Done Cycles')
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
                if int(bandNo) == self.__waitingBandNo:
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
    
    def __loopControlCallback(self, msg):
        """
        Callbacks from loop control
        
        Arguments:
            msg    --  msg to report
        
        """
        
        try:
            # This set comes from command completions via magcontrol
            if 'success' in msg:
                # Completed, so reset
                self.__loopEvt.set()
            elif 'failure' in msg:
                # Error, so reset
                _, reason = msg.split(':')
                print('Loop Control failed [%s]' % (reason))
            elif 'offline' in msg:
                print('Loop Controller is offline!')
        except Exception as e:
            print ('Exception getting loop response! [%s]', str(e))
     
    def __loopEvntCallback(self, msg):
        """
        Callbacks from loop control
        
        Arguments:
            msg    --  msg to report
        
        """
        
        # Ignore for now
        pass
        
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
        r = False
        while True:
            if self.__bandEvt.wait(EVNT_TIMEOUT):
                r = True
                break
            else:
                timeout -= EVNT_TIMEOUT
                if timeout <= 0:
                    # Timeout waiting for the band switch
                    print('Timeout waiting for WSPR to switch bands!')
                    break
        self.__bandEvt.clear()
        self.__waitingBandNo = None
        return r
             
    def __doTx(self, tx, power):
        """
        Instruct WSPR to set the TX feature to 0% or 20%
        
        Arguments:
            tx    --  True = 20%, False = 0%
            
        """
        
        if tx:
            cmd = 1
            # Do any power correction
            availablePwr = self.__script[S_POWER]
            if power != availablePwr:
                powerdBm = self.__powertodbm(power)
                availablePwrdBm = self.__powertodbm(availablePwr)
                diffdBm = availablePwrdBm - powerdBm
                if diffdBm > 30: diffdBm = 30
                self.__cmdSock.sendto(('power:%d' % diffdBm).encode('utf-8'), (CMD_IP, CMD_PORT))
        else:
            cmd = 0
        # Do TX command
        self.__cmdSock.sendto(('tx:%d' % cmd).encode('utf-8'), (CMD_IP, CMD_PORT))
        return True
    
    def __doAntenna(self, antenna, band):
        """
        Instruct the antenna switching module to switch to the given antenna
        Note this depends on the band
        
        Arguments:
            antenna     --  the internal antenna name
            band        --  the internal band name
            
        """
        
        # First main an tenna switching
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
                
        # Loop control
        if antenna == A_LOOP_160 or antenna == A_LOOP_80:
            # Switch the relays to the 160 position
            matrix = ANTENNA_TO_LOOP_MATRIX[antenna]
            for relay, state in matrix.items():
                if state == RELAY_OFF: state = 0
                else: state = 1
                self.__loopControl.setRelay((relay, state))
                if not self.__loopEvt.wait(EVNT_TIMEOUT):
                    print('Timeout waiting for loop changeover to respond to relay change!')
                    return False
            # Set the motor and position parameters
            self.__loopControl.setCapMaxSetpoint(ANTENNA_TO_LOOP_POSITION[antenna][L_SETPOINTS][0])
            if not self.__loopEvt.wait(EVNT_TIMEOUT):
                print('Timeout waiting for loop changeover to respond to cap max change!')
                return False
            self.__loopControl.setCapMinSetpoint(ANTENNA_TO_LOOP_POSITION[antenna][L_SETPOINTS][1])
            if not self.__loopEvt.wait(EVNT_TIMEOUT):
                print('Timeout waiting for loop changeover to respond to cap min change!')
                return False
            self.__loopControl.setLowSetpoint(ANTENNA_TO_LOOP_POSITION[antenna][L_BAND][0])
            if not self.__loopEvt.wait(EVNT_TIMEOUT):
                print('Timeout waiting for loop changeover to respond to low freq change!')
                return False
            self.__loopControl.setHighSetpoint(ANTENNA_TO_LOOP_POSITION[antenna][L_BAND][0])
            if not self.__loopEvt.wait(EVNT_TIMEOUT):
                print('Timeout waiting for loop changeover to respond to high freq change!')
                return False
            # Set the position for 160m or 80m WSPR dial frequency
            self.__loopControl.move(ANTENNA_TO_LOOP_POSITION[antenna][L_POSITION])
            if not self.__loopEvt.wait(EVNT_TIMEOUT*2):
                print('Timeout waiting for loop changeover to respond to position change!')
                return False
        
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
        return True
    
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
            if not self.__catEvt.wait(EVNT_TIMEOUT*2):
                print('Timeout waiting for radio to respond to mode change!')
                return False
            self.__catEvt.clear()
            self.__cat.do_command(CAT_FREQ_SET, dialFrequency)
            if not self.__catEvt.wait(EVNT_TIMEOUT*2):
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
        cycles = int(cycles)
        if tx: txtime = (EVNT_TIMEOUT * 24) * cycles/5
        timeout = int((EVNT_TIMEOUT * 24 * cycles) + txtime)
        # Give a generous amount as we have waiting periods to account for
        timeout = timeout * 2
        cycleCount = cycles
        print('Waiting for %d cycles with timeout %ds' % (cycleCount, timeout))
        while True:
            if self.__cycleEvt.wait(EVNT_TIMEOUT):
                self.__cycleEvt.clear()
                print('Cycle %d complete at timeout %ds' % (cycles - cycleCount + 1, timeout) )
                cycleCount -= 1
                if cycleCount <= 0:
                    # All done
                    break
            else:
                timeout -= EVNT_TIMEOUT
                if timeout <= 0:
                    # Timeout waiting for the cycle count
                    print('Timeout waiting for WSPR to complete %d cycles. Aborted at cycle %d!' % (cycles, cycles - cycleCount + 1))
                    return False
                else:
                    continue           
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
        return True
    
    def __doReset(self):
        """
        Instruct WSPR to reset.
        
        Arguments:
            
        """
        
        self.__cmdSock.sendto('reset'.encode('utf-8'), (CMD_IP, CMD_PORT))
        return True
    
    # =======================================================================================
    # Helpers
    
    def __powertodbm(self, power):
        """
        Convert power level to dbM
        
        Aerguments
            power   --  power in watts to convert
        
        """
        
        return int(10*math.log10(power*1000))
        
    def __dBmtopower(self, dBm):
        """
        Convert dbM to power in watts
        
        Arguments:
            dBm     --  dBm level to convert
        
        """
        
        return round(math.pow(10, dBm/10)/1000)
        
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
        
        # Arguments are:
        #   arg0 program name (always)
        #   arg1    --  path to script file
        #   arg2    --  COM port for CAT control
        #
        if len(sys.argv) != 3:
            print('Usage: python automation.py path-to-script-file, COM-port-for-CAT')
            sys.exit(0)
        path = sys.argv[1]
        com = sys.argv[2]
        if not os.path.exists(path):
            print('Error: Invalid path to script file!')
            sys.exit(0)
            
        print('Starting automation run...')
        app = Automate(path, com)
        # Parse the file
        r, struct = app.parseScript()
        if r:
            #print (struct)
            r = app.executeScript()
            if not r:
                print('Error: Execution error!')
        else:
            print('Error: Failed in parse!')
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