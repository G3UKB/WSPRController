#!/usr/bin/env python3
#
# test_client.py
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

# Exercise the application over the UDP interface.

import socket
from defs import *
import pickle
from time import sleep

address = ('localhost', 10001)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

pickledData = pickle.dumps((GET_CALLSIGN,))
sock.sendto(pickledData, address)
data, sender = sock.recvfrom(100)
print(pickle.loads(data))

pickledData = pickle.dumps((GET_LOCATOR,))
sock.sendto(pickledData, address)
data, sender = sock.recvfrom(100)
print(pickle.loads(data))

pickledData = pickle.dumps((GET_FREQ,))
sock.sendto(pickledData, address)
data, sender = sock.recvfrom(100)
print(pickle.loads(data))

pickledData = pickle.dumps((SET_TX,))
sock.sendto(pickledData, address)
resp = sock.recvfrom(100)
if resp == None:
    while True:
        resp = sock.recvfrom(100)
        if resp != None:
            break
        else:
            print("Waiting response to SET_TX...")
            sleep(10)    
print(pickle.loads(resp[0]))

sleep(3)

pickledData = pickle.dumps((SET_IDLE,))
sock.sendto(pickledData, address)
resp = sock.recvfrom(100)
if resp == None:
    while True:
        resp = sock.recvfrom(100)
        if resp != None:
            break
        else:
            print("Waiting response to SET_IDLE...")
            sleep(10)    
print(pickle.loads(resp[0]))