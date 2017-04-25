#!/usr/bin/env python3
#
# wsprauto.py
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
This programs reads from a script file with instructions to receive
and transmit on various bands for various cycle times with variable
parameters.

The program will run on Windows or Linux, including the RPi but is
targetted at the RPi as a complete WSPR station when using 3, 4 below.

Currently this program supports the following hardware:
    1. Icom tranceivers RX/TX (specifically the 7100) via CAT.
    2. Yausu tranceivers RX/TX (specifically the FT-857D) via CAT.
    3. FunCubeDonglePro+ via direct USB HID commands. Intended
    for RPi3 host but may be used on any computer. When used with
    RPi requires firmware upgrade to drop sample rate to 48Kb
    as the RPi cannot cope with the default 192Kb.
    4. RPi3 bareback TX via software.
    
Currently this program supports the following software:
    1. WSPR 2.1 (https://physics.princeton.edu/pulsar/k1jt/wspr.html)
    with stereo audio or I/Q inputs. The program must be configured
    manually for the required operation. It can be used
    for RX only in conjunction with (4 above + 2 below) or full RX/TX
    in conjunction with (1, 2 above). Note that WSPR has been modified
    to accept external commands via UDP.
    2. JamesP6000/WsprryPi (https://github.com/JamesP6000/WsprryPi)bareback
    for direct RPi 3 TX excitation.
    3. csete/fcdctl command line program (https://github.com/csete/fcdctl)
    for sending HID commands to FunCubeDonglePro+ for setting frequency etc.
    
Bespoke support:
As well as the hardware and software support above which is commercial or
open source the program supports specific hardware developed by the author.
Although this is bespoke hardware the fuctions are generic and may be required
in some form for other implementations. The interface to the controlling modules
has been made as generic as possible such that the implementation modules can
be more easily replaced as required for different implementations.
    1. LPF's and LPF switching. When using a TX capability that does not have
    inbuilt LPF's such as the barefoor RPi these filters must be supplied externally.
    The author uses a SotaBeams LPF kit for 160/80/40
    (http://www.sotabeams.co.uk/low-pass-filter-kit/) as these are the main bands
    of interest for TX. This PCB has no on-board switching so this is provided
    using the RPi GPIO and an 8 relay switching module.
    2. Main antenna switching. Whether using commercial tranceivers or the self
    contained RPi station it is probably necessary to route different antenna to
    the various inputs and outputs of the system. In the case of the RPi station for
    example it is possible to TX and RX on different bands concurrently and then switch
    antennas to change the TX/RX bands. In addition it may also be required to switch
    antennas to the main station. The author has a switch system that supports
    comprehensive routing in a many to many configuration.
    3. Antenna tuning. This may be an area of difficulty when using antennas that require
    tuning on different bands. Auto-tuners will not work at very low power (RPi barefoot
    outputs 10mW). Thus if tuning is required and there is insufficient power for an
    auto-tuner the tuner must support set-points for different frequencies. The autor
    currently uses an End Fed Dipole which will support 40/20/15/10 without tuning and
    160/80 loops that require tuning but are supported by a loop tuning system that
    can be configured with frequency setpoints.
    

"""

class Automate:
    
    """
    
    The script file consists of commands and comments.
    
    The commands are at a fairly fine granularity such that most of the logic to do what and
    when is in the script file rather than have a simple script file with most of the logic
    hard coded. This scheme makes the script file longer and harder to write but makes it more
    definitive and makes changing the what and when, adding and removing features much easier to do.
    
    Command lines are of this form:
        Major command: [Params | Minor command] [param, param, ...]
        Minor command/params are comma separated
        
    Comments start with # in the first column and can only extend over one line.
        
    Command types:
      Control commands:
        SEQ         # Start a sequence
        ENDSEQ      # End of loop
        TIME        # Start a time banded section
        ENDTIME     # End a time banded section
        PAUSE       # Pause the script file
        COMPLETE    # Script complete
      Hardware commands:
        LPF         # Commands related to the LPF filters
        ANTENNA     # Commands related to antenna switching
        LOOP        # Commands related to the loop switching and tuning
        RADIO       # CAT commands to external radios
      Software commands:
        WSPR        # Commands related to WSPR
        WSPRRYPI    # Commands related to WsprryPi        
        FCD         # Commands related to the FunCubeDonglePro+
    
    Command lines:
      Control commands:
        SEQ, n      # Iterate to END n times. If n is -1 iterate for ever.
        ENDSEQ      # Loopback to last SEQ while iteration < n
        TIME, start, end
                    # The commands banded by TIME and ENDTIME to be executed only between start, end time in hours
                    # 24 hour clock.
        ENDTIME     SKIP to ENDTIME if time criteria not met
        PAUSE, n.n  # Pause execution for n.n seconds
        COMPLETE    # End of script
      Hardware commands:
        LPF, band   # Where band is 160/80/40 etc. Mapping is involved to relay activation.
        ANTENNA, source, dest
                    # Sets up a route between an antenna and a destination TX or RX capability.
                    # e.g. 160-Loop, FCDPro+. Mapping is involved to relay activation.
        LOOP, band, extension
                    # Switch the loop to band, and extend the actuator to % extension.
        RADIO,  CAT, radio, com_port, baud_rate
                    # Supported radios IC7100 | FT817, baud-rate. Must be executed to initiate CAT control.
                FREQ, MHz
                    # Set the radio frequency to MHz using CAT
                MODE, LSB|USB|...
                    # Set the radio mode using CAT
      Software commands:
        WSPR    INVOKE                  # Invoke WSPR if not running. Must be running before any other WSPR command.
                IDLE, on|off            # Set idle on/off, i.e stop RX/TX
                BAND, 160|80|40|...     # Set band for reporting
                TX, on|off              # Set TX to 20% or 0%
                POWER, nn.nn            # Adjust power output when using external radio TX
                CYCLES, n               # Wait for n receive cycles
                SPOT, on|off            # Set spotting on/off.
        WSPRRY  OPTIONS, option_list    # Selection of -p -s -f -r -x -o -t -n. Must be set before START.
                CALLSIGN, callsign      # Set callsign for tx data. Must be set before START.
                LOCATOR, locator        # Set locator for tx data. Must be set before START.
                PWR, power              # Set Tx power in dBm for tx data. Must be set before START.
                START, f1, f2, f3, ...  # Start WsprryPi with the given frequency sequence and settings.
                STOP                    # Stop WsprryPI if running.
        FCD                             # Set FCDPro+ attributes using fcdctl program
                FREQ, MHz               # Set the FCDPro+ frequency.
                LNA, gain               # Set the FCDPro+ LNA gain, 0 == off, 1 == on.
                MIXER, gain             # Set the FCDPro+ MIXER gain, 0 == off, 1 == on.
                IF, gain                # Set the FCDPro+ IF gain, 0-59 dB.
    
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
        
        #CAT_SETTINGS[SERIAL][0] = self.__comPort
        
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
        #self.__antControl = antcontrol.AntControl(ANT_CTRL_ARDUINO_ADDR, ANT_CTRL_RELAY_DEFAULT_STATE, self.__antControlCallback)
        
        # Create the loop controller
        #self.__loopControl = loopcontrol.LoopControl(LOOP_CTRL_ARDUINO_ADDR, self.__loopControlCallback, self.__loopEvntCallback)
        # Allow full extension for the moment
        #self.__loopControl.setLowSetpoint(0)
        #self.__loopControl.setHighSetpoint(100)
        # Low to medium speed
        #self.__loopControl.speed(MOTOR_SPEED)
        
        # Create the CAT controller
        #self.__cat = cat.CAT(IC7100, CAT_SETTINGS)
        #if self.__cat.start_thrd():
        #    self.__catRunning = True
        #self.__cat.set_callback(self.__catCallback)
        
        # Script sequence and current state
        # The script file is parsed into an internal list of the following form:
        #
        # [
        #   [Major command, [Minor command|param, param, ...]],
        #   [Major command, [...]],
        #   ...
        # ]
        self.__script = []
        # State is kept in a separate dictionary.
        # {
        #     # Push down stack. If iterations nest, the new iteration is first in list.
        #     # As each iteration completes it is removed and execution continues with
        #     # the next iteration if any
        #     SEQ: [[iterations, count, offset], [iterations, count, offset], ...],
        #     # Wait for 'cycles' to complete
        #     CYCLES: [cycles, cycle-count],
        #     # CAT parameters
        #     CAT: [radio, baud],
        #     # WSPPRYPI fixed parameters
        #     WSPPRY: [options, callsign, locator, power]            
        # }
        self.__state = {}
        
        # Set up a dispatch table for major commands
        self.__dispatch = {
            'SEQ': self.__startseq,
            'ENDSEQ':  self.__endseq,
            'TIME':  self.__starttime,
            'ENDTIME':  self.__stoptime,
            'PAUSE':  self.__pause,
            'LPF':  self.__lpf,
            'ANTENNA':  self.__antenna,
            'LOOP':  self.__loop,
            'RADIO':  self.__radio,
            'WSPR':  self.__wspr,
            'WSPRRY':  self.__wsprry,
            'FCD':  self.__fcd,
            'COMPLETE': self.__complete,
        }
        
        # Low pass filters
        # Set modes and deactivate all relays        
        GPIO.setup(PIN_160_1, GPIO.OUT)
        GPIO.setup(PIN_160_2, GPIO.OUT)
        GPIO.setup(PIN_80_1, GPIO.OUT)
        GPIO.setup(PIN_80_2, GPIO.OUT)
        GPIO.setup(PIN_40_1, GPIO.OUT)
        GPIO.setup(PIN_40_2, GPIO.OUT)
        self.__resetLPF()

        # Defs
        LPF_160 = 'LPF-160'
        LPF_80 = 'LPF-80'
        LPF_40 = 'LPF-40'
        
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
        #self.__cat.terminate()
        #self.__loopControl.terminate()
    
    # =================================================================================
    # Main processing     
    def parseScript(self):
        
        """ Parse script file into an internal structure """
        
        try:
            f = open(self.__scriptPath)
            lines = f.readlines()
        except Exception as e:
            print('Error in file access [%s][%s]' % (self.__scriptPath, str(e)))
            return
        try:    
            # Process file
            index = 0
            for line in lines:
                if line[0] == '#':
                    # Comment line
                    continue
                line = line.strip('\n\r')
                cmd, remainder = line.split(':')
                self.__script.append([])
                self.__script[index].append(cmd)
                self.__script[index].append([])
                if len(remainder) > 0:
                    toks = remainder.split(',')
                    for tok in toks:
                        self.__script[index][1].append(tok.strip())
                index += 1
        except Exception as e:
            print('Error in file processing [%s][%s][%s]' % (self.__scriptPath, str(e), traceback.format_exc()))
            return False, None
        
        return True, self.__script
    
    def executeScript(self):
        """ Execute the script """
        
        try:
            # Run until complete or we run out of commands
            # Errors are managed in-line as recoverable or non-recoverable.
            index = 0
            while index < len(self.__script):
                commandLine = self.__script[index]
                majorCommand = commandLine[0]
                parameters = commandLine[1]
                result, qualifier = self.__dispatch[majorCommand](parameters, index)
                index += 1
                if result == DISP_COMPLETE:
                    print('Script execution complete, terminating...')
                    break
                elif result == DISP_RECOVERABLE_ERROR:
                    print ('Recoverable error [%s], skipping command and continuing' % (qualifier))
                elif result == DISP_NONRECOVERABLE_ERROR:
                    print ('Non-Recoverable error [%s], terminating...' % (qualifier))
                    break
                elif result == DISP_NEW_INDEX:
                    # Iteration or skipping a time section
                    index = qualifier
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
    # Main-Execution functions
    def __startseq(self, params, index):
        """
        Start an iteration sequence
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        iterations = params
        
        # Prepend this sequence start point into the structure
        if SEQ in self.state:
            self.__state[SEQ].insert(0, [iterations, iterations, index+1])
        else:
            self.__state[SEQ] = [[iterations, iterations, index+1],]
        return DISP_CONTINUE, None
    
    def __endseq(self, params, index):
        """
        End an iteration sequence
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        if SEQ in self.state:
            if len(self.__state[SEQ]) > 0:
                if self.__state[SEQ][0][1] == 0:
                    # Stop iterating
                    del self.__state[SEQ][0]
                    return DISP_CONTINUE, None
                else:
                    # Decrement the count
                    self.__state[SEQ][0][1] -= 1
                    # and loop back to the start
                    return DISP_NEW_INDEX, self.__state[SEQ][0][2]
    
    def __starttime(self, params, index):
        """
        Start a time section
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        return DISP_CONTINUE, None
    
    def __stoptime(self, params, index):
        """
        Stop a time sequence
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        return DISP_CONTINUE, None
    
    def __pause(self, params, index):
        """
        Pause execution
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        delay = params
        sleep(delay)
        return DISP_CONTINUE, None
    
    def __lpf(self, params, index):
        """
        Select a low pass filter
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        lpf = params
        # Deactivate
        self.__resetLPF()
        # Activate
        if lpf == LPF_160:
            GPIO.output(PIN_160_1, GPIO.LOW)
            GPIO.output(PIN_160_2, GPIO.LOW)
        elif lpf == LPF_80:
            GPIO.output(PIN_80_1, GPIO.LOW)
            GPIO.output(PIN_80_2, GPIO.LOW)
        elif lpf == LPF_4:
            GPIO.output(PIN_40_1, GPIO.LOW)
            GPIO.output(PIN_40_2, GPIO.LOW)
        else:
            return DISP_NONRECOVERABLE_ERROR, 'Failed to select LPF filter %s!', lpf
            
        return DISP_CONTINUE, None
    
    def __antenna(self, params, index):
        """
        Select an antenna to radio route
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        return DISP_CONTINUE, None
    
    def __loop(self, params, index):
        """
        Select a band and tune the loop
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        return DISP_CONTINUE, None
    
    def __radio(self, params, index):
        """
        Execute a CAT command
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        return DISP_CONTINUE, None
    
    def __wspr(self, params, index):
        """
        Send a WSPR command
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """

        return DISP_CONTINUE, None
    
    def __wsprry(self, params, index):
        """
        Invoke WsprryPi
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        return DISP_CONTINUE, None
    
    def __fcd(self, params, index):
        """
        Send a command to a FunCubeDonglePro+
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        return DISP_CONTINUE, None
    
    def __complete(self, params, index):
        """
        Commands complete
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        return DISP_COMPLETE, None
    
    # =================================================================================
    # Sub-Execution functions
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
    
    def __resetLPF():
        """ Deactivate all LPF filters """
        
        GPIO.output(PIN_160_1, GPIO.HIGH)
        GPIO.output(PIN_160_2, GPIO.HIGH)
        GPIO.output(PIN_80_1, GPIO.HIGH)
        GPIO.output(PIN_80_2, GPIO.HIGH)
        GPIO.output(PIN_40_1, GPIO.HIGH)
        GPIO.output(PIN_40_2, GPIO.HIGH)
            
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
        #
        if len(sys.argv) != 2:
            print('Usage: python automation.py path-to-script-file')
            sys.exit(0)
        path = sys.argv[1]
        if not os.path.exists(path):
            print('Error: Invalid path to script file!')
            sys.exit(0)
            
        print('Starting automation run...')
        app = Automate(path)
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