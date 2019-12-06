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

# please enter your ssh IPs and ssh usernames of the following servers:
external_host_ip="10.100.129.20"
ssh_username_external="user123"

loadgen_ips=("10.100.129.36" "10.100.129.37") # please add your loadgen IPs here like ("ip" "ip2" "ip3") and so on
ssh_username_loadgens="user123" # same user for all loadgens!

###########################################
# DO NOT CHANGE ANYTHING BELOW THIS POINT #
###########################################
RED='\033[0;31m'
NC='\033[0m' # No Color

chmod +x install_deps.sh install_host.sh

echo "Welcome to P4STA! Current configuration of installation script:"
echo "ssh_username_external: $ssh_username_external"
echo "external_host_ip: $external_host_ip"
echo "ssh_username_loadgens: $ssh_username_loadgens"
echo "loadgen_ips: "
for i in "${loadgen_ips[@]}"
do
	echo $i
done

echo "If you plan to use the BMV2 target only, the configuration can remain untouched."

while true; do
    read -p "Do you want to start the installation process now? Y/N: " yn
    case $yn in
        [Yy]* ) ./install_deps.sh $ssh_username_external $external_host_ip; break;;
        [Nn]* ) exit;;
        * ) echo "Please answer yes or no.";;
    esac
done


printf "Setting executeable bits for management server scripts...\n"
chmod +x gui.sh cli.sh run.sh
mkdir -p results
cd scripts

chmod +x ethtool.sh ping.sh reboot.sh refresh_links.sh retrieve_external_results.sh start_external.sh stop_all_py.sh stop_external.sh
cd ..
printf "Setting iPerf3 scripts executeable bits...\n"
cd load_generators/iperf3/scripts
chmod +x get_json.sh iperf_client.sh iperf_server.sh
cd ..
cd ..
cd ..
printf "finished...\n"


if [ -d "targets/bmv2" ]; then
  cd targets/bmv2/scripts
  chmod +x netgen.py start_mininet.sh return_ingress.py compile.sh stop_mininet.sh mn_status.sh
  cd ..
  cd ..
  cd ..
  printf "Finished setting executeable bits for BMV2.\n"
fi

### Add further targets here OR in the specific target folder (e.g. Wedge65)

printf "\n#########################\n"
printf "Try to ssh into other servers. If this does not work (e.g. no password prompt support, only pub key) please follow the README.MD.\n"
printf "You need to enter your sudo password for every visudo operation\n"
printf "#########################\n\n"

if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no $ssh_username_external@$external_host_ip "echo 'SSH to external host ***__worked__***'; mkdir p4sta; cd p4sta; mkdir receiver"; [ $? -eq 255 ]
then 
  echo -e "${RED}Connection to external host $2 failed!${NC} If you only use the BMV2 target this is not a problem."
else
  scp ./extHost/pythonExtHost/pythonRawSocketExtHost.py $ssh_username_external@$external_host_ip:/home/$ssh_username_external/p4sta/receiver
  scp install_receiver.sh $ssh_username_external@$external_host_ip:/home/$ssh_username_external/p4sta
  ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no $ssh_username_external@$external_host_ip "cd p4sta; chmod +x install_receiver.sh; cd receiver; chmod +x pythonRawSocketExtHost.py"
  ssh -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no $ssh_username_external@$external_host_ip "cd p4sta; ./install_receiver.sh"
fi

printf "Installing Loadgenerators...\n"
for i in "${loadgen_ips[@]}"
do
   if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no $ssh_username_loadgens@$i "echo 'SSH to loadgen $i ***__worked__***'; mkdir p4sta"; [ $? -eq 255 ]
   then 
     echo -e "${RED}Connection to loadgen $i failed!${NC} If you only use the BMV2 target this is not a problem."
   else
     scp install_host.sh $ssh_username_loadgens@$i:/home/$ssh_username_loadgens/p4sta
     ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no $ssh_username_loadgens@$i "cd p4sta; chmod +x install_host.sh"
     ssh -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no $ssh_username_loadgens@$i "cd p4sta; ./install_host.sh"
   fi
done

printf "Setting visudo enries for BMV2 mininet on management server...\n"
current_user=$USER
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/usr/local/bin/mn" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/bin/kill" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/usr/bin/killall" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/home/$current_user/p4-timestamping-middlebox/targets/bmv2/scripts/start_mininet.sh" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/home/$current_user/p4-timestamping-middlebox/targets/bmv2/scripts/netgen.py" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/home/$current_user/p4-timestamping-middlebox/targets/bmv2/scripts/return_ingress.py" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/home/$current_user/p4sta/receiver/pythonRawSocketExtHost.py" | sudo EDITOR='tee -a' visudo
printf "Setting visudo entries finished...\n"
printf "Installing loadgenerator applications on management server for BMV2 usage ...\n"
./install_host.sh
printf "Installing external host applications on management server for BMV2 usage ...\n"
pip install setproctitle

printf "\n FINISHED .. starting webserver now. Next time you can do this by starting ./run.sh \n\n"
./run.sh
