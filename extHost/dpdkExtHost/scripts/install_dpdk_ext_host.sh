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
sudo apt -y install build-essential libnuma-dev libpcap0.8-dev

if [ -d "dpdk-19.11/build/" ]
then
	printf "\n-----------------------------------------\n"
	printf "\n DPDK exists already on this machine in the p4sta directory and will not be reinstalled\n"
	printf "\n-----------------------------------------\n"
else
	printf "\n-----------------------------------------\n"
	printf "\nDownloading DPDK:\n"
	wget https://fast.dpdk.org/rel/dpdk-19.11.tar.xz
	tar xf dpdk-19.11.tar.xz
	cd dpdk-19.11/
	printf "\nDownloading DPDK complete\n"
	printf "\n-----------------------------------------\n"
	printf "\nCompile DPDK library:\n"
	make config T=x86_64-native-linuxapp-gcc
	sed -ri 's,(PMD_PCAP=).*,\1y,' build/.config
	if [ -f /.dockerenv ]; then
		#the following kernel modules can not be compiled in docker
		sed -ri 's,(CONFIG_RTE_LIBRTE_IGB_PMD=).*,\1n,' build/.config
		sed -ri 's,(CONFIG_RTE_EAL_IGB_UIO=).*,\1n,' build/.config
		sed -ri 's,(CONFIG_RTE_LIBRTE_KNI=).*,\1n,' build/.config
		sed -ri 's,(CONFIG_RTE_LIBRTE_PMD_KNI=).*,\1n,' build/.config
		sed -ri 's,(CONFIG_RTE_KNI_KMOD=).*,\1n,' build/.config
		sed -ri 's,(CONFIG_RTE_KNI_PREEMPT_DEFAULT=).*,\1n,' build/.config
	fi
	make
	printf "\nCompile DPDK library complete\n"
	export RTE_SDK=$PWD
	cd ..
	printf "\n-----------------------------------------\n"
	printf "\nCompile the external host program:\n"
	# we ignore warnings and errors here as we check the output later on
	make || true
	printf "\nSucceed in compiling the dpdk external host\n"
fi

printf "\n-----------------------------------------\n"
printf "\nConfigure Hugepages:\n"
sudo sh -c "echo 1024 > /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages"
sudo mkdir /mnt/huge
sudo mount -t hugetlbfs nodev /mnt/huge
printf "Succeed in configuring hugepages\n"

printf "\n-----------------------------------------\n"
printf "\nAdding the following entries to visudo at ***External Host***:\n"
add_sudo_rights /home/$current_user/p4sta/externalHost/dpdkExtHost/build/receiver
add_sudo_rights $(which pkill)
add_sudo_rights $(which killall)
add_sudo_rights $(which rmmod)
add_sudo_rights $(which modprobe)
printf "\n-----------------------------------------\n"
