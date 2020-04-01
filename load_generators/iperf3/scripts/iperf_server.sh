#!/bin/bash
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
# $7 => empty string or "sudo ip netns exec ID"
echo "iperf3 server at $1: open ports s$3 s$4 s$5 with NS option: $7"
ssh $2@$1 "$7 iperf3 -s -p $3 & $7 iperf3 -s -p $4 & $7 iperf3 -s -p $5 &" &
ssh $2@$1 "sleep $6; sudo pkill iperf3" &
