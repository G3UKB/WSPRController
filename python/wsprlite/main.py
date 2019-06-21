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

import os, sys
from time import sleep
import pickle

import netif

#========================================================================
# Main program for the WSPRLite remote operation.
class WSPRLiteMain:
    
    #----------------------------------------------
    # Constructor
    def __init__(self):
        
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
            
            print('Interrupt - exiting...')
    
    #----------------------------------------------
    # Callback when data received          
    def __netCallback(self, data):
        
        # Data arrived from caller
        try:
            request = pickle.loads(data)
            # request is an array of type followed by one or more parameters
            type = request[0]
            if type == 
                    self.__netif.response(self.__decoder.fres())
            response ??
        except pickle.UnpicklingError:
            print('Failed to unpickle request data!')

#========================================================================
# Entry point            
if __name__ == '__main__':
    # Create an instance of the main program
    main = WSPRLiteMain()
    # Run until terminated
    main.mainLoop()        
    