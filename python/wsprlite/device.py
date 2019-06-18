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

# Current POC for RPi access to the WSPRLite Flexi transmitter

"""
    Message format
    
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
    
    The 'C' message type enumeration:
    enum class MsgType
    {
    0    Version=0,
    1    NACK,
    2    ACK,
    3    Read,
    4    ResponseData,
    5    Write,
    6    Reset,
    7    Bootloader_State,
    8    Bootloader_Enter,
    9    Bootloader_EraseAll,
    a   Bootloader_ErasePage,
    b   Bootloader_ProgramHexRec,
    c   Bootloader_ProgramRow,
    d   Bootloader_ProgramWord,
    e   Bootloader_CRC,
    f   Bootloader_ProgramResetAddr,
    10   DeviceMode_Get,
    11   DeviceMode_Set,
    12   DumpEEPROM,
    13   WSPR_GetTime,
    14   TestCmd,
    };
    
    // EEPROM variable IDs, for use with MsgType::Read and Write
    enum class VarId
    {
    0    MemVersion=0,
    1    xoFreq,
    2    xoFreqFactory,
    3    ChangeCounter,
    4    DeviceId,
    5    DeviceSecret,
    6    WSPR_txFreq,
    7    WSPR_locator,
    8    WSPR_callsign,
    9    WSPR_paBias,
    a    WSPR_outputPower,
    b    WSPR_reportPower,
    c    WSPR_txPct,
    d    WSPR_maxTxDuration,
    e    CwId_Freq,
    f    CwId_Callsign,
    10    PaBiasSource,
    11    END,
    };

    enum class DeviceMode
    {
    0    Init=0,
    1    WSPR_Pending=1,
    2    WSPR_Active,
    3    WSPR_Invalid,
    4    Test_ConstantTx,
    5    FactoryInvalid,
    6    HardwareFail,
    7    FirmwareError,
    8    WSPR_MorseIdent,
    9    Test,
    };

"""

import serial
import binascii
import struct
from time import sleep

# g_device = '/dev/ttyUSB0'
g_device = 'COM5'

class WSPRLite(object):
    
    def __init__(self):
        
        # Create connection and set parameters according to device spec
        self.__ser = serial.Serial(g_device)
        self.__ser.baudrate = 1000000
        self.__ser.bytesize = 8
        self.__ser.parity = 'N'
        self.__ser.stopbits = 2
        self.__ser.rtscts = True
        self.__ser.timeout = 2.0
    
    """
    ### Read

        Read a config variable.
        
        Command data:
        
            msgData ::= variableId
            variableId ::= uint16
        
        Reply: NACK or ResponseData. Contents of ResponseData will depend on which variable is being read - see cfgvars.md for details.
    """
    def get_callsign(self):
        crc = self.calc_crc_32(b'\x03\x00\x08\x00')
        msg = bytearray(b'\x01\x03\x00\x08\x00')
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        print(self.__ser.readline())

    def get_locator(self):
        crc = self.calc_crc_32(b'\x03\x00\x07\x00')
        msg = bytearray(b'\x01\x03\x00\x07\x00')
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        print(self.__ser.readline())
        
    def get_freq(self):
        crc = self.calc_crc_32(b'\x03\x00\x06\x00')
        msg = bytearray(b'\x01\x03\x00\x06\x00')
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        print(self.__ser.readline())
    
    """
    ### Write

        Write a config variable.
        
        Command data:
        
            msgData ::= variableId variableData
            variableId ::= uint16
        
        variableData will depend on which variable is being written - see cfgvars.md for details.
        
        Reply: ACK or NACK.
    """
    
    def set_tx(self):
        crc = self.calc_crc_32(b'\x11\x00\x02\x00')
        msg = bytearray(b'\x01\x11\x00\x02\x00')
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        print(self.__ser.readline())
    
    def reset(self):
        crc = self.calc_crc_32(b'\x06\x00')
        msg = bytearray(b'\x01\x06\x00')
        msg = msg + crc + bytearray(b'\x04')
        self.__ser.write(msg)
        print(self.__ser.readline())
        
    def calc_crc_32(self, data):
        return struct.pack('<I', binascii.crc32(data))       
        
lite = WSPRLite()
lite.get_callsign()
lite.get_locator()
lite.get_freq()
lite.set_tx()
sleep(3)
lite.reset()