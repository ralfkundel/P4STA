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
scp $2@$1:s$4.json $5/iperf3_s$4_$3.json 
scp $2@$1:s$(($4 + 1)).json $5/iperf3_s$(($4 + 1))_$3.json
scp $2@$1:s$(($4 + 2)).json $5/iperf3_s$(($4 + 2))_$3.json
ssh -tt $2@$1 "rm -f s$4.json; rm -f s$(($4 + 1)).json; rm -f s$(($4 + 2)).json"
