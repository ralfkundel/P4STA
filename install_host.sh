current_user=$USER # to prevent root as $USER save it before root execution
printf "\n-----------------------------------------\n"
printf "Installing iPerf3"
sudo apt-get remove iperf3 libiperf0
wget https://iperf.fr/download/ubuntu/libiperf0_3.1.3-1_amd64.deb
wget https://iperf.fr/download/ubuntu/iperf3_3.1.3-1_amd64.deb
sudo dpkg -i libiperf0_3.1.3-1_amd64.deb iperf3_3.1.3-1_amd64.deb
rm libiperf0_3.1.3-1_amd64.deb iperf3_3.1.3-1_amd64.deb
printf "\n-----------------------------------------\n"
printf "Installing ethtool"
sudo apt -y install ethtool
printf "\n-----------------------------------------\n"
printf "\nAdding the following entries to visudo at ***HOST***:\n"
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/sbin/reboot" | sudo EDITOR='tee -a' visudo
echo "$current_user ALL=(ALL:ALL) NOPASSWD:/sbin/ethtool" | sudo EDITOR='tee -a' visudo
printf "\n 2 entries added to visudo."
printf "\n-----------------------------------------\n"
