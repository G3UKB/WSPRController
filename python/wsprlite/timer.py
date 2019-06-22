#!/usr/bin/env python3
#
# timer.py
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
    A WSPR transmission nominally starts 1 second into an even UTC minute.
    The transmission lasts for 110.6s.
    This module dispatches a request to wait for a transmission sync and for
    transmission idle time for a tidy stop.
    
    The timing is done in a separate thread and a callback is made when the
    start/stop time has been reached.
"""

# Python imports
import threading
import datetime
import queue
from time import sleep

# Application imports
from defs import *

#========================================================================
"""
    Main timer class for WSPRLite
"""
class TimerThrd (threading.Thread):
    
    #----------------------------------------------
    # Constructor
    def __init__(self, start_callback, stop_callback):
        """
        Constructor
        
        Arguments
            start_callback  -- callback here on a start time event
            stop_callback  -- callback here on a stop time event
        """

        super(TimerThrd, self).__init__()
        
        self.__start_callback = start_callback
        self.__stop_callback = stop_callback
        
        self.__terminate = False
        
        # Create a queue for communication with the thread
        self.__q = queue.Queue(5)
    
    #----------------------------------------------
    # Terminate
    def terminate(self):
        """
            Terminate thread
        """
        self.__terminate = True
    
    #----------------------------------------------
    # Called prior to executing a start TX 
    def wait_start(self):
        self.__q.put(WAIT_START)
    
    #----------------------------------------------
    # Called prior to executing a start TX 
    def wait_stop(self):
        self.__q.put(WAIT_STOP)

    #----------------------------------------------
    # Entry point   
    def run(self):
        """
            Wait for work
        """
        while not self.__terminate:
            try:
                rqst = self.__q.get(timeout=1)
                if rqst == WAIT_START:
                    self.__start_time()
                    self.__start_callback()
                elif rqst == WAIT_STOP:
                    self.__stop_time()
                    self.__stop_callback()
            except:
                continue
            
    #----------------------------------------------
    # Start time   
    def __start_time(self):
        """
            Wait for start time
        """
        while not self.__terminate:
            dt = datetime.datetime.utcnow()
            if dt.second == 0:
                if dt.minute%2 == 0:
                    # We just crossed an even minute
                    # Wait for the next tick
                    while not self.__terminate:
                        dt = datetime.datetime.utcnow()
                        if dt.second == 1:
                            break
                    return
            sleep(0.05)
    
    #----------------------------------------------
    # Stop time   
    def __stop_time(self):
        """
            Wait to enter stop window
        """
        
        while not self.__terminate:
            dt = datetime.datetime.utcnow()
            if dt.second >= 51:
                if dt.minute%2 != 0:
                    # We are at least 110.6s from the start time
                    # Any transmission should be finished
                    break                        
            sleep(1.0)
            
#========================================================================
# Module Test
def start_cb():
    print("START")

def stop_cb():
    print("STOP")

if __name__ == '__main__':
    
    t = TimerThrd(start_cb, stop_cb)
    t.start()
    t.wait_start()
    input('Press ENTER to stop...')
    t.wait_stop()
    input('Press ENTER to exit...')
    
    t.terminate()