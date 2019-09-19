current_user=$USER # to prevent root as $USER save it before root execution
printf "\n-----------------------------------------\n"
printf "Installing iPerf3"
echo "sudo apt install iperf3"
printf "\n-----------------------------------------\n"
printf "\nAdding the following entries to visudo at ***HOST***:\n"
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/sbin/reboot" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/sbin/ethtool" | sudo EDITOR='tee -a' visudo
printf "\n 2 entries added to visudo."
printf "\n-----------------------------------------\n"
