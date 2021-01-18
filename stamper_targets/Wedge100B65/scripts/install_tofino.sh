add_sudo_rights() {
  current_user=$USER 
  if (sudo -l | grep -q '(ALL : ALL) SETENV: NOPASSWD: '$1); then 
    echo 'visudo entry already exists';  
  else
    sleep 0.1
    echo $current_user' ALL=(ALL:ALL) NOPASSWD:SETENV:'$1 | sudo EDITOR='tee -a' visudo; 
  fi
}
add_sudo_rights $(which pkill)
add_sudo_rights $(which killall)
add_sudo_rights $1/run_switchd.sh

