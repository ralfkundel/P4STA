#!/bin/bash
if ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no $1@$2 "if sudo ifconfig $3 $4; then echo ifconfig_success; fi"; [ $? -eq 255 ]
then 
  echo "failed"
else
  echo "worked"
fi

