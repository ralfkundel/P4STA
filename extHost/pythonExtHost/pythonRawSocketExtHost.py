#!/usr/bin/env python3
# Copyright 2019-2020-present Ralf Kundel, Fridolin Siegmund, Kadir Eryigit
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
import csv
import setproctitle
import signal
import socket
from socket import AF_PACKET, SOCK_RAW, htons
import sys
import time
import traceback

csv.field_size_limit(sys.maxsize)

setproctitle.setproctitle("external_host_python_receiver")

parser = argparse.ArgumentParser(
    description='external host packet receiver and analyzer')
parser.add_argument('--name', help='Name for the output graphs',
                    type=str, action="store", required=True)
parser.add_argument('--interface', help='Interface to listen to',
                    type=str, action="store", required=True)
parser.add_argument(
    '--multi',
    help='Multiplicator for timestamps unit '
         '(1 = nanosec; 1000= microsec; 1000000=milisec)',
    type=str, action="store", required=True)
parser.add_argument(
    '--tsmax',
    help='Maximal possible value of the timestamps '
         '(e.g. 281474976710655 for whole 48bit)',
    type=str, action="store", required=True)
args = parser.parse_args()

ETH_P_ALL = 3
place = 0
timestamp1_array = []
timestamp2_array = []
packet_sizes = []
raw_packet_counter = 0
time_throughput = []
name = args.name
go = True


with open("receiver_finished.log", "w") as f:
    f.write("False")
with open("pythonRawSocketExtHost.log", "w") as f:
    f.write("Started \n")

# raw socket to listen for all packets
# (but they need to have the right mac address OR broadcast ff:ff:ff...)
try:
    s = socket.socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL))
    # timeouts s.recv() after 0.1 sec to allow break of while loop
    s.settimeout(0.1)
    s.bind((args.interface, 0))
    error = False
except Exception as e:
    with open("pythonRawSocketExtHost.log", "w") as f:
        f.write("Exception: \n")
        f.write(str(e))
    go = False
    error = True


# handles SIGTERM and SIGINT signals to write csv files when terminating
def stop_signals_handler(signum, frame):
    global go
    go = False


signal.signal(signal.SIGINT, stop_signals_handler)
signal.signal(signal.SIGTERM, stop_signals_handler)


while go:
    try:
        # message contains whole packet (max 4096byte) as hex string
        message = s.recv(4096).hex()
        raw_packet_counter = raw_packet_counter + 1
        ether_type = message[24:28]
        if ether_type == "0800":
            # ip header length in 32 bit words
            ihl = int(message[29], 16)
            # 17 = UDP and 6 = TCP
            ipv4_protocol = int(message[46:48], 16)
            # 28 is ethernet header length in bytes*2
            l4_start = 28 + ihl * 4 * 2
            # 14 byte eth + 20 IPv4 + 20 TCP + 16 options = 70 byte
            if ipv4_protocol == 6 and len(message) > 140:
                try:
                    # tcp header length in in 32 bit words
                    tcp_data_offs = int(message[l4_start + 24], 16)
                    # tcp header always has at least 5x32bit
                    tcp_options_len = tcp_data_offs - 5
                    tcp_options = message[l4_start + 40:
                                          l4_start + 40 + tcp_options_len * 8]
                    for x in range(tcp_options_len):
                        # only check valid locations for option type
                        if tcp_options[x*8:x*8+4] == "0f10":
                            ts_start = x*8
                            # one timestamp is 12 hex digits long (6 byte)
                            timestamp1 = int(
                                tcp_options[ts_start+4:ts_start+16], 16) * int(
                                args.multi)
                            timestamp2 = int(
                                tcp_options[ts_start+20:ts_start+32], 16) * \
                                int(args.multi)
                            if timestamp1 > 0 and timestamp2 > 0:
                                # divided by 2 because 2 hex digits = 1 byte
                                packet_sizes.append(int(len(message) / 2))
                                timestamp2_array.append(timestamp2)
                                timestamp1_array.append(timestamp1)
                            break
                except Exception:
                    print(traceback.format_exc())
            # 14 byte eth + 20 IPv4 + 8 UDP (16 byte opt in payload!) = 42 byte
            elif ipv4_protocol == 17 and len(message) > 84:
                try:
                    # UDP header is 64 bit big (8 byte) => 64/4
                    # => move 16 hex digits forward (4 bit = 1 hex digit)
                    ts_start = l4_start + 16
                    timestamps_udp = message[ts_start:ts_start+32]
                    option_type = timestamps_udp[0:4]
                    # needs to be 0 if it's a p4sta timestamp
                    # (16bit 0x0f10, 48bit tstamp1, 16bit empty, 48bit tstamp2)
                    empty = int(timestamps_udp[16:20], 16)
                    # only parse timestamps if 0f10 directly
                    # follows after UDP header
                    if option_type == "0f10" and empty == 0:
                        timestamp1 = int(timestamps_udp[4:16], 16) * int(
                            args.multi)
                        timestamp2 = int(timestamps_udp[20:], 16) * int(
                            args.multi)
                        if timestamp1 > 0 and timestamp2 > 0:
                            # divided by 2 because 2 hex digits = 1 byte
                            packet_sizes.append(int(len(message) / 2))
                            timestamp2_array.append(timestamp2)
                            timestamp1_array.append(timestamp1)
                except Exception:
                    print(traceback.format_exc())
    # s.recv throws exception if it timeouts
    except Exception as e:
        pass


# correct the overflows in the timestamps
epochsize = (int(args.tsmax) + 1) * int(args.multi)
ts1_last = 0
ts2_last = 0
for i in range(0, len(timestamp1_array)):
    ts1 = timestamp1_array[i]
    ts2 = timestamp2_array[i]
    while ts1 < ts1_last - epochsize / 2:
        ts1 += epochsize
    while ts2 < ts2_last - epochsize / 2:
        ts2 += epochsize
    ts1_last = ts1
    ts2_last = ts2
    timestamp1_array[i] = ts1
    timestamp2_array[i] = ts2

# save csv files
if not error:
    with open("raw_packet_counter_" + str(name) + ".csv", "w") as output:
        wr = csv.writer(output, lineterminator='\n')
        wr.writerow([raw_packet_counter])
    with open("packet_sizes_" + str(name) + ".csv", "w") as output:
        wr = csv.writer(output, lineterminator='\n')
        for e in packet_sizes:
            wr.writerow([e])
    with open("timestamp1_list_" + str(name) + ".csv", "w") as output:
        wr = csv.writer(output, lineterminator='\n')
        for e in timestamp1_array:
            wr.writerow([e])
    with open("timestamp2_list_" + str(name) + ".csv", "w") as output:
        wr = csv.writer(output, lineterminator='\n')
        for e in timestamp2_array:
            wr.writerow([e])

with open("receiver_finished.log", "w") as f:
    f.write("True")

quit()
