#!/bin/sh
sudo kill $(pidof target_bmv2_mininet_module)
sleep 1
sudo mn -c
sleep 3
