#!/usr/bin/env python
############################################
# File: pythonRawSocketExtHost.py          #
# Author: Fridolin Siegmund                #
# Last Change: 13.02.19                    #
# Receives Raw Packets on given interface  #
# and searches for timestamps              #
############################################

from socket import socket, AF_PACKET, SOCK_RAW, htons
import signal
import time
import sys
import argparse
import csv
import setproctitle
csv.field_size_limit(sys.maxsize)

setproctitle.setproctitle("external_host_python_receiver")

parser = argparse.ArgumentParser(description='external host packet receiver and analyzer')
parser.add_argument('--name', help='Name for the output graphs',
                    type=str, action="store", required=True)
parser.add_argument('--interface', help='Interface to listen to',
                    type=str, action="store", required=True)
parser.add_argument('--multi', help='Multiplicator for timestamps unit (1 = nanosec; 1000= microsec; 1000000=milisec)',
                    type=str, action="store", required=True)
args = parser.parse_args()

ETH_P_ALL = 3
place = 0
timestamp1_array = []
timestamp2_array = []
total_throughput = 0
throughput_at_time = []
raw_packet_counter = 0
time_throughput = []
name = args.name
go = True


# handles SIGTERM and SIGINT signals to write csv files when terminating
def stop_signals_handler(signum, frame):
    global go
    go = False


signal.signal(signal.SIGINT, stop_signals_handler)
signal.signal(signal.SIGTERM, stop_signals_handler)

with open("receiver_finished.log", "w") as f:
    f.write("False")

# raw socket to listen for all packets (but they need to have the right mac address OR broadcast ff:ff:ff...)
s = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL))
s.bind((args.interface, 0))
while go:
    try:
        message = s.recv(4096).encode("hex")  # message contains whole packet (max 4096byte) as hex string
        raw_packet_counter = raw_packet_counter + 1
        place = message[0:200].find('0f10')  # place is the BEGINNING of string 0f10 (our tcp options) in message
        if place == 132 or place == 108 or place == 84:  # if place = -1 there's no 0f10 sequence in message, should be around 132:135 OR 108:111 OR 84 (UDP)
            total_throughput = total_throughput + (len(message) / 2)  # divided by 2 because 2 hex digits = 1 byte
            throughput_at_time.append(total_throughput)
            timestamp1 = int(message[place+4:place+16], 16) * int(args.multi)  # one timestamp is 12 hex digits long (6 byte)
            timestamp2 = int(message[place+20:place+32], 16) * int(args.multi)
            timestamp2_array.append(timestamp2)
            timestamp1_array.append(timestamp1)
    except: # s.recv throws exception if it gets terminated while receiving
        pass

# save csv files
with open("raw_packet_counter_" + str(name) + ".csv", "w") as output:
    wr = csv.writer(output, lineterminator='\n')
    wr.writerow([raw_packet_counter])
with open("total_throughput_" + str(name) + ".csv", "w") as output:
    wr = csv.writer(output, lineterminator='\n')
    wr.writerow([total_throughput])
with open("throughput_at_time_" + str(name) + ".csv", "w") as output:
    wr = csv.writer(output, lineterminator='\n')
    for e in throughput_at_time:
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
