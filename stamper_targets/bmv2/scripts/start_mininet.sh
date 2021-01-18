#!/bin/sh
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
scp $4/data/config.json $2@$3:/home/$2/p4sta/
scp $4/stamper_targets/bmv2/scripts/netgen.py $2@$3:/home/$2/p4sta/stamper/bmv2/scripts/
ssh -tt -o StrictHostKeyChecking=no $2@$3 "chmod +x /home/$2/p4sta/stamper/bmv2/scripts/netgen.py; sudo kill \$(pidof target_bmv2_mininet_module); sudo mn -c; sleep"
ssh -tt -o StrictHostKeyChecking=no $2@$3 "sudo $1" &
sleep 5 

