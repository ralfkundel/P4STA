#!/bin/bash
add_sudo_rights() {
  current_user=$USER 
  if (sudo -l | grep -q '(ALL : ALL) NOPASSWD: '$1); then 
    echo 'visudo entry already exists';  
  else
    sleep 0.1
    echo $current_user' ALL=(ALL:ALL) NOPASSWD:'$1 | sudo EDITOR='tee -a' visudo; 
  fi
}

add_sudo_rights $(which mn)
add_sudo_rights $(which kill)
add_sudo_rights $(which killall)
add_sudo_rights /home/$USER/p4sta/stamper/bmv2/scripts/start_mininet.sh
add_sudo_rights /home/$USER/p4sta/stamper/bmv2/scripts/netgen.py
add_sudo_rights /home/$USER/p4sta/stamper/bmv2/scripts/return_ingress.py
