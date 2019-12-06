#!/bin/bash
RED='\033[0;31m'
NC='\033[0m' # No Color
sudo apt -y update
sudo apt -y install python3-matplotlib python3-pip ethtool python-pip
pip3 install tabulate Django numpy rpyc
if ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no $1@$2 "echo $2 connected"; [ $? -eq 255 ]
then 
  echo -e "${RED}Connection to external host $2 failed!${NC} If you only use the BMV2 target this is not a problem."
else
  ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no $1@$2 "pip install setproctitle"
fi

