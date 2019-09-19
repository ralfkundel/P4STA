#!/bin/bash
echo "iperf3 server at $1: open ports s$3 s$4 s$5"
ssh $2@$1 "iperf3 -s -p $3 & iperf3 -s -p $4 & iperf3 -s -p $5 &" &
ssh $2@$1 "sleep $6; pkill iperf3" &
