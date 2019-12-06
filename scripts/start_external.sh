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
ssh -o StrictHostKeyChecking=no $4@$3 -q "mkdir p4sta; cd p4sta; mkdir receiver" # create p4sta dir if not created already
scp $5/pythonRawSocketExtHost.py $4@$3:/home/$4/p4sta/receiver
scp $5/check_extH_status.sh $4@$3:/home/$4/p4sta/receiver
ssh -o StrictHostKeyChecking=no $4@$3 -q "cd p4sta; cd receiver; chmod +x pythonRawSocketExtHost.py; chmod +x check_extH_status.sh; sudo ./pythonRawSocketExtHost.py --name $1 --interface $2 --multi $6 &" &
