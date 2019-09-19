#!/bin/bash
#ssh -o ConnectTimeout=1 $1@$2 "sudo ifconfig $3 $4"
if ssh -o ConnectTimeout=1 $1@$2 "sudo ifconfig $3 $4"; [ $? -eq 255 ]
then 
  echo "failed"
else
  echo "worked"
fi
