#!/usr/bin/env python3
#
# main.py
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

# Python imports
import os, sys
from time import sleep
import pickle

# Application imports
from defs import *
import device
import netif

#========================================================================
# Main program for the WSPRLite remote operation.
class WSPRLiteMain:
    
    #----------------------------------------------
    # Constructor
    def __init__(self):
        
        # Create the device instance
        if sys.platform == 'win32' or sys.platform == 'win64':
            path = 'COM5'
        else:
            # Assume Linux
            path = '/dev/ttyUSB0'   
        self.__lite = device.WSPRLite(path, self.__startCallback, self.__stopCallback)
        
        # Run the net interface as this is the active thread.
        self.__netif = netif.NetIF(self.__netCallback)
        self.__netif.start()
                
    #----------------------------------------------
    # Idle loop      
    def mainLoop(self):
        
        print('WSPRLite remote interface running ...')
        try:
            # Main loop for ever, does nothing
            while True:
                sleep(1)                                
        except KeyboardInterrupt:  
            # User requested exit
            # Terminate the netif thread and wait for it to close
            self.__netif.terminate()
            self.__netif.join()
            # and the device
            self.__lite.terminate()
            
            print('Interrupt - exiting...')
    
    #----------------------------------------------
    # Callback when data received          
    def __netCallback(self, data):
        
        # Data arrived from caller
        try:
            request = pickle.loads(data)
            # request is an array of type followed by one or more parameters
            type = request[0]
            if type == GET_CALLSIGN:
                self.__netif.response(self.__lite.get_callsign())
            elif type == GET_LOCATOR:
                self.__netif.response(self.__lite.get_locator())
            elif type == GET_FREQ:
                self.__netif.response(self.__lite.get_freq())
            elif type == SET_FREQ:
                if len(request) != 2:
                    self.__netif.response("Error - wrong number of parameters!")
                else:
                    self.__netif.response(self.__lite.set_freq(request[1]))
            elif type == SET_BAND:
                if len(request) != 2:
                    self.__netif.response("Error - wrong number of parameters!")
                else:
                    self.__netif.response(self.__lite.set_band(request[1])) 
            elif type == SET_TX:
                self.__lite.set_tx()
            elif type == SET_IDLE:
                self.__lite.set_idle()
        except pickle.UnpicklingError:
            self.__netif.response('Failed to unpickle request data!')

    #----------------------------------------------
    # Callback when TX activated          
    def __startCallback(self, data):
        self.__netif.response(data)
    
    #----------------------------------------------
    # Callback when TX stopped          
    def __stopCallback(self, data):
        self.__netif.response(data)
        
#========================================================================
# Entry point            
if __name__ == '__main__':
    # Create an instance of the main program
    main = WSPRLiteMain()
    # Run until terminated
    main.mainLoop()        
    