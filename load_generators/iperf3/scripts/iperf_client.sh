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
echo "iperf3 client at $2: connect to $1 at ports s$5 s$6 s$7"
ssh -tt $3@$2 "iperf3 -c $1 -T s$8 -p $5 ${10} -J --logfile s$8.json -t $9 & iperf3 -c $1 -T s$(($8 + 1)) -p $6 ${10} -J --logfile s$(($8 + 1)).json -t $9 & iperf3 -c $1 -T s$(($8 + 2))0 -p $7 ${10} -J --logfile s$(($8 + 2)).json" -t $9 &
