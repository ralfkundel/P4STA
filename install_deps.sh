#!/bin/bash
sudo apt install python3-matplotlib
pip3 install tabulate Django numpy rpyc
ssh $1@$2 "pip install setproctitle"
