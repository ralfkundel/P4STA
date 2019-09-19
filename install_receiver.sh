current_user=$USER # to prevent root as $USER save it before root execution
if [ -d "receiver" ]; then #if directory receiver exists add receiver script sudo rights without password
	printf "\n-----------------------------------------\n"
	printf "\nAdding the following entries to visudo at ***RECEIVER***:\n"
	echo "$current_user ALL=(ALL:ALL) NOPASSWD:/home/$current_user/p4sta/receiver/pythonRawSocketExtHost.py" | sudo EDITOR='tee -a' visudo
	echo "$current_user ALL=(ALL:ALL) NOPASSWD:/usr/bin/pkill" | sudo EDITOR='tee -a' visudo
	echo "$current_user ALL=(ALL:ALL) NOPASSWD:/usr/bin/killall" | sudo EDITOR='tee -a' visudo
	printf "\n 2 entries added to visudo."
	printf "\n-----------------------------------------\n"
else
	printf "Directory receiver not found. Sure you executed install.sh at webserver first?\n"
fi

#TODO: check before inserting
