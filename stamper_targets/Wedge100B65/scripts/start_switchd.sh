#!/bin/bash
if [ "$2" == "root" ]; then
	ssh $2@$1 "mkdir /home/$2/p4sta; cd $3; SDE=$3 SDE_INSTALL=$3/install ./run_switchd.sh -p $4 > /home/$2/p4sta/startup.log 2>&1 &";
else
	ssh $2@$1 "mkdir /home/$2/p4sta; cd $3; sudo SDE=$3 SDE_INSTALL=$3/install ./run_switchd.sh -p $4 > /home/$2/p4sta/startup.log 2>&1 &";
fi
sleep 1

