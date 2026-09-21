#!/bin/bash
# if ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no $1@$2 "if sudo ifconfig $3 $4; then echo ifconfig_success; fi"; [ $? -eq 255 ]
# then 
#   echo "failed"
# else
#   echo "worked"
# fi


if ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no "$1@$2" \
  "sudo ip addr flush dev $3 && if sudo ip addr replace '$4' dev '$3' && sudo ip link set '$3' up; then echo ip_success; fi"; [ $? -eq 255 ]
then
  echo "failed"
else
  echo "worked"
fi