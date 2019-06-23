#!/usr/bin/env python3
#
# device.py
# 
# Copyright (C) 2019 by G3UKB Bob Cowdery
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
    Device driver for the WSPRLite WSPR transmitter.
    
    This is pretty much verbatim from the documentation to better understand the code.
    
    Physical connection
    =====================

    ## USB
    
    Communication between the config program and the WSPRlite is by means of a USB-to-UART serial bridge (currently a Silicon Labs CP2104 chip).
    
    The USB device description is set during manufacture to "SOTAbeams WSPRlite".
    
    Serial connection
    =================
    
    Serial settings are:
    
    * Baud rate: 1Mbps
    * 8 data bits, 2 stop bits, no parity
    * Flow control: RTS/CTS
    
    Note: flow control is not fully supported.
    
    RTS (pause flow from WSPRlite to computer) is deliberately not implemented in the hardware, since the USB-to-UART chip has quite a large buffer (576 bytes), and the WSPRlite only ever sends data back to the computer in response to messages from the computer. To pause flow from the WSPRlite to computer, simply stop sending data from the computer to the WSPRlite.
    
    CTS (pause flow from computer to WSPRlite) does not appear to work correctly, at least on Linux. This might be a bug in the libserialport library. Workaround: only send one message at a time to the WSPRlite, wait for the response before sending the next message.
    
    Testpoints TP1 and TP2 on the WSPRlite board are connected to the RX and TX pins for the serial connection.

    Message format
    ==============
    
    Integers are little-endian.
    
    The bytes which are sent through the serial connection for a single message are:
    
        transmittedBytes ::= start escapedMessage end
        escapedMessage ::= (plainByte | escapeSeq)*
    
        controlByte ::= start | end | esc
        plainByte ::= (uint8 - controlByte)   ; Any byte except one of the controlBytes
        escapeSeq ::= esc escapedByte
    
        start ::= '\x01'
        end ::= '\x04'
        esc ::= '\x10'
        ; The escaped version of each controlByte is obtained by adding 0x80 to the controlByte
        escapedByte ::= '\x81' | '\x84' | '\x90' 
    
    After unescaping `escapedMessage`:
    
        message ::= msgType msgData checksum
        msgType ::= uint16
        msgData ::= (uint8)*
        checksum ::= uint32
    
    The checksum is the CRC32 of `msgType msgData`.
    
    For message types, qualifiers and modes see enumerations.
    
    # Messages from WSPRlite to computer

    The WSPRlite only sends messages in response to commands sent by the computer.
    Note that there is no tracking built into the protocol of which command a message
    is replying to, though the WSPRlite is guaranteed to process and respond to messages
    sequentially. Unless you have a good reason to do otherwise, send one message at a
    time and wait for a response before sending the next one, to avoid losing track of
    which response was for which command.
    
    ### ACK
    Indicates that the command was successful. No msgData.
    
    ### NACK
    Indicates that the command was not successful.
    msgData may be present. If it is, it will be a null-terminated string which is the error message.
    
    ### ResponseData
    Indicates that the command was successful and has returned some data.
    The meaning of msgData depends on what the original command was - see "from computer to WSPRlite" section below.
    
    # Messages from computer to WSPRlite
    
    ### Version
    Retrieves information about firmware and hardware version. 
    No command data.
    Reply: ResponseData
    
        msgData ::= deviceVersion firmwareVersion
        deviceVersion ::= productId productRevision bootloaderVersion
        firmwareVersion ::=  major minor patch date
    
    All numbers (productId, productRevision, bootloaderVersion, major, minor, patch, date) are uint32.
    
    deviceVersion is currently 1,1,1 for the WSPRlite.
    
    ### Read
    Read a config variable.
    Command data:
    
        msgData ::= variableId
        variableId ::= uint16
    
    Reply: NACK or ResponseData. Contents of ResponseData will depend on which variable is being read
    - see cfgvars.md for details.
    
    ### Write
    Write a config variable.
    Command data:
    
        msgData ::= variableId variableData
        variableId ::= uint16
    
    variableData will depend on which variable is being written - see cfgvars.md for details.
    
    Reply: ACK or NACK.
    
    ### Reset
    Reboots the device. No command data. Reply: ACK.
    
    ### DeviceMode_Get
    Gets some information about what the WSPRlite is currently doing. Supported by firmware v1.0.4 and later,
    limited support in earlier versions.
    No command data.
    
    Reply: ResponseData
    
        msgData ::= deviceMode | deviceMode deviceModeSub
        deviceMode ::= uint16
        deviceModeSub ::= uint16
    
    See src/common/device/DeviceMode.hpp for valid device mode values, and WSPRConfigFrame::startStatusUpdate for
    hints on what they mean.
    
    deviceModeSub is only present for some deviceModes (currently, only DeviceMode::WSPR_Active).
    
    ### DeviceMode_Set
    Sets the current device state.
    
    E.g. setting to DeviceMode::WSPR_Active has the same effect as pressing the button on the WSPRlite.
    (This is currently unimplemented in the config program, since the config program does not yet have a way of
    checking the accuracy of the computer time.)
    
    Command data for most device modes is:
    
        msgData ::= deviceMode
        deviceMode ::= uint16
    
    For DeviceMode::Test_ConstantTx, which temporarily makes the WSPRlite emit a constant tone for testing purposes:
    
        msgData ::= deviceMode frequency paBias
        frequency ::= uint64
        paBias ::= uint16
    
    `frequency` is the output frequency in Hz. `paBias` controls the gate bias for the power amplifier stage,
    which affects the output power of the WSPRlite. It is a PWM duty cycle, range 0-1000.
    
    Reply: ACK or NACK
    
    ### Bootloader_State
    Checks whether the device is in bootloader (firmware update) mode.
    No command data.
    
    Reply: ResponseData.
    
        msgData ::= bootloaderMode
        bootloaderMode ::= '\x00' | '\x01' | '\x02'
    
    0=in normal mode, 1=in bootloader mode, 2=in bootloader mode with no valid firmware present to reboot into.
    
    ### Bootloader_Enter
    ### Bootloader_EraseAll,
    ### Bootloader_ErasePage,
    ### Bootloader_ProgramHexRec,
    ### Bootloader_ProgramRow,
    ### Bootloader_ProgramWord,
    ### Bootloader_CRC,
    ### Bootloader_ProgramResetAddr
    
    Currently undocumented since they are likely of limited interest. Note that you might break your WSPRlite
    if you use these incorrectly, to the extent of needing to use a PICkit or similar to fix it.
    
    ### DumpEEPROM
    Currently undocumented since it has not been properly tested yet, and might or might not remain in the firmware.
    
    ### WSPR_GetTime
    Gets the total time since WSPR transmission was started (either by pressing the button or by sending a
    DeviceMode_Set message). Supported by firmware v1.1.1 and later.
    
    Reply: ResponseData.
    
        msgData ::= milliseconds seconds minutes hours
        milliseconds ::= uint16
        seconds ::= uint8
        minutes ::= uint8
        hours ::= uint32
    
    ### TestCmd
    An undocumented command which allows some fine grained direct control of the hardware
    (e.g. set LED flash sequence, set RF output, get button status), used in factory testing.

"""

# Python imports
import os,sys
import serial
import binascii
import struct
from enum import Enum, auto
from time import sleep

# Application imports
from defs import *
import timer
import freq_table

#========================================================================
# Enumerations transferred from the C++ Config program
# The message types
class MsgType(Enum):
    Version = b'\x00\x00'
    NACK = b'\x01\x00'
    ACK = b'\x02\x00'
    Read = b'\x03\x00'
    ResponseData = b'\x04\x00'
    Write = b'\x05\x00'
    Reset = b'\x06\x00'
    Bootloader_State = b'\x07\x00'
    Bootloader_Enter = b'\x08\x00'
    Bootloader_EraseAll = b'\x09\x00'
    Bootloader_ErasePage = b'\x0a\x00'
    Bootloader_ProgramHexRec = b'\x0b\x00'
    Bootloader_ProgramRow = b'\x0c\x00'
    Bootloader_ProgramWord = b'\x0d\x00'
    Bootloader_CRC = b'\x0e\x00'
    Bootloader_ProgramResetAddr = b'\x0f\x00'
    DeviceMode_Get = b'\x10\x00'
    DeviceMode_Set = b'\x11\x00'
    DumpEEPROM = b'\x12\x00'
    WSPR_GetTime = b'\x13\x00'
    TestCmd = b'\x14\x00'

# The message qualifier
class VarId(Enum):
    MemVersion = b'\x00\x00'
    xoFreq = b'\x01\x00'
    xoFreqFactory = b'\x02\x00'
    ChangeCounter = b'\x03\x00'
    DeviceId = b'\x04\x00'
    DeviceSecret = b'\x05\x00'
    WSPR_txFreq = b'\x06\x00'
    WSPR_locator = b'\x07\x00'
    WSPR_callsign = b'\x08\x00'
    WSPR_paBias = b'\x09\x00'
    WSPR_outputPower = b'\x0a\x00'
    WSPR_reportPower = b'\x0b\x00'
    WSPR_txPct = b'\x0c\x00'
    WSPR_maxTxDuration = b'\x0d\x00'
    CwId_Freq = b'\x0e\x00'
    CwId_Callsign = b'\x0f\x00'
    PaBiasSource = b'\x10\x00'
    END = b'\x11\x00'

# The device mode
class DeviceMode(Enum):
    Init = b'\x00\x00'
    WSPR_Pending = b'\x01\x00'
    WSPR_Active = b'\x02\x00'
    WSPR_Invalid = b'\x03\x00'
    Test_ConstantTx = b'\x04\x00'
    FactoryInvalid = b'\x05\x00'
    HardwareFail = b'\x06\x00'
    FirmwareError = b'\x007\x00'
    WSPR_MorseIdent = b'\x08\x00'
    Test = 9

# Message delimiters
START = b'\x01'
END = b'\x04'

# Response states
class State(Enum):
    IDLE = auto()
    START = auto()
    ESC = auto()
    ACK = auto()
    NACK = auto()
    RESP = auto()
    DATA = auto()
    CS = auto()
    END = auto()
    DONE = auto()

# Response data length
data_def = {
    VarId.WSPR_callsign : 15,
    VarId.WSPR_locator : 8,
    VarId.WSPR_txFreq : 8
}
    
#========================================================================
"""
    Main device class for WSPRLite
"""
class WSPRLite(object):
    
    #----------------------------------------------
    # Constructor
    def __init__(self, device, m_start_cb, m_stop_cb):
        
        self.__m_start_cb = m_start_cb
        self.__m_stop_cb = m_stop_cb
        
        # Create connection and set parameters according to device spec
        try:
            self.__ser = serial.Serial(device)
        except serial.SerialException:
            print ("Could not open the specified serial port! [%s]" % (device))
            sys.exit()
        self.__ser.baudrate = 1000000
        self.__ser.bytesize = 8
        self.__ser.parity = 'N'
        self.__ser.stopbits = 2
        self.__ser.rtscts = True
        self.__ser.timeout = 2.0
        
        # Create timer instance
        self.__timer = timer.TimerThrd(self.__start_cb, self.__stop_cb)
        self.__timer.start()
    
    #----------------------------------------------
    # Terminate
    def terminate(self):
        self.__timer.terminate()
        self.__timer.join()
        
    #----------------------------------------------
    # Read methods
    #----------------------------------------------
    # Get current callsign
    def get_callsign(self):
        # msg = START/8 + READ/16 + WSPR_callsign/16 + CRC/32 + STOP/8
        data = MsgType.Read.value + VarId.WSPR_callsign.value
        crc = self.calc_crc_32(data)
        msg = START + data + crc + END
        self.__ser.write(msg)
        self.__do_response(VarId.WSPR_callsign)
        return self.__reply

    #----------------------------------------------
    # Get current locator
    def get_locator(self):
        # msg = START/8 + READ/16 + WSPR_locator/16 + CRC/32 + STOP/8
        data = MsgType.Read.value + VarId.WSPR_locator.value
        crc = self.calc_crc_32(data)
        msg = START + data + crc + END
        self.__ser.write(msg)
        self.__do_response(VarId.WSPR_locator)
        return self.__reply
    
    #----------------------------------------------
    # Get current transmit frequency
    def get_freq(self):
        # msg = START/8 + READ/16 + WSPR_txFreq/16 + CRC/32 + STOP/8
        data = MsgType.Read.value + VarId.WSPR_txFreq.value
        crc = self.calc_crc_32(data)
        msg = START + data + crc + END
        self.__ser.write(msg)
        self.__do_response(VarId.WSPR_txFreq)
        return self.__reply
    
    #----------------------------------------------
    # Write methods
    #----------------------------------------------
    # Set the transmit frequency
    # Freq is a float. This needs to be a 64 bit byte array in LE
    def set_freq(self, freq):
        f = int(freq*1000000)
        f_bytes = struct.pack('<Q', f)
        # msg = START/8 + WRITE/16 + WSPR_txFreq/16 + CRC/32 + STOP/8
        data = MsgType.Write.value + VarId.WSPR_txFreq.value + f_bytes
        crc = self.calc_crc_32(data)
        msg = START + data + crc + END
        self.__ser.write(msg)
        self.__do_response(VarId.WSPR_txFreq)
        return self.__reply
    
    # Set a transmit frequency given a band
    # Band is an integer wavelength.
    def set_band(self, band):
        freq = freq_table.get_tx_freq(band)
        f = int(freq*1000000)
        f_bytes = struct.pack('<Q', f)
        # msg = START/8 + WRITE/16 + WSPR_txFreq/16 + CRC/32 + STOP/8
        data = MsgType.Write.value + VarId.WSPR_txFreq.value + f_bytes
        crc = self.calc_crc_32(data)
        msg = START + data + crc + END
        self.__ser.write(msg)
        self.__do_response(VarId.WSPR_txFreq)
        if self.__reply[0] == True:
            return self.get_freq()
        else:
            return self.__reply

    #----------------------------------------------
    # Start transmitting
    # Note this must be correctly timed to an accurate clock
    def set_tx(self):
        # msg = START/8 + MsgType.DeviceMode_Set/16 + DeviceMode.WSPR_Active/16 + CRC/32 + STOP/8
        data = MsgType.DeviceMode_Set.value + DeviceMode.WSPR_Active.value
        crc = self.calc_crc_32(data)
        self.__set_tx_msg = START + data + crc + END
        self.__timer.wait_start()
    
    #----------------------------------------------
    # Stop transmitting
    # Note this should be done immediately after a transmission, not during tramsmission
    def set_idle(self):
        # msg = START/8 + MsgType.Reset/16 + CRC/32 + STOP/8
        data = MsgType.Reset.value
        crc = self.calc_crc_32(data)
        self.__idle_msg = START + data + crc + END
        self.__timer.wait_stop()
    
    #----------------------------------------------
    # Util methods
    #----------------------------------------------
    # Calculate a CRC32 of the given data
    def calc_crc_32(self, data):
        return struct.pack('<I', binascii.crc32(data))       

    #----------------------------------------------
    # Decode response
    def __do_response(self, cmd):
        # Responses are variable length and depend on the request type
        # Process response data
        self.__state = State.IDLE
        self.__reply = (False, '')
        while True:
            if self.__state == State.IDLE: self.__do_idle()
            elif self.__state == State.START: self.__do_start()
            elif self.__state == State.ESC: self.__do_esc()
            elif self.__state == State.ACK: self.__do_ack()
            elif self.__state == State.NACK: self.__do_nack()
            elif self.__state == State.RESP: self.__do_resp()
            elif self.__state == State.DATA: self.__do_data(cmd)
            elif self.__state == State.CS: self.__do_cs()
            elif self.__state == State.END: self.__do_end()
            elif self.__state == State.DONE: break

    #----------------------------------------------
    def __do_idle(self):
        # Wait for msg start
        b = self.__ser.read(1)
        if b == b'\x01':
            # We have message start
            self.__state = State.START
    
    #----------------------------------------------    
    def __do_start(self):
        # Read next byte
        b = self.__ser.read(1)
        if b == b'\x10':
            # Start of escape sequence
            self.__state = State.ESC
        elif  b == b'\x02':
            # We have an ACK
            # Its a 16 bit number
            self.__ser.read(1)
            self.__state = State.ACK
    
    #----------------------------------------------         
    def __do_esc(self):
        # Read next byte
        b = self.__ser.read(1)
        if b == b'\x81':
            # We have a NAK
            self.__ser.read(1)
            self.__state = State.NACK
        elif  b == b'\x84':
            # We have a RESPONSE
            self.__ser.read(1)
            self.__state = State.RESP
    
    #----------------------------------------------          
    def __do_ack(self):
        self.__reply = (True, '')
        self.__state = State.CS
    
    #----------------------------------------------      
    def __do_nack(self):
        self.__reply = (False, 'Command returned NACK!')
        self.__state = State.CS
    
    #----------------------------------------------      
    def __do_resp(self):
        # We now expect some response data
        # The length of this depends on the command
        self.__state = State.DATA
    
    #----------------------------------------------   
    def __do_data(self, cmd):
        # Decode the data according to the command type
        if cmd == VarId.WSPR_callsign:
            len = data_def[VarId.WSPR_callsign]
            data = self.__ser.read(len)
            self.__reply = (True, data.decode("ascii").rstrip('\0'))
            self.__state = State.CS
        elif cmd == VarId.WSPR_locator:
            len = data_def[VarId.WSPR_locator]
            data = self.__ser.read(len)
            self.__reply = (True, data.decode("ascii").rstrip('\0'))
            self.__state = State.CS            
        elif cmd == VarId.WSPR_txFreq:
            len = data_def[VarId.WSPR_txFreq]
            data = self.__ser.read(len)
            self.__reply = (True, struct.unpack('<Q',data)[0])
            self.__state = State.CS
            
    #----------------------------------------------     
    def __do_cs(self):
        # Should check this
        self.__ser.read(4)
        self.__state = State.END
    
    #----------------------------------------------      
    def __do_end(self):
        # Wait for msg end
        b = self.__ser.read(1)
        if b == b'\x04':
            # We have message end
            self.__state = State.DONE

    #========================================================================
    # Callbacks
    def __start_cb(self):
        # Complete the TX message at correct start time
        self.__ser.write(self.__set_tx_msg)
        self.__do_response(DeviceMode.WSPR_Active)
        self.__m_start_cb(self.__reply)
    
    #----------------------------------------------   
    def __stop_cb(self):
        # Complete the reset message during transmission window
        self.__ser.write(self.__idle_msg)
        self.__do_response(MsgType.Reset)
        self.__m_stop_cb(self.__reply)    

#========================================================================
# Module Test       
if __name__ == '__main__':
    
    if sys.platform == 'win32' or sys.platform == 'win64':
        device = 'COM5'
    else:
        # Assume Linux
        device = '/dev/ttyUSB0'
    
    lite = WSPRLite(device)
    print(lite.get_callsign())
    print(lite.get_locator())
    print(lite.get_freq())
    print(lite.set_freq(14.097066))
    print(lite.get_freq())
    print(lite.set_tx())
    sleep(3)
    print(lite.set_idle())