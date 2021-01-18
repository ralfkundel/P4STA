#!/bin/sh
ssh $1@$2 "sudo kill \$(pidof target_bmv2_mininet_module); sleep 1; sudo mn -c; sleep 1"
