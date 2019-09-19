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
scp $3@$2:/home/$3/p4sta/receiver/raw_packet_counter_$1.csv $4/
scp $3@$2:/home/$3/p4sta/receiver/total_throughput_$1.csv $4/
scp $3@$2:/home/$3/p4sta/receiver/throughput_at_time_$1.csv $4/
scp $3@$2:/home/$3/p4sta/receiver/timestamp1_list_$1.csv $4/
scp $3@$2:/home/$3/p4sta/receiver/timestamp2_list_$1.csv $4/
sleep 1
ssh $3@$2 "cd p4sta; cd receiver; rm *.csv" # to remove all old csv in case a crashed process left some csv files..
