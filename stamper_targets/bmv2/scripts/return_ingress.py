#!/usr/bin/env python

# Copyright 2019-present Ralf Kundel, Fridolin Siegmund
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import signal
import time
from socket import socket, AF_PACKET, SOCK_RAW, htons

parser = argparse.ArgumentParser(
    description='raw socket which returns the incoming packet as it is')
parser.add_argument('--interface', help='Interface to listen to',
                    type=str, action="store", required=True)

args = parser.parse_args()
ETH_P_ALL = 3
go = True

s = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL))
s.bind((args.interface, 0))


# handles SIGTERM and SIGINT signals to write csv files when terminating
def stop_signals_handler(signum, frame):
    global go
    go = False


signal.signal(signal.SIGINT, stop_signals_handler)
signal.signal(signal.SIGTERM, stop_signals_handler)

while go:
    try:
        # message contains whole packet (max 4096byte) as hex string
        message = s.recv(4096)
        # to not duplicate packets which are from this host
        # (in case of ping for example)
        if message.encode("hex")[12:24] != "aaaaaaaaff02":
            s.send(message)
    # s.recv throws exception if it gets terminated while receiving
    except Exception:
        pass
