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

import os,sys
import serial
import binascii
import struct
from enum import Enum
from time import sleep

#========================================================================
# Enumerations transferred from the C++ Config program
# The message types
class MsgType(Enum):
    Version = 0
    NACK = 1
    ACK = 2
    Read = 3
    ResponseData = 4
    Write = 5
    Reset = 6
    Bootloader_State = 7
    Bootloader_Enter = 8
    Bootloader_EraseAll = 9
    Bootloader_ErasePage = 10
    Bootloader_ProgramHexRec = 11
    Bootloader_ProgramRow = 12
    Bootloader_ProgramWord = 13
    Bootloader_CRC = 14
    Bootloader_ProgramResetAddr = 15
    DeviceMode_Get = 16
    DeviceMode_Set = 17
    DumpEEPROM = 18
    WSPR_GetTime = 19
    TestCmd = 20

# The message qualifier
class VarId(Enum):
    MemVersion = 0
    xoFreq = 1
    xoFreqFactory = 2
    ChangeCounter = 3
    DeviceId = 4
    DeviceSecret = 5
    WSPR_txFreq = 6
    WSPR_locator = 7
    WSPR_callsign = 8
    WSPR_paBias = 9
    WSPR_outputPower = 10
    WSPR_reportPower = 11
    WSPR_txPct = 12
    WSPR_maxTxDuration = 13
    CwId_Freq = 14
    CwId_Callsign = 15
    PaBiasSource = 16
    END = 18

# The device mode
class VarId(Enum):
    Init = 0
    WSPR_Pending = 1
    WSPR_Active = 2
    WSPR_Invalid = 3
    Test_ConstantTx = 4
    FactoryInvalid = 5
    HardwareFail = 6
    FirmwareError = 7
    WSPR_MorseIdent = 8
    Test = 9

#========================================================================
"""
    Main device class for WSPRLite
"""
class WSPRLite(object):
    
    #----------------------------------------------
    # Constructor
    def __init__(self, device):
        # Create connection and set parameters according to device spec
        self.__ser = serial.Serial(device)
        self.__ser.baudrate = 1000000
        self.__ser.bytesize = 8
        self.__ser.parity = 'N'
        self.__ser.stopbits = 2
        self.__ser.rtscts = True
        self.__ser.timeout = 2.0
    
    #----------------------------------------------
    # Read methods
    #----------------------------------------------
    # Get current callsign
    def get_callsign(self):
        crc = self.calc_crc_32(b'\x03\x00\x08\x00')
        msg = bytearray(b'\x01\x03\x00\x08\x00')
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        print(self.__ser.readline())

    #----------------------------------------------
    # Get current locator
    def get_locator(self):
        crc = self.calc_crc_32(b'\x03\x00\x07\x00')
        msg = bytearray(b'\x01\x03\x00\x07\x00')
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        print(self.__ser.readline())
    
    #----------------------------------------------
    # Get current transmit frequency
    def get_freq(self):
        crc = self.calc_crc_32(b'\x03\x00\x06\x00')
        msg = bytearray(b'\x01\x03\x00\x06\x00')
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        resp = self.__ser.readline()
        f = resp[4:12]
        print(struct.unpack('<Q',f)[0])
    
    #----------------------------------------------
    # Write methods
    #----------------------------------------------
    # Set the transmit frequency
    # Freq is a float. This needs to be a 64 bit byte array in LE
    def set_freq(self, freq):
        f = int(freq*1000000)
        f_bytes = struct.pack('<Q', f)
        crc = self.calc_crc_32(b'\x05\x00\x06\x00' + f_bytes)
        msg = bytearray(b'\x01\x05\x00\x06\x00' + f_bytes)
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        print(self.__ser.readline())
    
    #----------------------------------------------
    # Start transmitting
    # Note this must be correctly timed to an accurate clock
    def set_tx(self):
        crc = self.calc_crc_32(b'\x11\x00\x02\x00')
        msg = bytearray(b'\x01\x11\x00\x02\x00')
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        print(self.__ser.readline())
    
    #----------------------------------------------
    # Stop transmitting
    # Note this should be done immediately after a transmission, not during tramsmission
    def set_idle(self):
        crc = self.calc_crc_32(b'\x06\x00')
        msg = bytearray(b'\x01\x06\x00')
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        print(self.__ser.readline())
    
    #----------------------------------------------
    # Util methods
    #----------------------------------------------
    # Calculate a CRC32 of the given data
    def calc_crc_32(self, data):
        return struct.pack('<I', binascii.crc32(data))       

#========================================================================
# Module Test       
if __name__ == '__main__':
    
    if sys.platform == 'win32' or sys.platform == 'win64':
        device = 'COM5'
    else:
        # Assume Linux
        device = '/dev/ttyUSB0'
    
    lite = WSPRLite(device)
    lite.get_callsign()
    lite.get_locator()
    lite.get_freq()
    lite.set_freq(7.097066)
    lite.get_freq()
    lite.set_tx()
    sleep(3)
    lite.set_idle()