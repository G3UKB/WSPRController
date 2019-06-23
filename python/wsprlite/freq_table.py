#!/usr/bin/env python3
#
# freq_table.py
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

import random
# Return a random TX frequency within the given band.

band_lookup = {
    160: (1.836600, 1.838100),
    80: (3.568600, 3.570100),
    60: (5.364700, 5.366200),
    40: (7.038600, 7.040100),
    30: (10.138700, 10.140200),
    20: (14.095600, 14.097100),
    17: (18.104600, 18.106100),
    15: (21.094600, 21.096100),
    12: (24.924600, 24.926100),
    10: (28.124600, 28.126100),
    6: (50.293000, 50.294500),
    4: (70.091000, 70.092500),    
    2: (144.489000, 144.490500)
}

def get_tx_freq(band):
    
    range = band_lookup[band]
    return round(random.uniform(range[0], range[1]), 6)

#========================================================================
# Module Test
if __name__ == '__main__':
    print(get_tx_freq(160))
    print(get_tx_freq(80))
    print(get_tx_freq(60))
    print(get_tx_freq(40))
    print(get_tx_freq(30))
    print(get_tx_freq(20))
    print(get_tx_freq(17))
    print(get_tx_freq(15))
    print(get_tx_freq(12))
    print(get_tx_freq(10))
    print(get_tx_freq(6))
    print(get_tx_freq(4))
    print(get_tx_freq(2))