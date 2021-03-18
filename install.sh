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
	if [ -z "$BATCH_MODE" ]
	then
		while true; do
			sleep 1
			read -p "Do you want to create one? For other targets than BMV2 you have to copy it to all servers for yourself. Y/N: " yn
			case $yn in
				[Yy]* ) echo "Please just hit *enter* when asked where to store the file."; ssh-keygen -P ''; touch ~/.ssh/authorized_keys; cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys; echo "created key and copied into authorized key for bmv2"; break;;
				[Nn]* ) break;;
				* ) echo "Please answer yes or no.";;
			esac
		done
	else
		  ssh-keygen -P '' -f ~/.ssh/id_rsa; touch ~/.ssh/authorized_keys; cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys; echo "created key and copied into authorized key for bmv2";
	fi

}

add_sudo_rights() {
  current_user=$USER 
  if (sudo -l | grep -q '(ALL : ALL) NOPASSWD: '$1); then 
    echo 'visudo entry already exists for: '${1};  
  else
    sleep 0.1
    echo $current_user' ALL=(ALL:ALL) NOPASSWD:'$1 | sudo EDITOR='tee -a' visudo; 
  fi
}


pub_key=$(cat ~/.ssh/id_rsa.pub)
pub_key_length=`expr "$pub_key" : '.*'`

if (( $pub_key_length < 50)); then
	echo "It seems like there is no public key in your .ssh directory.";
	ask_and_create_key
fi

printf "Setting executeable bits for management server scripts...\n"
chmod +x gui.sh cli.sh run.sh

if [ -z "$BATCH_MODE" ]
then
	while true; do
		sleep 1
		read -p "Do you wish to install the dependencies on this machine? Y/N: " yn
		case $yn in
		    [Yy]* ) add_sudo_rights $(which pkill); sudo apt update; sudo apt -y install python3-pip virtualenv net-tools shellinabox; rm -rf p4staenv/; create_env; pip3 install -r requirements.txt ;  deactivate; echo "finished pip3 on webserver"; break;; 
		    [Nn]* ) break;;
		    * ) echo "Please answer yes or no.";;
		esac
	done
else
      add_sudo_rights $(which pkill);
      sudo apt update; sudo apt -y install python3-pip virtualenv net-tools;  rm -rf pastaenv/; create_env; pip3 install -r requirements.txt ;  deactivate; echo "finished pip3 on webserver";
fi

mkdir -p results


if [ -d "stamper_targets/bmv2" ]; then
  printf "Setting bmv2 scripts executeable bits on localhost...\n"
  cd stamper_targets/bmv2/scripts
  chmod +x netgen.py start_mininet.sh return_ingress.py compile.sh stop_mininet.sh mn_status.sh
  printf "Setting visudo on locahost to allow route add to bmv2 server if neccessary"
  add_sudo_rights $(which ip)
  cd ../../..
fi


if [ -z "$BATCH_MODE" ]
then
	printf "FINISHED! starting p4sta core and webserver now. Next time you can do this by starting ./run.sh \n\n"
	./run.sh
fi

