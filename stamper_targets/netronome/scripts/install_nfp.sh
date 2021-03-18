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
add_sudo_rights /bin/systemctl start nfp-sdk6-rte.service
add_sudo_rights /opt/netronome/bin/nfp-reg
