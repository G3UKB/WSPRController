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
import subprocess
import signal
from time import sleep
import datetime
import math
import logging
import logging.handlers
# This is specific to the RPi for LPF switching
import RPi.GPIO as GPIO

# Application imports
from defs import *
# We need to pull in antennacontrol, loopcontrol and cat from the Common project
sys.path.append(os.path.join('..','..','..','..','Common','trunk','python'))
import antcontrol
import loop_control_if as loopcontrol
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
    antennas to the main station. The author has built a switch system that supports
    comprehensive routing in a many to many configuration.
    3. Antenna tuning. This may be an area of difficulty when using antennas that require
    tuning on different bands. Auto-tuners will not work at very low power (RPi barefoot
    outputs 10mW). Thus if tuning is required and there is insufficient power for an
    auto-tuner the tuner must support set-points for different frequencies. The author
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
        MSG         # Output a message to the console
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
        SEQ: n      # Iterate to END n times. If n is -1 iterate for ever.
        ENDSEQ:     # Loopback to last SEQ while iteration < n
        TIME: start, end
                    # The commands banded by TIME and ENDTIME to be executed only between start, end time in hours
                    # 24 hour clock.
        ENDTIME:     SKIP to ENDTIME if time criteria not met
        PAUSE: n.n  # Pause execution for n.n seconds
        MSG: message# Output the message
        COMPLETE:   # End of script
      Hardware commands:
        LPF: band   # Where band is LPF-160/LPF-80/LPF-40 etc. Mapping is involved to relay activation.
        ANTENNA: SWITCH, source, dest
                    # Sets up a route between an antenna and a destination TX or RX capability.
                    # e.g. 160-80m-loop, FCDPro+. Mapping is involved to relay activation.
                    # see defs.py ANTENNA_TO_INTERNAL for antenna constants
        ANTENNA: SWR
                    # Checks current antenna SWR using the VNA.
        LOOP: INIT, % low_setpoint, % high_setpoint, % motor_speed, driver max speed_factor
                    # Initialise the loop tuner with offsets etc
        LOOP: BAND, antenna, extension
                    # Switch the loop to band, and extend the actuator to % extension.
                    # see defs.py ANTENNA_TO_LOOP_INTERNAL for antenna constants
        LOOP: ADJUST
                    # Micro-adjust tuning for lowest SWR using VNA
        RADIO:  CAT, radio, com_port, baud_rate
                    # Supported radios IC7100 | FT817, baud-rate. Must be executed to initiate CAT control.
                BAND, MHz
                    # Set the radio frequency to the WSPR frequency for BAND using CAT
                MODE, LSB|USB|...
                    # Set the radio mode using CAT
      Software commands:
        WSPR:   INVOKE                  # Invoke WSPR if not running. Must be running before any other WSPR command.
                RESET                   # Reset
                IDLE, on|off            # Set idle on/off, i.e stop RX/TX
                BAND, B_160 etc ...     # Set band for reporting
                TX, on|off              # Set TX to 20% or 0%
                POWER, nn.nn, nn.nn     # Available, required. Adjust power output when using external radio TX
                CYCLES, n               # Wait for n receive cycles
                SPOT, on|off            # Set spotting on/off.
        WSPRRY: WSPRRY_OPTIONS, option_list    # Selection of -p -s -f -r -x -o -t -n. Must be set before START.
                WSPRRY_CALLSIGN, callsign      # Set callsign for tx data. Must be set before START.
                WSPRRY_LOCATOR, locator        # Set locator for tx data. Must be set before START.
                WSPRRY_PWR, power              # Set Tx power in dBm for tx data. Must be set before START.
                WSPRRY_START, f1, f2, f3, ...  # Start WsprryPi with the given frequency sequence and settings.
                WSPRRY_WAIT                    # Wait for WsprryPi to terminate
                WSPRRY_KILL                    # Uncerimoneously kill WsprryPi (this may not work on Windows)
                WSPRRY_STOP                    # Stop WsprryPI if running.
        FCD:                            # Set FCDPro+ attributes using fcdctl program
                BAND, band              # Set the FCDPro+ frequency to the WSPR band + IF offset.
                LNA, gain               # Set the FCDPro+ LNA gain, 0 == off, 1 == on.
                MIXER, gain             # Set the FCDPro+ MIXER gain, 0 == off, 1 == on.
                IF, gain                # Set the FCDPro+ IF gain, 0-59 dB.
                STATUS                  # Show status
    
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
        self.__loopEvt = threading.Event()
        
        # Instance vars
        self.__waitingBandNo = None
        self.__catRunning = False
        self.__wsprrypi_proc = None
        self.__WSPRProc = None
        self.__cat  = None
        self.__loopControl = None
        self.__wsprTx = False
        self.__antennaRoute = (None, None)
        self.__wsprrypiFreqList = []
        self.__currentLoop = None
        
        # Create the antenna controller
        self.__antControl = antcontrol.AntControl(ANT_CTRL_ARDUINO_ADDR, ANT_CTRL_RELAY_DEFAULT_STATE, self.__antControlCallback)
        sleep(2.0)
        # Create the loop controller
        self.__loopControl = loopcontrol.ControllerAPI(LOOP_CTRL_ARDUINO_ADDR, self.__loopControlCallback, self.__loopEvntCallback)
        sleep(2.0)
        
        # Create a socket for the VNA application
        self.__vnasock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__vnasock.bind((VNA_LOCAL_IP, VNA_REPLY_PORT))
        self.__vnasock.settimeout(VNA_TIMEOUT)

        # Script sequence and current state
        self.__script = []
        # The script file is parsed into an internal list of the following form:
        #
        # [
        #   [Major command, [Minor command|param, param, ...]],
        #   [Major command, [...]],
        #   ...
        # ]
        
        # State is kept in a separate dictionary.
        self.__state = {
            SEQ: [],
            CYCLES: [None, None],
            CAT: [None, None],
            WSPRRY: [None, None, None, None]
        }
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
        #     WSPRRY: [options, callsign, locator, power]            
        # }
        
        # Set up a dispatch table for major commands
        self.__dispatch = {
            'SEQ': self.__startseq,
            'ENDSEQ':  self.__endseq,
            'TIME':  self.__starttime,
            'ENDTIME':  self.__stoptime,
            'PAUSE':  self.__pause,
            'MSG':  self.__message,
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
        # Initialise
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(PIN_160_1, GPIO.OUT)
        GPIO.setup(PIN_160_2, GPIO.OUT)
        GPIO.setup(PIN_80_1, GPIO.OUT)
        GPIO.setup(PIN_80_2, GPIO.OUT)
        GPIO.setup(PIN_40_1, GPIO.OUT)
        GPIO.setup(PIN_40_2, GPIO.OUT)
        self.__resetLPF()
        
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
        if self.__cat != None: self.__cat.terminate()
        if self.__loopControl != None: self.__loopControl.terminate()
        if self.__WSPRProc != None: self.__WSPRProc.send_signal(signal.SIGTERM)
    
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
                if len(line) == 0: continue
                cmd, remainder = line.split(':')
                self.__script.append([])
                self.__script[index].append(cmd)
                self.__script[index].append([])
                if cmd == MSG:
                    self.__script[index][1].append(remainder.strip())
                else:
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
        
        iterations, = params
        iterations = int(iterations)
        # Prepend this sequence start point into the structure
        if SEQ in self.__state:
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
        
        if SEQ in self.__state:
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
        
        if len(params) != 2:
            return DISP_RECOVERABLE_ERROR, 'Wrong number of parameters for time section %s ... skipping section' % (params)
        startHour, stopHour = params
        startHour = int(startHour)
        stopHour = int(stopHour)
        if (startHour < 0 or startHour > 23) or (stopHour < 0 or stopHour > 23):
            return DISP_RECOVERABLE_ERROR, 'Invalid parameters for time section %s ... skipping section' % (params)
        
        # Is current time within timespan
        currentHour = datetime.datetime.now().hour
        runSection = False
        if (startHour == 0 and stopHour == 0):
            # This means all day, although absence of a time command does the same thing
            runSection = True
        elif stopHour < startHour:
            # Crossing midnight
            if currentHour <= stopHour:
                # Past midnight
                runSection = True
            else:
                # Before midnight
                if currentHour >= startHour:
                    runSection = True
        else:
            # Normal progression
            if currentHour >= startHour and stopHour > currentHour:
                runSection = True
        
        # Decision time
        if runSection:
            # Continue through the section
            return DISP_CONTINUE, None
        else:
            # We need to skip to the ENDTIME command
            # The index param is the next command index
            while index < len(self.__script):
                commandLine = self.__script[index]
                if commandLine[0] == ENDTIME:
                    return DISP_NEW_INDEX, index + 1
                index += 1
            # oops, didn't find the ENDTIME
            return DISP_NONRECOVERABLE_ERROR, 'Reached end of commands without finding an ENDTIME command!'      
    
    def __stoptime(self, params, index):
        """
        Stop a time sequence
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        # This is a noop as it is only there as a skip to command for STARTTIME
        return DISP_CONTINUE, None
    
    def __pause(self, params, index):
        """
        Pause execution
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        delay, = params
        sleep(float(delay))
        return DISP_CONTINUE, None
    
    def __message(self, params, index):
        """
        Output a message
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        message, = params
        print(message)
        return DISP_CONTINUE, None

    def __lpf(self, params, index):
        """
        Select a low pass filter
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        lpf, = params
        # Deactivate
        self.__resetLPF()
        # Activate
        if lpf == LPF_160:
            GPIO.output(PIN_160_1, GPIO.LOW)
            GPIO.output(PIN_160_2, GPIO.LOW)
        elif lpf == LPF_80:
            GPIO.output(PIN_80_1, GPIO.LOW)
            GPIO.output(PIN_80_2, GPIO.LOW)
        elif lpf == LPF_40:
            GPIO.output(PIN_40_1, GPIO.LOW)
            GPIO.output(PIN_40_2, GPIO.LOW)
        else:
            return DISP_NONRECOVERABLE_ERROR, 'Failed to select LPF filter %s!' % (lpf)
            
        return DISP_CONTINUE, None
    
    def __antenna(self, params, index):
        """
        Select an antenna to radio route
        
        Arguments:
            params      --  params for this command
                            antenna, sourcesink
            index       --  current index into command structure
        
        """
        
        subcommand = params[0]
        if subcommand == SWITCH:
            if len(params) != 2:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for antenna switch %s!' % (params)
            return self.__doAntenna(params[0], params[1])
        elif subcommand == SWR:
            # Switch the current antenna to the VNA
            return self.__doAntennaSWR(self.__antennaRoute[0], SS_VNA)
        
        return DISP_NONRECOVERABLE_ERROR, 'Invalid command to Antenna Switch %s!', params
    
    def __loop(self, params, index):
        """
        Init loop
        Select a band and tune the loop
        
        Arguments:
            params      --  params for this command
                            sub-command dependent
            index       --  current index into command structure
        
        """
        
        subcommand = params[0]
        if subcommand == LOOP_INIT:
            if not self.__loopControl.is_online():
                return DISP_NONRECOVERABLE_ERROR, 'Loop controller is off-line!'
            if len(params) != 5:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for loop init %s!' % (params)
            _, lowSetpoint, highSetpoint, motorSpeed, speedFactor = params
            # Set the extension range
            self.__loopEvt.clear()
            self.__loopControl.setLowSetpoint(int(lowSetpoint))
            if not self.__loopEvt.wait(EVNT_TIMEOUT):
                return DISP_RECOVERABLE_ERROR, 'Timeout waiting for loop setLowSetpoint to respond!'
            self.__loopEvt.clear()
            self.__loopControl.setHighSetpoint(int(highSetpoint))
            if not self.__loopEvt.wait(EVNT_TIMEOUT):
                return DISP_RECOVERABLE_ERROR, 'Timeout waiting for loop setHighSetpoint to respond!'
            self.__loopEvt.clear()
            self.__loopControl.setCapMaxSetpoint(int(highSetpoint))
            if not self.__loopEvt.wait(EVNT_TIMEOUT):
                return DISP_RECOVERABLE_ERROR, 'Timeout waiting for loop setCapMaxSetpoint to respond!'
            self.__loopEvt.clear()
            self.__loopControl.setCapMinSetpoint(int(lowSetpoint))
            if not self.__loopEvt.wait(EVNT_TIMEOUT):
                return DISP_RECOVERABLE_ERROR, 'Timeout waiting for loop setCapMinSetpoint to respond!'
            # We use an external analog ref voltage
            self.__loopEvt.clear()
            self.__loopControl.setAnalogRef(EXTERNAL)
            if not self.__loopEvt.wait(EVNT_TIMEOUT):
                return DISP_RECOVERABLE_ERROR, 'Timeout waiting for loop setAnalogRef to respond!'
            # Set the motor speed
            # This is given in 0-100% and the factor is whatever the motor driver accepts as a maximum
            # speed value.
            self.__loopEvt.clear()
            self.__loopControl.speed(int((float(motorSpeed)/100.0)* float(speedFactor)))
            if not self.__loopEvt.wait(EVNT_TIMEOUT):
                return DISP_RECOVERABLE_ERROR, 'Timeout waiting for loop speed to respond!'
            return DISP_CONTINUE, None
        elif subcommand == LOOP_BAND: 
            if len(params) != 3:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for loop tune %s!' % (params)
            _, antenna, extension = params
            return self.__doLoopTune(antenna, int(extension))
        elif subcommand == LOOP_ADJUST:
            return self.__doLoopAdjust(A_LOOP, SS_VNA)
        
        return DISP_NONRECOVERABLE_ERROR, 'Invalid command to Loop %s!', params
    
    def __radio(self, params, index):
        """
        Execute a RADIO command
        
        Arguments:
            params      --  params for this command
                            sub-command dependent
            index       --  current index into command structure
        
        """
        
        if len(params) < 2:
            return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for radio %s!' % (params)
        
        return self.__doRadio(params)
    
    def __wspr(self, params, index):
        """
        Send a WSPR command
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """

        subcommand = params[0]
        if subcommand == INVOKE:
            if self.__WSPRProc == None:
                # Process not running, so start
                self.__WSPRProc = subprocess.Popen(['python3', 'wspr.py'], cwd=WSPR_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                sleep(1.0)
            else:
                if self.__WSPRProc.poll() != None:
                    # Process was running but has terminated, so restart
                    self.__WSPRProc = subprocess.Popen(['python3', 'wspr.py'], cwd=WSPR_PATH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    sleep(1.0)
            return DISP_CONTINUE, None
        elif subcommand == RESET:
            return self.__doWSPRReset()            
        elif subcommand == IDLE:
            if len(params) != 2:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for WSPR IDLE %s!' % (params)
            _, state = params
            if state == 'on': state = True
            elif state == 'off': state = False
            else: return DISP_NONRECOVERABLE_ERROR, 'WSPR IDLE command must be "on" or "off" %s!' % (params)
            return self.__doWSPRIdle(state)
        elif subcommand == BAND:
            if len(params) != 2:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for WSPR BAND %s!' % (params)
            _, band = params
            if band in BAND_TO_EXTERNAL:
                return self.__doWSPRBand(band)
            else:
                return DISP_NONRECOVERABLE_ERROR, 'WSPR BAND command must be "B-160,B-80" etc %s!' % (params)
        elif subcommand == TX:
            if len(params) != 2:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for WSPR TX %s!' % (params)
            _, state = params
            if state == 'on': self.__wsprTx = True
            elif state == 'off': self.__wsprTx = False
            else: return DISP_NONRECOVERABLE_ERROR, 'WSPR TX command must be "on" or "off" %s!' % (params)
            return self.__doWSPRTx(self.__wsprTx)
        elif subcommand == POWER:
            if len(params) != 3:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for WSPR POWER %s!' % (params)
            _, availablePower, requiredPower = params
            try:
                availablePower = float(availablePower)
                requiredPower = float(requiredPower)
            except Exception as e:
                return DISP_NONRECOVERABLE_ERROR, 'WSPR POWER command must be a float in watts %s!' % (params)
            return self.__doWSPRPower(availablePower, requiredPower)
        elif subcommand == CYCLES:
            if len(params) != 2:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for WSPR CYCLES %s!' % (params)
            _, cycles = params
            try:
                cycles = int(cycles)
            except Exception as e:
                return DISP_NONRECOVERABLE_ERROR, 'WSPR CYCLES command must be a int %s!' % (params)
            return self.__doWSPRCycles(cycles, self.__doWSPRTx)
        elif subcommand == SPOT:
            if len(params) != 2:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for WSPR SPOT %s!' % (params)
            _, state = params
            if state == 'on': state = True
            elif state == 'off': state = False
            else: return DISP_NONRECOVERABLE_ERROR, 'WSPR SPOT command must be "on" or "off" %s!' % (params)
            return self.__doWSPRSpot(state)
        
        return DISP_NONRECOVERABLE_ERROR, 'Invalid command to WSPR %s!', params
    
    def __wsprry(self, params, index):
        """
        Send a WsprryPi command
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        subcommand = params[0]
        if subcommand == WSPRRY_OPTIONS:
            options = params[1:]
            self.__state[WSPRRY][0] = options
        elif subcommand == WSPRRY_CALLSIGN:
            if len(params) == 2:
                _, callsign = params
                self.__state[WSPRRY][1] = callsign
            else:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for WsprryPi command %s!' % (params)
        elif subcommand == WSPRRY_LOCATOR:
            if len(params) == 2:
                _, locator = params
                self.__state[WSPRRY][2] = locator
            else:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for WsprryPi command %s!' % (params)
        elif subcommand == WSPRRY_PWR:
            if len(params) == 2:
                _, power = params
                self.__state[WSPRRY][3] = power
            else:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for WsprryPi command %s!' % (params)
        elif subcommand == WSPRRY_START:
            # Construct parameter list
            p = []
            p.append('sudo')
            p.append(WSPRRYPI_PATH)
            for option in self.__state[WSPRRY][0]:
                p.append(option)
            p.append(self.__state[WSPRRY][1])
            p.append(self.__state[WSPRRY][2])
            p.append(self.__state[WSPRRY][3])
            
            freqList = params[1:]
            for freq in freqList:
                p.append(freq)
            self.__wsprrypiFreqList = freqList
            # Invoke WsprryPi
            try:
                self.__wsprrypi_proc = subprocess.Popen(p)
            except Exception as e:
                return DISP_NONRECOVERABLE_ERROR, 'Exception starting WsprryPi [%s]' % (str(e))
        elif subcommand == WSPRRY_WAIT:
            if self.__wsprrypi_proc != None:
                if self.__wsprrypi_proc.poll() == None:
                    while True:
                        print('Waiting for WsprryPi to finish')
                        try:
                            # Give it 20.0 minutes to close as cycles are 2 mins and we could wait 2 mins for the start
                            self.__wsprrypi_proc.wait(1200)
                            print('WsprryPi exited')
                            break
                        except subprocess.TimeoutExpired:
                            return DISP_NONRECOVERABLE_ERROR, 'Timeout waiting for WsprryPi to terminate ... killing!'
                            break
        elif subcommand == WSPRRY_KILL:
            if self.__wsprrypi_proc.poll() == None:
                self.__wsprrypi_proc.kill()
            
        return DISP_CONTINUE, None
    
    def __fcd(self, params, index):
        """
        Send a command to a FunCubeDonglePro+
        
        Arguments:
            params      --  params for this command
            index       --  current index into command structure
        
        """
        
        if len(params) > 2:
            return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for FCD command %s!' % (params)
        
        subcommand = params[0]
        p = [FCDCTL_PATH,]
        
        # fcdctl is a command line program which should execute the command and exit.
        if subcommand == BAND:
            _ , band = params
            if band not in BAND_TO_FREQ:
                return DISP_NONRECOVERABLE_ERROR, 'Unknown band %s for FCD command' % (band)
            wsprFreq = BAND_TO_FREQ[band]
            fcdFreq = wsprFreq - FCD_IF
            p.append('-f')
            p.append(str(fcdFreq))
        elif subcommand == LNA:
            _ , gain = params
            if gain == 'on': gain = '1'
            else: gain = '0'
            p.append('-g')
            p.append(gain)
        elif subcommand == MIXER:
            _ , gain = params
            if gain == 'on': gain = '1'
            else: gain = '0'
            p.append('-m')
            p.append(gain)
        elif subcommand == IF:
            _ , gain = params
            p.append('-i')
            p.append(str(gain))
        elif subcommand == STATUS:
            p.append('-s')
        else:
            return DISP_NONRECOVERABLE_ERROR, 'Invalid command for FCD %s!' % (params)
        
        # Invoke fcdctl
        try:
            proc = subprocess.Popen(p)
            proc.wait()
        except Exception as e:
            return DISP_NONRECOVERABLE_ERROR, 'Exception starting FCDCTL [%s]' % (str(e)) % (params)
            
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
    
    # =================================================================================
    # WSPR
    def __doWSPRBand(self, band):
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
        while True:
            if self.__bandEvt.wait(EVNT_TIMEOUT):
                break
            else:
                timeout -= EVNT_TIMEOUT
                if timeout <= 0:
                    # Timeout waiting for the band switch
                    return DISP_RECOVERABLE_ERROR, 'Timeout waiting for WSPR to switch bands!'
                    
        self.__bandEvt.clear()
        self.__waitingBandNo = None
        
        return DISP_CONTINUE, None
             
    def __doWSPRTx(self, tx):
        """
        Instruct WSPR to set the TX feature to 0% or 20%
        
        Arguments:
            tx    --  True = 20%, False = 0%
            
        """
        
        if tx: cmd = 1
        else: cmd = 0
        # Do TX command
        self.__cmdSock.sendto(('tx:%d' % cmd).encode('utf-8'), (CMD_IP, CMD_PORT))
        
        return DISP_CONTINUE, None
    
    def __doWSPRPower(self, availablePwr, power):
        """
        Instruct WSPR to set the TX power level
        
        Arguments:
            availablePwr    --  max power output from transmitter
            power           --  required power output
            
        """
        
        # Change power level
        if power != availablePwr:
            powerdBm = self.__powertodbm(power)
            availablePwrdBm = self.__powertodbm(availablePwr)
            diffdBm = availablePwrdBm - powerdBm
            if diffdBm > 30: diffdBm = 30
            self.__cmdSock.sendto(('power:%d' % diffdBm).encode('utf-8'), (CMD_IP, CMD_PORT))
    
        return DISP_CONTINUE, None
    
    def __doWSPRSpot(self, spot):
        """
        Instruct WSPR to set the spot feature on or off
        
        Arguments:
            spot    --  True = ON, False = OFF
            
        """
        
        if spot: cmd = 1
        else: cmd = 0
        self.__cmdSock.sendto(('upload:%d' % cmd).encode('utf-8'), (CMD_IP, CMD_PORT))
        
        return DISP_CONTINUE, None
       
    def __doWSPRCycles(self, cycles, tx):
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
                    return DISP_RECOVERABLE_ERROR, 'Timeout waiting for WSPR to complete %d cycles. Aborted at cycle %d!' % (cycles, cycles - cycleCount + 1)
                else:
                    continue
                
        return DISP_CONTINUE, None
    
    def __doWSPRIdle(self, state):
        """
        Instruct WSPR to enter the IDLE mode.
        
        Arguments:
            state    --  True == IDLE
            
        """
        
        if state: cmd = 1
        else: cmd = 0
        self.__cmdSock.sendto(('idle:%d' % cmd).encode('utf-8'), (CMD_IP, CMD_PORT))
        
        return DISP_CONTINUE, None
    
    def __doWSPRReset(self):
        """
        Instruct WSPR to reset.
        
        Arguments:
            
        """
        
        self.__cmdSock.sendto('reset'.encode('utf-8'), (CMD_IP, CMD_PORT))
        
        return DISP_CONTINUE, None
    
    # =================================================================================
    # Antennas
    def __doAntenna(self, antenna, sourceSink, save=True):
        """
        Instruct the antenna switching module to switch to the given route.
        A route is an antenna to a source (TX) or sink (RX).
        
        Arguments:
            antenna       --  the internal antenna name
            sourceSink    --  the internal RX/TX/Both name
            save          --  if True save the route
            
        """
        
        # The key to the dictionary id antenna:sourceSink
        try:
            key = '%s:%s' % (antenna, sourceSink)
            if save: self.__antennaRoute = (antenna, sourceSink)
            matrix = ANTENNA_TO_SS_ROUTE[key]
            for relay, state in matrix.items():
                if state != RELAY_NA:
                    self.__relayEvt.clear()
                    self.__antControl.set_relay(relay, state)
                    if not self.__relayEvt.wait(EVNT_TIMEOUT):
                        return DISP_RECOVERABLE_ERROR, 'Timeout waiting for antenna changeover to respond to relay change!'
                    # ToDo, why do we need a long pause between switches, seems to be on relay 5 there is an issue
                    sleep(2.0)
            self.__relayEvt.clear()
        except Exception as e:
            return DISP_NONRECOVERABLE_ERROR, 'Exception in antenna switching [%s]' % (str(e))
        
        return DISP_CONTINUE, None
    
    def __doAntennaSWR(self, antenna, sourceSink):
        """
        Instruct the antenna switching module to switch the antenna
        to the VNA for checking the SWR.
        Switch back to the previous route after checking.
        
        Arguments:
            antenna       --  the internal antenna name
            sourceSink    --  the internal VNA name
            
        """
        
        msg = None
        
        # Switch antenna to the VNA port
        resp = self.__doAntenna(antenna, sourceSink, False) 
        if resp[0] != DISP_CONTINUE:
            return resp, None
            
        # Get the SWR at the mid TX frequency of the current WSPR band
        # Get the current TX band
        wsprFreq = None
        for f in self.__wsprrypiFreqList:
            if f != '0':
                # Translate to an actual frequency in Hz
                wsprFreq = WSPRRY_TO_FREQ[f]
                # Query the VNA for SWR at the TX frequency
                r, swr = self.__doVNA(RQST_FSWR, wsprFreq)
                if r:
                    # Good response
                    print('VSWR: ', swr[1])
                else:
                    # Oops #1
                    msg = 'Error getting VSWR'
        if wsprFreq == None:
            # Oops #2
            msg = 'Failed to find valid frequency for VNA [%s]' % (self.__wsprrypiFreqList)
            
        # Switch the antenna back to its previous route
        r = self.__doAntenna(self.__antennaRoute[0], self.__antennaRoute[1])
        if r != DISP_CONTINUE:
            return r, None
        
        # Did we have a previous failure
        if msg != None:
            return DISP_RECOVERABLE_ERROR, msg
        
        return DISP_CONTINUE, None
        
    def __doLoopTune(self, antenna, value):            
        """
        Instruct the loop module to set and tune the selected loop
        
        Arguments:
            antenna   --  the internal antenna name for the loop
            value     --  the analog pot value for the the band WSPR freq
        """
        
        if antenna in ANTENNA_TO_LOOP_INTERNAL:
            internalAntennaName = ANTENNA_TO_LOOP_INTERNAL[antenna]
            self.__currentLoop = internalAntennaName
            if internalAntennaName == A_LOOP_160 or internalAntennaName == A_LOOP_80:
                # Switch the relays to the selected antenna
                matrix = ANTENNA_TO_LOOP_MATRIX[internalAntennaName]
                for relay, state in matrix.items():
                    if state == RELAY_OFF: state = 0
                    else: state = 1
                    self.__loopEvt.clear()
                    self.__loopControl.setRelay((relay, state))
                    if not self.__loopEvt.wait(EVNT_TIMEOUT):
                        return DISP_RECOVERABLE_ERROR, 'Timeout waiting for loop changeover to respond to relay change!'
                # Set the position for antenna band WSPR dial frequency
                self.__loopEvt.clear()
                self.__loopControl.move((value, False))
                if not self.__loopEvt.wait(EVNT_TIMEOUT*2):
                    return DISP_RECOVERABLE_ERROR, 'Timeout waiting for loop changeover to respond to position change!'
        else:
            return DISP_RECOVERABLE_ERROR, 'Unknown loop antenna %s' % (antenna)
        
        return DISP_CONTINUE, None
    
    def __doLoopAdjust(self, antenna, sourceSink):
        """
        Fine tune the antenna for lowest SWR if required.
        Only applies to the loops at present.
        
        Arguments:
            antenna       --  the internal antenna name
            sourceSink    --  the internal VNA name
            
        """
        
        # Switch antenna to the VNA port
        resp = self.__doAntenna(antenna, sourceSink, False) 
        if resp[0] != DISP_CONTINUE:
            return resp
        
        # Get the WSPR frequency for the current band
        if self.__currentLoop == A_LOOP_160:
            wsprFreq = WSPRRY_TO_FREQ['160m']
        elif self.__currentLoop == A_LOOP_80:
            wsprFreq = WSPRRY_TO_FREQ['80m']
        else:
            return DISP_RECOVERABLE_ERROR, 'Failed to find valid frequency for VNA [%s]' % (self.__wsprrypiFreqList)
        
        # Query the VNA for SWR at the TX frequency
        r, swr = self.__getSWR(wsprFreq)
        if not r:
            # Try to improve
            r, swr = self.__loopNudge(wsprFreq)
            if r:
                # Good response
                if swr <= 1.7:
                    print ('SWR now is OK at %d', swr)
                else:
                    print ('Failed to obtain good SWR best at %d', swr)
        else:
            return DISP_RECOVERABLE_ERROR, 'Error getting SWR from VNA for frequency %d' % (wsprFreq)
            
        # Switch the antenna back to its previous route
        r = self.__doAntenna(self.__antennaRoute[0], self.__antennaRoute[1])
        if r != DISP_CONTINUE:
            return r, None
        
        return DISP_CONTINUE, None
        
    def __loopNudge(self, freq):
        """
        Try to nudge the tuning to a better SWR
        
        Arguments:
            freq    --  the required resonant frequency
            
        """
        
        tries = 5
        while True:
            # Get the current resonant frequency
            r, freq = self.__doVNA(RQST_FRES, freq - 1000, freq + 1000)
            diff = wsprFreq - freq
            self.__loopEvt.clear()
            if diff > 0:
                # Too low so need to nudge reverse
                self.__loopControl.nudge(REVERSE, 0.5, 100, 900)
            else:
                # Too high so need to nudge forward
                self.__loopControl.nudge(FORWARD, 0.5, 100, 900)
                        
            if not self.__loopEvt.wait(EVNT_TIMEOUT*2):
                return DISP_RECOVERABLE_ERROR, 'Timeout waiting for loop changeover to respond to position change!'
            # Improve this!
            r, swr = self.__getSWR(wsprFreq)
            if r:
                break
            tries -= 1
            if tries <= 0:
                return False, swr
            
        return True, swr
    
    def __getSWR(self, freq):
        """
        Return the SWR at the given frequency
        
        Arguments:
            freq    --  the required resonant frequency
            
        """
        
        # Query the VNA for SWR at the TX frequency
        r, swr = self.__doVNA(RQST_FSWR, freq)
        if r:
            # Good response
            if swr[1] <= 1.7:
                print ('SWR is OK at %d', swr[1])
                return True, swr
            else:
                print ('SWR is too high at %d', swr[1])
                return False, swr
                
    # =================================================================================
    # Radios
    def __doRadio(self, params):
        """
        Execute radio CAT commands
        
        Arguments:
            params    --  subcommand dependent
            
        """
        
        subcommand = params[0]
        if subcommand == CAT:
            if len(params) != 4:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for radio subcommand %s!' % (params)
            else:
                _, radio, com, baud = params
                if radio == IC7100:
                    CAT_SETTINGS[VARIANT] = IC7100
                elif  radio == FT_817ND:
                    CAT_SETTINGS[VARIANT] = FT_817ND
                CAT_SETTINGS[SERIAL][0] = com
                CAT_SETTINGS[SERIAL][1] = baud
                self.__cat = cat.CAT(radio, CAT_SETTINGS)
                if self.__cat.start_thrd():
                    self.__catRunning = True
                else:
                    return DISP_RECOVERABLE_ERROR, 'Failed to start CAT %s!' % (params)
                self.__cat.set_callback(self.__catCallback)                
        elif subcommand == BAND:
            if len(params) != 2:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for radio subcommand %s!' % (params)
            else:
                _, band = params
                dialFrequency = BAND_TO_FREQ[band]
                self.__catEvt.clear()
                self.__cat.do_command(CAT_FREQ_SET, dialFrequency)
                if not self.__catEvt.wait(EVNT_TIMEOUT*2):
                    return DISP_RECOVERABLE_ERROR, 'Timeout waiting for radio to respond to set frequency command!'
                self.__catEvt.clear()            
        elif subcommand == MODE:
            if len(params) != 2:
                return DISP_NONRECOVERABLE_ERROR, 'Wrong number of parameters for radio subcommand %s!' % (params)
            else:
                _, mode = params
                self.__catEvt.clear()
                self.__cat.do_command(CAT_MODE_SET, mode)
                if not self.__catEvt.wait(EVNT_TIMEOUT*2):
                    return DISP_RECOVERABLE_ERROR, 'Timeout waiting for radio to respond to set mode command!'
                    return False
                self.__catEvt.clear()
            
        return DISP_CONTINUE, None
        
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
    
    def __resetLPF(self):
        """ Deactivate all LPF filters """
        
        GPIO.output(PIN_160_1, GPIO.HIGH)
        GPIO.output(PIN_160_2, GPIO.HIGH)
        GPIO.output(PIN_80_1, GPIO.HIGH)
        GPIO.output(PIN_80_2, GPIO.HIGH)
        GPIO.output(PIN_40_1, GPIO.HIGH)
        GPIO.output(PIN_40_2, GPIO.HIGH)
    
    def __doVNA(rqstType, wsprFreq1, wsprFreq2=0):
        """
        Send a command to the VNA and return the response
        
        Arguments:
            rqstType    --  RQST_FRES | RQST_FSWR | RQST_SCAN
            wsprFreq1   --  the start or target frequency
            wsprFreq2   --  type dependent stop frequency
        
        """
        
        try:
            # Make the request
            self.__vnasock.sendto(pickle.dumps([rqstType, wsprFreq1, wsprFreq2]), (VNA_RQST_IP, VNA_RQST_PORT))
            # Wait for a reply
            data, address = sock.recvfrom(VNA_BUFFER)
            return True, pickle.loads(data)
        except socket.timeout:
            # No VNA application or something failed
            return False, None
        
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
            print('Usage: python wsprauto.py path-to-script-file')
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