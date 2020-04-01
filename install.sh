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
create_env () {
# create virtual environment and activate
python3_dir=$(which python3)
virtualenv -p $python3_dir pastaenv
source pastaenv/bin/activate
}

ask_and_create_key () {
  while true; do
		read -p "Do you want to create one? For other targets than BMV2 you have to copy it to all servers for yourself. Y/N: " yn
		case $yn in
		    [Yy]* ) echo "Please just hit *enter* when asked where to store the file."; ssh-keygen; cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys; echo "created key and copied into authorized key for bmv2"; break;;
		    [Nn]* ) break;;
		    * ) echo "Please answer yes or no.";;
		esac
	done
}


pub_key=$(cat ~/.ssh/id_rsa.pub)
pub_key_length=`expr "$pub_key" : '.*'`

if (( $pub_key_length < 50)); then
	echo "It seems like there is no public key in your .ssh directory.";
	ask_and_create_key
fi

printf "Setting executeable bits for management server scripts...\n"
chmod +x gui.sh cli.sh run.sh
while true; do
    read -p "Do you wish to install the dependencies on this machine and at the external host? Y/N: " yn
    case $yn in
        [Yy]* ) sudo apt -y install python3-pip virtualenv;  create_env; pip3 install -r requirements.txt ;  deactivate; echo "finished pip3 on webserver"; ssh -o ConnectTimeout=5 $ssh_username_external@$external_host_ip "pip3 install setproctitle"; echo "finished pip3 on ext Host"; break;; #apt install python3-matplotlib # tabulate Django==2.2.9 numpy rpyc matplotlib grpcio protobuf
        [Nn]* ) break;;
        * ) echo "Please answer yes or no.";;
    esac
done

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


if ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no $ssh_username_external@$external_host_ip "echo 'SSH to external host ***__worked__***'; mkdir -p p4sta/receiver"; [ $? -eq 255 ]
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
   if ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no $ssh_username_loadgens@$i "echo 'SSH to loadgen $i ***__worked__***'; mkdir -p p4sta"; [ $? -eq 255 ]
   then 
     echo -e "${RED}Connection to loadgen $i failed!${NC} If you only use the BMV2 target this is not a problem."
   else
     scp install_host.sh $ssh_username_loadgens@$i:/home/$ssh_username_loadgens/p4sta
     ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no $ssh_username_loadgens@$i "cd p4sta; chmod +x install_host.sh"
     ssh -t -o ConnectTimeout=2 -o StrictHostKeyChecking=no $ssh_username_loadgens@$i "cd p4sta; ./install_host.sh"
   fi
done

printf "Setting visudo enries for BMV2 mininet...\n"
current_user=$USER
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/usr/local/bin/mn" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/bin/kill" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/usr/bin/killall" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/home/$current_user/p4-timestamping-middlebox/targets/bmv2/scripts/start_mininet.sh" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/home/$current_user/p4-timestamping-middlebox/targets/bmv2/scripts/netgen.py" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/home/$current_user/p4-timestamping-middlebox/targets/bmv2/scripts/return_ingress.py" | sudo EDITOR='tee -a' visudo
printf "Setting visudo entries finished...\n"

printf "FINISHED! starting webserver now. Next time you can do this by starting ./run.sh \n\n"
./run.sh

