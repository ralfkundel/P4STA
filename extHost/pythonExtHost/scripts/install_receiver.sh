current_user=$USER # to prevent root as $USER save it before root execution
add_sudo_rights() {
  current_user=$USER 
  if (sudo -l | grep -q '(ALL : ALL) NOPASSWD: '$1); then 
    echo 'visudo entry already exists';  
  else
    sleep 2
    echo $current_user' ALL=(ALL:ALL) NOPASSWD:'$1 | sudo EDITOR='tee -a' visudo; 
  fi
}

sudo apt update
sudo apt -y install python3-pip
pip3 install setproctitle 

printf "\n-----------------------------------------\n"
printf "\nAdding the following entries to visudo at ***RECEIVER***:\n"
add_sudo_rights /home/$current_user/p4sta/externalHost/python/pythonRawSocketExtHost.py
add_sudo_rights $(which pkill)
add_sudo_rights $(which killall)
printf "\n-----------------------------------------\n"

