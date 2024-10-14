current_user=$USER
add_sudo_rights() {
  current_user=$USER
  if (sudo -l | grep -q '(ALL : ALL) SETENV: NOPASSWD: '$1); then
    echo 'visudo entry already exists';
  else
    sleep 0.1
    echo $current_user' ALL=(ALL:ALL) NOPASSWD:SETENV:'$1 | sudo EDITOR='tee -a' visudo;
  fi
}
sudo apt update

sudo apt install psmisc

printf "Adding the following entries to visudo at ***External Host***:"
add_sudo_rights /home/fsiegmund/p4sta/externalHost/go/go/bin/go
add_sudo_rights /home/fsiegmund/p4sta/externalHost/go/goUdpSocketExtHost.py
add_sudo_rights $(which pkill)
add_sudo_rights $(which killall)
add_sudo_rights $(which ip)
add_sudo_rights $(which ifconfig)

